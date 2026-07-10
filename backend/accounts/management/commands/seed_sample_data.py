from django.core.management.base import BaseCommand

from accounts.models import Tenant
from checklist.models import Checklist
from restaurants.models import Restaurant

RESTAURANTS = [
    {
        'code': 'NH001',
        'name': 'Nha hang Quan 1',
        'brand': 'Brand A',
        'city': 'Ho Chi Minh',
        'district': 'Quan 1',
        'region': 'Mien Nam',
    },
    {
        'code': 'NH002',
        'name': 'Nha hang Quan 3',
        'brand': 'Brand A',
        'city': 'Ho Chi Minh',
        'district': 'Quan 3',
        'region': 'Mien Nam',
    },
    {
        'code': 'NH003',
        'name': 'Nha hang Cau Giay',
        'brand': 'Brand B',
        'city': 'Ha Noi',
        'district': 'Cau Giay',
        'region': 'Mien Bac',
    },
]

CHECKLIST_ITEMS = [
    {
        'brand': 'Brand A',
        'position': 'Nhan vien nha hang',
        'day': 1,
        'category': 'Tai lieu',
        'task_name': 'Doc noi quy cong ty',
        'level_group': 'S',
        'order': 1,
    },
    {
        'brand': 'Brand A',
        'position': 'Nhan vien nha hang',
        'day': 1,
        'category': 'Ly thuyet',
        'task_name': 'Quy trinh phuc vu ban',
        'level_group': 'S',
        'order': 2,
    },
    {
        'brand': 'Brand A',
        'position': 'Bep pho',
        'day': 3,
        'category': 'Thuc hanh',
        'task_name': 'Ve sinh an toan thuc pham',
        'level_group': 'P',
        'order': 1,
    },
    {
        'brand': 'Brand B',
        'position': 'Giam sat',
        'day': 5,
        'category': 'Ly thuyet',
        'task_name': 'Quan ly ca lam viec',
        'level_group': 'O',
        'order': 1,
    },
]


class Command(BaseCommand):
    help = 'Seed du lieu mau: 1 tenant, vai nha hang, vai checklist de test'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(name=options['tenant'])

        for data in RESTAURANTS:
            Restaurant.objects.get_or_create(tenant=tenant, code=data['code'], defaults=data)

        for data in CHECKLIST_ITEMS:
            Checklist.objects.get_or_create(tenant=tenant, task_name=data['task_name'], defaults=data)

        self.stdout.write(self.style.SUCCESS(
            'Seed xong: tenant=%s, %d nha hang, %d checklist'
            % (
                tenant.name,
                Restaurant.objects.filter(tenant=tenant).count(),
                Checklist.objects.filter(tenant=tenant).count(),
            )
        ))
