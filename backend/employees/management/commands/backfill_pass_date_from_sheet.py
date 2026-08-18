"""
backfill_pass_date_from_sheet — sua pass_date SAI do loi parser cu trong import_july_data.py
(Prompt_Fix_PassDate_DungLoTrinh.md).

CHAN DOAN (da xac minh qua diagnose_dung_lo_trinh / kiem tra truc tiep du lieu that): pass_date
KHONG rong (khong phai truong hop A theo nghia den) - 19/20 nhan su cohort thang 7/2026 DA co
final_result='Pass thu viec' VA pass_date. Nhung khi doi chieu voi Google Sheet 'app_employees'
(nguon "chot" ma import_july_data.py doc) thi pass_date trong DB KHONG khop gia tri that tren
Sheet. Nguyen nhan goc: import_july_data.py::_parse_sheet_date TRUOC DAY khong doc duoc dinh
dang JS Date.toString() cua cot Pass_Date tren Sheet (vd 'Wed Jul 29 2026 14:01:38 GMT+0700
(Indochina Time)') -> tra ve None -> dong ghi pass_date bi BO QUA AM THAM luc import (khong
loi, khong canh bao). pass_date hien co trong DB la san pham cua 1 lan recompute_final_result
KHAC chay SAU do (vd sync_cls dinh ky, hoac 1 su kien checklist/danh gia) dong dau ngay HOM DO
(xem employees/services.py::recompute_final_result), KHONG phai gia tri "chot" tu Sheet.

Da sua parser (import_july_data.py::_parse_sheet_date, ho tro them dinh dang JS Date.toString())
- lenh nay doc LAI Sheet bang parser DA SUA va cap nhat pass_date cho nhan su dang 'Pass thu
viec' co gia tri Sheet KHAC voi DB hien tai (bao gom ca truong hop DB dang rong). Idempotent -
chay lai sau khi da khop se khong doi gi.

--dry-run: chi in bang chan doan (KHONG ghi).
--month/--year: thang chan doan de in bang (mac dinh 7/2026 - ky bi bao cao).
"""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from config.csv_source import load_csv_rows, pick
from employees.models import Employee

from .import_july_data import _parse_sheet_date

PASS_RESULT = 'Pass thử việc'


def diagnose_cohort(tenant, month, year):
    """Buoc 1 chan doan (Prompt_Fix_PassDate_DungLoTrinh.md) - dung DUNG cohort nhu
    kpi.services._bql_cohort_stats (Khoi Nha hang, loai nghi viec + cap P, han danh gia roi
    trong thang). CHI DOC, khong ghi gi."""
    from kpi.services import _is_parttime_p, _kpi_tier_days

    cohort = []
    for e in Employee.objects.filter(tenant=tenant, is_legacy=False).select_related('restaurant'):
        if not e.start_date or e.operation_unit != Employee.OperationUnit.RESTAURANT:
            continue
        tier = _kpi_tier_days(e.position)
        deadline = e.start_date + datetime.timedelta(days=tier)
        if not (deadline.month == month and deadline.year == year):
            continue
        if e.employee_status == Employee.EmployeeStatus.RESIGNED or _is_parttime_p(e):
            continue
        cohort.append((e, tier))

    is_pass = [(e, tier) for e, tier in cohort if e.final_result == PASS_RESULT]
    with_date = [(e, tier) for e, tier in is_pass if e.pass_date]
    without_date = [(e, tier) for e, tier in is_pass if not e.pass_date]
    on_time = [(e, tier) for e, tier in with_date if (e.pass_date - e.start_date).days <= tier]

    return {
        'month': month, 'year': year,
        'cohort_total': len(cohort), 'pass_count': len(is_pass),
        'with_pass_date': len(with_date), 'without_pass_date': len(without_date),
        'on_time': len(on_time),
        'on_time_rate': round(len(on_time) / len(with_date) * 100, 1) if with_date else None,
    }


