"""
Dashboard Phan A: khung nang luc (cau hinh duoc) + engine tinh diem + Ho so 360 +
cau hinh hien thi chi so (Prompt_Dashboard_A_NangLuc_HoSo360.md).

AN TOAN: TOAN BO file nay CHI DOC du lieu nguon (courses.Enrollment/LessonProgress,
exams.Attempt, evaluation.Evaluation/EvaluationDetail, employees.Employee) - KHONG ghi de bat
cu dong nao, va KHONG BAO GIO goi/dung lai employees.services.compute_final_result hay
recompute_final_result. Logic pass thu viec la nguon rieng, doc qua Employee.final_result/
pass_date/employee_status san co, khong tinh lai.
"""
import csv
import datetime
import io
import re
import unicodedata
from collections import defaultdict

from django.conf import settings
from django.db.models import Avg, Count, F, Max, Q
from django.utils import timezone

from .models import (
    ClsExamCompetencyMap,
    CompetencyGroup,
    Competency,
    CompetencyScoreSnapshot,
    CompetencyScoringConfig,
    CompetencySnapshot,
    DashboardIndicator,
    PositionGroupWeight,
    PositionTarget,
    TrainingCost,
    TrainingCostSource,
)


class ValidationError(Exception):
    pass


# ==================================================================== Chuan hoa ten (khop mo,
# khong phan biet hoa/thuong, dau, khoang trang thua) - dung cho import + tra cuu theo vi tri
# (Prompt_Fix_ImportKhungNangLuc.md: import lech tao nhom/nang luc rac vi so khop chuoi tho).

