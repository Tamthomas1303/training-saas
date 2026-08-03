"""
import_july_data - ETL mot lan: keo anh minh chung/danh gia ky nang/phieu ket qua thu viec/bien
ban dao tao thang 7/2026 tu Google Drive (qua service account) vao v2.1, danh dau checklist da
hoan thanh, roi tinh lai final_result/pass_date/phu cap. KHONG tao moi nhan su/checklist - v2.1
da co san 45 nhan su thang 7 + danh muc checklist, lenh nay CHI dinh file + danh dau + tinh lai.

Nguon du lieu (da khao sat - xem Prompt_v2.1_ImportJuly_Drive.md):
  - Drive root TRAINING_DRIVE_ROOT_FOLDER_ID:
      02_Evidence_Photos/<ma NH>/2026-07/<ma NV>/{tailieu,huongdan,bienban}_CL-xxxxx_<epoch_ms>.jpg
        (co the co them thu muc con 'eval' - KHONG xu ly, chi liet ke de biet ton tai).
      04_Assessment_PDFs/Skill_BQL/2026-07/DanhGia_<ma NV>_Skill_BQL.pdf
      04_Assessment_PDFs/KetQuaThuViec/2026-07/KetQuaThuViec_<ma NV>.pdf
      03_Training_Records/<ma NH>/2026-07/BienBanDaoTao_<ma NV>_CL-xxxxx.pdf
  - Spreadsheet TRAINING_DB_SHEET_ID (tab position_checklists) qua Sheets API.
  - Tab 'app_employees' KHONG nam trong spreadsheet tren (Sheets API bao "Unable to parse
    range") - doc rieng qua link CSV "Publish to web" cong khai (APP_EMPLOYEES_CSV_URL) bang
    requests, giong cac lenh import_* khac (xem config/csv_source.py).

Anh xa file -> model (da doi chieu voi checklist/models.py, evaluation/models.py,
employees/models.py):
  - tailieu_* -> TrainingProgress.img_tailieu ; huongdan_* -> img_lythuyet ;
    bienban_* -> img_thuchanh (ten "bienban" trong 02_Evidence_Photos la anh THUC HANH, KHAC
    voi "bien ban dao tao" PDF trong 03_Training_Records - trung ten tinh co giua 2 quy uoc).
  - DanhGia_<NV>_Skill_BQL.pdf -> evaluation.Evaluation(eval_type='Skill_BQL').pdf_url
    (+ percent/result tu tab app_employees).
  - KetQuaThuViec_<NV>.pdf -> employees.Employee.probation_result_pdf_url (khong co model
    AuditLog rieng trong code hien tai nen day chinh la "cho luu phieu ket qua" cua v2.1).
  - BienBanDaoTao_<NV>_CL-xxxxx.pdf -> checklist.TrainingProgress.pdf_url cua muc tuong ung.

Khop Checklist_ID (CL-xxxxx) voi Checklist v2.1: can backfill Checklist.code (them o migration
0006) tu tab position_checklists, khop theo (brand, position, task_name) da chuan hoa (strip +
lower), disambiguate bang day/category khi trung task_name. Ham build_checklist_code_map tinh
mapping nay TRONG BO NHO moi lan chay (khong phu thuoc code da luu san) - chi ghi vao DB khi
--confirm - de --dry-run van xem duoc so lieu du chua ghi Checklist.code lan nao.

Trainer_ID (tab app_employees): code hien tai KHONG CO quy uoc anh xa Trainer_ID -> tai khoan
User (khong co truong ma nhan vien tren User). KHONG doan - chi in doi chieu, khong ghi vao
Employee.trainer/TrainingProgress.trainer. He qua: sau khi import, trainer_of(employee) van
tra ve None cho toi khi ai do gan Employee.trainer thu cong - luc do recompute_commission (xem
Phan 1 - kpi/services.py) se dat NA cho toi khi co trainer that duoc gan.

An toan: mac dinh KHONG ghi gi (dry-run), chi in so luong se lam. Phai truyen --confirm moi
thuc su tai Drive/ghi DB/day R2. --tenant loc tenant, --employee loc 1 ma NV (thu truoc khi
chay ca lo). Idempotent: bo qua field/ban ghi da co du lieu (khong tai/ghi de).
"""
import datetime
import json
import re
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

