"""
Don du lieu rac sinh ra truoc khi sua importer khung nang luc (Prompt_Fix_ImportKhungNangLuc.md):
- Xoa CompetencyGroup ngoai khung 6 nhom he thong (AT/A1/A2/B/C/D) - vd 'Bep thop'/'Bep chao'
  bi tao nham tu ten vi tri khi file trong so nhom bi import qua importer muc tieu.
- Gop Competency trung ten (sau khi chuan hoa) trong cung 1 nhom ve 1 ban ghi duy nhat, chuyen
  moi tham chieu (PositionTarget, Course/Assessment/EvaluationCriteria.competency) sang ban giu.

Idempotent - chay lai nhieu lan an toan, khong con gi rac/trung thi khong lam gi.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Tenant
from courses.models import Course
from evaluation.models import EvaluationCriteria
from exams.models import Assessment

from ...models import Competency, CompetencyGroup, PositionTarget
from ...services import VALID_GROUP_CODES, _normalize_competency_name


class Command(BaseCommand):
    help = 'Xoa CompetencyGroup rac (ngoai khung AT/A1/A2/B/C/D) va gop Competency trung ten trong cung 1 nhom.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")

        with transaction.atomic():
            rac_codes = list(
                CompetencyGroup.objects.filter(tenant=tenant).exclude(code__in=VALID_GROUP_CODES)
                .values_list('code', flat=True)
            )
            deleted, _detail = CompetencyGroup.objects.filter(
                tenant=tenant,
            ).exclude(code__in=VALID_GROUP_CODES).delete()
            if rac_codes:
                self.stdout.write(self.style.WARNING(
                    f"Đã xóa {len(rac_codes)} nhóm rác: {', '.join(rac_codes)} ({deleted} bản ghi liên quan)."
                ))

            merged = 0
            for group in CompetencyGroup.objects.filter(tenant=tenant):
                buckets = defaultdict(list)
                for c in group.competencies.all():
                    buckets[_normalize_competency_name(c.name)].append(c)
                for comps in buckets.values():
                    if len(comps) < 2:
                        continue
                    comps.sort(key=lambda c: -PositionTarget.objects.filter(competency=c).count())
                    keep, dupes = comps[0], comps[1:]
                    keep_positions = set(
                        PositionTarget.objects.filter(competency=keep).values_list('position', flat=True)
                    )
                    for dup in dupes:
                        for pt in list(PositionTarget.objects.filter(competency=dup)):
                            if pt.position in keep_positions:
                                pt.delete()
                            else:
                                pt.competency = keep
                                pt.save(update_fields=['competency'])
                                keep_positions.add(pt.position)
                        Course.objects.filter(competency=dup).update(competency=keep)
                        Assessment.objects.filter(competency=dup).update(competency=keep)
                        EvaluationCriteria.objects.filter(competency=dup).update(competency=keep)
                        self.stdout.write(self.style.WARNING(
                            f'Đã gộp năng lực trùng: "{dup.name}" -> "{keep.name}" (nhóm {group.code}).'
                        ))
                        dup.delete()
                        merged += 1

        if not rac_codes and not merged:
            self.stdout.write(self.style.SUCCESS('Không có gì để dọn - dữ liệu đã sạch.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Hoàn tất: xóa {len(rac_codes)} nhóm rác, gộp {merged} năng lực trùng.'
            ))
        self.stdout.write(
            f'Hiện có {CompetencyGroup.objects.filter(tenant=tenant).count()} nhóm, '
            f'{Competency.objects.filter(tenant=tenant).count()} năng lực.'
        )
