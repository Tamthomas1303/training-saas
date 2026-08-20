"""import_cls_questions — import ngan hang cau hoi tu file Excel xuat tu CLS (xem exams/cls_import.py
cho logic parse + ghi DB; file nay chi la CLI wrapper mong theo dung quy uoc cac management
command khac trong repo)."""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant

from ...cls_import import import_rows, parse_workbook


class Command(BaseCommand):
    help = (
        "Import ngan hang cau hoi tu file Excel CLS (sheet 'Cau Hoi') vao QuestionBank/Question/"
        "QuestionOption. Idempotent - chay lai khong tao trung."
    )

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Duong dan file .xlsx xuat tu CLS')
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--dry-run', action='store_true', help='Chi in thong ke, khong ghi gi')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'.")

        try:
            result = parse_workbook(options['file'])
        except FileNotFoundError as exc:
            raise CommandError(f"Không tìm thấy file: {options['file']}") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        parsed, skipped = result['parsed'], result['skipped']
        dry_run = options['dry_run']
        stats = import_rows(tenant, parsed, dry_run=dry_run)

        label = 'SẼ ' if dry_run else 'ĐÃ '
        self.stdout.write(f"Đọc file: {options['file']}")
        self.stdout.write(f"Tổng số dòng đọc được: {len(parsed) + len(skipped)}")
        self.stdout.write(f"  - Hợp lệ: {len(parsed)}")
        self.stdout.write(f"  - Bỏ qua: {len(skipped)}")
        if skipped:
            reasons = {}
            for s in skipped:
                reasons[s['reason']] = reasons.get(s['reason'], 0) + 1
            for reason, count in reasons.items():
                self.stdout.write(f"      · {reason}: {count} dòng")

        self.stdout.write('')
        self.stdout.write(self.style.NOTICE(f"--- Thống kê {label}xử lý ---"))
        self.stdout.write(f"  Ngân hàng câu hỏi mới {label.lower()}tạo: {stats['banks_created']}")
        self.stdout.write(f"  Ngân hàng câu hỏi đã có sẵn: {stats['banks_existing']}")
        self.stdout.write(
            f"  Câu hỏi {label.lower()}tạo: {stats['questions_created']} "
            f"({stats['single_created']} một lựa chọn, {stats['multiple_created']} nhiều lựa chọn)"
        )
        self.stdout.write(f"  Câu hỏi bỏ qua vì đã tồn tại (trùng nội dung): {stats['questions_skipped_duplicate']}")
        self.stdout.write(f"  Đáp án (QuestionOption) {label.lower()}tạo: {stats['options_created']}")
        if stats['competency_matched'] or stats['competency_unmatched']:
            self.stdout.write(
                f"  Cột 'Năng lực': {label.lower()}gán {stats['competency_matched']} câu, "
                f"{stats['competency_unmatched']} câu không khớp tên năng lực nào (bỏ trống)"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY-RUN — chưa ghi gì. Chạy lại không có --dry-run để nhập thật.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nĐã nhập xong.'))