import requests

from accounts.models import Tenant
from checklist.models import Checklist, TrainingProgress
from checklist.storage import StorageError, upload_file_bytes
from config.csv_source import load_csv_rows, pick
from employees.models import Employee
from employees.services import normalize_key, recompute_final_result
from evaluation.models import Evaluation
from kpi.services import recompute_commission

MONTH_FOLDER = '2026-07'
DEFAULT_MONTH_DATE = datetime.date(2026, 7, 1)

EVIDENCE_TYPE_MAP = {'tailieu': 'img_tailieu', 'huongdan': 'img_lythuyet', 'bienban': 'img_thuchanh'}
EVIDENCE_FILE_RE = re.compile(r'^(tailieu|huongdan|bienban)_(CL-\d+)_(\d+)\.(jpg|jpeg|png)$', re.IGNORECASE)
TRAINING_RECORD_RE = re.compile(r'^BienBanDaoTao_([A-Za-z0-9]+)_(CL-\d+)\.pdf$', re.IGNORECASE)
EXT_CONTENT_TYPE = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'pdf': 'application/pdf'}

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]


def _match_evidence_filename(name):
    """Tra (kind, cl_code, timestamp:int, ext) neu name khop quy uoc anh minh chung, None neu khong."""
    m = EVIDENCE_FILE_RE.match(name)
    if not m:
        return None
    kind, cl_code, ts, ext = m.groups()
    return kind.lower(), cl_code, int(ts), ext.lower()


def _match_training_record_filename(name):
    """Tra (employee_code, cl_code) neu name khop quy uoc bien ban dao tao, None neu khong."""
    m = TRAINING_RECORD_RE.match(name)
    if not m:
        return None
    return m.group(1), m.group(2)


def _parse_skill_percent(raw):
    """'0,94' (phan so, dau phay thap phan) -> 94.0 ; '94' hoac '94,5' (da la %) -> giu nguyen.
    None neu rong/khong parse duoc."""
    raw = (raw or '').strip().replace('%', '')
    if not raw:
        return None
    try:
        value = float(raw.replace(',', '.'))
    except ValueError:
        return None
    return value * 100 if value <= 1 else value


def _parse_skill_result(raw):
    raw = (raw or '').strip()
    if not raw:
        return ''
    return Evaluation.Result.PASS if raw == 'Đạt' else Evaluation.Result.FAIL


def build_checklist_code_map(tenant, position_checklist_rows):
    """Khop Checklist v2.1 <-> Checklist_ID (CL-xxxxx) tu tab position_checklists, TRONG BO NHO
    (chua ghi DB). Tra (code_to_checklist: {code: Checklist}, checklist_to_code: {checklist.id:
    code}, unmatched: [Checklist khong khop duoc]). Khop theo (brand, position, task_name) chuan
    hoa; trung task_name trong cung position thi phan biet bang day/category."""
    index = defaultdict(list)
    for row in position_checklist_rows:
        position = pick(row, 'Position', 'position')
        if not position:
            continue  # dong rong (CL-000080 tro di la placeholder) - bo qua theo yeu cau
        key = (
            normalize_key(pick(row, 'Brand', 'brand')),
            normalize_key(position),
            normalize_key(pick(row, 'Task_Name', 'task_name')),
        )
        index[key].append(row)

    code_to_checklist = {}
    checklist_to_code = {}
    unmatched = []

    for c in Checklist.objects.filter(tenant=tenant):
        key = (normalize_key(c.brand), normalize_key(c.position), normalize_key(c.task_name))
        candidates = index.get(key, [])
        chosen = None
        if len(candidates) == 1:
            chosen = candidates[0]
        elif len(candidates) > 1:
            day_str = str(c.day) if c.day is not None else ''
            refined = [
                r for r in candidates
                if pick(r, 'Day', 'day') == day_str and normalize_key(pick(r, 'Category', 'category')) == normalize_key(c.category)
            ]
            if len(refined) == 1:
                chosen = refined[0]

        code = pick(chosen, 'Checklist_ID', 'checklist_id') if chosen else ''
        if code:
            code_to_checklist[code] = c
            checklist_to_code[c.id] = code
        else:
            unmatched.append(c)

    return code_to_checklist, checklist_to_code, unmatched


