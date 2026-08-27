"""
remind_managers_probation — Nhom 3C (Prompt_Nhom3C_NhacViec_TrongApp.md muc 3): quet nhan su
dang thu viec (is_legacy=False, co nha hang) va nhac QLNH/Bep truong qua thong bao trong app +
email (sourcing.services.notify_users, xem employees.automation.check_probation_reminders) khi
(a) con noi dung chua dao tao qua nguong ngay, hoac (b) sap den han thi/danh gia thu viec.

Chi xu ly tenant co AutomationSettings.remind_managers bat. Chay hang ngay qua co che lich hien
co (giong bao cao dao tao tuan/thang - cron/GitHub Actions goi management command nay).
"""
from django.core.management.base import BaseCommand

from accounts.models import Tenant
from employees.automation import check_probation_reminders, get_automation_settings
from employees.models import Employee


class Command(BaseCommand):
    help = 'Nhac QLNH/Bep truong ve nhan su dang thu viec con noi dung chua dao tao / sap den han (Nhom 3C).'

    def handle(self, *args, **options):
        total_checked = total_reminded = errors = 0
        for tenant in Tenant.objects.all():
            cfg = get_automation_settings(tenant)
            if not cfg.remind_managers:
                continue
            qs = (
                Employee.objects.filter(
                    tenant=tenant, is_legacy=False, employee_status=Employee.EmployeeStatus.PROBATION,
                    restaurant__isnull=False,
                )
                .select_related('tenant', 'restaurant')
            )
            for employee in qs.iterator(chunk_size=200):
                total_checked += 1
                try:
                    sent = check_probation_reminders(employee, cfg=cfg)
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    self.stderr.write(f'Loi khi nhac NV {employee.code} (id={employee.id}): {exc}')
                    continue
                total_reminded += len(sent)

        self.stdout.write(self.style.SUCCESS(
            f'Da quet {total_checked} nhan su dang thu viec - gui {total_reminded} luot nhac, {errors} loi.'
        ))
