from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from dashboard.models import Competency, CompetencyGroup

from .models import EvaluationCriteria


class EvaluationCriteriaCompetencyBulkAssignTests(TestCase):
    """Gan hang loat nang luc cho bo tieu chi/vi tri (Prompt_Dashboard_A1_GanNhanNangLuc.md,
    muc 1). Endpoint nam tren CouncilCriteriaViewSet nhung van thao tac tren EvaluationCriteria
    (ten viewset la lich su, dung chung cho ca cap S lan cap O - xem council_views.py)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        self.c1 = EvaluationCriteria.objects.create(
            tenant=self.tenant, brand='KMP', position='NV Phục vụ', eval_type='Skill_BQL', content='Tiêu chí 1',
        )
        self.c2 = EvaluationCriteria.objects.create(
            tenant=self.tenant, brand='KMP', position='NV Phục vụ', eval_type='Skill_BQL', content='Tiêu chí 2',
        )
        self.c3 = EvaluationCriteria.objects.create(
            tenant=self.tenant, brand='KMP', position='Thu ngân', eval_type='Skill_BQL', content='Tiêu chí khác vị trí',
        )
        self.url = reverse('council-criteria-bulk-assign-competency')
        self.client = APIClient()

    def test_bulk_assign_by_filter(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            self.url,
            {'eval_type': 'Skill_BQL', 'position': 'NV Phục vụ', 'competency': self.comp.id},
            format='json',
        )
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
        resp = self.client.post(self.url, {'ids': [self.c3.id], 'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated'], 1)
        self.c3.refresh_from_db()
        self.assertEqual(self.c3.competency_id, self.comp.id)

    def test_non_admin_om_forbidden(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(self.url, {'ids': [self.c1.id], 'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_missing_ids_and_filters_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'competency': self.comp.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_competency_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(self.url, {'ids': [self.c1.id], 'competency': 999999}, format='json')
        self.assertEqual(resp.status_code, 400)
