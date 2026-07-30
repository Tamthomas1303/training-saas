"""Di trú file minh chứng/PDF từ Supabase Storage sang Cloudflare R2, cập nhật URL trong DB.

Chạy:  python manage.py migrate_storage_to_r2 --dry-run   # rà trước, không đổi gì
       python manage.py migrate_storage_to_r2             # di trú thật
       python manage.py migrate_storage_to_r2 --limit 20  # thử vài file đầu

Chỉ đụng tới các URL đang trỏ về Supabase Storage; URL ngoài (link CSV, tài liệu ngoài) được bỏ qua.
Giữ nguyên đường dẫn folder/tên file khi chuyển sang R2.
"""
import mimetypes

import requests
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand

from checklist.storage import _upload_to_r2

# (app_label, ModelName, [các cột URL chứa file upload])
TARGETS = [
    ('accounts', 'User', ['avatar_url']),
    ('checklist', 'TrainingProgress', ['img_tailieu', 'img_lythuyet', 'img_thuchanh', 'sign_trainer', 'sign_trainee', 'pdf_url']),
    ('checklist', 'Document', ['file_url']),
    ('employees', 'Employee', ['probation_result_pdf_url']),
    ('employees', 'LevelUpEnrollment', ['proposal_pdf_url']),
    ('evaluation', 'Evaluation', ['sign_evaluator', 'sign_trainee', 'pdf_url']),
    ('evaluation', 'EvaluationDetail', ['photo_url']),
    ('kpi', 'KpiSession', ['img_tailieu', 'img_lythuyet', 'img_thuchanh', 'pdf_url']),
    ('kpi', 'KpiParticipant', ['sign_url']),
]

MARKER = '/storage/v1/object/public/'


class Command(BaseCommand):
    help = 'Di trú file từ Supabase Storage sang Cloudflare R2 và cập nhật URL trong DB.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Chỉ liệt kê, không thay đổi.')
        parser.add_argument('--limit', type=int, default=0, help='Giới hạn số file xử lý (0 = không giới hạn).')

    def handle(self, *args, **opts):
        dry, limit = opts['dry_run'], opts['limit']
        sup_base = (settings.SUPABASE_URL or '').rstrip('/')
        if not sup_base:
            self.stdout.write(self.style.WARNING('Chưa cấu hình SUPABASE_URL — không có nguồn để di trú.'))
            return
        if not dry and (settings.STORAGE_BACKEND or '').lower() != 'r2':
            self.stdout.write(self.style.WARNING('STORAGE_BACKEND != r2 (nhưng lệnh này luôn đẩy lên R2). Kiểm tra R2_* đã cấu hình.'))

        total = done = failed = 0
        for app_label, model_name, fields in TARGETS:
            try:
                Model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            for obj in Model.objects.all().iterator():
                changed = []
                for f in fields:
                    val = getattr(obj, f, '') or ''
                    if not (val.startswith(sup_base) and MARKER in val):
                        continue
                    total += 1
                    if limit and total > limit:
                        break
                    tail = val.split(MARKER, 1)[1]           # {bucket}/{folder}/{file}
                    key = tail.split('/', 1)[1] if '/' in tail else tail  # bỏ tên bucket -> {folder}/{file}
                    ctype = mimetypes.guess_type(key)[0] or 'application/octet-stream'
                    if dry:
                        self.stdout.write(f'[DRY] {model_name}.{f} #{obj.pk}: {key}')
                        continue
                    try:
                        resp = requests.get(val, timeout=30)
                        resp.raise_for_status()
                        new_url = _upload_to_r2(key, resp.content, ctype)
                        setattr(obj, f, new_url)
                        changed.append(f)
                        done += 1
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        self.stdout.write(self.style.ERROR(f'  LỖI {model_name}.{f} #{obj.pk}: {exc}'))
                if changed:
                    obj.save(update_fields=changed)
                if limit and total > limit:
                    break
            if limit and total > limit:
                break

        suffix = ' (dry-run, chưa thay đổi)' if dry else ''
        self.stdout.write(self.style.SUCCESS(f'Xong. Phát hiện {total} file Supabase, di trú {done}, lỗi {failed}.{suffix}'))
