"""
send_training_report — gui bao cao dao tao tuan/thang qua email (SMTP), chay tu GitHub Actions
(xem .github/workflows/send_training_report.yml), KHONG goi tu web nua.

Ly do: Render (goi free) chan cong SMTP ra ngoai - socket.connect toi smtp.gmail.com:587 treo
mai khong bao gio tra ve, khien worker Render bi timeout/kill khi nut "Gui email" tren web goi
truc tiep send_report_email(). Chuyen viec GUI sang chay tu GitHub Actions runner (khong bi
chan SMTP), giong cach alert_no_training.py da lam cho canh bao chua dao tao. Trang web chi
con "Xem truoc" (khong goi SMTP, an toan).

Dung lai nguyen ham build+gui bao cao da co (reports/services.py::send_report_email) -
khong tinh toan lai logic gui, chi la lop CLI goi vao ham do.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from reports.services import send_report_email


class Command(BaseCommand):
    help = (
        'Gui bao cao dao tao tuan/thang qua email (SMTP) - chay tu GitHub Actions, '
        'KHONG goi tu web (Render chan cong SMTP ra ngoai)'
    )

    def add_arguments(self, parser):
        parser.add_argument('--kind', choices=['week', 'month'], default='week')
        parser.add_argument('--date', default=None, help='YYYY-MM-DD, mac dinh hom nay')
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        date_str = options['date']
        if date_str:
            try:
                ref_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                raise CommandError('date khong hop le (dinh dang YYYY-MM-DD).')
        else:
            ref_date = datetime.date.today()

        try:
            result = send_report_email(tenant, options['kind'], ref_date)
        except ValueError as exc:
            raise CommandError(str(exc))
        except Exception as exc:
            raise CommandError(f'Gui bao cao that bai: {exc}')

        cc_note = f" (CC: {', '.join(result['cc'])})" if result['cc'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"Da gui bao cao '{result['subject']}' toi: {', '.join(result['to'])}{cc_note}"
        ))
