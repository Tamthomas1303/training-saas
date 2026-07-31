"""
alert_no_training — canh bao nhan su vao lam 5-30 ngay ma tien do dao tao (checklist) van con
0%. Tao Notification in-app + gui email cho Trainer/BQL cua nha hang do (dung chung
notify_users, xem sourcing/services.py - Notification model cung dung chung, khong tao model
rieng vi da co san).

Dedup 1 lan/nhan su: kiem tra da co Notification category='no_training' voi link tro toi nhan
su do chua truoc khi tao moi - khong dung bang log rieng vi Notification.link (duong dan toi
trang chi tiet nhan su) da du de lam khoa dedup, dong thoi van la link "bam de xem" that su
tren chuong thong bao.

Lich chay: xem README.md muc "Cron job" (GitHub Actions .github/workflows/alert_no_training.yml,
theo dung mau sync_cls.yml da co san trong repo).
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Tenant, User
from employees.models import Employee
from employees.services import checklist_progress_percent

NO_TRAINING_CATEGORY = 'no_training'
MIN_DAYS_SINCE_START = 5
MAX_DAYS_SINCE_START = 30


class Command(BaseCommand):
    help = 'Canh bao nhan su vao lam 5-30 ngay ma tien do dao tao van 0% (in-app + email Trainer/BQL)'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        from sourcing.models import Notification
        from sourcing.services import notify_users

        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        today = timezone.now().date()
        candidates = (
            Employee.objects.filter(
                tenant=tenant, is_legacy=False, start_date__isnull=False, restaurant__isnull=False,
            )
            .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
            .select_related('restaurant')
        )

        alerted = skipped_days = skipped_progress = skipped_dup = skipped_no_recipient = 0

        for employee in candidates:
            days_since_start = (today - employee.start_date).days
            if not (MIN_DAYS_SINCE_START <= days_since_start <= MAX_DAYS_SINCE_START):
                skipped_days += 1
                continue
            if checklist_progress_percent(employee) != 0:
                skipped_progress += 1
                continue

            link = f'/employees/{employee.id}'
            if Notification.objects.filter(tenant=tenant, category=NO_TRAINING_CATEGORY, link=link).exists():
                skipped_dup += 1
                continue

            recipients = list(User.objects.filter(
                tenant=tenant, restaurant=employee.restaurant, role__in=['bql', 'trainer'],
                status=User.Status.ACTIVE,
            ))
            if not recipients:
                skipped_no_recipient += 1
                continue

            notify_users(
                recipients,
                title=f'Chưa đào tạo: {employee.name} ({employee.code})',
                body=(
                    f'{employee.name} ({employee.code}) vào làm được {days_since_start} ngày tại '
                    f'{employee.restaurant.name} nhưng tiến độ đào tạo vẫn 0%. Vui lòng kiểm tra '
                    'và triển khai đào tạo sớm.'
                ),
                link=link, category=NO_TRAINING_CATEGORY,
            )
            alerted += 1

        self.stdout.write(self.style.SUCCESS(
            f'Da canh bao {alerted} nhan su. Bo qua: {skipped_days} ngoai khoang 5-30 ngay, '
            f'{skipped_progress} da co tien do, {skipped_dup} da canh bao truoc do, '
            f'{skipped_no_recipient} khong co Trainer/BQL de gui.'
        ))
