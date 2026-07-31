"""
clear_backfilled_pass_date — don du lieu pass_date bi ghi SAI boi loi cu trong
recompute_final_result: truoc day ham nay set pass_date = hom nay MOI LAN duoc goi cho nhan
su dang Pass thu viec ma pass_date dang trong, thay vi CHI ghi khi final_result THAT SU
CHUYEN sang Pass (da sua trong employees/services.py::recompute_final_result). Vi vay nhieu
nhan su da Pass tu lau co the dang mang pass_date la ngay GAN DAY nhat ma recompute duoc goi
(vd lan sync_cls/checklist/evaluation gan nhat), KHONG phai ngay Pass that su - sai lech nay
anh huong truc tiep den viec tinh luong (pass_date dung de tinh luong).

Chay 1 LAN sau khi da trien khai ban sua: xoa (set None) pass_date cho TOAN BO nhan su dang
Pass thu viec, vi khong the biet duoc ngay Pass that su tu du lieu hien co (chi biet la SAI,
khong the phuc hoi dung). Sau lenh nay, pass_date se duoc ghi lai DUNG tu lan chuyen trang
thai Pass KE TIEP (vd neu nhan su roi Pass roi Pass lai) - nhung da Pass tu truoc va o nguyen
trang thai Pass thi pass_date se o trong vinh vien tru khi HR nhap tay lai (chap nhan duoc,
tot hon la giu 1 ngay SAI).

An toan chay lai nhieu lan: lan sau se khong tim thay ban ghi nao con pass_date can xoa (da
None tu lan truoc), khong lam gi them.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from employees.models import Employee


class Command(BaseCommand):
    help = (
        'Xoa (set None) pass_date bi backfill sai cho nhan su dang Pass thu viec - '
        'chay 1 lan sau khi da sua loi recompute_final_result'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        updated = Employee.objects.filter(
            tenant=tenant, final_result='Pass thử việc', pass_date__isnull=False,
        ).update(pass_date=None)

        self.stdout.write(self.style.SUCCESS(
            f'Da xoa pass_date bi backfill sai cho {updated} nhan su dang Pass thu viec.'
        ))
