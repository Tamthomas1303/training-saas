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
from django.utils import timezone

from .models import CompetencyGroup, Competency, DashboardIndicator, PositionGroupWeight, PositionTarget


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
    phieu danh gia DA HOAN THANH (status=done) cua nhan su -> % (score/max_score)."""
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


def compute_competency_scores(employee):
    """Dashboard Phan A muc 3 - engine tinh diem nang luc, CHI DOC (khong ghi de gi). Tra ve
    {'position', 'ci', 'competencies': [...], 'groups': [...]}. Competency/group khong co
    nguon nao -> score=None ("chưa đủ dữ liệu"), KHONG tinh la 0 (tranh lam hong radar).
    Employee.position duoc khop CHUAN HOA (bo dau/hoa-thuong/khoang trang) voi vi tri da import
    trong PositionTarget/PositionGroupWeight de khong bi lech du lieu (Prompt_Fix_
    ImportKhungNangLuc.md, Loi 3)."""
    position = employee.position or ''
    competencies = Competency.objects.filter(tenant=employee.tenant).select_related('group')

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
        source_scores = (
            _course_source_scores(employee, comp)
            + _exam_source_scores(employee, comp)
            + _skill_eval_source_scores(employee, comp)
        )
        score = round(sum(source_scores) / len(source_scores), 1) if source_scores else None
        target = targets.get(comp.id)
        gap = round(target - score, 1) if (score is not None and target is not None) else None
        competency_results.append({
            'id': comp.id, 'name': comp.name, 'group_id': comp.group_id, 'group_code': comp.group.code,
            'score': score, 'target': target, 'gap': gap, 'source_count': len(source_scores),
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
    """Bang khoang trong (gap > 0) sap giam dan + goi y khoa (gan nang luc do, chua hoan
    thanh) - dung y muc 3 cua prompt."""
    from courses.models import Course, Enrollment

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
    result = []
    for c in gaps:
        suggested = list(
            Course.objects.filter(tenant=employee.tenant, competency_id=c['id'])
            .exclude(id__in=completed_course_ids)
            .values('id', 'title')[:3]
        )
        result.append({**c, 'suggested_courses': suggested})
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
