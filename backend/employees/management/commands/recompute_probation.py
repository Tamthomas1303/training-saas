"""
recompute_probation — tính lại kết quả thử việc (final_result) cho toàn bộ nhân sự theo điều
kiện pass mới (LMS + đào tạo tại điểm 100% + thi đạt + đánh giá thực hành đạt). Dùng để sửa dữ
liệu đã import từ hệ cũ (cột final_result cũ có thể ghi 'Pass' dù chưa đủ điều kiện).
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from employees.models import Employee
from employees.services import recompute_final_result


class Command(BaseCommand):
    help = 'Tinh lai final_result cho tat ca nhan su theo dieu kien pass moi'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        changed = total = 0
        for e in Employee.objects.filter(tenant=tenant):
            before = e.final_result
            after = recompute_final_result(e)
            total += 1
            if before != after:
                changed += 1

        self.stdout.write(self.style.SUCCESS(
            f'Da tinh lai final_result cho {total} nhan su ({changed} thay doi).'
        ))