class DriveContext:
    """Bao boc Drive API v3 + cache danh sach con theo parent_id (tranh goi lai API khi nhieu
    nhan su cung nha hang/thang duoc duyet qua)."""

    def __init__(self, service):
        self.service = service
        self._children_cache = {}

    def list_children(self, parent_id):
        if parent_id not in self._children_cache:
            files, page_token = [], None
            while True:
                res = self.service.files().list(
                    q=f"'{parent_id}' in parents and trashed=false",
                    fields='nextPageToken, files(id,name,mimeType,modifiedTime)',
                    pageSize=1000, pageToken=page_token,
                ).execute()
                files.extend(res.get('files', []))
                page_token = res.get('nextPageToken')
                if not page_token:
                    break
            self._children_cache[parent_id] = files
        return self._children_cache[parent_id]

    def find_child(self, parent_id, name):
        return next((f for f in self.list_children(parent_id) if f['name'] == name), None)

    def download(self, file_id):
        return self.service.files().get_media(fileId=file_id).execute()


class Command(BaseCommand):
    help = (
        'Nhap minh chung/danh gia ky nang/phieu ket qua thu viec/bien ban dao tao thang 7/2026 '
        'tu Google Drive vao v2.1. Mac dinh dry-run, phai them --confirm moi thuc su ghi.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--employee', default=None, help='Chi xu ly 1 ma nhan su (vd AM002868) de thu truoc')
        parser.add_argument('--dry-run', action='store_true', help='Chi liet ke, khong tai Drive/ghi DB (mac dinh)')
        parser.add_argument('--confirm', action='store_true', help='Thuc su tai Drive, day R2, ghi DB')

    def handle(self, *args, **options):
        if options['dry_run'] and options['confirm']:
            raise CommandError('Chi dung 1 trong 2 co --dry-run hoac --confirm, khong dung ca hai.')
        dry_run = not options['confirm']

        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        employee_filter = (options['employee'] or '').strip() or None

        self.stdout.write(self.style.WARNING(
            f"{'[DRY-RUN - chua ghi/tai gi] ' if dry_run else '[CONFIRM - THUC SU GHI] '}"
            f"Tenant: {tenant.name} (id={tenant.id})"
        ))

        creds = self._google_credentials()
        drive = DriveContext(self._drive_service(creds))
        sheets = self._sheets_service(creds)

        position_rows = self._read_sheet_safely(sheets, 'position_checklists')
        app_employee_rows = self._read_app_employees_csv()
        app_employees_by_code = {
            pick(row, 'Employee_ID', 'employee_id'): row for row in app_employee_rows if pick(row, 'Employee_ID', 'employee_id')
        }

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(tenant, position_rows)
        self.stdout.write(
            f'[Checklist.code] {len(checklist_to_code)} khop duoc, {len(unmatched)} chua khop '
            f'(tren tong {len(checklist_to_code) + len(unmatched)} checklist cua tenant)'
        )
        if unmatched:
            for c in unmatched[:20]:
                self.stdout.write(f'    chua khop: [{c.id}] {c.brand} / {c.position} / {c.task_name}')
            if len(unmatched) > 20:
                self.stdout.write(f'    ... va {len(unmatched) - 20} checklist khac')
        if not dry_run:
            to_update = list(checklist_to_code.items())
            for cid, code in to_update:
                Checklist.objects.filter(id=cid).update(code=code)
            self.stdout.write(self.style.SUCCESS(f'Da ghi Checklist.code cho {len(to_update)} checklist'))

        root_id = settings.TRAINING_DRIVE_ROOT_FOLDER_ID
        if not root_id:
            raise CommandError('Chua cau hinh TRAINING_DRIVE_ROOT_FOLDER_ID trong .env')
        evidence_root = drive.find_child(root_id, '02_Evidence_Photos')
        if not evidence_root:
            raise CommandError('Khong tim thay thu muc 02_Evidence_Photos tren Drive (kiem tra quyen chia se)')

        employees_qs = Employee.objects.filter(tenant=tenant, restaurant__isnull=False)
        if employee_filter:
            employees_qs = employees_qs.filter(code=employee_filter)
        employees_qs = employees_qs.select_related('restaurant').order_by('code')

        totals = defaultdict(int)
        processed = 0

        for employee in employees_qs:
            try:
                stats = self._process_employee(
                    drive, root_id, evidence_root, tenant, employee, code_to_checklist,
                    app_employees_by_code, dry_run,
                )
            except Exception as exc:  # noqa: BLE001 - 1 loi khong duoc chan ca lo
                self.stdout.write(self.style.ERROR(f'[{employee.code}] LOI: {exc}'))
                totals['employee_errors'] += 1
                continue

            if stats is None:
                continue  # khong co thu muc Drive cho nhan su nay

            processed += 1
            for key, value in stats.items():
                totals[key] += value

            if not dry_run:
                recompute_final_result(employee)
                recompute_commission(employee)

            self.stdout.write(
                f"[{employee.code}] {stats['checklist_matched']} muc checklist se/da done "
                f"({stats['checklist_unmatched']} co anh nhung KHONG khop duoc CL-code), "
                f"{stats['photos']} anh, danh gia ky nang: {'co' if stats['skill_eval'] else 'khong'}, "
                f"phieu KQ thu viec: {'co' if stats['probation_result'] else 'khong'}, "
                f"bien ban dao tao: {stats['training_records']}, file R2: {stats['files_ok']} OK/{stats['files_fail']} loi"
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== TONG KET ==='))
        self.stdout.write(f'  Nhan su xu ly: {processed} (loi: {totals["employee_errors"]})')
        self.stdout.write(
            f'  TrainingProgress danh dau done: {totals["checklist_matched"]} '
            f'({totals["checklist_unmatched"]} co anh nhung khong khop duoc CL-code)'
        )
        self.stdout.write(f'  Danh gia ky nang tao moi: {totals["skill_eval"]}')
        self.stdout.write(f'  Phieu ket qua thu viec dinh: {totals["probation_result"]}')
        self.stdout.write(f'  Bien ban dao tao dinh: {totals["training_records"]}')
        self.stdout.write(f'  File R2: {totals["files_ok"]} OK, {totals["files_fail"]} loi')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Day la DRY-RUN - chua tai Drive/ghi DB/day R2 gi. Doi chieu so lieu roi chay lai voi --confirm.'
            ))

    # ------------------------------------------------------------------ Google clients

    def _google_credentials(self):
        from google.oauth2 import service_account

        raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON
        if not raw:
            raise CommandError('Chua cau hinh GOOGLE_SERVICE_ACCOUNT_JSON trong .env')
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f'GOOGLE_SERVICE_ACCOUNT_JSON khong phai JSON hop le: {exc}')
        return service_account.Credentials.from_service_account_info(info, scopes=GOOGLE_SCOPES)

    def _drive_service(self, creds):
        from googleapiclient.discovery import build

        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    def _sheets_service(self, creds):
        from googleapiclient.discovery import build

        return build('sheets', 'v4', credentials=creds, cache_discovery=False)

    def _read_sheet_safely(self, sheets_service, tab_name):
        from googleapiclient.errors import HttpError

        try:
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=settings.TRAINING_DB_SHEET_ID, range=tab_name,
            ).execute()
        except HttpError as exc:
            self.stdout.write(self.style.ERROR(
                f"[Sheets] Khong doc duoc tab '{tab_name}': {exc}. "
                f"Bo qua du lieu tab nay (co the can bat Sheets API cho project cua service account)."
            ))
            return []
        values = result.get('values', [])
        if not values:
            return []
        headers = [h.strip() for h in values[0]]
        return [dict(zip(headers, row + [''] * (len(headers) - len(row)))) for row in values[1:]]

    def _read_app_employees_csv(self):
        try:
            return load_csv_rows(settings.APP_EMPLOYEES_CSV_URL)
        except (requests.RequestException, OSError) as exc:
            self.stdout.write(self.style.ERROR(
                f"[CSV] Khong doc duoc APP_EMPLOYEES_CSV_URL: {exc}. Bo qua Skill_Score_%/Skill_Result."
            ))
            return []

    # ------------------------------------------------------------------ Per-employee

    def _process_employee(self, drive, root_id, evidence_root, tenant, employee, code_to_checklist, app_employees_by_code, dry_run):
        rest_folder = drive.find_child(evidence_root['id'], employee.restaurant.code)
        if not rest_folder:
            return None
        month_folder = drive.find_child(rest_folder['id'], MONTH_FOLDER)
        if not month_folder:
            return None
        emp_folder = drive.find_child(month_folder['id'], employee.code)
        if not emp_folder:
            return None

        stats = {
            'checklist_matched': 0, 'checklist_unmatched': 0, 'photos': 0,
            'skill_eval': 0, 'probation_result': 0, 'training_records': 0,
            'files_ok': 0, 'files_fail': 0,
        }

        self._process_evidence_photos(drive, tenant, employee, emp_folder, code_to_checklist, dry_run, stats)
        self._process_skill_eval(drive, root_id, tenant, employee, app_employees_by_code, dry_run, stats)
        self._process_probation_result(drive, root_id, employee, dry_run, stats)
        self._process_training_records(drive, root_id, employee, code_to_checklist, dry_run, stats)
        return stats

    def _upload(self, raw_bytes, folder, filename_prefix, ext, content_type, stats):
        try:
            url = upload_file_bytes(raw_bytes, folder, filename_prefix, ext, content_type)
            stats['files_ok'] += 1
            return url
        except StorageError as exc:
            self.stdout.write(self.style.ERROR(f'    loi day R2 ({filename_prefix}): {exc}'))
            stats['files_fail'] += 1
            return None

    def _process_evidence_photos(self, drive, tenant, employee, emp_folder, code_to_checklist, dry_run, stats):
        groups = defaultdict(dict)
        for f in drive.list_children(emp_folder['id']):
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                continue  # vd 'eval' - khong xu ly
            matched = _match_evidence_filename(f['name'])
            if not matched:
                continue
            kind, cl_code, ts, ext = matched
            current = groups[cl_code].get(kind)
            if current is None or ts > current[0]:
                groups[cl_code][kind] = (ts, ext, f)

        for cl_code, kinds in groups.items():
            checklist = code_to_checklist.get(cl_code)
            if not checklist:
                stats['checklist_unmatched'] += 1
                continue

            progress = TrainingProgress.objects.filter(tenant=tenant, employee=employee, checklist=checklist).first()
            if progress and progress.status == TrainingProgress.Status.DONE:
                continue  # idempotent - da hoan thanh tu truoc

            latest_ts = None
            new_values = {}
            for kind, field in EVIDENCE_TYPE_MAP.items():
                entry = kinds.get(kind)
                if not entry:
                    continue
                ts, ext, f = entry
                latest_ts = ts if latest_ts is None else max(latest_ts, ts)
                if progress and getattr(progress, field):
                    continue  # idempotent - field nay da co URL
                stats['photos'] += 1
                if dry_run:
                    continue
                content = drive.download(f['id'])
                url = self._upload(
                    content, f'evidence/{tenant.id}/{employee.code}', f'{cl_code}_{kind}',
                    ext, EXT_CONTENT_TYPE[ext], stats,
                )
                if url:
                    new_values[field] = url

            stats['checklist_matched'] += 1
            if dry_run:
                continue
            if not progress:
                progress = TrainingProgress(tenant=tenant, employee=employee, checklist=checklist)
            for field, url in new_values.items():
                setattr(progress, field, url)
            progress.status = TrainingProgress.Status.DONE
            if latest_ts is not None:
                progress.completed_at = datetime.datetime.fromtimestamp(latest_ts / 1000, tz=datetime.timezone.utc)
            elif not progress.completed_at:
                progress.completed_at = timezone.make_aware(
                    datetime.datetime.combine(DEFAULT_MONTH_DATE, datetime.time.min)
                )
            progress.save()

    def _process_skill_eval(self, drive, root_id, tenant, employee, app_employees_by_code, dry_run, stats):
        if Evaluation.objects.filter(tenant=tenant, employee=employee, eval_type='Skill_BQL').exists():
            return  # idempotent theo (employee, eval_type)

        assess_root = drive.find_child(root_id, '04_Assessment_PDFs')
        skill_root = drive.find_child(assess_root['id'], 'Skill_BQL') if assess_root else None
        skill_month = drive.find_child(skill_root['id'], MONTH_FOLDER) if skill_root else None
        if not skill_month:
            return
        pdf_file = drive.find_child(skill_month['id'], f'DanhGia_{employee.code}_Skill_BQL.pdf')
        if not pdf_file:
            return

        stats['skill_eval'] += 1
        if dry_run:
            return

        row = app_employees_by_code.get(employee.code, {})
        percent = _parse_skill_percent(pick(row, 'Skill_Score_%', 'Skill_Score', 'skill_score_%'))
        result = _parse_skill_result(pick(row, 'Skill_Result', 'skill_result'))

        content = drive.download(pdf_file['id'])
        pdf_url = self._upload(content, f'danhgia/{tenant.id}', f'SkillBQL_{employee.code}', 'pdf', 'application/pdf', stats)

        completed_at = timezone.now()
        Evaluation.objects.create(
            tenant=tenant, employee=employee, evaluator=None, eval_type='Skill_BQL',
            date=completed_at.date(), total_score=percent or 0, max_score=100, percent=percent or 0,
            result=result, pdf_url=pdf_url or '', status=Evaluation.Status.DONE, completed_at=completed_at,
        )

    def _process_probation_result(self, drive, root_id, employee, dry_run, stats):
        if employee.probation_result_pdf_url:
            return  # idempotent - da co phieu

        assess_root = drive.find_child(root_id, '04_Assessment_PDFs')
        kqtv_root = drive.find_child(assess_root['id'], 'KetQuaThuViec') if assess_root else None
        kqtv_month = drive.find_child(kqtv_root['id'], MONTH_FOLDER) if kqtv_root else None
        if not kqtv_month:
            return
        pdf_file = drive.find_child(kqtv_month['id'], f'KetQuaThuViec_{employee.code}.pdf')
        if not pdf_file:
            return

        stats['probation_result'] += 1
        if dry_run:
            return

        content = drive.download(pdf_file['id'])
        pdf_url = self._upload(
            content, f'ketquathuviec/{employee.tenant_id}', f'KetQuaThuViec_{employee.code}',
            'pdf', 'application/pdf', stats,
        )
        if pdf_url:
            employee.probation_result_pdf_url = pdf_url
            employee.save(update_fields=['probation_result_pdf_url'])

    def _process_training_records(self, drive, root_id, employee, code_to_checklist, dry_run, stats):
        tr_root = drive.find_child(root_id, '03_Training_Records')
        rest_folder = drive.find_child(tr_root['id'], employee.restaurant.code) if tr_root else None
        month_folder = drive.find_child(rest_folder['id'], MONTH_FOLDER) if rest_folder else None
        if not month_folder:
            return

        candidates = {}
        for f in drive.list_children(month_folder['id']):
            matched = _match_training_record_filename(f['name'])
            if not matched:
                continue
            code, cl_code = matched
            if code != employee.code:
                continue
            current = candidates.get(cl_code)
            if current is None or f['modifiedTime'] > current['modifiedTime']:
                candidates[cl_code] = f

        for cl_code, f in candidates.items():
            checklist = code_to_checklist.get(cl_code)
            if not checklist:
                continue
            progress = TrainingProgress.objects.filter(
                tenant_id=employee.tenant_id, employee=employee, checklist=checklist,
            ).first()
            if progress and progress.pdf_url:
                continue  # idempotent - da co bien ban

            stats['training_records'] += 1
            if dry_run:
                continue

            content = drive.download(f['id'])
            pdf_url = self._upload(
                content, f'bienban/{employee.tenant_id}', f'BienBanDaoTao_{employee.code}_{cl_code}',
                'pdf', 'application/pdf', stats,
            )
            if not pdf_url:
                continue
            if not progress:
                progress = TrainingProgress(tenant_id=employee.tenant_id, employee=employee, checklist=checklist)
            progress.pdf_url = pdf_url
            progress.save()
