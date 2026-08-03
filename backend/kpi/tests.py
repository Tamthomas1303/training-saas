from django.test import TestCase

from accounts.models import Tenant, User
from employees.models import Employee

from .models import Commission
from .services import recompute_commission


class RecomputeCommissionTrainerRoleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_bql_trainer_sets_na_and_hides_existing_eligible(self):
        bql = User.objects.create_user(username='bql1', password='x', tenant=self.tenant, role='bql')
        employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV Demo', trainer=bql)
        Commission.objects.create(
            tenant=self.tenant, employee=employee, trainer=bql, status=Commission.Status.ELIGIBLE,
        )

        result = recompute_commission(employee)

        self.assertEqual(result.status, Commission.Status.NA)

    def test_no_trainer_sets_na(self):
        employee = Employee.objects.create(tenant=self.tenant, code='NV2', name='NV Demo 2')

        result = recompute_commission(employee)

        self.assertIsNone(result)

    def test_trainer_role_proceeds_normally(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        employee = Employee.objects.create(tenant=self.tenant, code='NV3', name='NV Demo 3', trainer=trainer)

        result = recompute_commission(employee)

        self.assertIsNotNone(result)
        self.assertEqual(result.trainer_id, trainer.id)
        self.assertNotEqual(result.status, Commission.Status.NA)

    def test_paid_commission_stays_paid_even_if_trainer_is_bql(self):
        bql = User.objects.create_user(username='bql2', password='x', tenant=self.tenant, role='bql')
        employee = Employee.objects.create(tenant=self.tenant, code='NV4', name='NV Demo 4', trainer=bql)
        Commission.objects.create(
            tenant=self.tenant, employee=employee, trainer=bql, status=Commission.Status.PAID,
        )

        result = recompute_commission(employee)

        self.assertEqual(result.status, Commission.Status.PAID)
