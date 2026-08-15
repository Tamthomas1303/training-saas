from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from dashboard.models import Competency, CompetencyGroup

from .models import Checklist


class ChecklistCompetencyBulkAssignTests(TestCase):
    """Gan hang loat nang luc cho checklist theo ids/category (Prompt_Dashboard_A1_
    GanNhanNangLuc.md, muc 1)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        self.c1 = Checklist.objects.create(tenant=self.tenant, task_name='Đầu việc 1', category='POS', order=0)
        self.c2 = Checklist.objects.create(tenant=self.tenant, task_name='Đầu việc 2', category='POS', order=1)
        self.c3 = Checklist.objects.create(tenant=self.tenant, task_name='Đầu việc khác nhóm', category='Vệ sinh', order=2)
        self.url = reverse('checklist-bulk-assign-competency')
        self.client = APIClient()

    def test_bulk_assign_by_category(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'category': 'POS', 'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated'], 2)
        self.c1.refresh_from_db()
        self.c2.refresh_from_db()
        self.c3.refresh_from_db()
        self.assertEqual(self.c1.competency_id, self.comp.id)
        self.assertEqual(self.c2.competency_id, self.comp.id)
        self.assertIsNone(self.c3.competency_id)

    def test_bulk_assign_by_ids(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'ids': [self.c1.id, self.c3.id], 'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated'], 2)
        self.c2.refresh_from_db()
        self.assertIsNone(self.c2.competency_id)

    def test_bulk_assign_null_clears_competency(self):
        self.c1.competency = self.comp
        self.c1.save()
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'ids': [self.c1.id], 'competency': None}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.c1.refresh_from_db()
        self.assertIsNone(self.c1.competency_id)

    def test_invalid_competency_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'ids': [self.c1.id], 'competency': 999999}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(self.url, {'ids': [self.c1.id], 'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_missing_ids_and_category_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 400)
