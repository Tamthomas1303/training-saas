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


def sync_courses(tenant, base_url, secret_key, stdout, style):
    employees_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    course_list = _get_json(base_url, '/course/get-list', {'secretKey': secret_key, 'pageSize': 2000}, stdout, style)
    courses = [
        c for c in _as_list(course_list)
        if str(c.get('code') or '').strip().upper().startswith(('HOINHAP_', 'LEVEL_'))
    ]

    created = updated = skipped_no_employee = skipped_incomplete = 0

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
                    'cls_id': str(course_id),
                },
            )
            created += int(was_created)
            updated += int(not was_created)

    return {
        'scanned': len(courses),
        'created': created,
        'updated': updated,
        'skipped_no_employee': skipped_no_employee,
        'skipped_incomplete': skipped_incomplete,
    }


def sync_exams(tenant, base_url, secret_key, start_date, probation_types, stdout, style):
    employees_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    exam_list = _get_json(base_url, '/exam/get-list', {'secretKey': secret_key, 'pageSize': 500}, stdout, style)
    exams = _as_list(exam_list)
    exams = [e for e in exams if (_parse_exam_date(e) or start_date) >= start_date]
    exams.sort(key=lambda e: _parse_exam_date(e) or start_date)

    # raw[(employee_code, candidate_type)] = danh sach lan thi theo dung thu tu thoi gian
    raw = defaultdict(list)

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
                if not code:
                    continue
                raw[(code, candidate_type)].append({
                    'score': user.get('point'),
                    'passed': bool(user.get('isPassed')),
                    'topic_id': topic.get('id'),
                })

    created = updated = skipped_no_employee = 0

    for (code, candidate_type), entries in raw.items():
        employee = employees_by_code.get(code)
        if not employee:
            skipped_no_employee += 1
            continue

        # lan 1: giu nguyen nhu lan dau tien gap; lan 2-3: chi giu diem CAO NHAT trong 2 lan do
        slots = [(1, entries[0])]
        retries = entries[1:3]
        if retries:
            best = max(retries, key=lambda r: (r['score'] is not None, r['score'] or 0))
            slots.append((2, best))

        for attempt, entry in slots:
            _, was_created = ExamResult.objects.update_or_create(
                tenant=tenant, employee=employee, exam_name=candidate_type, attempt=attempt,
                defaults={
                    'score': entry['score'],
                    'passed': entry['passed'],
                    'cls_id': str(entry['topic_id']) if entry['topic_id'] is not None else '',
                },
            )
            created += int(was_created)
            updated += int(not was_created)

    return {
        'scanned': len(exams),
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

        eligible = sum(
            1 for emp in Employee.objects.filter(tenant=tenant) if onboarding_eligible(emp)
        )
        self.stdout.write(
            f'Nhan su du dieu kien thi (Hoi nhap >= {settings.CLS_ONBOARDING_PASS_SCORE}): {eligible}'
        )
