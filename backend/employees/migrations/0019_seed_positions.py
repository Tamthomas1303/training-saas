# Muc 16 Phase 1 (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md phan A) - "Seed an toan": tao Position
# tu cac chuoi vi tri distinct DANG CO (Employee + Checklist + dashboard.PositionTarget +
# dashboard.PositionGroupWeight) de danh muc moi KHONG vo du lieu cu (PositionListView se doc
# tu danh muc nay neu KHONG rong - xem employees/views.py). Cac field 'position' o cac model do
# VAN la chuoi tu do, KHONG doi sang FK o Phase 1 nen migration nay chi THEM du lieu, khong dong
# cham gi den cac bang hien co.

from django.db import migrations

# Tu khoa nhan dien vi tri cap O (Ban quan ly) - port employees.services._o_position (khong
# import truc tiep code app trong migration de tranh vo neu logic thay doi sau nay).
_O_KEYWORDS = ('quản lý', 'giám sát', 'bếp trưởng', 'bếp phó')


def _guess_level_group(name):
    n = (name or '').strip().lower()
    if any(k in n for k in _O_KEYWORDS):
        return 'O'
    return ''


def seed_positions(apps, schema_editor):
    Tenant = apps.get_model('accounts', 'Tenant')
    Employee = apps.get_model('employees', 'Employee')
    Position = apps.get_model('employees', 'Position')
    Checklist = apps.get_model('checklist', 'Checklist')
    PositionTarget = apps.get_model('dashboard', 'PositionTarget')
    PositionGroupWeight = apps.get_model('dashboard', 'PositionGroupWeight')

    for tenant in Tenant.objects.all():
        names = set(
            Employee.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        names |= set(
            Checklist.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        names |= set(
            PositionTarget.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        names |= set(
            PositionGroupWeight.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        if not names:
            continue

        existing = set(Position.objects.filter(tenant=tenant).values_list('name', flat=True))
        Position.objects.bulk_create([
            Position(tenant=tenant, name=name, level_group=_guess_level_group(name))
            for name in sorted(names)
            if name not in existing
        ])


def noop_reverse(apps, schema_editor):
    # Khong xoa nguoc - Position co the da duoc Admin sua/them tiep sau khi migrate (vd qua man
    # "Vi tri chuc danh"); xoa nguoc co the mat du lieu that admin da nhap.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0018_position'),
        ('checklist', '0007_checklist_competency'),
        ('dashboard', '0004_competencysnapshot_competencyscoresnapshot'),
    ]

    operations = [
        migrations.RunPython(seed_positions, noop_reverse),
    ]
