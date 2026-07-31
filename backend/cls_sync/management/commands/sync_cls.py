"""
sync_cls — kéo Kết quả học (CourseResult) và Kết quả thi (ExamResult) từ API CLS.

Port từ AppsScript Ver 2.0/CLS_Sync_KetQuaHoc_FIX.gs + CLS_Sync_KetQuaThi_FIX.gs + ProbationService.gs,
giữ nguyên logic nghiệp vụ:
  - Khóa học Hội nhập (mã bắt đầu HOINHAP_) chỉ lấy học viên ĐÃ HOÀN THÀNH (progress>=100 hoặc isPassed
    hoặc result chứa "đạt"). Khóa Lên Level (mã bắt đầu LEVEL_) lấy tất cả (kể cả dở dang).
  - Điểm Hội nhập cao nhất >= CLS_ONBOARDING_PASS_SCORE (mặc định 80) → đủ điều kiện thi
    (xem cls_sync.services.onboarding_eligible).
  - Kỳ thi thử việc: CLS không trả số lần thi trực tiếp — số lần thi được suy ra theo thứ tự thời gian
    (exam.startDate) trong lịch sử thi của từng nhân sự, cùng "loại" thi (tiền tố trước dấu "_" trong
    tên topic, vd "10N_BT_BTT_..." → loại "10N"; xem CLS_PROBATION_EXAM_TYPES). Lần thi đầu tiên giữ
    nguyên điểm/kết quả; lần 2 và lần 3 (nếu có) chỉ giữ lại điểm CAO NHẤT trong 2 lần đó — đúng logic
    J/K (lần 1) + L/M (cao nhất lần 2/3) của ProbationService.gs::_examFrom.
"""
import re
from collections import defaultdict
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from cls_sync.models import CourseResult, ExamResult
from cls_sync.services import onboarding_eligible
from employees.models import Employee

TOPIC_PREFIX_RE = re.compile(r'^([A-Za-z0-9]+)_')
REQUEST_TIMEOUT = 30


def _get_json(base_url, path, params, stdout, style):
    url = f'{base_url}{path}'
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        stdout.write(style.WARNING(f'  Loi goi {path}: {exc}'))
        return None


def _as_list(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    return payload.get('data') or []


def _parse_exam_date(exam):
    raw = exam.get('startDate') or exam.get('createdDate')
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace('Z', ''))
    except ValueError:
        return None


def _parse_complete_date(record):
    raw = record.get('completeDate')
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace('Z', ''))
    except ValueError:
        return None


def _fetch_user_result_exams(base_url, secret_key, user_code, stdout, style):
    """Lay TOAN BO lich su thi (moi chuyen de, khong chi loai thu viec) cua 1 userCode qua
    endpoint phan trang /user/result-exams - day la nguon co NGAY-GIO THI THAT (completeDate),
    khac voi /exam/get-learner-result chi co ngay mo ky thi (exam.startDate, thuong la mung 1).
    Tra ve list cac ban ghi {completeDate, thematicName, examName, point}."""
    page_size = 100
    page_number = 1
    records = []
    while True:
        payload = _get_json(
            base_url, '/user/result-exams',
            {'secretKey': secret_key, 'Code': user_code, 'PageNumber': page_number, 'PageSize': page_size},
            stdout, style,
        )
        page_lists = ((payload or {}).get('data') or {}).get('pageLists') or []
        if not page_lists:
            break
        records.extend(page_lists)
        if len(page_lists) < page_size:
            break
        page_number += 1
    return records


