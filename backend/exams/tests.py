from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from cls_sync.models import ExamResult
from employees.models import Employee
from integration.models import XapiStatement

from .models import (
    Answer,
    Assessment,
    AssessmentAssignment,
    AssessmentQuestion,
    Attempt,
    Question,
    QuestionBank,
    QuestionOption,
)
from .services import grade_objective_answer


class QuestionBankAdminApiTests(TestCase):
    """CRUD ngan hang cau hoi - chi Admin duoc ghi, moi role dang nhap doc duoc."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_admin_can_create_bank(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('exam-bank-list'), {'name': 'An toàn thực phẩm'})
        self.assertEqual(resp.status_code, 201)
        bank = QuestionBank.objects.get(id=resp.data['id'])
        self.assertEqual(bank.tenant_id, self.tenant.id)

    def test_non_admin_cannot_create_bank(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('exam-bank-list'), {'name': 'X'})
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_can_read_banks(self):
        QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')
        self.client.force_authenticate(self.trainer)
        resp = self.client.get(reverse('exam-bank-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)


class QuestionAdminApiTests(TestCase):
    """Tao cau hoi single kem options long trong body (dung serializer sync options)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')
        self.client = APIClient()

    def test_create_single_question_with_options(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('exam-question-list'), {
            'bank': self.bank.id, 'type': Question.Type.SINGLE, 'stem_html': 'Thủ đô VN?', 'points': 2,
            'options': [
                {'content_html': 'Hà Nội', 'is_correct': True},
                {'content_html': 'Đà Nẵng', 'is_correct': False},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        question = Question.objects.get(id=resp.data['id'])
        self.assertEqual(question.options.count(), 2)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)


class ObjectiveGradingTests(TestCase):
    """Cham diem CA 8 DANG - test truc tiep services.grade_objective_answer, dac biet
    matching/dragdrop/multiple all-or-nothing, text_fill khong phan biet hoa/thuong, numeric
    trong nguong sai so."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')

    def _make_question(self, qtype, **kwargs):
        return Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=qtype, stem_html='Câu hỏi', **kwargs,
        )

    def test_single_correct_and_incorrect(self):
        q = self._make_question(Question.Type.SINGLE)
        correct = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='A', is_correct=True)
        wrong = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='B', is_correct=False)

        score, is_correct = grade_objective_answer(q, {'option_id': correct.id}, 2)
        self.assertEqual(score, Decimal('2'))
        self.assertTrue(is_correct)

        score, is_correct = grade_objective_answer(q, {'option_id': wrong.id}, 2)
        self.assertEqual(score, Decimal('0'))
        self.assertFalse(is_correct)

    def test_truefalse(self):
        q = self._make_question(Question.Type.TRUEFALSE)
        true_opt = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='Đúng', is_correct=True)
        QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='Sai', is_correct=False)

        score, is_correct = grade_objective_answer(q, {'option_id': true_opt.id}, 1)
        self.assertEqual(score, Decimal('1'))
        self.assertTrue(is_correct)

    def test_multiple_all_or_nothing(self):
        q = self._make_question(Question.Type.MULTIPLE)
        a = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='A', is_correct=True)
        b = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='B', is_correct=True)
        c = QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='C', is_correct=False)

        score, is_correct = grade_objective_answer(q, {'option_ids': [a.id, b.id]}, 3)
        self.assertEqual(score, Decimal('3'))
        self.assertTrue(is_correct)

        # thieu 1 dap an dung -> sai het (khong cham 1 phan)
        score, is_correct = grade_objective_answer(q, {'option_ids': [a.id]}, 3)
        self.assertEqual(score, Decimal('0'))
        self.assertFalse(is_correct)

        # dung nhung thua 1 dap an sai -> sai het
        score, is_correct = grade_objective_answer(q, {'option_ids': [a.id, b.id, c.id]}, 3)
        self.assertEqual(score, Decimal('0'))
        self.assertFalse(is_correct)

    def test_text_fill_case_insensitive(self):
        q = self._make_question(
            Question.Type.TEXT_FILL, config={'accepted': ['Paris'], 'case_sensitive': False},
        )
        score, is_correct = grade_objective_answer(q, {'text': 'paris'}, 1)
        self.assertEqual(score, Decimal('1'))
        self.assertTrue(is_correct)

        score, is_correct = grade_objective_answer(q, {'text': '  PARIS  '}, 1)
        self.assertTrue(is_correct)

        score, is_correct = grade_objective_answer(q, {'text': 'london'}, 1)
        self.assertFalse(is_correct)

    def test_text_fill_case_sensitive(self):
        q = self._make_question(
            Question.Type.TEXT_FILL, config={'accepted': ['Paris'], 'case_sensitive': True},
        )
        score, is_correct = grade_objective_answer(q, {'text': 'paris'}, 1)
        self.assertFalse(is_correct)

    def test_numeric_within_tolerance(self):
        q = self._make_question(Question.Type.NUMERIC, config={'answer': 10, 'tolerance': 0.5})
        score, is_correct = grade_objective_answer(q, {'value': 10.5}, 1)
        self.assertTrue(is_correct)
        score, is_correct = grade_objective_answer(q, {'value': 9.5}, 1)
        self.assertTrue(is_correct)

    def test_numeric_outside_tolerance(self):
        q = self._make_question(Question.Type.NUMERIC, config={'answer': 10, 'tolerance': 0.5})
        score, is_correct = grade_objective_answer(q, {'value': 10.6}, 1)
        self.assertFalse(is_correct)
        self.assertEqual(score, Decimal('0'))

    def test_matching_all_or_nothing(self):
        q = self._make_question(
            Question.Type.MATCHING,
            config={'pairs': [{'left': 'A', 'right': '1'}, {'left': 'B', 'right': '2'}]},
        )
        score, is_correct = grade_objective_answer(
            q, {'pairs': [{'left': 'A', 'right': '1'}, {'left': 'B', 'right': '2'}]}, 2,
        )
        self.assertTrue(is_correct)
        self.assertEqual(score, Decimal('2'))

        score, is_correct = grade_objective_answer(
            q, {'pairs': [{'left': 'A', 'right': '2'}, {'left': 'B', 'right': '1'}]}, 2,
        )
        self.assertFalse(is_correct)
        self.assertEqual(score, Decimal('0'))

    def test_dragdrop_all_or_nothing(self):
        q = self._make_question(
            Question.Type.DRAGDROP,
            config={'tokens': ['x', 'y'], 'gaps': [{'id': 1, 'answer': 'x'}, {'id': 2, 'answer': 'y'}]},
        )
        score, is_correct = grade_objective_answer(q, {'placements': {'1': 'x', '2': 'y'}}, 2)
        self.assertTrue(is_correct)

        score, is_correct = grade_objective_answer(q, {'placements': {'1': 'y', '2': 'x'}}, 2)
        self.assertFalse(is_correct)
        self.assertEqual(score, Decimal('0'))

    def test_essay_not_auto_graded(self):
        q = self._make_question(Question.Type.ESSAY)
        score, is_correct = grade_objective_answer(q, {'text': 'bài làm của tôi'}, 5)
        self.assertIsNone(score)
        self.assertIsNone(is_correct)


class ExamFlowApiTests(TestCase):
    """Smoke test theo muc 4 cua prompt: 1 ngan hang + 8 cau (moi dang 1 cau) -> 1 de 8 cau ->
    gan 1 nhan su -> lam bai -> tu cham 7 cau khach quan -> cham tay cau tu luan -> xem ket qua."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')

        self.q_single = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.SINGLE, stem_html='Q single',
        )
        self.opt_single_correct = QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_single, content_html='Đúng', is_correct=True,
        )
        QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_single, content_html='Sai', is_correct=False,
        )

        self.q_multiple = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.MULTIPLE, stem_html='Q multiple',
        )
        self.opt_m1 = QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_multiple, content_html='A', is_correct=True,
        )
        self.opt_m2 = QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_multiple, content_html='B', is_correct=True,
        )
        QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_multiple, content_html='C', is_correct=False,
        )

        self.q_truefalse = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.TRUEFALSE, stem_html='Q truefalse',
        )
        self.opt_tf_true = QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_truefalse, content_html='Đúng', is_correct=True,
        )
        QuestionOption.objects.create(
            tenant=self.tenant, question=self.q_truefalse, content_html='Sai', is_correct=False,
        )

        self.q_text_fill = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.TEXT_FILL, stem_html='Q text_fill',
            config={'accepted': ['Paris'], 'case_sensitive': False},
        )
        self.q_numeric = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.NUMERIC, stem_html='Q numeric',
            config={'answer': 10, 'tolerance': 0.5},
        )
        self.q_matching = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.MATCHING, stem_html='Q matching',
            config={'pairs': [{'left': 'A', 'right': '1'}, {'left': 'B', 'right': '2'}]},
        )
        self.q_dragdrop = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.DRAGDROP, stem_html='Q dragdrop',
            config={'tokens': ['x', 'y'], 'gaps': [{'id': 1, 'answer': 'x'}, {'id': 2, 'answer': 'y'}]},
        )
        self.q_essay = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.ESSAY, stem_html='Q essay',
        )

        self.questions = [
            self.q_single, self.q_multiple, self.q_truefalse, self.q_text_fill, self.q_numeric,
            self.q_matching, self.q_dragdrop, self.q_essay,
        ]
        self.assessment = Assessment.objects.create(
            tenant=self.tenant, title='Đề kiểm tra tổng hợp', status=Assessment.Status.PUBLISHED,
            max_attempts=1, pass_mark=80, created_by=self.admin,
        )
        for i, q in enumerate(self.questions):
            AssessmentQuestion.objects.create(tenant=self.tenant, assessment=self.assessment, question=q, order=i)

        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        AssessmentAssignment.objects.create(tenant=self.tenant, assessment=self.assessment, employee=self.employee)

        self.client = APIClient()

    def _correct_response(self, question):
        if question.id == self.q_single.id:
            return {'option_id': self.opt_single_correct.id}
        if question.id == self.q_multiple.id:
            return {'option_ids': [self.opt_m1.id, self.opt_m2.id]}
        if question.id == self.q_truefalse.id:
            return {'option_id': self.opt_tf_true.id}
        if question.id == self.q_text_fill.id:
            return {'text': 'paris'}
        if question.id == self.q_numeric.id:
            return {'value': 10.3}
        if question.id == self.q_matching.id:
            return {'pairs': [{'left': 'A', 'right': '1'}, {'left': 'B', 'right': '2'}]}
        if question.id == self.q_dragdrop.id:
            return {'placements': {'1': 'x', '2': 'y'}}
        return {'text': 'Bài làm tự luận của tôi.'}

    def test_full_flow_start_answer_submit_grade(self):
        self.client.force_authenticate(self.learner_user)

        start_resp = self.client.post(reverse('exam-start', args=[self.assessment.id]))
        self.assertEqual(start_resp.status_code, 200)
        attempt_id = start_resp.data['attempt_id']
        self.assertEqual(len(start_resp.data['questions']), 8)
        # khong lo dap an dung ra ngoai
        for q_payload in start_resp.data['questions']:
            if q_payload['type'] in ('single', 'multiple', 'truefalse'):
                for opt in q_payload['options']:
                    self.assertNotIn('is_correct', opt)

        attempt = Attempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.status, Attempt.Status.IN_PROGRESS)
        self.assertEqual(len(attempt.question_ids), 8)

        items = [{'question': q.id, 'response': self._correct_response(q)} for q in self.questions]
        save_resp = self.client.post(
            reverse('exam-attempt-answer', args=[attempt.id]), {'items': items}, format='json',
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertEqual(save_resp.data['saved'], 8)
        self.assertEqual(Answer.objects.filter(attempt=attempt).count(), 8)

        submit_resp = self.client.post(reverse('exam-attempt-submit', args=[attempt.id]))
        self.assertEqual(submit_resp.status_code, 200)
        self.assertEqual(submit_resp.data['status'], Attempt.Status.SUBMITTED)
        self.assertEqual(submit_resp.data['score'], Decimal('7.00'))
        self.assertEqual(submit_resp.data['max_score'], Decimal('8.00'))

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.SUBMITTED)

        # nop lai lan 2 se bi tu choi
        resubmit_resp = self.client.post(reverse('exam-attempt-submit', args=[attempt.id]))
        self.assertEqual(resubmit_resp.status_code, 400)

        # danh sach cham tay hien attempt nay
        self.client.force_authenticate(self.admin)
        grading_resp = self.client.get(reverse('exam-grading'))
        self.assertEqual(len(grading_resp.data), 1)
        self.assertEqual(grading_resp.data[0]['id'], attempt.id)

        grade_resp = self.client.post(
            reverse('exam-attempt-grade', args=[attempt.id]),
            {'scores': {str(self.q_essay.id): 1}}, format='json',
        )
        self.assertEqual(grade_resp.status_code, 200)
        self.assertEqual(grade_resp.data['status'], Attempt.Status.GRADED)
        self.assertEqual(grade_resp.data['score'], Decimal('8.00'))
        self.assertEqual(grade_resp.data['percent'], Decimal('100.00'))
        self.assertTrue(grade_resp.data['passed'])

        assignment = AssessmentAssignment.objects.get(assessment=self.assessment, employee=self.employee)
        self.assertEqual(assignment.status, AssessmentAssignment.Status.DONE)

    def test_max_attempts_enforced(self):
        self.client.force_authenticate(self.learner_user)
        first = self.client.post(reverse('exam-start', args=[self.assessment.id]))
        self.assertEqual(first.status_code, 200)
        # nop luon lan 1 de duoc phep bat dau lan tiep theo (khong con IN_PROGRESS)
        self.client.post(reverse('exam-attempt-submit', args=[first.data['attempt_id']]))

        second = self.client.post(reverse('exam-start', args=[self.assessment.id]))
        self.assertEqual(second.status_code, 400)
        self.assertIn('hết số lần', second.data['detail'])

    def test_start_requires_assignment(self):
        other_user = User.objects.create_user(
            username='nv2', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', user=other_user)
        self.client.force_authenticate(other_user)
        resp = self.client.post(reverse('exam-start', args=[self.assessment.id]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('chưa được gán', resp.data['detail'])

    def test_cannot_start_unpublished_assessment(self):
        self.assessment.status = Assessment.Status.DRAFT
        self.assessment.save(update_fields=['status'])
        self.client.force_authenticate(self.learner_user)
        resp = self.client.post(reverse('exam-start', args=[self.assessment.id]))
        self.assertEqual(resp.status_code, 400)


class AssessmentAssignApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.assessment = Assessment.objects.create(tenant=self.tenant, title='Đề demo')
        self.e1 = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', position='Phục vụ')
        self.e2 = Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', position='Thu ngân')
        self.client = APIClient()

    def test_assign_by_employee_ids(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('exam-assessment-assign', args=[self.assessment.id]),
            {'employee_ids': [self.e1.id, self.e2.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['created'], 2)

    def test_assign_skips_already_assigned(self):
        AssessmentAssignment.objects.create(tenant=self.tenant, assessment=self.assessment, employee=self.e1)
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('exam-assessment-assign', args=[self.assessment.id]),
            {'employee_ids': [self.e1.id, self.e2.id]}, format='json',
        )
        self.assertEqual(resp.data['created'], 1)

    def test_assign_requires_admin(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client.force_authenticate(trainer)
        resp = self.client.post(
            reverse('exam-assessment-assign', args=[self.assessment.id]),
            {'employee_ids': [self.e1.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


class EmployeeLearnerScopeExamsApiTests(TestCase):
    """role='employee' duoc phep goi /api/exams/ (bo sung vao ALLOWED_PREFIXES o Dot 2)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.client = APIClient()

    def test_employee_role_can_call_exams_my(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('exam-my'))
        # 403 vi chua lien ket Employee, khong phai bi EmployeeLearnerScope chan truoc do
        self.assertEqual(resp.status_code, 403)
        self.assertIn('hồ sơ nhân sự', resp.data['detail'])

    def test_employee_role_blocked_from_employees_endpoint(self):
        self.client.force_authenticate(self.learner_user)
        resp = self.client.get(reverse('employee-list'))
        self.assertEqual(resp.status_code, 403)


class ExamHookTests(TestCase):
    """Dot 3 phan A/C: bat dau/nop/dat/khong dat bai thi phai sinh XapiStatement dung verb, va
    CHI dong bo ExamResult khi THAT SU dat (dung trigger cua prompt: 'graded & passed')."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')
        self.question = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.SINGLE, stem_html='Q1',
        )
        self.correct_opt = QuestionOption.objects.create(
            tenant=self.tenant, question=self.question, content_html='Đúng', is_correct=True,
        )
        QuestionOption.objects.create(tenant=self.tenant, question=self.question, content_html='Sai')
        self.assessment = Assessment.objects.create(
            tenant=self.tenant, title='Đề 1 câu', status=Assessment.Status.PUBLISHED,
            sync_exam_type='15N', pass_mark=80,
        )
        AssessmentQuestion.objects.create(tenant=self.tenant, assessment=self.assessment, question=self.question)
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        AssessmentAssignment.objects.create(tenant=self.tenant, assessment=self.assessment, employee=self.employee)
        self.client = APIClient()

    def _start(self):
        self.client.force_authenticate(self.learner_user)
        return self.client.post(reverse('exam-start', args=[self.assessment.id])).data['attempt_id']

    def test_start_logs_started_xapi(self):
        self._start()
        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='started', object_type='assessment', object_id=self.assessment.id,
            ).exists()
        )

    def test_pass_logs_passed_xapi_and_syncs_exam_result(self):
        attempt_id = self._start()
        self.client.post(
            reverse('exam-attempt-answer', args=[attempt_id]),
            {'question': self.question.id, 'response': {'option_id': self.correct_opt.id}}, format='json',
        )
        self.client.post(reverse('exam-attempt-submit', args=[attempt_id]))

        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='passed', object_type='assessment', object_id=self.assessment.id,
            ).exists()
        )
        result = ExamResult.objects.get(employee=self.employee, exam_name='15N')
        self.assertTrue(result.passed)
        self.assertEqual(result.source, 'internal_lms')

    def test_fail_logs_failed_xapi_and_does_not_sync(self):
        attempt_id = self._start()
        wrong_opt = self.question.options.exclude(id=self.correct_opt.id).first()
        self.client.post(
            reverse('exam-attempt-answer', args=[attempt_id]),
            {'question': self.question.id, 'response': {'option_id': wrong_opt.id}}, format='json',
        )
        self.client.post(reverse('exam-attempt-submit', args=[attempt_id]))

        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='failed', object_type='assessment', object_id=self.assessment.id,
            ).exists()
        )
        # KHONG dat -> KHONG dong bo (dung trigger 'graded & passed' cua prompt)
        self.assertFalse(ExamResult.objects.filter(employee=self.employee, exam_name='15N').exists())


class ExamEssayHookTests(TestCase):
    """Bai co essay: xAPI/dong bo CHI ban hanh khi cham tay xong (GRADED that su), khong phai
    luc nop (van con SUBMITTED cho cham)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank demo')
        self.question = Question.objects.create(
            tenant=self.tenant, bank=self.bank, type=Question.Type.ESSAY, stem_html='Q1', points=10,
        )
        self.assessment = Assessment.objects.create(
            tenant=self.tenant, title='Đề tự luận', status=Assessment.Status.PUBLISHED,
            sync_exam_type='ESSAY1', pass_mark=80,
        )
        AssessmentQuestion.objects.create(tenant=self.tenant, assessment=self.assessment, question=self.question)
        self.learner_user = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=self.learner_user)
        AssessmentAssignment.objects.create(tenant=self.tenant, assessment=self.assessment, employee=self.employee)
        self.client = APIClient()

    def test_no_finalize_until_manual_grade_then_finalizes(self):
        self.client.force_authenticate(self.learner_user)
        attempt_id = self.client.post(reverse('exam-start', args=[self.assessment.id])).data['attempt_id']
        self.client.post(
            reverse('exam-attempt-answer', args=[attempt_id]),
            {'question': self.question.id, 'response': {'text': 'Bài làm của tôi'}}, format='json',
        )
        self.client.post(reverse('exam-attempt-submit', args=[attempt_id]))

        self.assertFalse(XapiStatement.objects.filter(employee=self.employee, verb__in=['passed', 'failed']).exists())
        self.assertFalse(ExamResult.objects.filter(employee=self.employee, exam_name='ESSAY1').exists())

        self.client.force_authenticate(self.admin)
        self.client.post(
            reverse('exam-attempt-grade', args=[attempt_id]),
            {'scores': {str(self.question.id): 9}}, format='json',
        )

        self.assertTrue(
            XapiStatement.objects.filter(
                employee=self.employee, verb='passed', object_type='assessment', object_id=self.assessment.id,
            ).exists()
        )
        self.assertTrue(ExamResult.objects.filter(employee=self.employee, exam_name='ESSAY1', passed=True).exists())