def _print_diagnosis(stdout, label, diag):
    stdout.write(f"--- {label}: tháng {diag['month']}/{diag['year']} ---")
    stdout.write(f"  Tổng cohort (Khối Nhà hàng, đã loại nghỉ việc/cấp P): {diag['cohort_total']}")
    stdout.write(f"  final_result = 'Pass thử việc': {diag['pass_count']}")
    stdout.write(f"    - trong đó CÓ pass_date: {diag['with_pass_date']}")
    stdout.write(f"    - trong đó RỖNG pass_date: {diag['without_pass_date']}")
    stdout.write(f"    - trong nhóm CÓ pass_date, ĐÚNG HẠN (<= số ngày theo cấp): {diag['on_time']}")
    rate = f"{diag['on_time_rate']}%" if diag['on_time_rate'] is not None else '—'
    stdout.write(f"    => % đúng lộ trình (trong nhóm có pass_date): {rate}")


def compute_pass_date_updates(tenant, sheet_rows):
    """{'to_update': [(employee, sheet_pass_date)], 'no_sheet_row': int, 'no_sheet_date': int,
    'already_match': int} - nhan su final_result='Pass thu viec' co gia tri Pass_Date tren Sheet
    (da parse) KHAC pass_date hien tai trong DB. CHI DOC, khong ghi gi."""
    by_id = {pick(r, 'Employee_ID'): r for r in sheet_rows}
    to_update, no_sheet_row, no_sheet_date, already_match = [], 0, 0, 0

    for e in Employee.objects.filter(tenant=tenant, final_result=PASS_RESULT).order_by('code'):
        row = by_id.get(e.code)
        if not row:
            no_sheet_row += 1
            continue
        sheet_pass_date = _parse_sheet_date(pick(row, 'Pass_Date'))
        if not sheet_pass_date:
            no_sheet_date += 1
            continue
        if e.pass_date == sheet_pass_date:
            already_match += 1
            continue
        to_update.append((e, sheet_pass_date))

    return {
        'to_update': to_update, 'no_sheet_row': no_sheet_row,
        'no_sheet_date': no_sheet_date, 'already_match': already_match,
    }


class Command(BaseCommand):
    help = (
        "Sua pass_date sai do loi parser cu (khong doc duoc dinh dang JS Date cua cot "
        "Pass_Date tren Sheet app_employees) - doc lai tu Sheet, chi cap nhat nhan su dang "
        "'Pass thu viec' co gia tri khac DB. In bang chan doan truoc/sau."
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de link CSV app_employees')
        parser.add_argument('--month', type=int, default=7, help='Thang de in bang chan doan (mac dinh 7)')
        parser.add_argument('--year', type=int, default=2026, help='Nam de in bang chan doan (mac dinh 2026)')
        parser.add_argument('--dry-run', action='store_true', help='Chi in bang chan doan, khong ghi')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")

        csv_url = options['csv_url'] or settings.APP_EMPLOYEES_CSV_URL
        if not csv_url:
            raise CommandError('Chưa có link CSV app_employees (APP_EMPLOYEES_CSV_URL).')

        try:
            rows = load_csv_rows(csv_url)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f'Không đọc được nguồn dữ liệu: {exc}') from exc

        month, year = options['month'], options['year']
        _print_diagnosis(self.stdout, 'TRƯỚC backfill', diagnose_cohort(tenant, month, year))

        plan = compute_pass_date_updates(tenant, rows)
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE(f"{'Mã NV':<12}{'DB pass_date (trước)':<24}{'Sheet Pass_Date':<16}"))
        for e, sheet_pass_date in plan['to_update']:
            self.stdout.write(f"{e.code:<12}{str(e.pass_date or '—'):<24}{str(sheet_pass_date):<16}")
        self.stdout.write(
            f"\nNhân sự 'Pass thử việc' không có dòng trong Sheet: {plan['no_sheet_row']} | "
            f"Sheet không có Pass_Date hợp lệ: {plan['no_sheet_date']} | "
            f"Đã khớp sẵn: {plan['already_match']} | Sẽ cập nhật: {len(plan['to_update'])}"
        )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDRY-RUN — chưa ghi gì. Chạy lại không có --dry-run để áp dụng.'))
            return

        for e, sheet_pass_date in plan['to_update']:
            e.pass_date = sheet_pass_date
            e.save(update_fields=['pass_date'])

        self.stdout.write(self.style.SUCCESS(f"\nĐã cập nhật pass_date cho {len(plan['to_update'])} nhân sự."))
        self.stdout.write('')
        _print_diagnosis(self.stdout, 'SAU backfill', diagnose_cohort(tenant, month, year))