def sync_courses(tenant, base_url, secret_key, stdout, style):
    employees_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    course_list = _get_json(base_url, '/course/get-list', {'secretKey': secret_key, 'pageSize': 2000}, stdout, style)
    courses = [
        c for c in _as_list(course_list)
        if str(c.get('code') or '').strip().upper().startswith(('HOINHAP_', 'LEVEL_'))
    ]

    created = updated = skipped_no_employee = skipped_incomplete = 0
    affected_employee_ids = set()

    for course in courses:
        course_id = course.get('id')
        course_code = str(course.get('code') or '').strip().upper()
        course_name = course.get('name') or course_code
        is_onboarding = course_code.startswith('HOINHAP_')

        result = _get_json(
            base_url, '/course/get-student-result',
            {'secretKey': secret_key, 'id': course_id, 'pageSize': 2000}, stdout, style,
        )
        for row in _as_list(result):
            code = str(row.get('userCode') or row.get('username') or '').strip()
            if not code:
                continue

            progress = row.get('progress') or 0
            is_passed = bool(row.get('isPassed'))
            result_text = str(row.get('result') or '').lower()

            if is_onboarding and progress < 100 and not is_passed and 'đạt' not in result_text:
                skipped_incomplete += 1
                continue

            employee = employees_by_code.get(code)
            if not employee:
                skipped_no_employee += 1
                continue

            status_text = 'Đạt' if (is_passed or 'đạt' in result_text) else 'Chưa đạt'
            _, was_created = CourseResult.objects.update_or_create(
                tenant=tenant, employee=employee, course_name=course_name,
                defaults={
                    'score': row.get('point') or 0,
                    'status': status_text,
                    'progress': progress,
                    'cls_id': str(course_id),
                },
            )
            created += int(was_created)
            updated += int(not was_created)
            affected_employee_ids.add(employee.id)

    return {
        'scanned': len(courses),
        'created': created,
        'updated': updated,
        'skipped_no_employee': skipped_no_employee,
        'skipped_incomplete': skipped_incomplete,
        'affected_employee_ids': affected_employee_ids,
    }


def sync_exams(tenant, base_url, secret_key, start_date, probation_types, stdout, style):
    """Ngay thi/ten chuyen de/diem lay tu /user/result-exams (co NGAY-GIO THI THAT qua
    completeDate) - port ban sua vi /exam/get-learner-result chi tra ngay MO ky thi
    (exam.startDate, thuong la mung 1 thang, khong phai ngay hoc vien thuc su thi).

    Buoc 1 (roster): van dung /exam/get-list + /exam/get-learner-result nhu truoc, nhung CHI
    de xac dinh danh sach userCode nao co lien quan toi thi thu viec (xuat hien trong topic co
    tien to khop probation_types) - KHONG con lay diem/ngay/ten tu day.

    Buoc 2: voi tung userCode trong roster, goi /user/result-exams (phan trang) lay TOAN BO
    lich su thi cua nguoi do, loc lai theo candidate_type (tien to trong thematicName) + bo
    qua lan point=0 (thi sinh chua kip thi ma API da tra ve)."""
    employees_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    exam_list = _get_json(base_url, '/exam/get-list', {'secretKey': secret_key, 'pageSize': 500}, stdout, style)
    exams = _as_list(exam_list)
    exams = [e for e in exams if (_parse_exam_date(e) or start_date) >= start_date]

    roster_codes = set()
    for exam in exams:
        result = _get_json(
            base_url, '/exam/get-learner-result',
            {'secretKey': secret_key, 'id': exam.get('id'), 'pageSize': 1000}, stdout, style,
        )
        for topic in _as_list(result):
            match = TOPIC_PREFIX_RE.match(str(topic.get('name') or ''))
            candidate_type = match.group(1).upper() if match else None
            if not candidate_type or candidate_type not in probation_types:
                continue
            for user in topic.get('users') or []:
                code = str(user.get('userCode') or user.get('code') or '').strip()
                if code:
                    roster_codes.add(code)

    # raw[(employee_code, candidate_type)] = danh sach lan thi (chua sap xep - sap theo
    # completeDate that su truoc khi tach lan 1/2)
    raw = defaultdict(list)

    for code in roster_codes:
        for record in _fetch_user_result_exams(base_url, secret_key, code, stdout, style):
            point = record.get('point')
            if not point:
                continue  # bo lan point=0/None - thi sinh chua kip thi ma API da goi ve
            thematic_name = str(record.get('thematicName') or '')
            match = TOPIC_PREFIX_RE.match(thematic_name)
            candidate_type = match.group(1).upper() if match else None
            if not candidate_type or candidate_type not in probation_types:
                continue
            complete_date = _parse_complete_date(record)
            raw[(code, candidate_type)].append({
                'score': point,
                'exam_full_name': thematic_name,
                'exam_date': complete_date.date() if complete_date else None,
                'sort_key': complete_date or datetime.min,
            })

    created = updated = skipped_no_employee = 0
    affected_employee_ids = set()

    for (code, candidate_type), entries in raw.items():
        employee = employees_by_code.get(code)
        if not employee:
            skipped_no_employee += 1
            continue

        entries.sort(key=lambda r: r['sort_key'])
        # lan 1: giu nguyen nhu lan dau tien gap; lan 2-3: chi giu diem CAO NHAT trong 2 lan do
        slots = [(1, entries[0])]
        retries = entries[1:3]
        if retries:
            best = max(retries, key=lambda r: (r['score'] is not None, r['score'] or 0))
            slots.append((2, best))

        for attempt, entry in slots:
            # 'defaults' KHONG duoc them 'score_adjusted' - update_or_create chi ghi de cac
            # truong co trong defaults, nen diem phuc khao (admin sua tay) khong bao gio bi
            # dong bo CLS ghi de, du chay sync_cls bao nhieu lan sau do.
            _, was_created = ExamResult.objects.update_or_create(
                tenant=tenant, employee=employee, exam_name=candidate_type, attempt=attempt,
                defaults={
                    'score': entry['score'],
                    # /user/result-exams khong tra co isPassed - suy tu diem so voi nguong
                    # thi thu viec chuan (COMMISSION_EXAM_THRESHOLD); truong nay chi de hien
                    # thi/tuong thich nguoc, logic pass thuc te dung final_score (xem
                    # employees/services.py::exam_pass), khong doc truong nay.
                    'passed': entry['score'] >= settings.COMMISSION_EXAM_THRESHOLD,
                    'exam_full_name': entry['exam_full_name'],
                    'exam_date': entry['exam_date'],
                },
            )
            created += int(was_created)
            updated += int(not was_created)
            affected_employee_ids.add(employee.id)

    return {
        'scanned': len(roster_codes),
        'affected_employee_ids': affected_employee_ids,
        'created': created,
        'updated': updated,
        'skipped_no_employee': skipped_no_employee,
    }