def _deburr_lower(text):
    """Bo dau tieng Viet + ha chu thuong + gom khoang trang - dung khop VI TRI va MA NHOM
    (khong dung cho ten nang luc vi can xu ly them ngoac/dau '/', xem _normalize_competency_name)."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('Đ', 'D').replace('đ', 'd')
    return re.sub(r'\s+', ' ', text).strip().lower()


def _normalize_competency_name(text):
    """Chuan hoa ten nang luc de khop file import voi khung da seed du chenh nhau khoang trang,
    hoa/thuong, dau, hoac hau to trong ngoac (vd '(upsell)') - tranh tao nang luc trung
    (Prompt_Fix_ImportKhungNangLuc.md, Loi 2)."""
    text = re.sub(r'\([^)]*\)', '', text or '')
    text = re.sub(r'\s*/\s*', '/', text)
    return _deburr_lower(text)


def resolve_position(position_values, raw_position):
    """Tra ve gia tri vi tri CHINH XAC nhu da luu (trong position_values) khop voi raw_position
    sau khi chuan hoa - dung cho engine + 'Xem cau hinh theo vi tri' de khong lech hoa/thuong/dau
    cach voi Employee.position (Prompt_Fix_ImportKhungNangLuc.md, Loi 3). Khong khop -> None."""
    target = _deburr_lower(raw_position)
    if not target:
        return None
    for value in position_values:
        if _deburr_lower(value) == target:
            return value
    return None


# ==================================================================== Seed khung nang luc

# 6 nhom x 24 nang luc (dung y prompt muc 1). CSV import (import_position_targets) se TU TAO
# them Competency/CompetencyGroup neu ten trong file thuc te khac chut it (xem ham do) - danh
# sach nay chi la diem khoi dau hop ly, khong phai gioi han cung.
COMPETENCY_FRAMEWORK_SEED = [
    ('AT', 'An toàn & Tuân thủ', [
        'An toàn thực phẩm & vệ sinh (HACCP/5S)',
        'Tuân thủ quy trình vận hành chuẩn (SOP)',
    ]),
    ('A1', 'Chuyên môn Bếp', [
        'Sơ chế & bảo quản nguyên liệu',
        'Kỹ thuật chế biến & định lượng',
        'Vận hành & bảo quản thiết bị bếp',
        'Kiểm soát chất lượng món',
    ]),
    ('A2', 'Chuyên môn Phục vụ', [
        'Quy trình phục vụ chuẩn',
        'Kiến thức món & đồ uống / menu (upsell)',
        'Xử lý order & POS',
        'Chăm sóc khách & xử lý phàn nàn',
        'Vệ sinh, set-up & đóng đồ mang về',
    ]),
    ('B', 'Kỹ năng mềm', [
        'Giao tiếp',
        'Làm việc nhóm',
        'Giải quyết vấn đề',
        'Quản lý thời gian & tốc độ',
    ]),
    ('C', 'Thái độ', [
        'Kỷ luật & chấp hành',
        'Tinh thần dịch vụ',
        'Trách nhiệm & trung thực',
        'Cầu tiến, chủ động',
    ]),
    ('D', 'Quản lý', [
        'Điều phối ca & phân công',
        'Đào tạo & kèm cặp',
        'Quản lý chi phí & định mức',
        'Quản lý con người',
        'Ra quyết định & xử lý sự cố',
    ]),
]

# 6 ma nhom he thong dung khung - dung de dep rac (nhom nao ngoai danh sach nay la du lieu loi
# import, xem quan ly lenh cleanup_competency_data) va de importer tu choi tao nhom moi.
VALID_GROUP_CODES = {code for code, _name, _competencies in COMPETENCY_FRAMEWORK_SEED}


def seed_competency_framework(tenant):
    """Idempotent - goi lai nhieu lan khong tao trung (get_or_create theo code/ten)."""
    created_groups = created_competencies = 0
    for order, (code, name, competencies) in enumerate(COMPETENCY_FRAMEWORK_SEED):
        group, g_created = CompetencyGroup.objects.get_or_create(
            tenant=tenant, code=code, defaults={'name': name, 'order': order},
        )
        created_groups += int(g_created)
        for c_order, comp_name in enumerate(competencies):
            _, c_created = Competency.objects.get_or_create(
                tenant=tenant, group=group, name=comp_name, defaults={'order': c_order},
            )
            created_competencies += int(c_created)
    return {'groups_created': created_groups, 'competencies_created': created_competencies}


# ==================================================================== Import CSV khung v0.5

def _read_csv_rows(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    return [row for row in reader if any((cell or '').strip() for cell in row)]


def _parse_number(raw):
    """So thap phan, chap nhan ca dang '15%' (Excel xuat CSV tu o dinh dang %) -> 0.15 (chia
    100), dung chung cho ca sheet muc tieu (0-100, khong dau %) lan trong so nhom (0-1)."""
    raw = (raw or '').strip()
    if not raw or raw == '—' or raw == '-':
        return None
    is_percent = raw.endswith('%')
    if is_percent:
        raw = raw[:-1].strip()
    try:
        value = float(raw.replace(',', '.'))
    except ValueError:
        return None
    return value / 100 if is_percent else value


def import_position_targets(tenant, csv_text):
    """Import sheet 'Muc tieu theo vi tri' (xuat CSV tu KhungNangLuc_MucTieu_TheoViTri_v0.5.xlsx).
    Dong 1 = tieu de (bo qua), dong 2 = ten vi tri tu cot C, dong 3+ = 'Nhóm,Năng lực,<điểm theo
    từng vị trí>'. Nhom dang 'AT · An toàn & Tuân thủ' - tach ma truoc dau '·'. '—'/rong = khong
    ap dung, bo qua.

    TUYET DOI KHONG tao CompetencyGroup/Competency moi tu du lieu import (Prompt_Fix_
    ImportKhungNangLuc.md, Loi 2) - CHI khop vao khung da co (get_or_create -> filter), khop
    nhom theo MA (khong phan biet hoa/thuong) va khop nang luc theo TEN DA CHUAN HOA (bo dau,
    ha chu thuong, bo phan trong ngoac, chuan hoa dau '/') de khong tao nang luc trung khi file
    ghi ten hoi khac seed (vd them hau to '(upsell)'). Nhom/nang luc la la (khong khop duoc)
    -> bo qua dong + ghi canh bao, khong doan/tao moi."""
    rows = _read_csv_rows(csv_text)
    if len(rows) < 3:
        raise ValidationError('File thiếu dữ liệu (cần dòng tiêu đề vị trí + ít nhất 1 dòng năng lực).')

    position_row = rows[1]
    positions = [(p or '').strip() for p in position_row[2:]]
    while positions and not positions[-1]:
        positions.pop()
    if not positions:
        raise ValidationError('Không đọc được danh sách vị trí ở dòng 2 (từ cột C).')

    groups_by_code = {g.code.upper(): g for g in CompetencyGroup.objects.filter(tenant=tenant)}
    competencies_by_group = {}

    def _competencies_of(group):
        if group.id not in competencies_by_group:
            competencies_by_group[group.id] = {
                _normalize_competency_name(c.name): c for c in group.competencies.all()
            }
        return competencies_by_group[group.id]

    written = 0
    warnings = []
    for row in rows[2:]:
        if len(row) < 2 or not (row[0] or '').strip():
            continue
        group_raw = (row[0] or '').strip()
        comp_name = (row[1] or '').strip()
        if not comp_name:
            continue
        code, _, _name = group_raw.partition('·')
        code = code.strip().upper()
        if not code:
            warnings.append(f'Bỏ qua dòng không đọc được nhóm năng lực: "{group_raw}"')
            continue
        group = groups_by_code.get(code)
        if not group:
            warnings.append(f'Bỏ qua: chưa có nhóm năng lực "{group_raw}" trong khung hiện tại.')
            continue
        competency = _competencies_of(group).get(_normalize_competency_name(comp_name))
        if not competency:
            warnings.append(f'Bỏ qua: chưa có năng lực "{comp_name}" trong nhóm {group.code}.')
            continue

        for i, position in enumerate(positions):
            col = i + 2
            if col >= len(row) or not position:
                continue
            value = _parse_number(row[col])
            if value is None:
                continue
            PositionTarget.objects.update_or_create(
                tenant=tenant, position=position, competency=competency,
                defaults={'target_score': int(round(value))},
            )
            written += 1

    return {'targets_written': written, 'positions': len(positions), 'warnings': warnings}


# Cot header dang '<Ten nhom> (<MA>)' - vd 'Chuyên môn (A)'. Ma 'A' dai dien CA A1 va A2 (1
# nguoi chi thuoc 1 tuyen bep/phuc vu - xem PositionGroupWeight docstring).
_GROUP_WEIGHT_CODE_ALIASES = {'A': ['A1', 'A2']}
_HEADER_CODE_RE = re.compile(r'\(([A-Za-z0-9]+)\)\s*$')


def import_position_group_weights(tenant, csv_text):
    """Import sheet 'Trong so nhom'. Cot 1 = Vi tri, cac cot sau = trong so (0-1, hoac '15%')
    cua tung nhom, nhan dien qua ma trong ngoac o cuoi ten cot (vd 'Chuyên môn (A)' -> A). Bo
    qua cot khong co ma (vd TỔNG). Luu lai thanh % (0-100) dung field PositionGroupWeight.weight.

    Cot 'Chuyên môn (A)' (gop chung, file khong tach A1/A2) duoc ap CUNG trong so cho CA hai
    nhom A1 va A2 (_GROUP_WEIGHT_CODE_ALIASES) - 1 nguoi chi thuoc 1 tuyen bep/phuc vu nen
    khong xung dot. TUYET DOI KHONG tao CompetencyGroup moi (Prompt_Fix_ImportKhungNangLuc.md,
    Loi 1): ma khong khop nhom nao da co -> bo qua + ghi canh bao."""
    rows = _read_csv_rows(csv_text)
    if len(rows) < 2:
        raise ValidationError('File thiếu dữ liệu (cần dòng tiêu đề + ít nhất 1 dòng vị trí).')

    header = rows[0]
    col_codes = {}
    for idx, col_name in enumerate(header[1:], start=1):
        m = _HEADER_CODE_RE.search((col_name or '').strip())
        if not m:
            continue
        code = m.group(1).upper()
        col_codes[idx] = _GROUP_WEIGHT_CODE_ALIASES.get(code, [code])

    groups_by_code = {g.code.upper(): g for g in CompetencyGroup.objects.filter(tenant=tenant)}

    written = 0
    warnings = []
    for row in rows[1:]:
        position = (row[0] or '').strip() if row else ''
        if not position:
            continue
        for idx, codes in col_codes.items():
            if idx >= len(row):
                continue
            value = _parse_number(row[idx])
            if value is None:
                continue
            weight_percent = round(value * 100, 2)
            for code in codes:
                group = groups_by_code.get(code)
                if not group:
                    warnings.append(f'Bỏ qua: chưa có nhóm năng lực "{code}" (vị trí "{position}").')
                    continue
                PositionGroupWeight.objects.update_or_create(
                    tenant=tenant, position=position, group=group, defaults={'weight': weight_percent},
                )
                written += 1

    return {'weights_written': written, 'warnings': warnings}


# ==================================================================== Seed chi so Dashboard

# (key, label, group_label, role_scope, direction, green, yellow) - tu file
# ChiSo_Dashboard_ChonLua_v0.2.xlsx, CHI cac dong CHỌN='x'. role_scope: ho_so=360, ceo, gdt.
DASHBOARD_INDICATOR_SEED = [
    ('radar_nang_luc_ca_nhan', 'Radar năng lực cá nhân (thực tế vs mục tiêu)', 'Năng lực', ['ho_so'], 'none', None, None),
    ('ci_tong_hop', 'Chỉ số năng lực tổng hợp (CI)', 'Năng lực', ['ho_so', 'ceo', 'gdt'], 'higher_better', 90, 80),
    ('ty_le_dat_muc_tieu_nang_luc', '% NV đạt mục tiêu năng lực vị trí', 'Năng lực', ['ceo', 'gdt'], 'higher_better', 90, 80),
    ('top_skill_gap', 'Top khoảng trống năng lực (skill gap)', 'Năng lực', ['gdt', 'ho_so'], 'none', None, None),

    ('dung_lo_trinh', '% NV đúng lộ trình', 'Onboarding', ['ceo', 'gdt'], 'higher_better', 90, 80),
    ('dat_ky_nang_lan_dau', '% Đạt kỹ năng lần đầu', 'Onboarding', ['gdt', 'ho_so'], 'higher_better', 90, 80),
    ('ty_le_pass_thu_viec', 'Tỷ lệ pass thử việc', 'Onboarding', ['ceo'], 'higher_better', 90, 80),
    ('thoi_gian_tb_den_pass', 'Thời gian TB đến khi pass (ngày)', 'Onboarding', ['ceo', 'gdt'], 'lower_better', None, None),

    ('ty_le_hoan_thanh_khoa', 'Tỷ lệ hoàn thành khóa', 'Học & thi', ['gdt'], 'higher_better', 90, 80),
    ('hoan_thanh_dung_han', 'Hoàn thành đúng hạn (vs quá hạn)', 'Học & thi', ['gdt'], 'higher_better', 90, 80),
    ('ty_le_thi_dat', 'Tỷ lệ thi đạt', 'Học & thi', ['gdt'], 'higher_better', 90, 80),
    ('ty_le_dat_lan_dau', 'Tỷ lệ đạt ngay lần đầu', 'Học & thi', ['gdt'], 'higher_better', 90, 80),
    ('diem_thi_trung_binh', 'Điểm thi trung bình', 'Học & thi', ['gdt', 'ho_so'], 'higher_better', 90, 80),

    ('ty_le_nghi_viec_thu_viec', 'Tỷ lệ nghỉ việc (trong thử việc)', 'Nhân sự', ['ceo'], 'lower_better', 10, 20),
    ('nghi_viec_som', 'Nghỉ việc sớm (<30/60 ngày)', 'Nhân sự', ['ceo'], 'lower_better', None, None),
    ('san_sang_nhan_luc', 'Sẵn sàng nhân lực (đủ chuẩn/tổng) theo vị trí', 'Nhân sự', ['ceo'], 'higher_better', 90, 80),
    ('san_sang_ke_can', 'Sẵn sàng kế cận (nguồn Giám sát/QLNH/Bếp trưởng)', 'Nhân sự', ['ceo'], 'none', None, None),

    ('so_buoi_kem_theo_trainer', 'Số buổi / số NV đã kèm theo trainer', 'Trainer & đơn vị', ['gdt'], 'none', None, None),
    ('ty_le_pass_theo_trainer', 'Tỷ lệ pass của học viên theo trainer', 'Trainer & đơn vị', ['gdt'], 'higher_better', 90, 80),
    ('phu_cap_dao_tao', 'Phụ cấp đào tạo (tổng & theo trainer)', 'Trainer & đơn vị', ['ceo', 'gdt'], 'none', None, None),
    ('xep_hang_nha_hang', 'Xếp hạng nhà hàng theo KPI đào tạo', 'Trainer & đơn vị', ['ceo', 'gdt'], 'none', None, None),
    ('nha_hang_duoi_nguong', 'Nhà hàng dưới ngưỡng (đỏ)', 'Trainer & đơn vị', ['ceo', 'gdt'], 'none', None, None),

    ('so_chung_chi_da_cap', 'Số chứng chỉ đã cấp', 'Chứng chỉ & tuân thủ', ['gdt', 'ho_so'], 'none', None, None),
    ('tuan_thu_dao_tao_bat_buoc', 'Tuân thủ đào tạo bắt buộc (ATTP/SOP/PCCC)', 'Chứng chỉ & tuân thủ', ['ceo', 'gdt'], 'higher_better', 90, 80),

    ('tong_chi_phi_dao_tao', 'Tổng chi phí đào tạo theo kỳ/đơn vị', 'Chi phí (cổng chờ)', ['ceo'], 'none', None, None),
    ('chi_phi_moi_nhan_su_pass', 'Chi phí / nhân sự pass', 'Chi phí (cổng chờ)', ['ceo'], 'lower_better', None, None),

    ('nv_qua_han', 'NV quá hạn học/đánh giá', 'Cảnh báo', ['ceo', 'gdt', 'ho_so'], 'none', None, None),
    ('nv_nguy_co_khong_pass', 'NV nguy cơ không pass', 'Cảnh báo', ['gdt', 'ho_so'], 'none', None, None),
    ('nha_hang_do_nhieu_ky', 'Nhà hàng đỏ nhiều kỳ liên tiếp', 'Cảnh báo', ['ceo'], 'none', None, None),
]


def seed_dashboard_indicators(tenant):
    """Idempotent - CHI tao moi (khong ghi de enabled/threshold admin da tung chinh tay)."""
    created = 0
    for order, (key, label, group_label, role_scope, direction, green, yellow) in enumerate(DASHBOARD_INDICATOR_SEED):
        _, was_created = DashboardIndicator.objects.get_or_create(
            tenant=tenant, key=key,
            defaults={
                'label': label, 'group_label': group_label, 'role_scope': role_scope,
                'order': order, 'direction': direction, 'green_threshold': green, 'yellow_threshold': yellow,
            },
        )
        created += int(was_created)
    return {'indicators_created': created}


def indicator_color(indicator, value):
    """Xanh/vang/do theo nguong cua 1 DashboardIndicator - dung y prompt muc 6. None = khong
    to mau (thieu nguong, huong 'none', hoac value None)."""
    if value is None or indicator.direction == DashboardIndicator.Direction.NONE:
        return None
    if indicator.green_threshold is None or indicator.yellow_threshold is None:
        return None
    v = float(value)
    g, y = float(indicator.green_threshold), float(indicator.yellow_threshold)
    if indicator.direction == DashboardIndicator.Direction.HIGHER_BETTER:
        if v >= g:
            return 'green'
        if v >= y:
            return 'yellow'
        return 'red'
    if v <= g:
        return 'green'
    if v <= y:
        return 'yellow'
    return 'red'


# ==================================================================== Engine tinh diem nang luc

def _course_source_scores(employee, competency):
    """Tung Enrollment cua cac Course gan nang luc nay -> % hoan thanh (hoan thanh=100, dang
    hoc = % bai da xong, offline-confirmed tinh nhu binh thuong vi da la status=done)."""
    from courses.models import Enrollment, Lesson, LessonProgress

    scores = []
    for e in Enrollment.objects.filter(employee=employee, course__competency=competency):
        if e.status == Enrollment.Status.COMPLETED:
            scores.append(100.0)
            continue
        total = Lesson.objects.filter(module__course_id=e.course_id).count()
        if not total:
            continue
        done = e.progresses.filter(status=LessonProgress.Status.DONE).count()
        scores.append(done / total * 100)
    return scores


def _exam_source_scores(employee, competency):
    """Cac Attempt DA CHAM XONG cua de thi gan nang luc nay -> % diem (percent)."""
    from exams.models import Attempt

    return [
        float(a.percent) for a in Attempt.objects.filter(
            employee=employee, assessment__competency=competency, status=Attempt.Status.GRADED,
        )
        if a.percent is not None
    ]


def _skill_eval_source_scores(employee, competency):
    """Diem EvaluationDetail cua cac tieu chi (EvaluationCriteria) gan nang luc nay, trong cac
    phieu danh gia DA HOAN THANH (status=done) cua nhan su -> % (score/max_score). Thuoc khoi
    THUC HANH (danh gia ky nang thuc te tai nha hang)."""
    from evaluation.models import Evaluation, EvaluationCriteria, EvaluationDetail

    criteria_ids = list(
        EvaluationCriteria.objects.filter(tenant=employee.tenant, competency=competency)
        .values_list('id', flat=True)
    )
    if not criteria_ids:
        return []
    criteria_id_strs = {str(cid) for cid in criteria_ids}
    details = EvaluationDetail.objects.filter(
        evaluation__employee=employee, evaluation__status=Evaluation.Status.DONE,
        criteria_id__in=criteria_id_strs,
    )
    return [float(d.score) / float(d.max_score) * 100 for d in details if d.max_score]


def _checklist_source_scores(employee, competency):
    """Cac muc checklist dao tao khop Brand+Vi tri hien tai cua nhan su va gan nang luc nay ->
    danh sach diem tung muc (100=da Hoan thanh, 0=chua). Quy trinh checklist LUON co xac nhan
    truc tiep (anh + 2 chu ky) nen moi status=done deu tinh nhu "offline-confirmed" - khong co
    khai niem % lam do rieng nhu bai hoc online. Thuoc khoi THUC HANH."""
    from checklist.models import TrainingProgress
    from employees.services import matching_checklist_items

    items = [c for c in matching_checklist_items(employee) if c.competency_id == competency.id]
    if not items:
        return []
    done_ids = set(
        TrainingProgress.objects.filter(
            employee=employee, checklist_id__in=[c.id for c in items], status=TrainingProgress.Status.DONE,
        ).values_list('checklist_id', flat=True)
    )
    return [100.0 if c.id in done_ids else 0.0 for c in items]


def _cls_exam_source_scores(employee, competency):
    """Cac ExamResult (nguon CLS, de thi ngoai he thong khong co Assessment noi bo) co exam_name
    da duoc ANH XA (ClsExamCompetencyMap) toi nang luc nay -> % diem (final_score = uu tien diem
    phuc khao). Chua map -> khong dong gop (bo qua, khong doan). Thuoc khoi LY THUYET."""
    from cls_sync.models import ExamResult

    exam_names = list(
        ClsExamCompetencyMap.objects.filter(tenant=employee.tenant, competency=competency)
        .values_list('exam_name', flat=True)
    )
    if not exam_names:
        return []
    return [
        float(r.final_score) for r in ExamResult.objects.filter(employee=employee, exam_name__in=exam_names)
        if r.final_score is not None
    ]


DEFAULT_THEORY_WEIGHT = 50.0
DEFAULT_PRACTICE_WEIGHT = 50.0


def get_scoring_weights(tenant):
    """(trong_so_ly_thuyet, trong_so_thuc_hanh) - doc CompetencyScoringConfig cua tenant, mac
    dinh 50/50 neu tenant CHUA cau hinh (khong tu tao dong - xem views.py::
    CompetencyScoringConfigView, PATCH moi tao). Luu duoi dang % nhung khong bat buoc tong=100,
    _combine_theory_practice tu chuan hoa theo ty le."""
    config = CompetencyScoringConfig.objects.filter(tenant=tenant).first()
    if not config:
        return DEFAULT_THEORY_WEIGHT, DEFAULT_PRACTICE_WEIGHT
    return float(config.theory_weight), float(config.practice_weight)


def _combine_theory_practice(theory_score, practice_score, theory_weight, practice_weight):
    """Ket hop diem Ly thuyet + Thuc hanh theo trong so cau hinh (Prompt_Dashboard_A1_
    GanNhanNangLuc.md, muc 2). Khoi nao khong co du lieu thi BO KHOI trung binh (khong tinh la
    0) - vd chi co Ly thuyet thi diem = diem Ly thuyet, khong bi keo xuong boi Thuc hanh=0. Ca 2
    khoi cung khong co du lieu -> None. Neu trong so cau hinh ca 2 ve 0 (hy huu, cau hinh loi)
    van fallback trung binh don gian de khong mat du lieu."""
    pairs = []
    if theory_score is not None:
        pairs.append((theory_score, theory_weight))
    if practice_score is not None:
        pairs.append((practice_score, practice_weight))
    if not pairs:
        return None
    total_weight = sum(w for _, w in pairs)
    if total_weight > 0:
        return sum(s * w for s, w in pairs) / total_weight
    return sum(s for s, _ in pairs) / len(pairs)


def compute_competency_scores(employee):
    """Dashboard Phan A + A.1 - engine tinh diem nang luc, CHI DOC (khong ghi de gi). Cong don 4
    NGUON, chia 2 khoi (Prompt_Dashboard_A1_GanNhanNangLuc.md, muc 2):
      - Ly thuyet: khoa hoc online hoan thanh + diem thi (Assessment noi bo hoac ExamResult CLS
        theo ClsExamCompetencyMap).
      - Thuc hanh: checklist dao tao hoan thanh + danh gia ky nang thuc hanh.
    Diem 1 nang luc = trong_so_LT × diem_LT + trong_so_TH × diem_TH (CompetencyScoringConfig,
    mac dinh 50/50, cau hinh duoc theo tenant). Nguon/khoi nao khong co du lieu thi BO KHOI trung
    binh (khong tinh 0); khong khoi nao co du lieu -> score=None ("chưa đủ dữ liệu", khong ve
    truc, khong keo diem xuong).
    Tra ve {'position', 'ci', 'competencies': [...], 'groups': [...]}. Employee.position duoc
    khop CHUAN HOA (bo dau/hoa-thuong/khoang trang) voi vi tri da import trong PositionTarget/
    PositionGroupWeight de khong bi lech du lieu (Prompt_Fix_ImportKhungNangLuc.md, Loi 3)."""
    position = employee.position or ''
    competencies = Competency.objects.filter(tenant=employee.tenant).select_related('group')
    theory_weight, practice_weight = get_scoring_weights(employee.tenant)

    target_positions = PositionTarget.objects.filter(tenant=employee.tenant).values_list('position', flat=True).distinct()
    resolved_target_position = resolve_position(target_positions, position) or position
    targets = {
        pt.competency_id: pt.target_score
        for pt in PositionTarget.objects.filter(tenant=employee.tenant, position=resolved_target_position)
    }

    competency_results = []
    group_scores_data = defaultdict(list)
    group_targets_data = defaultdict(list)

    for comp in competencies:
        theory_sources = _course_source_scores(employee, comp) + _exam_source_scores(employee, comp) + _cls_exam_source_scores(employee, comp)
        practice_sources = _checklist_source_scores(employee, comp) + _skill_eval_source_scores(employee, comp)

        theory_score = round(sum(theory_sources) / len(theory_sources), 1) if theory_sources else None
        practice_score = round(sum(practice_sources) / len(practice_sources), 1) if practice_sources else None
        combined = _combine_theory_practice(theory_score, practice_score, theory_weight, practice_weight)
        score = round(combined, 1) if combined is not None else None

        target = targets.get(comp.id)
        gap = round(target - score, 1) if (score is not None and target is not None) else None
        competency_results.append({
            'id': comp.id, 'name': comp.name, 'group_id': comp.group_id, 'group_code': comp.group.code,
            'score': score, 'target': target, 'gap': gap,
            'theory_score': theory_score, 'practice_score': practice_score,
            'source_count': len(theory_sources) + len(practice_sources),
        })
        if score is not None:
            group_scores_data[comp.group_id].append(score)
        if target is not None:
            group_targets_data[comp.group_id].append(target)

    weight_positions = PositionGroupWeight.objects.filter(tenant=employee.tenant).values_list('position', flat=True).distinct()
    resolved_weight_position = resolve_position(weight_positions, position) or position
    weights = {
        w.group_id: float(w.weight)
        for w in PositionGroupWeight.objects.filter(tenant=employee.tenant, position=resolved_weight_position)
    }
    group_results = []
    for g in CompetencyGroup.objects.filter(tenant=employee.tenant):
        g_scores = group_scores_data.get(g.id) or []
        g_targets = group_targets_data.get(g.id) or []
        group_score = round(sum(g_scores) / len(g_scores), 1) if g_scores else None
        group_target = round(sum(g_targets) / len(g_targets), 1) if g_targets else None
        group_results.append({
            'id': g.id, 'code': g.code, 'name': g.name, 'score': group_score, 'target': group_target,
            'weight': weights.get(g.id),
        })

    weighted_sum = weight_total = 0.0
    for g in group_results:
        if g['score'] is not None and g['weight']:
            weighted_sum += g['score'] * g['weight']
            weight_total += g['weight']
    ci = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

    return {'position': position, 'ci': ci, 'competencies': competency_results, 'groups': group_results}


def competency_gaps(employee, scores=None, limit=10):
    """Bang khoang trong (gap > 0) sap giam dan + goi y khoa/checklist (gan nang luc do, chua
    hoan thanh) - dung y muc 3 cua Prompt_Dashboard_A_NangLuc_HoSo360.md, mo rong them checklist
    o Prompt_Dashboard_A1_GanNhanNangLuc.md muc 3."""
    from checklist.models import TrainingProgress
    from courses.models import Course, Enrollment
    from employees.services import matching_checklist_items

    scores = scores or compute_competency_scores(employee)
    gaps = sorted(
        (c for c in scores['competencies'] if c['gap'] is not None and c['gap'] > 0),
        key=lambda c: -c['gap'],
    )
    if limit:
        gaps = gaps[:limit]

    completed_course_ids = set(
        Enrollment.objects.filter(employee=employee, status=Enrollment.Status.COMPLETED)
        .values_list('course_id', flat=True)
    )
    matching_items = matching_checklist_items(employee)
    done_checklist_ids = set(
        TrainingProgress.objects.filter(
            employee=employee, checklist_id__in=[c.id for c in matching_items],
            status=TrainingProgress.Status.DONE,
        ).values_list('checklist_id', flat=True)
    )

    result = []
    for c in gaps:
        suggested_courses = list(
            Course.objects.filter(tenant=employee.tenant, competency_id=c['id'])
            .exclude(id__in=completed_course_ids)
            .values('id', 'title')[:3]
        )
        suggested_checklist = [
            {'id': item.id, 'task_name': item.task_name}
            for item in matching_items
            if item.competency_id == c['id'] and item.id not in done_checklist_ids
        ][:3]
        result.append({**c, 'suggested_courses': suggested_courses, 'suggested_checklist': suggested_checklist})
    return result


# ==================================================================== Ho so 360

def _probation_deadline_days_left(employee):
    """So ngay con lai toi han thu viec (am = qua han). CHI DOC Employee.start_date/
    probation_days (khong tinh lai pass/fail - xem module docstring)."""
    days = employee.probation_days
    if not days:
        days = (
            settings.PROBATION_O_DAYS if (employee.level_group or '').upper() == 'O'
            else settings.PROBATION_S_DAYS
        )
    if not employee.start_date or not days:
        return None
    deadline = employee.start_date + datetime.timedelta(days=days)
    return (deadline - timezone.now().date()).days


def _employee_warnings(employee):
    """Canh bao ca nhan (muc 4 cua prompt): qua han thu viec / nguy co khong pass (sap toi han
    ma chua Pass). Doc Employee.final_result (san co, KHONG tinh lai)."""
    warnings = []
    if employee.employee_status == 'resigned' or employee.pass_date:
        return warnings
    days_left = _probation_deadline_days_left(employee)
    if days_left is None:
        return warnings
    if days_left < 0:
        warnings.append({'type': 'overdue', 'label': f'Quá hạn thử việc {abs(days_left)} ngày, chưa Pass'})
    elif days_left <= 7:
        warnings.append({'type': 'at_risk', 'label': f'Còn {days_left} ngày tới hạn thử việc, chưa Pass'})
    return warnings


def _build_timeline(employee, enrollments, attempts):
    from evaluation.models import Evaluation

    events = []
    if employee.start_date:
        events.append({'date': employee.start_date, 'type': 'joined', 'label': 'Vào làm'})
    for e in enrollments.filter(status__in=['completed']).select_related('course'):
        last_done = e.progresses.filter(status='done', completed_at__isnull=False).order_by('-completed_at').first()
        if last_done:
            events.append({
                'date': last_done.completed_at.date(), 'type': 'course',
                'label': f'Hoàn thành khóa: {e.course.title}',
            })
    for a in attempts.select_related('assessment'):
        if a.submitted_at:
            events.append({
                'date': a.submitted_at.date(), 'type': 'exam',
                'label': f'Thi "{a.assessment.title}": {"Đạt" if a.passed else "Chưa đạt"} ({a.percent}%)',
            })
    for ev in Evaluation.objects.filter(employee=employee, status=Evaluation.Status.DONE, completed_at__isnull=False):
        events.append({
            'date': ev.completed_at.date(), 'type': 'evaluation',
            'label': f'Đánh giá {ev.get_eval_type_display()}: {ev.percent}%',
        })
    if employee.pass_date:
        events.append({'date': employee.pass_date, 'type': 'pass', 'label': 'Pass thử việc'})
    events.sort(key=lambda x: x['date'])
    return [{**ev, 'date': ev['date'].isoformat()} for ev in events]


def _resolve_indicator_value(key, context):
    """Gia tri thuc te cho 1 chi so co role_scope chua 'ho_so' (man Ho so 360) - CHI cac chi
    so co nguon du lieu that. Chua co nguon -> None ("Chờ dữ liệu")."""
    if key == 'ci_tong_hop':
        return context['ci']
    if key == 'dat_ky_nang_lan_dau':
        result = (context['employee'].skill_result or '').strip()
        if not result:
            return None
        return 100.0 if result == 'Đạt' else 0.0
    if key == 'diem_thi_trung_binh':
        return context['exam']['avg_percent']
    if key == 'so_chung_chi_da_cap':
        return float(len(context['certificates']))
    if key == 'nv_qua_han':
        return 1.0 if any(w['type'] == 'overdue' for w in context['warnings']) else 0.0
    if key == 'nv_nguy_co_khong_pass':
        return 1.0 if any(w['type'] == 'at_risk' for w in context['warnings']) else 0.0
    return None  # radar/top_skill_gap: hien thi rieng (chart/bang), khong phai 1 con so


def employee_360(employee):
    """Dashboard Phan A muc 4 - goi du lieu Ho so 360. CHI DOC (xem module docstring)."""
    from courses.models import Enrollment
    from exams.models import Attempt
    from integration.models import CertificateIssued

    scores = compute_competency_scores(employee)
    gaps = competency_gaps(employee, scores=scores)

    enrollments = Enrollment.objects.filter(employee=employee)
    attempts = Attempt.objects.filter(employee=employee, status=Attempt.Status.GRADED)
    percents = [float(a.percent) for a in attempts if a.percent is not None]
    avg_percent = round(sum(percents) / len(percents), 1) if percents else None

    certificates = [
        {
            'id': c.id, 'code': c.code, 'ref_type': c.ref_type, 'issue_date': c.issue_date,
            'pdf_url': c.pdf_url, 'program_name': c.program.name if c.program_id else '',
        }
        for c in CertificateIssued.objects.filter(employee=employee).select_related('program').order_by('-issued_at')
    ]

    warnings = _employee_warnings(employee)
    context = {
        'employee': employee, 'ci': scores['ci'],
        'exam': {'attempts': attempts.count(), 'avg_percent': avg_percent},
        'certificates': certificates, 'warnings': warnings,
    }

    indicators = []
    for ind in DashboardIndicator.objects.filter(tenant=employee.tenant, enabled=True):
        if 'ho_so' not in (ind.role_scope or []):
            continue
        value = _resolve_indicator_value(ind.key, context)
        indicators.append({
            'key': ind.key, 'label': ind.label, 'value': value,
            'color': indicator_color(ind, value), 'pending': value is None,
        })

    return {
        'employee': {
            'id': employee.id, 'code': employee.code, 'name': employee.name,
            'position': employee.position,
            'restaurant': employee.restaurant.name if employee.restaurant_id else '',
            'start_date': employee.start_date, 'employee_status': employee.employee_status,
            'final_result': employee.final_result, 'pass_date': employee.pass_date,
        },
        'ci': scores['ci'], 'position': scores['position'],
        'competencies': scores['competencies'], 'groups': scores['groups'],
        'gaps': gaps,
        'study': {'total': enrollments.count(), 'done': enrollments.filter(status=Enrollment.Status.COMPLETED).count()},
        'exam': context['exam'],
        'certificates': certificates,
        'timeline': _build_timeline(employee, enrollments, attempts),
        'warnings': warnings,
        'indicators': indicators,
    }


# ==================================================================== Phan B: Man tong hop CEO/GDDT
#
# TAI DUNG service da co (kpi/employees/courses/exams/integration) - KHONG tinh lai logic pass
# thu viec/hoa hong/CI da co san. 2 chi so KHONG the tinh voi du lieu hien co (chua co model
# theo doi): 'tuan_thu_dao_tao_bat_buoc' (chua co khai niem khoa/chung trinh BAT BUOC trong he
# thong) va 'nha_hang_do_nhieu_ky' (can luu snapshot nhieu ky lien tiep, chua co bang luu tru) -
# 2 chi so nay LUON tra ve None ("Chờ dữ liệu") cho toi khi co du lieu nguon tuong ung.

def _month_bounds(year, month):
    from reports.period import _last_day_of_month

    start = datetime.date(year, month, 1)
    return start, _last_day_of_month(start)


def _restaurant_matches_cost_row(restaurant, scope, unit_code):
    """1 dong TrainingCost (scope+unit_code) co ap dung cho 1 Restaurant cu the khong."""
    if scope == TrainingCost.Scope.SYSTEM:
        return True
    if not restaurant:
        return False
    if scope == TrainingCost.Scope.REGION:
        return bool(unit_code) and _deburr_lower(unit_code) == _deburr_lower(restaurant.region or '')
    if scope == TrainingCost.Scope.RESTAURANT:
        return bool(unit_code) and _deburr_lower(unit_code) == _deburr_lower(restaurant.code or '')
    return False


def training_cost_total(tenant, month, year, restaurant=None):
    """Tong chi phi dao tao cua 1 ky (thang/nam). restaurant=None -> cong tat ca dong bat ke
    pham vi; restaurant=<Restaurant> -> chi cong dong SYSTEM + REGION/RESTAURANT khop nha hang
    do. None (khac 0.0) neu tenant CHUA IMPORT dong chi phi nao cho ky nay - "Chờ dữ liệu"."""
    costs = list(TrainingCost.objects.filter(tenant=tenant, month=month, year=year))
    if not costs:
        return None
    if restaurant is None:
        return float(sum(c.amount for c in costs))
    return float(sum(
        c.amount for c in costs if _restaurant_matches_cost_row(restaurant, c.scope, c.unit_code)
    ))


def cost_per_passed_employee(tenant, month, year, restaurant=None):
    """Chi phi / nhan su pass = tong chi phi ky / so NV Pass thu viec trong ky (pass_date trong
    thang, doc Employee.pass_date co san - khong tinh lai pass/fail). None neu chua co chi phi
    HOAC chua co ai pass trong ky (tranh chia 0)."""
    from employees.models import Employee

    total = training_cost_total(tenant, month, year, restaurant)
    if total is None:
        return None
    start, end = _month_bounds(year, month)
    qs = Employee.objects.filter(tenant=tenant, pass_date__range=(start, end))
    if restaurant is not None:
        qs = qs.filter(restaurant=restaurant)
    passed = qs.count()
    if not passed:
        return None
    return round(total / passed, 1)


_COST_TYPE_ALIASES = {
    TrainingCost.CostType.TRAINER_SALARY: ['luong', 'phu cap trainer', 'luong & phu cap trainer'],
    TrainingCost.CostType.MATERIALS: ['tai lieu', 'in an', 'tai lieu & in an'],
    TrainingCost.CostType.SOFTWARE: ['phan mem', 'lms', 'phan mem / lms'],
    TrainingCost.CostType.FACILITIES: ['co so vat chat', 'csvc'],
    TrainingCost.CostType.TRAVEL: ['an o', 'di lai', 'an o & di lai'],
    TrainingCost.CostType.OTHER: ['khac'],
}
_SCOPE_ALIASES = {
    TrainingCost.Scope.SYSTEM: ['toan he thong'],
    TrainingCost.Scope.REGION: ['vung'],
    TrainingCost.Scope.RESTAURANT: ['nha hang'],
}


def _match_choice(raw, aliases):
    norm = _deburr_lower(raw)
    if not norm:
        return None
    for key, keywords in aliases.items():
        if norm == _deburr_lower(key) or any(_deburr_lower(kw) in norm for kw in keywords):
            return key
    return None


def import_training_costs(tenant, rows):
    """Nap chi phi dao tao tu danh sach dong CSV da doc san (list[dict], xem config.csv_source.
    load_csv_rows - dung chung co che voi RecruitmentSource/HrSyncSource) theo dung cau truc
    File_HachToan_ChiPhiDaoTao_MAU.xlsx: Tháng, Năm, Loại chi phí, Đơn vị áp dụng, Mã đơn vị, Số
    tiền (VND), Ghi chú. Idempotent - update_or_create theo (thang, nam, loai, pham vi, ma don
    vi); dong thieu du lieu/khong nhan dien duoc loai chi phi -> bo qua + canh bao, khong doan."""
    from config.csv_source import pick

    written = 0
    warnings = []
    for i, row in enumerate(rows, start=2):  # dong 1 la tieu de
        month_raw = pick(row, 'Tháng', 'Thang', 'month')
        year_raw = pick(row, 'Năm', 'Nam', 'year')
        cost_type_raw = pick(row, 'Loại chi phí', 'Loai chi phi', 'cost_type')
        scope_raw = pick(row, 'Đơn vị áp dụng', 'Don vi ap dung', 'scope')
        unit_code = pick(row, 'Mã đơn vị', 'Ma don vi', 'unit_code')
        amount_raw = pick(row, 'Số tiền (VND)', 'So tien (VND)', 'So tien', 'amount')
        note = pick(row, 'Ghi chú', 'Ghi chu', 'note')

        if not any([month_raw, year_raw, cost_type_raw, amount_raw]):
            continue  # dong trong hoan toan - bo qua am tham
        if not (month_raw and year_raw and cost_type_raw and amount_raw):
            warnings.append(f'Dòng {i}: thiếu tháng/năm/loại chi phí/số tiền, đã bỏ qua.')
            continue
        try:
            month, year = int(month_raw), int(year_raw)
            amount = float(str(amount_raw).replace(',', '').replace(' ', ''))
        except ValueError:
            warnings.append(f'Dòng {i}: tháng/năm/số tiền không hợp lệ, đã bỏ qua.')
            continue

        cost_type = _match_choice(cost_type_raw, _COST_TYPE_ALIASES)
        if not cost_type:
            warnings.append(f'Dòng {i}: không nhận diện được loại chi phí "{cost_type_raw}", đã bỏ qua.')
            continue
        scope = _match_choice(scope_raw, _SCOPE_ALIASES) or TrainingCost.Scope.SYSTEM
        if scope != TrainingCost.Scope.SYSTEM and not unit_code:
            warnings.append(f'Dòng {i}: phạm vi "{scope_raw}" cần "Mã đơn vị", đã bỏ qua.')
            continue

        TrainingCost.objects.update_or_create(
            tenant=tenant, month=month, year=year, cost_type=cost_type,
            scope=scope, unit_code=unit_code if scope != TrainingCost.Scope.SYSTEM else '',
            defaults={'amount': amount, 'note': note},
        )
        written += 1

    return {'written': written, 'warnings': warnings}


def sync_training_costs(tenant):
    """Doc link CSV da cau hinh (TrainingCostSource) va nap qua import_training_costs. Rong ->
    ValidationError (giong RecruitmentSourceView khi chua co link)."""
    from config.csv_source import load_csv_rows

    source = TrainingCostSource.objects.filter(tenant=tenant).first()
    csv_url = source.csv_url if source else ''
    if not csv_url:
        raise ValidationError('Chưa cấu hình link CSV nguồn chi phí đào tạo.')
    rows = load_csv_rows(csv_url)
    return import_training_costs(tenant, rows)


def refresh_competency_snapshots(tenant):
    """Tinh NEN dinh ky CompetencySnapshot/CompetencyScoreSnapshot cho toan bo nhan su dang lam
    cua 1 tenant (Prompt_Fix_OOM_DashboardTongHop.md) - dung LAI DUNG engine
    compute_competency_scores (Phan A/A.1), KHONG doi cong thuc/y nghia so lieu, chi doi CHO
    tinh (background/cron thay vi trong 1 request cua man tong hop). Chay qua management
    command (xem management/commands/refresh_competency_snapshots.py), KHONG goi tu web request
    de tranh chinh no gay OOM. Dung .iterator(chunk_size=500) de khong giu ca list ~1000+
    Employee trong bo nho cung luc."""
    from employees.models import Employee

    employees_qs = (
        Employee.objects.filter(tenant=tenant, is_legacy=False)
        .exclude(employee_status='resigned')
        .select_related('restaurant')
        .iterator(chunk_size=500)
    )

    updated = 0
    kept_employee_ids = []
    for e in employees_qs:
        scores = compute_competency_scores(e)
        CompetencySnapshot.objects.update_or_create(
            tenant=tenant, employee=e,
            defaults={'restaurant': e.restaurant, 'ci': scores['ci']},
        )
        CompetencyScoreSnapshot.objects.filter(employee=e).delete()
        rows = [
            CompetencyScoreSnapshot(
                tenant=tenant, employee=e, competency_id=c['id'], group_id=c['group_id'],
                score=c['score'], target=c['target'], gap=c['gap'],
            )
            for c in scores['competencies']
        ]
        if rows:
            CompetencyScoreSnapshot.objects.bulk_create(rows)
        kept_employee_ids.append(e.id)
        updated += 1

    # Don snapshot cua nhan su khong con trong scope (nghi viec/xoa/is_legacy) - tranh so lieu ma.
    CompetencySnapshot.objects.filter(tenant=tenant).exclude(employee_id__in=kept_employee_ids).delete()
    CompetencyScoreSnapshot.objects.filter(tenant=tenant).exclude(employee_id__in=kept_employee_ids).delete()

    return {'updated': updated}


def _competency_aggregate_from_snapshot(tenant, restaurant=None):
    """Chi so nang luc cap he thong: CI trung binh, % dat muc tieu, san sang nhan luc (CI >= 80 -
    nguong toi thieu, dong bo voi nguong xanh/vang 90/80 mac dinh cua cac chi so "higher_better"
    khac), top skill gap toan he thong, diem trung binh THEO NHOM (Radar CI trung bình) - ĐỌC
    TỪ CompetencySnapshot/CompetencyScoreSnapshot (da tinh nen dinh ky) bang truy van aggregate
    (Avg/Count), KHONG lap Python qua tung nhan su - so truy van HANG SO du tenant co bao nhieu
    nhan su (Prompt_Fix_OOM_DashboardTongHop.md, sua thay the ham _competency_aggregate cu goi
    compute_competency_scores() cho tung nhan su, la nguyen nhan gay OOM)."""
    snap_qs = CompetencySnapshot.objects.filter(tenant=tenant)
    if restaurant is not None:
        snap_qs = snap_qs.filter(restaurant=restaurant)
    snap_agg = snap_qs.aggregate(
        ci_avg=Avg('ci'),
        total_scored=Count('id', filter=Q(ci__isnull=False)),
        ready=Count('id', filter=Q(ci__gte=80)),
    )
    ci_avg = round(float(snap_agg['ci_avg']), 1) if snap_agg['ci_avg'] is not None else None
    ready_rate = (
        round(snap_agg['ready'] / snap_agg['total_scored'] * 100, 1) if snap_agg['total_scored'] else None
    )

    score_qs = CompetencyScoreSnapshot.objects.filter(tenant=tenant)
    if restaurant is not None:
        score_qs = score_qs.filter(employee__restaurant=restaurant)
    score_agg = score_qs.aggregate(
        comp_total=Count('id', filter=Q(score__isnull=False, target__isnull=False)),
        comp_hit=Count('id', filter=Q(score__isnull=False, target__isnull=False, gap__lte=0)),
    )
    target_rate = (
        round(score_agg['comp_hit'] / score_agg['comp_total'] * 100, 1) if score_agg['comp_total'] else None
    )

    top_gaps = [
        {'name': row['competency__name'], 'avg_gap': round(float(row['avg_gap']), 1), 'count': row['count']}
        for row in (
            score_qs.filter(gap__gt=0)
            .values('competency__name')
            .annotate(avg_gap=Avg('gap'), count=Count('id'))
            .order_by('-avg_gap')[:10]
        )
    ]

    group_avg = [
        {'code': row['group__code'], 'name': row['group__name'], 'avg_score': round(float(row['avg_score']), 1)}
        for row in (
            score_qs.filter(score__isnull=False)
            .values('group__code', 'group__name')
            .annotate(avg_score=Avg('score'))
            .order_by('group__code')
        )
    ]

    computed_at = snap_qs.aggregate(latest=Max('computed_at'))['latest']

    return {
        'ci_avg': ci_avg, 'target_rate': target_rate, 'ready_rate': ready_rate,
        'top_gaps': top_gaps, 'group_avg': group_avg, 'computed_at': computed_at,
    }


def _dung_lo_trinh_trend(user, month, year, months=6):
    """Xu huong '% dung lo trinh'/'% dat ky nang lan dau' toan he thong theo N thang gan nhat
    (mac dinh 6), goi lai kpi.services.kpi_bql_totals (ban nhe, bo qua khoi AM/KCS/OM khong can
    cho bieu do) cho tung thang - khong luu snapshot rieng, tinh truc tiep tu du lieu hien co."""
    from kpi.services import kpi_bql_totals

    trend = []
    y, m = year, month
    for _ in range(months):
        totals = kpi_bql_totals(user, m, y)
        trend.append({'month': m, 'year': y, 'on_rate': totals['on_rate'], 'skill_rate': totals['skill_rate']})
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    trend.reverse()
    return trend


def _aggregate_context(user, month, year, restaurant):
    """Xay du lieu dung chung cho toan bo chi so CEO/GDDT trong 1 lan goi (tranh tinh lai N lan
    cho tung chi so trong 29 chi so). CHI DOC - khong ghi gi vao bat ky model nguon nao."""
    from courses.models import Enrollment
    from employees.career import talent_pool_employees
    from employees.models import Employee
    from exams.models import Attempt
    from integration.models import CertificateIssued
    from kpi.models import KpiParticipant, KpiSession
    from kpi.services import allowance_report_data, kpi_bql_report_data
    from reports.metrics_training import exam_block

    tenant = user.tenant
    month_start, month_end = _month_bounds(year, month)

    # --- Onboarding: dung lo trinh + dat ky nang lan dau (tai dung kpi.services co san) ---
    kpi_data = kpi_bql_report_data(user, month, year)
    kpi_rows = kpi_data['rows']
    if restaurant:
        matched = next((r for r in kpi_rows if r.get('restaurant_id') == restaurant.id), None)
        kpi_totals = matched or {'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0, 'on_rate': 0, 'skill_rate': 0}
    else:
        kpi_totals = kpi_data['totals']

    # --- Nhan su: pass thu viec / nghi viec (Employee.pass_date/resigned_at, khong tinh lai) ---
    cohort_qs = Employee.objects.filter(tenant=tenant, is_legacy=False, start_date__range=(month_start, month_end))
    if restaurant:
        cohort_qs = cohort_qs.filter(restaurant=restaurant)
    cohort = list(cohort_qs)
    resigned_cohort = [e for e in cohort if e.employee_status == 'resigned']
    pass_count = sum(1 for e in cohort if e.pass_date)
    pass_rate = round(pass_count / len(cohort) * 100, 1) if cohort else None
    resign_rate = round(len(resigned_cohort) / len(cohort) * 100, 1) if cohort else None
    pass_days = [(e.pass_date - e.start_date).days for e in cohort if e.pass_date and e.start_date]
    avg_days_to_pass = round(sum(pass_days) / len(pass_days), 1) if pass_days else None
    early_leavers = [
        e for e in resigned_cohort
        if e.resigned_at and e.start_date and (e.resigned_at - e.start_date).days < 60
    ]
    with_trainer = [e for e in cohort if e.trainer_id]
    trainer_pass_rate = (
        round(sum(1 for e in with_trainer if e.pass_date) / len(with_trainer) * 100, 1) if with_trainer else None
    )

    # --- Nang luc (CI/muc tieu/san sang nhan luc/skill gap) - DOC snapshot da tinh nen dinh ky
    #     (CompetencySnapshot/CompetencyScoreSnapshot), KHONG goi compute_competency_scores cho
    #     tung nhan su trong request nay (nguyen nhan OOM cu - Prompt_Fix_OOM_
    #     DashboardTongHop.md). Snapshot lam moi qua management command
    #     refresh_competency_snapshots (chay nen/cron, xem docstring). ---
    competency = _competency_aggregate_from_snapshot(tenant, restaurant)

    # --- San sang ke can (tai dung employees.career.talent_pool_employees) ---
    talent_pool = talent_pool_employees(tenant)
    if restaurant:
        talent_pool = [e for e in talent_pool if e.restaurant_id == restaurant.id]

    # --- Hoc & thi: hoan thanh khoa (courses.Enrollment), dat lan dau (exams.Attempt), thi dat/
    #     diem TB (reports.metrics_training.exam_block - da co san, chi them loc nha hang) ---
    enroll_qs = Enrollment.objects.filter(tenant=tenant, created_at__date__range=(month_start, month_end))
    if restaurant:
        enroll_qs = enroll_qs.filter(employee__restaurant=restaurant)
    enroll_total = enroll_qs.count()
    completed_qs = enroll_qs.filter(status=Enrollment.Status.COMPLETED)
    enroll_completed = completed_qs.count()
    course_completion_rate = round(enroll_completed / enroll_total * 100, 1) if enroll_total else None
    # So sanh ngay hoan thanh vs han (F() -> 1 truy van aggregate, khong nap Enrollment vao Python).
    due_qs = completed_qs.filter(due_date__isnull=False)
    due_total = due_qs.count()
    on_time = due_qs.filter(updated_at__date__lte=F('due_date')).count()
    on_time_rate = round(on_time / due_total * 100, 1) if due_total else None

    attempt_qs = Attempt.objects.filter(
        tenant=tenant, attempt_no=1, status=Attempt.Status.GRADED, submitted_at__date__range=(month_start, month_end),
    )
    if restaurant:
        attempt_qs = attempt_qs.filter(employee__restaurant=restaurant)
    first_attempt_total = attempt_qs.count()
    first_attempt_pass = attempt_qs.filter(passed=True).count()
    first_pass_rate = round(first_attempt_pass / first_attempt_total * 100, 1) if first_attempt_total else None

    exam = exam_block(tenant, month_start, month_end, restaurant_id=restaurant.id if restaurant else None)

    # --- Chung chi (integration.CertificateIssued) ---
    cert_qs = CertificateIssued.objects.filter(tenant=tenant, issue_date__range=(month_start, month_end))
    if restaurant:
        cert_qs = cert_qs.filter(employee__restaurant=restaurant)
    cert_count = cert_qs.count()

    # --- Trainer & don vi: buoi kem (kpi.KpiSession) + phu cap (kpi.services.allowance_report_data) ---
    session_qs = KpiSession.objects.filter(tenant=tenant, date__range=(month_start, month_end))
    if restaurant:
        session_qs = session_qs.filter(restaurant=restaurant)
    session_count = session_qs.count()
    participant_count = KpiParticipant.objects.filter(session__in=session_qs).values('employee').distinct().count()

    allowance = allowance_report_data(user, month, year)
    if restaurant:
        allowance_total = sum(r['amount'] for r in allowance['rows'] if r['trainer_restaurant'] == restaurant.name)
    else:
        allowance_total = allowance['total_amount']
    trainer_amounts = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    for r in allowance['rows']:
        key = r['trainer'] or '(Chưa gán trainer)'
        trainer_amounts[key]['amount'] += r['amount']
        trainer_amounts[key]['count'] += 1
    trainer_breakdown = sorted(
        ({'trainer': t, **v} for t, v in trainer_amounts.items()), key=lambda x: -x['amount'],
    )

    # --- Xep hang nha hang + nha hang duoi nguong (tu kpi_rows, luon toan he thong) - to mau
    #     tung dong theo DUNG nguong da cau hinh cua chi so 'dung_lo_trinh' (khong bia nguong
    #     rieng cho bieu do, dong bo voi Cau hinh Dashboard). ---
    dlt_indicator = DashboardIndicator.objects.filter(tenant=tenant, key='dung_lo_trinh').first()
    green_threshold = float(dlt_indicator.green_threshold) if dlt_indicator and dlt_indicator.green_threshold is not None else 90.0
    low_threshold = float(dlt_indicator.yellow_threshold) if dlt_indicator and dlt_indicator.yellow_threshold is not None else 80.0

    restaurant_ranking = sorted(kpi_rows, key=lambda r: -r['on_rate'])
    for row in restaurant_ranking:
        if row['on_den'] == 0:
            row['color'] = None
        elif row['on_rate'] >= green_threshold:
            row['color'] = 'green'
        elif row['on_rate'] >= low_threshold:
            row['color'] = 'yellow'
        else:
            row['color'] = 'red'
    below_threshold_restaurants = [r for r in kpi_rows if r['on_den'] > 0 and r['on_rate'] < low_threshold]

    # --- Canh bao (tai dung _probation_deadline_days_left da co san, khong tinh lai) - LOC
    #     TRUOC o DB (chua Pass + chua nghi viec) thay vi nap toan bo nhan su dang lam roi loai
    #     trong Python: mau chi con nhan su CON DANG thu viec (nho hon nhieu so voi toan bo
    #     roster), select_related('restaurant') tranh N+1 khi doc ten nha hang. ---
    probation_qs = (
        Employee.objects.filter(tenant=tenant, is_legacy=False, pass_date__isnull=True)
        .exclude(employee_status='resigned')
        .select_related('restaurant')
    )
    if restaurant:
        probation_qs = probation_qs.filter(restaurant=restaurant)
    overdue_count, at_risk_count, warnings_table = _employee_warning_rows(probation_qs.iterator(chunk_size=500))

    # --- Cong chi phi (muc 4) ---
    cost_total = training_cost_total(tenant, month, year, restaurant)
    cost_per_pass = cost_per_passed_employee(tenant, month, year, restaurant)

    return {
        'kpi_totals': kpi_totals,
        'pass_rate': pass_rate, 'resign_rate': resign_rate, 'avg_days_to_pass': avg_days_to_pass,
        'early_leavers_count': len(early_leavers), 'trainer_pass_rate': trainer_pass_rate,
        'competency': competency, 'talent_pool_count': len(talent_pool),
        'course_completion_rate': course_completion_rate, 'on_time_rate': on_time_rate,
        'first_pass_rate': first_pass_rate, 'exam': exam, 'cert_count': cert_count,
        'session_count': session_count, 'participant_count': participant_count,
        'allowance_total': allowance_total, 'trainer_breakdown': trainer_breakdown,
        'restaurant_ranking': restaurant_ranking, 'below_threshold_restaurants': below_threshold_restaurants,
        'overdue_count': overdue_count, 'at_risk_count': at_risk_count, 'warnings_table': warnings_table,
        'cost_total': cost_total, 'cost_per_pass': cost_per_pass,
        'trend': _dung_lo_trinh_trend(user, month, year),
    }


def _employee_warning_rows(employees, today=None):
    """1 lan duyet: (so qua han, so nguy co khong pass, danh sach dong) - tai dung
    _probation_deadline_days_left da co (khong tinh lai logic pass thu viec)."""
    today = today or timezone.now().date()
    overdue = at_risk = 0
    rows = []
    for e in employees:
        if e.employee_status == 'resigned' or e.pass_date:
            continue
        days_left = _probation_deadline_days_left(e)
        if days_left is None:
            continue
        if days_left < 0:
            overdue += 1
            kind = 'overdue'
        elif days_left <= 7:
            at_risk += 1
            kind = 'at_risk'
        else:
            continue
        rows.append({
            'employee_id': e.id, 'code': e.code, 'name': e.name,
            'restaurant': e.restaurant.name if e.restaurant_id else '', 'days_left': days_left, 'type': kind,
        })
    rows.sort(key=lambda r: r['days_left'])
    return overdue, at_risk, rows


def _resolve_aggregate_indicator_value(key, c):
    """Gia tri 1 chi so tren man tong hop CEO/GDDT tu context da build (_aggregate_context).
    Chi so nao hien thi rieng thanh bang/danh sach (khong phai 1 con so) tra ve None (khong
    'Chờ dữ liệu' sai nghia - frontend biet chi nay render bang rieng qua field khac cua
    payload). Chi so chua co nguon du lieu (tuan_thu_dao_tao_bat_buoc, nha_hang_do_nhieu_ky)
    LUON None - xem ghi chu dau file."""
    if key == 'ci_tong_hop':
        return c['competency']['ci_avg']
    if key == 'ty_le_dat_muc_tieu_nang_luc':
        return c['competency']['target_rate']
    if key == 'top_skill_gap':
        return None
    if key == 'dung_lo_trinh':
        return float(c['kpi_totals']['on_rate']) if c['kpi_totals']['on_den'] else None
    if key == 'dat_ky_nang_lan_dau':
        return float(c['kpi_totals']['skill_rate']) if c['kpi_totals']['skill_total'] else None
    if key == 'ty_le_pass_thu_viec':
        return c['pass_rate']
    if key == 'thoi_gian_tb_den_pass':
        return c['avg_days_to_pass']
    if key == 'ty_le_hoan_thanh_khoa':
        return c['course_completion_rate']
    if key == 'hoan_thanh_dung_han':
        return c['on_time_rate']
    if key == 'ty_le_thi_dat':
        return c['exam']['pass_rate']
    if key == 'ty_le_dat_lan_dau':
        return c['first_pass_rate']
    if key == 'diem_thi_trung_binh':
        return c['exam']['avg_score']
    if key == 'ty_le_nghi_viec_thu_viec':
        return c['resign_rate']
    if key == 'nghi_viec_som':
        return float(c['early_leavers_count'])
    if key == 'san_sang_nhan_luc':
        return c['competency']['ready_rate']
    if key == 'san_sang_ke_can':
        return float(c['talent_pool_count'])
    if key == 'so_buoi_kem_theo_trainer':
        return float(c['session_count'])
    if key == 'ty_le_pass_theo_trainer':
        return c['trainer_pass_rate']
    if key == 'phu_cap_dao_tao':
        return float(c['allowance_total'])
    if key == 'xep_hang_nha_hang':
        return None
    if key == 'nha_hang_duoi_nguong':
        return float(len(c['below_threshold_restaurants']))
    if key == 'so_chung_chi_da_cap':
        return float(c['cert_count'])
    if key == 'tuan_thu_dao_tao_bat_buoc':
        return None
    if key == 'tong_chi_phi_dao_tao':
        return c['cost_total']
    if key == 'chi_phi_moi_nhan_su_pass':
        return c['cost_per_pass']
    if key == 'nv_qua_han':
        return float(c['overdue_count'])
    if key == 'nv_nguy_co_khong_pass':
        return float(c['at_risk_count'])
    if key == 'nha_hang_do_nhieu_ky':
        return None
    return None


def compute_aggregate_dashboard(user, scope, month, year, restaurant_id=None):
    """Dashboard Phan B - man tong hop CEO/GDDT (Prompt_Dashboard_B_ManTongHop.md). Render DONG
    theo DashboardIndicator: chi tra ve chi so dang BAT va co scope ('ceo'/'gdt') trong
    role_scope, mau theo nguong da cau hinh (indicator_color, Phan A). TAI DUNG toan bo service
    da co (kpi/employees/courses/exams/integration) - KHONG tinh lai logic pass thu viec/hoa
    hong/engine nang luc."""
    from restaurants.models import Restaurant

    tenant = user.tenant
    restaurant = Restaurant.objects.filter(tenant=tenant, pk=restaurant_id).first() if restaurant_id else None
    context = _aggregate_context(user, month, year, restaurant)

    indicators = []
    for ind in DashboardIndicator.objects.filter(tenant=tenant, enabled=True).order_by('order'):
        if scope not in (ind.role_scope or []):
            continue
        value = _resolve_aggregate_indicator_value(ind.key, context)
        indicators.append({
            'key': ind.key, 'label': ind.label, 'group_label': ind.group_label,
            'value': value, 'color': indicator_color(ind, value), 'pending': value is None,
        })

    return {
        'scope': scope, 'month': month, 'year': year,
        'restaurant': {'id': restaurant.id, 'name': restaurant.name} if restaurant else None,
        'indicators': indicators,
        'restaurant_ranking': context['restaurant_ranking'],
        'trend': context['trend'],
        'warnings_table': context['warnings_table'],
        'top_skill_gap': context['competency']['top_gaps'],
        'competency_group_avg': context['competency']['group_avg'],
        # Cac chi so nang luc (CI/muc tieu/san sang/skill gap) doc tu snapshot tinh nen dinh ky
        # (khong realtime) - gui kem thoi diem tinh gan nhat de UI hien "tinh luc ...".
        'competency_snapshot_at': context['competency']['computed_at'],
        'trainer_breakdown': context['trainer_breakdown'],
    }
