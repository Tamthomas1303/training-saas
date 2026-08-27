"""
scan_probation_exam_candidates — Nhom 3B luong 4 (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 2),
buoc 2 "1 management command quet hang ngay": luoi an toan cho check_probation_exam_eligibility,
phong khi 2 hook truc tiep (hoan thanh khoa / luu checklist 100%) bo lot 1 nhan su nao do (vd
diem du dieu kien tu truoc nhung hook chua tung chay lai sau khi bat cong tac). Chay TOAN BO
tenant (khong tham so --tenant nhu recompute_probation - day la job nen chay dinh ky qua cron/
scheduler, khong phai lenh thao tac tay 1 tenant).
"""
from django.core.management.base import BaseCommand

from employees.automation import check_probation_exam_eligibility
from employees.models import Employee


class Command(BaseCommand):
    help = 'Quet nhan su dang thu viec du dieu kien vao hang doi "Cho duyet thi" (luoi an toan hang ngay).'

    def handle(self, *args, **options):
        qs = (
            Employee.objects.filter(is_legacy=False, employee_status=Employee.EmployeeStatus.PROBATION)
            .select_related('tenant', 'restaurant')
        )
        total = created = errors = 0
        for employee in qs.iterator(chunk_size=200):
            total += 1
            try:
                candidate = check_probation_exam_eligibility(employee)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                self.stderr.write(f'Loi khi kiem tra NV {employee.code} (id={employee.id}): {exc}')
                continue
            if candidate:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Da quet {total} nhan su dang thu viec - {created} them vao hang doi "Cho duyet thi", {errors} loi.'
        ))
