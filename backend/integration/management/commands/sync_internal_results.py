"""
Chay lai dong bo ho so (Dot 3 phan A) cho TOAN BO Enrollment da completed / Attempt da graded &
passed cua 1 tenant - dung de backfill (vd sau khi admin moi gan sync_course_code/sync_exam_type
cho 1 khoa/de da co nguoi hoan thanh tu truoc). IDEMPOTENT - chay lai nhieu lan an toan (xem
integration.services.sync_result_to_profile: khong bao gio ghi de dong nguon CLS, update_or_create
khong tao trung).
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from courses.models import Enrollment
from exams.models import Attempt
from integration.services import sync_result_to_profile


class Command(BaseCommand):
    help = 'Chay lai dong bo CourseResult/ExamResult tu module Khoa hoc/Ky thi noi bo (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")

        synced_courses = skipped_courses = 0
        for enrollment in Enrollment.objects.filter(tenant=tenant, status=Enrollment.Status.COMPLETED):
            result = sync_result_to_profile(enrollment)
            if result is None:
                skipped_courses += 1
            else:
                synced_courses += 1

        synced_exams = skipped_exams = 0
        for attempt in Attempt.objects.filter(tenant=tenant, status=Attempt.Status.GRADED, passed=True):
            result = sync_result_to_profile(attempt)
            if result is None:
                skipped_exams += 1
            else:
                synced_exams += 1

        self.stdout.write(self.style.SUCCESS(
            f'Khóa học: đồng bộ {synced_courses}, bỏ qua (chưa gán sync_course_code) {skipped_courses}. '
            f'Bài thi: đồng bộ {synced_exams}, bỏ qua (chưa gán sync_exam_type) {skipped_exams}.'
        ))