class Command(BaseCommand):
    help = 'Dong bo Ket qua hoc / Ket qua thi tu API CLS vao CourseResult / ExamResult theo tenant'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        secret_key = settings.CLS_SECRET_KEY
        if not secret_key:
            raise CommandError('CLS_SECRET_KEY chua duoc cau hinh trong .env')

        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        base_url = settings.CLS_API_BASE
        start_date = datetime.strptime(settings.CLS_EXAM_START_DATE, '%Y-%m-%d')

        self.stdout.write('Dong bo Ket qua hoc (CourseResult)...')
        courses = sync_courses(tenant, base_url, secret_key, self.stdout, self.style)
        self.stdout.write(self.style.SUCCESS(
            'Khoa hoc: quet {scanned}, tao moi {created}, cap nhat {updated}, '
            'bo qua (khong khop nhan su) {skipped_no_employee}, '
            'bo qua (hoi nhap chua hoan thanh) {skipped_incomplete}'.format(**courses)
        ))

        self.stdout.write('Dong bo Ket qua thi (ExamResult)...')
        exams = sync_exams(
            tenant, base_url, secret_key, start_date, settings.CLS_PROBATION_EXAM_TYPES,
            self.stdout, self.style,
        )
        self.stdout.write(self.style.SUCCESS(
            'Ky thi: quet {scanned}, tao moi {created}, cap nhat {updated}, '
            'bo qua (khong khop nhan su) {skipped_no_employee}'.format(**exams)
        ))

        # Diem thi/khoa hoc vua dong bo co the lam thay doi dieu kien Pass thu viec - tinh lai
        # ngay cho tung nhan su bi anh huong (khong tinh lai ca tenant de tranh du thua).
        from employees.models import Employee
        from employees.services import recompute_final_result

        affected_ids = courses['affected_employee_ids'] | exams['affected_employee_ids']
        for employee in Employee.objects.filter(tenant=tenant, id__in=affected_ids):
            recompute_final_result(employee)
        self.stdout.write(self.style.SUCCESS(
            f'Da tinh lai ket qua thu viec cho {len(affected_ids)} nhan su bi anh huong.'
        ))

        eligible = sum(
            1 for emp in Employee.objects.filter(tenant=tenant) if onboarding_eligible(emp)
        )
        self.stdout.write(
            f'Nhan su du dieu kien thi (Hoi nhap >= {settings.CLS_ONBOARDING_PASS_SCORE}): {eligible}'
        )
