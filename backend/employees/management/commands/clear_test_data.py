"""
clear_test_data - don TOAN BO du lieu test (minh chung dao tao/bien ban/danh gia/phieu ket qua
thu viec) truoc khi nhap du lieu that. GIU NGUYEN: tai khoan (User), nhan su (Employee - chi
RESET vai truong, khong xoa dong), nha hang, va du lieu CLS that (cls_sync.ExamResult/
CourseResult). Port Phan 2 - Prompt_v2.1_PhuCap_DonTest_03.08.2026.md.

Cac model/field duoc XOA:
  - checklist.TrainingProgress (xoa toan bo dong): anh minh chung (img_tailieu/img_lythuyet/
    img_thuchanh), chu ky (sign_trainer/sign_trainee), bien ban dao tao PDF (pdf_url - sinh o
    checklist/pdf.py::build_training_record_pdf).
  - evaluation.Evaluation + evaluation.EvaluationDetail (xoa toan bo dong, EvaluationDetail
    cascade theo Evaluation trong DB nhung file cua EvaluationDetail.photo_url duoc xoa TRUOC
    khi xoa dong vi cascade DB khong tu goi delete_by_url). Chu ky (sign_evaluator/
    sign_trainee), PDF (pdf_url), anh minh chung tung tieu chi (photo_url).
    evaluation.EvaluationCriteria la CAU HINH (bo tieu chi dung chung, giong Checklist/
    Document) - KHONG xoa.
  - evaluation.Council + evaluation.CouncilMember (xoa toan bo dong): gan voi Evaluation qua FK
    SET_NULL nen khong tu mat khi xoa Evaluation - suy luan la du lieu test cung nhom (khong
    phai "cau hinh" nhu EvaluationCriteria) nen xoa cung, khong duoc prompt neu ten rieng.
  - employees.Employee (KHONG xoa dong - CHI RESET field, CHI cho nhan su is_legacy=False):
    probation_result_pdf_url (+ xoa file R2 - la "phieu ket qua thu viec" PDF sinh o
    employees/pdf.py::build_probation_result_pdf), pass_date, final_result, commission_status,
    retrain_deadline -> ve rong/None de nhap lai tu dau. Code hien tai khong co model AuditLog
    rieng nen "dau vet export" chinh la field probation_result_pdf_url nay.
    QUAN TRONG: chi ap dung cho is_legacy=False (nhan su onboarding he moi tu 1/7, tinh nang
    dang test). Nhan su is_legacy=True nap tu Data_LichSu la LO TRINH THAT trong qua khu, DA
    duoc anh Chung xac nhan KHONG dua vao pham vi reset - xem doi thoai xac nhan 03/08/2026.

Model TIM THAY nhung KHONG nam trong pham vi prompt neu ro - CHI liet ke o --dry-run (va moi
lan chay) de doi chieu, KHONG dong den (tranh xoa nham theo yeu cau "DUNG hoi toi, dung doan"):
  - kpi.KpiSession/KpiParticipant: cung la "anh minh chung + bien ban" nhung sinh boi
    kpi/pdf.py (khac checklist/pdf.py ma prompt neu ten) - tinh nang "buoi KPI/coaching" rieng
    voi checklist onboarding.
  - employees.LevelUpEnrollment (proposal_pdf_url): phieu de xuat len level - tinh nang "dao
    tao thang tien" rieng, khong phai checklist onboarding/danh gia ky nang ban dau.
  - employees.TalentReview, employees.MgmtDevelopment: du lieu nap tu Google Sheet (lo trinh/
    Daotao_BQL...), khong ro la du lieu "test" hay du lieu that da nhap - khong doan.
  - cls_sync.CourseResult: cung nhom "du lieu that keo tu CLS" nhu ExamResult (prompt chi neu
    dich danh ExamResult) - suy luan GIU NGUYEN, khong xoa.

An toan: mac dinh KHONG xoa gi (dry-run), chi in so luong. Phai truyen --confirm moi thuc su
xoa. --tenant loc theo tenant (mac dinh 'Demo Tenant' - giong quy uoc cac command khac trong
repo).
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from checklist.models import TrainingProgress
from checklist.storage import delete_by_url
from employees.models import Employee, LevelUpEnrollment, MgmtDevelopment, TalentReview
from evaluation.models import Council, CouncilMember, Evaluation, EvaluationDetail


class Command(BaseCommand):
    help = (
        'Don toan bo du lieu test (minh chung/bien ban/danh gia/phieu KQ thu viec) truoc khi '
        'nhap du lieu that. Mac dinh dry-run, phai them --confirm moi thuc su xoa.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--dry-run', action='store_true', help='Chi in so luong se xoa, khong xoa gi (mac dinh)')
        parser.add_argument('--confirm', action='store_true', help='Thuc su xoa ban ghi + file R2')

    def handle(self, *args, **options):
        if options['dry_run'] and options['confirm']:
            raise CommandError('Chi dung 1 trong 2 co --dry-run hoac --confirm, khong dung ca hai.')

        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        dry_run = not options['confirm']

        self.stdout.write(self.style.WARNING(
            f"{'[DRY-RUN - chua xoa gi] ' if dry_run else '[CONFIRM - XOA THAT] '}"
            f"Tenant: {tenant.name} (id={tenant.id})"
        ))
        self.stdout.write('')

        results = {
            'TrainingProgress (minh chung + bien ban dao tao)': self._process_training_progress(tenant, dry_run),
            'Evaluation + EvaluationDetail (danh gia ky nang)': self._process_evaluation(tenant, dry_run),
            'Council + CouncilMember (hoi dong danh gia)': self._process_council(tenant, dry_run),
            'Employee (reset phieu ket qua thu viec)': self._process_probation_result(tenant, dry_run),
        }

        self._print_excluded_info(tenant)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== TONG KET ==='))
        total_records = total_files_ok = total_files_fail = 0
        for label, c in results.items():
            self.stdout.write(
                f"  {label}: {c['records']} ban ghi, {c['files_ok']} file R2 OK, {c['files_fail']} file loi"
            )
            total_records += c['records']
            total_files_ok += c['files_ok']
            total_files_fail += c['files_fail']

        verb = 'SE xoa (dry-run, CHUA xoa gi)' if dry_run else 'Da xoa'
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: {total_records} ban ghi, {total_files_ok} file R2 OK, {total_files_fail} file loi"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Day la DRY-RUN - chua xoa gi. Doi chieu so lieu roi chay lai voi --confirm de thuc su xoa.'
            ))

    def _delete_file(self, url, dry_run):
        """Dem 1 file se/da xoa qua delete_by_url. Ham nay tu nuot loi ben trong (khong bao gio
        raise) nen trong thuc te files_fail se luon la 0 tru khi co loi bat ngo khac ben ngoai."""
        if not url:
            return 0, 0
        if dry_run:
            return 1, 0
        try:
            delete_by_url(url)
            return 1, 0
        except Exception:
            return 0, 1

    def _process_training_progress(self, tenant, dry_run):
        qs = TrainingProgress.objects.filter(tenant=tenant)
        records = qs.count()
        files_ok = files_fail = 0
        url_fields = ('img_tailieu', 'img_lythuyet', 'img_thuchanh', 'sign_trainer', 'sign_trainee', 'pdf_url')
        for row in qs.iterator():
            for field in url_fields:
                ok, fail = self._delete_file(getattr(row, field), dry_run)
                files_ok += ok
                files_fail += fail
        self.stdout.write(
            f'[TrainingProgress] {records} ban ghi, {files_ok} file R2, {files_fail} file loi'
        )
        if not dry_run:
            qs.delete()
        return {'records': records, 'files_ok': files_ok, 'files_fail': files_fail}

    def _process_evaluation(self, tenant, dry_run):
        eval_qs = Evaluation.objects.filter(tenant=tenant)
        detail_qs = EvaluationDetail.objects.filter(tenant=tenant)
        eval_records = eval_qs.count()
        detail_records = detail_qs.count()
        files_ok = files_fail = 0

        for row in eval_qs.iterator():
            for field in ('sign_evaluator', 'sign_trainee', 'pdf_url'):
                ok, fail = self._delete_file(getattr(row, field), dry_run)
                files_ok += ok
                files_fail += fail
        for row in detail_qs.iterator():
            ok, fail = self._delete_file(row.photo_url, dry_run)
            files_ok += ok
            files_fail += fail

        self.stdout.write(
            f'[Evaluation] {eval_records} phieu + {detail_records} dong tieu chi, '
            f'{files_ok} file R2, {files_fail} file loi'
        )
        if not dry_run:
            eval_qs.delete()  # cascade xoa EvaluationDetail trong DB
        return {'records': eval_records + detail_records, 'files_ok': files_ok, 'files_fail': files_fail}

    def _process_council(self, tenant, dry_run):
        council_qs = Council.objects.filter(tenant=tenant)
        member_qs = CouncilMember.objects.filter(tenant=tenant)
        council_records = council_qs.count()
        member_records = member_qs.count()
        self.stdout.write(f'[Council] {council_records} hoi dong + {member_records} thanh vien (khong co file)')
        if not dry_run:
            member_qs.delete()
            council_qs.delete()
        return {'records': council_records + member_records, 'files_ok': 0, 'files_fail': 0}

    def _process_probation_result(self, tenant, dry_run):
        # Chi is_legacy=False (onboarding he moi) - is_legacy=True la lo trinh THAT nap tu
        # Data_LichSu, anh Chung da xac nhan KHONG dua vao pham vi reset (03/08/2026).
        qs = Employee.objects.filter(tenant=tenant, is_legacy=False).exclude(
            probation_result_pdf_url='', pass_date__isnull=True,
            final_result='', commission_status='', retrain_deadline__isnull=True,
        )
        records = qs.count()
        files_ok = files_fail = 0
        for row in qs.iterator():
            ok, fail = self._delete_file(row.probation_result_pdf_url, dry_run)
            files_ok += ok
            files_fail += fail
        self.stdout.write(
            f'[Employee] {records} nhan su (is_legacy=False) co du lieu can reset (phieu KQ thu viec / '
            f'pass_date / final_result / commission_status / retrain_deadline), '
            f'{files_ok} file R2, {files_fail} file loi'
        )
        if not dry_run:
            qs.update(
                probation_result_pdf_url='', pass_date=None, final_result='',
                commission_status='', retrain_deadline=None,
            )
        return {'records': records, 'files_ok': files_ok, 'files_fail': files_fail}

    def _print_excluded_info(self, tenant):
        from cls_sync.models import CourseResult
        from kpi.models import KpiParticipant, KpiSession

        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            '--- Model TIM THAY nhung KHONG nam trong pham vi prompt (chi liet ke de doi chieu, KHONG xoa) ---'
        ))
        self.stdout.write(f'  kpi.KpiSession: {KpiSession.objects.filter(tenant=tenant).count()} ban ghi '
                           f'(anh + bien ban PDF rieng cua tinh nang "buoi KPI/coaching", sinh boi kpi/pdf.py)')
        self.stdout.write(f'  kpi.KpiParticipant: {KpiParticipant.objects.filter(tenant=tenant).count()} ban ghi')
        self.stdout.write(
            f'  employees.LevelUpEnrollment: '
            f'{LevelUpEnrollment.objects.filter(tenant=tenant).exclude(proposal_pdf_url="").count()} '
            f'ban ghi co proposal_pdf_url (phieu de xuat len level)'
        )
        self.stdout.write(f'  employees.TalentReview: {TalentReview.objects.filter(tenant=tenant).count()} ban ghi')
        self.stdout.write(
            f'  employees.MgmtDevelopment: {MgmtDevelopment.objects.filter(tenant=tenant).count()} ban ghi'
        )
        self.stdout.write(
            f'  cls_sync.CourseResult: {CourseResult.objects.filter(tenant=tenant).count()} ban ghi '
            f'(du lieu that tu CLS, cung nhom voi ExamResult - GIU NGUYEN)'
        )
