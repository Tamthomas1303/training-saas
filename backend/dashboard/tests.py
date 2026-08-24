from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from checklist.models import Checklist, TrainingProgress
from cls_sync.models import ExamResult
from courses.models import Course, CourseModule, Enrollment, Lesson, LessonProgress
from employees.models import Employee
from evaluation.models import Evaluation, EvaluationCriteria, EvaluationDetail
from exams.models import Assessment, Attempt
from kpi.services import kpi_bql_report_data
from restaurants.models import Restaurant

from .models import (
    ClsExamCompetencyMap,
    CompetencyGroup,
    Competency,
    CompetencyScoreSnapshot,
    CompetencyScoringConfig,
    CompetencySnapshot,
    DashboardIndicator,
    PositionGroupWeight,
    PositionTarget,
    TrainingCost,
    TrainingCostSource,
)
from .services import (
    ValidationError,
    _competency_aggregate_from_snapshot,
    compute_aggregate_dashboard,
    compute_competency_scores,
    competency_gaps,
    cost_per_passed_employee,
    employee_360,
    get_scoring_weights,
    import_position_group_weights,
    import_position_targets,
    import_training_costs,
    indicator_color,
    refresh_competency_snapshots,
    resolve_position,
    seed_competency_framework,
    seed_dashboard_indicators,
    sync_training_costs,
    training_cost_total,
)

# Mau CSV thuc te (trich tu KhungNangLuc_MucTieu_TheoViTri_v0.5.xlsx, xuat CSV) - dung y he
# BOM utf-8-sig + dau '·' nhu file that.
SAMPLE_TARGETS_CSV = (
    '﻿Nhóm,Năng lực,ĐIỂM MỤC TIÊU THEO VỊ TRÍ (0–100),,\r\n'
    ',,TTS / Phụ bếp,Bếp trưởng\r\n'
    'AT · An toàn & Tuân thủ,An toàn thực phẩm & vệ sinh (HACCP/5S),72,88\r\n'
    'A1 · Chuyên môn Bếp,Sơ chế & bảo quản nguyên liệu,65,89\r\n'
    'B · Kỹ năng mềm,Giao tiếp,58,80\r\n'
    'D · Quản lý,Điều phối ca & phân công,—,83\r\n'
)

SAMPLE_WEIGHTS_CSV = (
    '﻿Vị trí,An toàn & Tuân thủ (AT),Chuyên môn (A),Kỹ năng mềm (B),Thái độ (C),Quản lý (D),TỔNG\r\n'
    'TTS / Phụ bếp,0.15,0.45,0.15,0.25,0,1\r\n'
    'Bếp trưởng,0.1,0.3,0.15,0.15,0.3,1\r\n'
)

# Bien the CSV trong so voi gia tri dinh dang '%' (Excel xuat tu o dinh dang phan tram) - tai
# hien dung loi thuc te lam PositionGroupWeight rong toan bo truoc khi sua _parse_number.
SAMPLE_WEIGHTS_CSV_PERCENT = (
    '﻿Vị trí,An toàn & Tuân thủ (AT),Chuyên môn (A),Kỹ năng mềm (B),Thái độ (C),Quản lý (D),TỔNG\r\n'
    'TTS / Phụ bếp,15%,45%,15%,25%,0%,100%\r\n'
)

# CSV "trong so nhom" bi doc lech qua importer muc tieu (dung nguyen nhan Loi 1 trong prompt):
# moi dong la 1 VI TRI (khong phai nhom nang luc) - importer muc tieu phai BO QUA, KHONG tao
# CompetencyGroup "Bếp thớt"/"Bếp chảo" tu day.
MISROUTED_WEIGHTS_AS_TARGETS_CSV = (
    '﻿Nhóm,Năng lực,ĐIỂM MỤC TIÊU THEO VỊ TRÍ (0–100),\r\n'
    ',,X,\r\n'
    'Bếp thớt,15%,1,\r\n'
    'Bếp chảo,15%,1,\r\n'
)


class SeedCompetencyFrameworkTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_creates_6_groups_24_competencies(self):
        result = seed_competency_framework(self.tenant)
        self.assertEqual(result['groups_created'], 6)
        self.assertEqual(result['competencies_created'], 24)
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)

    def test_idempotent(self):
        seed_competency_framework(self.tenant)
        result = seed_competency_framework(self.tenant)
        self.assertEqual(result['groups_created'], 0)
        self.assertEqual(result['competencies_created'], 0)
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)


class ImportPositionTargetsTests(TestCase):
    """Importer muc tieu PHAI khop vao khung nang luc da co (khong tao nhom/nang luc moi) -
    Prompt_Fix_ImportKhungNangLuc.md, Loi 2."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        seed_competency_framework(self.tenant)

    def test_imports_targets_matches_existing_framework_no_creation(self):
        result = import_position_targets(self.tenant, SAMPLE_TARGETS_CSV)
        self.assertEqual(result['positions'], 2)
        # 3 dong co gia tri that (AT, A1, B) x 2 vi tri = 6; dong D chi co 1 gia tri (Bep truong,
        # TTS/Phu bep la '—' bo qua) = 1. Tong = 7.
        self.assertEqual(result['targets_written'], 7)
        # Khung khong doi: van 6 nhom / 24 nang luc, khong tao them gi.
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)

        group_at = CompetencyGroup.objects.get(tenant=self.tenant, code='AT')
        comp = Competency.objects.get(tenant=self.tenant, group=group_at, name='An toàn thực phẩm & vệ sinh (HACCP/5S)')
        target = PositionTarget.objects.get(tenant=self.tenant, position='TTS / Phụ bếp', competency=comp)
        self.assertEqual(target.target_score, 72)
        target2 = PositionTarget.objects.get(tenant=self.tenant, position='Bếp trưởng', competency=comp)
        self.assertEqual(target2.target_score, 88)

    def test_dash_value_skipped(self):
        import_position_targets(self.tenant, SAMPLE_TARGETS_CSV)
        group_d = CompetencyGroup.objects.get(tenant=self.tenant, code='D')
        comp = Competency.objects.get(tenant=self.tenant, group=group_d, name='Điều phối ca & phân công')
        self.assertFalse(PositionTarget.objects.filter(tenant=self.tenant, position='TTS / Phụ bếp', competency=comp).exists())
        self.assertTrue(PositionTarget.objects.filter(tenant=self.tenant, position='Bếp trưởng', competency=comp).exists())

    def test_reimport_updates_not_duplicates(self):
        import_position_targets(self.tenant, SAMPLE_TARGETS_CSV)
        import_position_targets(self.tenant, SAMPLE_TARGETS_CSV)
        self.assertEqual(PositionTarget.objects.filter(tenant=self.tenant).count(), 7)
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)

    def test_too_short_file_raises(self):
        with self.assertRaises(ValidationError):
            import_position_targets(self.tenant, 'chỉ 1 dòng')

    def test_unknown_group_row_skipped_no_group_created(self):
        """Tai hien dung Loi 1 that xay ra: file trong so nhom (moi dong la 1 VI TRI) bi nap
        nham qua importer muc tieu -> phai bo qua + canh bao, KHONG tao nhom 'Bếp thớt'/'Bếp
        chảo'."""
        result = import_position_targets(self.tenant, MISROUTED_WEIGHTS_AS_TARGETS_CSV)
        self.assertEqual(result['targets_written'], 0)
        self.assertTrue(result['warnings'])
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertFalse(CompetencyGroup.objects.filter(tenant=self.tenant, code__in=['Bếp thớt', 'Bếp chảo']).exists())

    def test_unknown_competency_name_skipped_no_duplicate(self):
        csv_text = (
            '﻿Nhóm,Năng lực,ĐIỂM MỤC TIÊU THEO VỊ TRÍ (0–100),\r\n'
            ',,TTS / Phụ bếp,\r\n'
            'AT · An toàn & Tuân thủ,Năng lực lạ không có trong khung,72,\r\n'
        )
        result = import_position_targets(self.tenant, csv_text)
        self.assertEqual(result['targets_written'], 0)
        self.assertTrue(result['warnings'])
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)

    def test_matches_competency_by_normalized_name_variant(self):
        """Ten trong file lech chut it (hoa/thuong, khoang trang, hau to '(upsell)') voi ten da
        seed van phai khop vao CUNG 1 Competency, khong tao ban trung (Loi 2)."""
        csv_text = (
            '﻿Nhóm,Năng lực,ĐIỂM MỤC TIÊU THEO VỊ TRÍ (0–100),\r\n'
            ',,NV Phục vụ,\r\n'
            'A2 · Chuyên môn Phục vụ,kiến thức món & đồ uống/menu   (upsell),85,\r\n'
        )
        before = Competency.objects.filter(tenant=self.tenant).count()
        result = import_position_targets(self.tenant, csv_text)
        self.assertEqual(result['targets_written'], 1)
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), before)
        comp = Competency.objects.get(
            tenant=self.tenant, group__code='A2', name='Kiến thức món & đồ uống / menu (upsell)',
        )
        self.assertTrue(PositionTarget.objects.filter(tenant=self.tenant, position='NV Phục vụ', competency=comp, target_score=85).exists())


class ImportPositionGroupWeightsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        seed_competency_framework(self.tenant)

    def test_imports_weights_duplicates_combined_a_into_a1_a2(self):
        result = import_position_group_weights(self.tenant, SAMPLE_WEIGHTS_CSV)
        # 5 cot (AT, A->A1+A2, B, C, D) x 2 vi tri = 12 dong ghi (A tach thanh 2).
        self.assertEqual(result['weights_written'], 12)

        a1 = CompetencyGroup.objects.get(tenant=self.tenant, code='A1')
        a2 = CompetencyGroup.objects.get(tenant=self.tenant, code='A2')
        w1 = PositionGroupWeight.objects.get(tenant=self.tenant, position='TTS / Phụ bếp', group=a1)
        w2 = PositionGroupWeight.objects.get(tenant=self.tenant, position='TTS / Phụ bếp', group=a2)
        self.assertEqual(w1.weight, Decimal('45.00'))
        self.assertEqual(w2.weight, Decimal('45.00'))

        at = CompetencyGroup.objects.get(tenant=self.tenant, code='AT')
        w_at = PositionGroupWeight.objects.get(tenant=self.tenant, position='Bếp trưởng', group=at)
        self.assertEqual(w_at.weight, Decimal('10.00'))

    def test_percent_formatted_values_parsed(self):
        """Excel xuat CSV tu o dinh dang % ('15%') - truoc khi sua _parse_number, gia tri nay bi
        bo qua toan bo (float('15%') loi) khien PositionGroupWeight rong (nguyen nhan that cua
        Loi 1/Loi 3 tren production)."""
        result = import_position_group_weights(self.tenant, SAMPLE_WEIGHTS_CSV_PERCENT)
        self.assertEqual(result['weights_written'], 6)  # AT, A->A1+A2, B, C, D (1 vi tri x 6, A tach 2)
        at = CompetencyGroup.objects.get(tenant=self.tenant, code='AT')
        w_at = PositionGroupWeight.objects.get(tenant=self.tenant, position='TTS / Phụ bếp', group=at)
        self.assertEqual(w_at.weight, Decimal('15.00'))
        a1 = CompetencyGroup.objects.get(tenant=self.tenant, code='A1')
        w_a1 = PositionGroupWeight.objects.get(tenant=self.tenant, position='TTS / Phụ bếp', group=a1)
        self.assertEqual(w_a1.weight, Decimal('45.00'))

    def test_unknown_group_code_skipped_no_group_created(self):
        csv_text = (
            '﻿Vị trí,An toàn & Tuân thủ (AT),Ngoại ngữ (Z),TỔNG\r\n'
            'TTS / Phụ bếp,0.15,0.2,1\r\n'
        )
        result = import_position_group_weights(self.tenant, csv_text)
        self.assertTrue(result['warnings'])
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertFalse(CompetencyGroup.objects.filter(tenant=self.tenant, code='Z').exists())


class ComputeCompetencyScoresTests(TestCase):
    """Test B (Phan A muc 3/7): engine tinh diem nang luc - co nguon / khong nguon (N/A) /
    nhieu nguon trung binh / gap so muc tieu."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='NV Phục vụ',
        )
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp_a = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        self.comp_b = Competency.objects.create(tenant=self.tenant, group=self.group, name='Xử lý order & POS')
        PositionTarget.objects.create(tenant=self.tenant, position='NV Phục vụ', competency=self.comp_a, target_score=80)
        PositionGroupWeight.objects.create(tenant=self.tenant, position='NV Phục vụ', group=self.group, weight=Decimal('100'))

    def test_competency_without_source_is_na_not_zero(self):
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertIsNone(comp_result['score'])
        self.assertIsNone(comp_result['gap'])
        self.assertIsNone(scores['ci'])  # khong nhom nao co du lieu -> CI cung N/A

    def test_course_source_completed_gives_100(self):
        course = Course.objects.create(tenant=self.tenant, title='Khóa phục vụ', competency=self.comp_a)
        Enrollment.objects.create(
            tenant=self.tenant, course=course, employee=self.employee, status=Enrollment.Status.COMPLETED,
        )
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['score'], 100.0)
        self.assertEqual(comp_result['target'], 80)
        self.assertEqual(comp_result['gap'], -20.0)  # vuot muc tieu -> gap am, khong hien trong bang gap

    def test_course_source_in_progress_gives_partial_percent(self):
        course = Course.objects.create(tenant=self.tenant, title='Khóa phục vụ', competency=self.comp_a)
        module = CourseModule.objects.create(tenant=self.tenant, course=course, title='Chương 1')
        lesson1 = Lesson.objects.create(tenant=self.tenant, module=module, title='Bài 1', order=0)
        Lesson.objects.create(tenant=self.tenant, module=module, title='Bài 2', order=1)
        enrollment = Enrollment.objects.create(
            tenant=self.tenant, course=course, employee=self.employee, status=Enrollment.Status.IN_PROGRESS,
        )
        LessonProgress.objects.create(
            tenant=self.tenant, enrollment=enrollment, lesson=lesson1, status=LessonProgress.Status.DONE,
        )
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['score'], 50.0)  # 1/2 bai
        self.assertEqual(comp_result['gap'], 30.0)  # thieu 30 diem so voi muc tieu 80

    def test_exam_source_score(self):
        assessment = Assessment.objects.create(tenant=self.tenant, title='Đề phục vụ', competency=self.comp_a)
        Attempt.objects.create(
            tenant=self.tenant, assessment=assessment, employee=self.employee, attempt_no=1,
            status=Attempt.Status.GRADED, percent=Decimal('90.00'),
        )
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['score'], 90.0)

    def test_skill_evaluation_source_score(self):
        criteria = EvaluationCriteria.objects.create(
            tenant=self.tenant, content='Phục vụ chuẩn', max_score=100, competency=self.comp_a,
        )
        evaluation = Evaluation.objects.create(
            tenant=self.tenant, employee=self.employee, eval_type='Skill_BQL', status=Evaluation.Status.DONE,
        )
        EvaluationDetail.objects.create(
            tenant=self.tenant, evaluation=evaluation, criteria_id=str(criteria.id),
            content=criteria.content, max_score=100, score=Decimal('70'),
        )
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['score'], 70.0)

    def test_multiple_sources_averaged(self):
        course = Course.objects.create(tenant=self.tenant, title='Khóa phục vụ', competency=self.comp_a)
        Enrollment.objects.create(
            tenant=self.tenant, course=course, employee=self.employee, status=Enrollment.Status.COMPLETED,
        )
        assessment = Assessment.objects.create(tenant=self.tenant, title='Đề phục vụ', competency=self.comp_a)
        Attempt.objects.create(
            tenant=self.tenant, assessment=assessment, employee=self.employee, attempt_no=1,
            status=Attempt.Status.GRADED, percent=Decimal('60.00'),
        )
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['score'], 80.0)  # (100 + 60) / 2

    def test_group_score_only_averages_competencies_with_data(self):
        course = Course.objects.create(tenant=self.tenant, title='Khóa phục vụ', competency=self.comp_a)
        Enrollment.objects.create(
            tenant=self.tenant, course=course, employee=self.employee, status=Enrollment.Status.COMPLETED,
        )
        # comp_b khong co nguon -> khong duoc tinh vao trung binh nhom (chi comp_a).
        scores = compute_competency_scores(self.employee)
        group_result = next(g for g in scores['groups'] if g['id'] == self.group.id)
        self.assertEqual(group_result['score'], 100.0)
        self.assertEqual(scores['ci'], 100.0)

    def test_target_matched_despite_position_case_and_spacing_mismatch(self):
        """Prompt_Fix_ImportKhungNangLuc.md, Loi 3: Employee.position ghi khac hoa/thuong/
        khoang trang so voi PositionTarget/PositionGroupWeight da import van phai khop duoc
        (deburr) de radar co duong 'Muc tieu'."""
        self.employee.position = '  nv   phục vụ '
        self.employee.save(update_fields=['position'])
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp_a.id)
        self.assertEqual(comp_result['target'], 80)
        group_result = next(g for g in scores['groups'] if g['id'] == self.group.id)
        self.assertEqual(group_result['weight'], 100.0)


class ResolvePositionTests(TestCase):
    def test_matches_ignoring_case_diacritics_and_spacing(self):
        values = ['NV Phục vụ', 'Bếp trưởng']
        self.assertEqual(resolve_position(values, 'nv   phuc vu'), 'NV Phục vụ')
        self.assertEqual(resolve_position(values, 'BẾP TRƯỞNG'), 'Bếp trưởng')

    def test_no_match_returns_none(self):
        self.assertIsNone(resolve_position(['NV Phục vụ'], 'Quản lý vùng'))

    def test_empty_input_returns_none(self):
        self.assertIsNone(resolve_position(['NV Phục vụ'], ''))


class ScoringWeightsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_default_50_50_when_not_configured(self):
        self.assertEqual(get_scoring_weights(self.tenant), (50.0, 50.0))

    def test_reads_configured_weights(self):
        CompetencyScoringConfig.objects.create(
            tenant=self.tenant, theory_weight=Decimal('30'), practice_weight=Decimal('70'),
        )
        self.assertEqual(get_scoring_weights(self.tenant), (30.0, 70.0))


class EngineFourSourcesTests(TestCase):
    """Prompt_Dashboard_A1_GanNhanNangLuc.md: engine cong don 4 nguon (khoa hoc + thi noi bo/CLS
    = khoi Ly thuyet; checklist + danh gia ky nang = khoi Thuc hanh), trong so LT/TH cau hinh
    duoc theo tenant."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='NV Phục vụ', restaurant=self.restaurant,
        )
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        PositionTarget.objects.create(tenant=self.tenant, position='NV Phục vụ', competency=self.comp, target_score=80)
        PositionGroupWeight.objects.create(tenant=self.tenant, position='NV Phục vụ', group=self.group, weight=Decimal('100'))

    def test_checklist_source_only_contributes_to_practice(self):
        c1 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 1', brand='KMP', position='Phục vụ', competency=self.comp)
        c2 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 2', brand='KMP', position='Phục vụ', competency=self.comp)
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=c1, status=TrainingProgress.Status.DONE)
        # c2 chua lam -> tinh nhu 0, keo trung binh Thuc hanh xuong 50.

        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp.id)
        self.assertEqual(comp_result['practice_score'], 50.0)
        self.assertIsNone(comp_result['theory_score'])
        self.assertEqual(comp_result['score'], 50.0)  # chi co Thuc hanh -> diem = diem Thuc hanh

    def test_cls_exam_source_only_contributes_to_theory(self):
        ClsExamCompetencyMap.objects.create(tenant=self.tenant, exam_name='15N', competency=self.comp)
        ExamResult.objects.create(tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1, score=Decimal('88'))

        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp.id)
        self.assertEqual(comp_result['theory_score'], 88.0)
        self.assertIsNone(comp_result['practice_score'])
        self.assertEqual(comp_result['score'], 88.0)

    def test_unmapped_cls_exam_is_ignored(self):
        # Khong tao ClsExamCompetencyMap cho 'UNMAPPED' -> bai thi nay khong duoc tinh, khong doan.
        ExamResult.objects.create(tenant=self.tenant, employee=self.employee, exam_name='UNMAPPED', attempt=1, score=Decimal('99'))

        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp.id)
        self.assertIsNone(comp_result['score'])

    def test_combines_theory_and_practice_with_default_weights(self):
        ClsExamCompetencyMap.objects.create(tenant=self.tenant, exam_name='15N', competency=self.comp)
        ExamResult.objects.create(tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1, score=Decimal('80'))
        c1 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 1', brand='KMP', position='Phục vụ', competency=self.comp)
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=c1, status=TrainingProgress.Status.DONE)

        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp.id)
        self.assertEqual(comp_result['theory_score'], 80.0)
        self.assertEqual(comp_result['practice_score'], 100.0)
        self.assertEqual(comp_result['score'], 90.0)  # mac dinh 50/50 -> (80+100)/2

    def test_changing_tenant_weight_changes_score(self):
        ClsExamCompetencyMap.objects.create(tenant=self.tenant, exam_name='15N', competency=self.comp)
        ExamResult.objects.create(tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1, score=Decimal('80'))
        c1 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 1', brand='KMP', position='Phục vụ', competency=self.comp)
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=c1, status=TrainingProgress.Status.DONE)

        CompetencyScoringConfig.objects.create(tenant=self.tenant, theory_weight=Decimal('20'), practice_weight=Decimal('80'))
        scores = compute_competency_scores(self.employee)
        comp_result = next(c for c in scores['competencies'] if c['id'] == self.comp.id)
        self.assertEqual(comp_result['score'], 96.0)  # 0.2*80 + 0.8*100 = 96


class CompetencyGapsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', position='NV Phục vụ')
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        PositionTarget.objects.create(tenant=self.tenant, position='NV Phục vụ', competency=self.comp, target_score=90)

    def test_gap_suggests_uncompleted_course_with_same_competency(self):
        course_done = Course.objects.create(tenant=self.tenant, title='Khóa đã xong', competency=self.comp)
        Enrollment.objects.create(
            tenant=self.tenant, course=course_done, employee=self.employee, status=Enrollment.Status.COMPLETED,
        )
        course_todo = Course.objects.create(tenant=self.tenant, title='Khóa nâng cao', competency=self.comp)

        # Diem hien tai = 100 (da hoan thanh course_done) nhung muc tieu 90 -> khong con gap.
        # Ha diem bang cach them 1 khoa dang do de trung binh < 90.
        course_partial = Course.objects.create(tenant=self.tenant, title='Khóa dở dang', competency=self.comp)
        module = CourseModule.objects.create(tenant=self.tenant, course=course_partial, title='Chương 1')
        Lesson.objects.create(tenant=self.tenant, module=module, title='Bài 1', order=0)
        Enrollment.objects.create(
            tenant=self.tenant, course=course_partial, employee=self.employee, status=Enrollment.Status.IN_PROGRESS,
        )

        gaps = competency_gaps(self.employee)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]['id'], self.comp.id)
        suggested_ids = {c['id'] for c in gaps[0]['suggested_courses']}
        self.assertIn(course_todo.id, suggested_ids)
        self.assertNotIn(course_done.id, suggested_ids)  # da hoan thanh, khong goi y lai

    def test_gap_suggests_undone_checklist_item(self):
        """Prompt_Dashboard_A1_GanNhanNangLuc.md muc 3: goi y checklist chua hoan thanh gan
        nang luc dang thieu, khong goi y lai muc da xong."""
        restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')
        self.employee.restaurant = restaurant
        self.employee.save(update_fields=['restaurant'])

        done_item = Checklist.objects.create(tenant=self.tenant, task_name='Đã xong', brand='KMP', position='Phục vụ', competency=self.comp)
        todo_item = Checklist.objects.create(tenant=self.tenant, task_name='Chưa xong', brand='KMP', position='Phục vụ', competency=self.comp)
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=done_item, status=TrainingProgress.Status.DONE)

        gaps = competency_gaps(self.employee)
        self.assertEqual(len(gaps), 1)
        suggested_ids = {c['id'] for c in gaps[0]['suggested_checklist']}
        self.assertIn(todo_item.id, suggested_ids)
        self.assertNotIn(done_item.id, suggested_ids)


class IndicatorColorTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_higher_better(self):
        ind = DashboardIndicator.objects.create(
            tenant=self.tenant, key='k1', label='L1', direction=DashboardIndicator.Direction.HIGHER_BETTER,
            green_threshold=90, yellow_threshold=80,
        )
        self.assertEqual(indicator_color(ind, 95), 'green')
        self.assertEqual(indicator_color(ind, 85), 'yellow')
        self.assertEqual(indicator_color(ind, 70), 'red')

    def test_lower_better(self):
        ind = DashboardIndicator.objects.create(
            tenant=self.tenant, key='k2', label='L2', direction=DashboardIndicator.Direction.LOWER_BETTER,
            green_threshold=10, yellow_threshold=20,
        )
        self.assertEqual(indicator_color(ind, 5), 'green')
        self.assertEqual(indicator_color(ind, 15), 'yellow')
        self.assertEqual(indicator_color(ind, 30), 'red')

    def test_no_threshold_or_none_direction_returns_none(self):
        ind = DashboardIndicator.objects.create(
            tenant=self.tenant, key='k3', label='L3', direction=DashboardIndicator.Direction.NONE,
        )
        self.assertIsNone(indicator_color(ind, 50))
        ind2 = DashboardIndicator.objects.create(
            tenant=self.tenant, key='k4', label='L4', direction=DashboardIndicator.Direction.HIGHER_BETTER,
        )
        self.assertIsNone(indicator_color(ind2, 50))

    def test_none_value_returns_none(self):
        ind = DashboardIndicator.objects.create(
            tenant=self.tenant, key='k5', label='L5', direction=DashboardIndicator.Direction.HIGHER_BETTER,
            green_threshold=90, yellow_threshold=80,
        )
        self.assertIsNone(indicator_color(ind, None))


class SeedDashboardIndicatorsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_seeds_selected_indicators(self):
        result = seed_dashboard_indicators(self.tenant)
        # Danh sach seed CHI gom cac dong CHỌN='x' trong ChiSo_Dashboard_ChonLua_v0.2.xlsx (29
        # / 34 dong - 5 dong khong chon nhu 'Phễu onboarding', 'Tỷ lệ thi lại' bi loai).
        self.assertEqual(result['indicators_created'], 29)
        self.assertEqual(DashboardIndicator.objects.filter(tenant=self.tenant).count(), 29)
        self.assertTrue(DashboardIndicator.objects.filter(tenant=self.tenant, key='ci_tong_hop').exists())

    def test_idempotent_does_not_overwrite_admin_changes(self):
        seed_dashboard_indicators(self.tenant)
        ind = DashboardIndicator.objects.get(tenant=self.tenant, key='ci_tong_hop')
        ind.enabled = False
        ind.green_threshold = 95
        ind.save()
        seed_dashboard_indicators(self.tenant)
        ind.refresh_from_db()
        self.assertFalse(ind.enabled)
        self.assertEqual(ind.green_threshold, 95)


class Employee360ApiTests(TestCase):
    """Test C (Phan A muc 4/7): API Ho so 360 + bat/tat chi so."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='Nguyễn Văn A', position='NV Phục vụ',
        )
        seed_competency_framework(self.tenant)
        seed_dashboard_indicators(self.tenant)
        self.client = APIClient()

    def test_admin_can_view_360_by_id(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-employee-360', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['employee']['code'], 'NV1')
        self.assertIn('competencies', resp.data)
        self.assertIn('indicators', resp.data)

    def test_view_by_code(self):
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('dashboard-employee-360', args=['NV1']))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['employee']['id'], self.employee.id)

    def test_not_found(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-employee-360', args=['KHONGTONTAI']))
        self.assertEqual(resp.status_code, 404)

    def test_trainer_role_blocked(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.get(reverse('dashboard-employee-360', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 403)

    def test_search_employees(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-employee-search'), {'q': 'Nguyễn'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['code'], 'NV1')

    def test_disabled_indicator_is_excluded_from_360(self):
        ind = DashboardIndicator.objects.get(tenant=self.tenant, key='ci_tong_hop')
        self.client.force_authenticate(self.admin)

        resp = self.client.get(reverse('dashboard-employee-360', args=[self.employee.id]))
        self.assertTrue(any(i['key'] == 'ci_tong_hop' for i in resp.data['indicators']))

        patch_resp = self.client.patch(
            reverse('dashboard-indicator-detail', args=[ind.id]), {'enabled': False}, format='json',
        )
        self.assertEqual(patch_resp.status_code, 200)

        resp2 = self.client.get(reverse('dashboard-employee-360', args=[self.employee.id]))
        self.assertFalse(any(i['key'] == 'ci_tong_hop' for i in resp2.data['indicators']))

    def test_pending_indicator_marked_when_no_data(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-employee-360', args=[self.employee.id]))
        ci_indicator = next(i for i in resp.data['indicators'] if i['key'] == 'ci_tong_hop')
        self.assertTrue(ci_indicator['pending'])
        self.assertIsNone(ci_indicator['value'])

    def test_non_admin_cannot_toggle_indicator(self):
        ind = DashboardIndicator.objects.get(tenant=self.tenant, key='ci_tong_hop')
        self.client.force_authenticate(self.om)
        resp = self.client.patch(
            reverse('dashboard-indicator-detail', args=[ind.id]), {'enabled': False}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


class CompetencyFrameworkCrudApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_admin_creates_group_and_competency(self):
        self.client.force_authenticate(self.admin)
        g_resp = self.client.post(reverse('competency-group-list'), {'code': 'X', 'name': 'Nhóm X', 'order': 0})
        self.assertEqual(g_resp.status_code, 201)
        c_resp = self.client.post(
            reverse('competency-list'), {'group': g_resp.data['id'], 'name': 'Năng lực X', 'order': 0},
        )
        self.assertEqual(c_resp.status_code, 201)

    def test_non_admin_cannot_write(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('competency-group-list'), {'code': 'X', 'name': 'Nhóm X'})
        self.assertEqual(resp.status_code, 403)

    def test_import_csv_endpoints_admin_only(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(self.trainer)
        f = SimpleUploadedFile('targets.csv', SAMPLE_TARGETS_CSV.encode('utf-8'), content_type='text/csv')
        resp = self.client.post(reverse('dashboard-import-targets'), {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_import_targets_via_api(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        seed_competency_framework(self.tenant)
        self.client.force_authenticate(self.admin)
        f = SimpleUploadedFile('targets.csv', SAMPLE_TARGETS_CSV.encode('utf-8'), content_type='text/csv')
        resp = self.client.post(reverse('dashboard-import-targets'), {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['targets_written'], 7)

    def test_seed_defaults_via_api(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('dashboard-seed-defaults'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['groups_created'], 6)
        self.assertEqual(resp.data['indicators_created'], 29)


class PositionLookupNormalizedTests(TestCase):
    """'Xem cấu hình theo vị trí' phai khop du go sai hoa/thuong/dau cach so voi du lieu da
    import (Prompt_Fix_ImportKhungNangLuc.md, Loi 3)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        seed_competency_framework(self.tenant)
        import_position_targets(self.tenant, SAMPLE_TARGETS_CSV)
        import_position_group_weights(self.tenant, SAMPLE_WEIGHTS_CSV)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_position_targets_matches_case_and_spacing_variant(self):
        resp = self.client.get(reverse('position-target-list'), {'position': '  tts / phụ bếp  '})
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 0)
        self.assertTrue(all(r['position'] == 'TTS / Phụ bếp' for r in resp.data['results']))

    def test_position_weights_matches_diacritic_variant(self):
        resp = self.client.get(reverse('position-weight-list'), {'position': 'bep truong'})
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.data['count'], 0)
        self.assertTrue(all(r['position'] == 'Bếp trưởng' for r in resp.data['results']))

    def test_unknown_position_returns_empty(self):
        resp = self.client.get(reverse('position-target-list'), {'position': 'Vị trí không tồn tại'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)


class CleanupCompetencyDataCommandTests(TestCase):
    """Lenh don rac + gop trung (Prompt_Fix_ImportKhungNangLuc.md) - idempotent."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        seed_competency_framework(self.tenant)

    def test_removes_stray_group_created_by_misrouted_import(self):
        rac_group = CompetencyGroup.objects.create(tenant=self.tenant, code='Bếp thớt', name='Bếp thớt')
        Competency.objects.create(tenant=self.tenant, group=rac_group, name='15%')

        call_command('cleanup_competency_data', tenant='Demo Tenant')

        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertFalse(CompetencyGroup.objects.filter(tenant=self.tenant, code='Bếp thớt').exists())
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)

    def test_merges_duplicate_competency_and_reassigns_targets(self):
        """Ban ghi giu lai la ban co NHIEU PositionTarget hon (uu tien du lieu that da import,
        dung nhu tinh huong that tren production: id co 9 PositionTarget duoc giu, ban 0 target
        bi xoa) - khong dua theo ten nao 'dung chinh ta' hon."""
        a2 = CompetencyGroup.objects.get(tenant=self.tenant, code='A2')
        keeper = Competency.objects.get(tenant=self.tenant, group=a2, name='Kiến thức món & đồ uống / menu (upsell)')
        dupe = Competency.objects.create(tenant=self.tenant, group=a2, name='Kiến thức món & đồ uống/menu')
        PositionTarget.objects.create(tenant=self.tenant, position='Bếp trưởng', competency=keeper, target_score=90)
        PositionTarget.objects.create(tenant=self.tenant, position='Bếp phó', competency=keeper, target_score=88)
        PositionTarget.objects.create(tenant=self.tenant, position='NV Phục vụ', competency=dupe, target_score=85)
        course = Course.objects.create(tenant=self.tenant, title='Khóa cũ', competency=dupe)

        call_command('cleanup_competency_data', tenant='Demo Tenant')

        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)
        self.assertFalse(Competency.objects.filter(id=dupe.id).exists())
        self.assertTrue(
            PositionTarget.objects.filter(tenant=self.tenant, position='NV Phục vụ', competency=keeper, target_score=85).exists()
        )
        self.assertTrue(
            PositionTarget.objects.filter(tenant=self.tenant, position='Bếp trưởng', competency=keeper, target_score=90).exists()
        )
        course.refresh_from_db()
        self.assertEqual(course.competency_id, keeper.id)

    def test_idempotent_second_run_changes_nothing(self):
        call_command('cleanup_competency_data', tenant='Demo Tenant')
        call_command('cleanup_competency_data', tenant='Demo Tenant')
        self.assertEqual(CompetencyGroup.objects.filter(tenant=self.tenant).count(), 6)
        self.assertEqual(Competency.objects.filter(tenant=self.tenant).count(), 24)


class ScoringConfigApiTests(TestCase):
    """GET/PATCH /api/dashboard/scoring-config/ (Prompt_Dashboard_A1_GanNhanNangLuc.md, muc 2)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.client = APIClient()

    def test_get_default_when_not_configured(self):
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('dashboard-scoring-config'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'theory_weight': 50.0, 'practice_weight': 50.0})

    def test_admin_can_patch_and_it_persists(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(reverse('dashboard-scoring-config'), {'theory_weight': 30, 'practice_weight': 70}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data['theory_weight']), 30.0)

        resp2 = self.client.get(reverse('dashboard-scoring-config'))
        self.assertEqual(float(resp2.data['theory_weight']), 30.0)
        self.assertEqual(float(resp2.data['practice_weight']), 70.0)

    def test_non_admin_cannot_patch(self):
        self.client.force_authenticate(self.om)
        resp = self.client.patch(reverse('dashboard-scoring-config'), {'theory_weight': 10}, format='json')
        self.assertEqual(resp.status_code, 403)


class ClsExamCompetencyMapApiTests(TestCase):
    """CRUD /api/dashboard/cls-exam-map/ (Prompt_Dashboard_A1_GanNhanNangLuc.md, muc 1)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.group = CompetencyGroup.objects.create(tenant=self.tenant, code='A2', name='Chuyên môn Phục vụ')
        self.comp = Competency.objects.create(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        self.client = APIClient()

    def test_admin_can_create(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('cls-exam-map-list'), {'exam_name': '15N', 'competency': self.comp.id})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ClsExamCompetencyMap.objects.filter(tenant=self.tenant, exam_name='15N', competency=self.comp).exists())

    def test_om_cannot_create(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post(reverse('cls-exam-map-list'), {'exam_name': '15N', 'competency': self.comp.id})
        self.assertEqual(resp.status_code, 403)

    def test_om_can_list(self):
        ClsExamCompetencyMap.objects.create(tenant=self.tenant, exam_name='15N', competency=self.comp)
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('cls-exam-map-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['competency_name'], self.comp.name)


class ImportTrainingCostsTests(TestCase):
    """Prompt_Dashboard_B_ManTongHop.md, muc 4 - import CSV chi phi dao tao (co che nhu
    RecruitmentSource/CLS)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_imports_rows_and_normalizes_cost_type_scope(self):
        rows = [
            {
                'Tháng': '7', 'Năm': '2026', 'Loại chi phí': 'Lương & phụ cấp trainer',
                'Đơn vị áp dụng': 'Toàn hệ thống', 'Mã đơn vị': '', 'Số tiền (VND)': '15000000',
                'Ghi chú': 'Ví dụ',
            },
            {
                'Tháng': '7', 'Năm': '2026', 'Loại chi phí': 'Tài liệu & in ấn',
                'Đơn vị áp dụng': 'Nhà hàng', 'Mã đơn vị': 'KMP-HNO-HBT', 'Số tiền (VND)': '1200000',
                'Ghi chú': '',
            },
        ]
        result = import_training_costs(self.tenant, rows)
        self.assertEqual(result['written'], 2)
        self.assertEqual(result['warnings'], [])
        c1 = TrainingCost.objects.get(tenant=self.tenant, cost_type=TrainingCost.CostType.TRAINER_SALARY)
        self.assertEqual(c1.scope, TrainingCost.Scope.SYSTEM)
        self.assertEqual(c1.amount, 15000000)
        c2 = TrainingCost.objects.get(tenant=self.tenant, cost_type=TrainingCost.CostType.MATERIALS)
        self.assertEqual(c2.scope, TrainingCost.Scope.RESTAURANT)
        self.assertEqual(c2.unit_code, 'KMP-HNO-HBT')

    def test_reimport_updates_not_duplicates(self):
        rows = [{
            'Tháng': '7', 'Năm': '2026', 'Loại chi phí': 'Khác', 'Đơn vị áp dụng': 'Toàn hệ thống',
            'Mã đơn vị': '', 'Số tiền (VND)': '500000', 'Ghi chú': '',
        }]
        import_training_costs(self.tenant, rows)
        rows[0]['Số tiền (VND)'] = '700000'
        import_training_costs(self.tenant, rows)
        self.assertEqual(TrainingCost.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(TrainingCost.objects.get(tenant=self.tenant).amount, 700000)

    def test_unknown_cost_type_skipped_with_warning(self):
        rows = [{
            'Tháng': '7', 'Năm': '2026', 'Loại chi phí': 'Không rõ', 'Đơn vị áp dụng': 'Toàn hệ thống',
            'Số tiền (VND)': '1', 'Ghi chú': '',
        }]
        result = import_training_costs(self.tenant, rows)
        self.assertEqual(result['written'], 0)
        self.assertTrue(result['warnings'])
        self.assertEqual(TrainingCost.objects.filter(tenant=self.tenant).count(), 0)

    def test_restaurant_scope_without_unit_code_skipped(self):
        rows = [{
            'Tháng': '7', 'Năm': '2026', 'Loại chi phí': 'Khác', 'Đơn vị áp dụng': 'Nhà hàng',
            'Mã đơn vị': '', 'Số tiền (VND)': '1', 'Ghi chú': '',
        }]
        result = import_training_costs(self.tenant, rows)
        self.assertEqual(result['written'], 0)
        self.assertTrue(result['warnings'])

    def test_missing_required_fields_skipped(self):
        rows = [{'Tháng': '', 'Năm': '2026', 'Loại chi phí': 'Khác', 'Số tiền (VND)': '1'}]
        result = import_training_costs(self.tenant, rows)
        self.assertEqual(result['written'], 0)
        self.assertTrue(result['warnings'])

    def test_blank_row_skipped_silently(self):
        rows = [{
            'Tháng': '', 'Năm': '', 'Loại chi phí': '', 'Đơn vị áp dụng': '', 'Mã đơn vị': '',
            'Số tiền (VND)': '', 'Ghi chú': '',
        }]
        result = import_training_costs(self.tenant, rows)
        self.assertEqual(result['written'], 0)
        self.assertEqual(result['warnings'], [])


class TrainingCostAggregateTests(TestCase):
    """training_cost_total / cost_per_passed_employee - 'Chờ dữ liệu' khi chưa import."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(
            tenant=self.tenant, code='KMP-HNO-HBT', name='NH HBT', brand='Kampong', region='Hà Nội',
        )

    def test_no_data_returns_none(self):
        self.assertIsNone(training_cost_total(self.tenant, 7, 2026))
        self.assertIsNone(cost_per_passed_employee(self.tenant, 7, 2026))

    def test_total_sums_all_scopes_when_no_restaurant_filter(self):
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='trainer_salary', scope='system',
            amount=Decimal('1000000'),
        )
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='materials', scope='restaurant',
            unit_code='KMP-HNO-HBT', amount=Decimal('200000'),
        )
        self.assertEqual(training_cost_total(self.tenant, 7, 2026), 1200000.0)

    def test_restaurant_filter_includes_system_and_matching_restaurant_only(self):
        other = Restaurant.objects.create(tenant=self.tenant, code='OTHER', name='NH khác', brand='Kampong')
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='trainer_salary', scope='system',
            amount=Decimal('1000000'),
        )
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='materials', scope='restaurant',
            unit_code='KMP-HNO-HBT', amount=Decimal('200000'),
        )
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='software', scope='restaurant',
            unit_code='OTHER', amount=Decimal('50000'),
        )
        self.assertEqual(training_cost_total(self.tenant, 7, 2026, restaurant=self.restaurant), 1200000.0)
        self.assertEqual(training_cost_total(self.tenant, 7, 2026, restaurant=other), 1050000.0)

    def test_region_scope_matches_restaurant_region(self):
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='travel', scope='region',
            unit_code='Hà Nội', amount=Decimal('300000'),
        )
        self.assertEqual(training_cost_total(self.tenant, 7, 2026, restaurant=self.restaurant), 300000.0)

    def test_cost_per_passed_employee(self):
        import datetime

        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='trainer_salary', scope='system',
            amount=Decimal('1000000'),
        )
        Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', pass_date=datetime.date(2026, 7, 15))
        Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', pass_date=datetime.date(2026, 7, 20))
        self.assertEqual(cost_per_passed_employee(self.tenant, 7, 2026), 500000.0)

    def test_cost_per_passed_employee_none_when_nobody_passed(self):
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='trainer_salary', scope='system',
            amount=Decimal('1000000'),
        )
        self.assertIsNone(cost_per_passed_employee(self.tenant, 7, 2026))


class AggregateDashboardEngineTests(TestCase):
    """Prompt_Dashboard_B_ManTongHop.md, muc 1-2: compute_aggregate_dashboard render dong theo
    DashboardIndicator (bat/tat + scope + nguong mau) + bo loc thang/nha hang."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        seed_dashboard_indicators(self.tenant)
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')

    def test_scope_filters_indicators_by_role_scope(self):
        result_ceo = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        result_gdt = compute_aggregate_dashboard(self.admin, 'gdt', 7, 2026)
        ceo_keys = {i['key'] for i in result_ceo['indicators']}
        gdt_keys = {i['key'] for i in result_gdt['indicators']}
        self.assertIn('ty_le_pass_thu_viec', ceo_keys)  # role_scope=['ceo']
        self.assertNotIn('ty_le_pass_thu_viec', gdt_keys)
        self.assertIn('ty_le_hoan_thanh_khoa', gdt_keys)  # role_scope=['gdt']
        self.assertNotIn('ty_le_hoan_thanh_khoa', ceo_keys)

    def test_disabled_indicator_excluded(self):
        DashboardIndicator.objects.filter(tenant=self.tenant, key='ty_le_pass_thu_viec').update(enabled=False)
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        keys = {i['key'] for i in result['indicators']}
        self.assertNotIn('ty_le_pass_thu_viec', keys)

    def test_pending_when_no_data(self):
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        by_key = {i['key']: i for i in result['indicators']}
        self.assertTrue(by_key['ty_le_pass_thu_viec']['pending'])
        self.assertIsNone(by_key['ty_le_pass_thu_viec']['value'])

    def test_color_applied_from_threshold(self):
        import datetime

        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', restaurant=self.restaurant,
            operation_unit='restaurant', start_date=datetime.date(2026, 7, 1),
            pass_date=datetime.date(2026, 7, 10), employee_status='active',
        )
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        by_key = {i['key']: i for i in result['indicators']}
        self.assertEqual(by_key['ty_le_pass_thu_viec']['value'], 100.0)
        self.assertEqual(by_key['ty_le_pass_thu_viec']['color'], 'green')

    def test_restaurant_filter_changes_indicator_value(self):
        import datetime

        other = Restaurant.objects.create(tenant=self.tenant, code='R2', name='NH 2', brand='Kampong')
        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', restaurant=self.restaurant,
            operation_unit='restaurant', start_date=datetime.date(2026, 7, 1),
            pass_date=datetime.date(2026, 7, 10), employee_status='active',
        )
        Employee.objects.create(
            tenant=self.tenant, code='NV2', name='NV2', restaurant=other,
            operation_unit='restaurant', start_date=datetime.date(2026, 7, 1), employee_status='probation',
        )
        result_r1 = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026, restaurant_id=self.restaurant.id)
        result_r2 = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026, restaurant_id=other.id)
        by_key_r1 = {i['key']: i for i in result_r1['indicators']}
        by_key_r2 = {i['key']: i for i in result_r2['indicators']}
        self.assertEqual(by_key_r1['ty_le_pass_thu_viec']['value'], 100.0)
        self.assertEqual(by_key_r2['ty_le_pass_thu_viec']['value'], 0.0)

    def test_month_filter_changes_indicator_value(self):
        import datetime

        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', restaurant=self.restaurant,
            operation_unit='restaurant', start_date=datetime.date(2026, 7, 1),
            pass_date=datetime.date(2026, 7, 10), employee_status='active',
        )
        result_july = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        result_aug = compute_aggregate_dashboard(self.admin, 'ceo', 8, 2026)
        by_key_july = {i['key']: i for i in result_july['indicators']}
        by_key_aug = {i['key']: i for i in result_aug['indicators']}
        self.assertEqual(by_key_july['ty_le_pass_thu_viec']['value'], 100.0)
        self.assertIsNone(by_key_aug['ty_le_pass_thu_viec']['value'])


class RefreshCompetencySnapshotsTests(TestCase):
    """Prompt_Fix_OOM_DashboardTongHop.md: tinh nen CompetencySnapshot/CompetencyScoreSnapshot
    dung LAI DUNG engine compute_competency_scores (khong doi cong thuc), chi doi CHO tinh
    (background/cron) - chay qua management command, khong phai trong request man tong hop."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')
        seed_competency_framework(self.tenant)
        self.group = CompetencyGroup.objects.get(tenant=self.tenant, code='A2')
        self.comp = Competency.objects.get(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        PositionGroupWeight.objects.create(tenant=self.tenant, position='NV Phục vụ', group=self.group, weight=Decimal('100'))
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='NV Phục vụ', restaurant=self.restaurant,
            employee_status='active',
        )
        course = Course.objects.create(tenant=self.tenant, title='Khóa phục vụ', competency=self.comp)
        Enrollment.objects.create(tenant=self.tenant, course=course, employee=self.employee, status=Enrollment.Status.COMPLETED)

    def test_snapshot_matches_live_engine_exactly(self):
        """Khong doi y nghia so lieu - snapshot phai khop CHINH XAC voi compute_competency_scores
        (chi khac THOI DIEM tinh, khong khac CONG THUC)."""
        live = compute_competency_scores(self.employee)
        refresh_competency_snapshots(self.tenant)
        snap = CompetencySnapshot.objects.get(tenant=self.tenant, employee=self.employee)
        self.assertEqual(float(snap.ci), live['ci'])
        self.assertEqual(snap.restaurant_id, self.restaurant.id)

        live_comp = next(c for c in live['competencies'] if c['id'] == self.comp.id)
        score_snap = CompetencyScoreSnapshot.objects.get(employee=self.employee, competency=self.comp)
        self.assertEqual(float(score_snap.score), live_comp['score'])
        self.assertEqual(score_snap.target, live_comp['target'])

    def test_creates_one_score_row_per_competency(self):
        refresh_competency_snapshots(self.tenant)
        self.assertEqual(CompetencyScoreSnapshot.objects.filter(employee=self.employee).count(), 24)

    def test_resigned_employee_excluded(self):
        self.employee.employee_status = 'resigned'
        self.employee.save(update_fields=['employee_status'])
        refresh_competency_snapshots(self.tenant)
        self.assertFalse(CompetencySnapshot.objects.filter(employee=self.employee).exists())

    def test_rerun_updates_not_duplicates(self):
        refresh_competency_snapshots(self.tenant)
        refresh_competency_snapshots(self.tenant)
        self.assertEqual(CompetencySnapshot.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(CompetencyScoreSnapshot.objects.filter(tenant=self.tenant).count(), 24)

    def test_stale_snapshot_removed_when_employee_leaves_scope(self):
        refresh_competency_snapshots(self.tenant)
        self.assertTrue(CompetencySnapshot.objects.filter(employee=self.employee).exists())
        self.employee.employee_status = 'resigned'
        self.employee.save(update_fields=['employee_status'])
        refresh_competency_snapshots(self.tenant)
        self.assertFalse(CompetencySnapshot.objects.filter(employee=self.employee).exists())
        self.assertFalse(CompetencyScoreSnapshot.objects.filter(employee=self.employee).exists())

    def test_management_command_runs(self):
        call_command('refresh_competency_snapshots', tenant='Demo Tenant')
        self.assertTrue(CompetencySnapshot.objects.filter(tenant=self.tenant, employee=self.employee).exists())


class CompetencyAggregateFromSnapshotTests(TestCase):
    """_competency_aggregate_from_snapshot - DOC snapshot bang truy van aggregate (Avg/Count),
    khong lap Python qua tung nhan su."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')
        self.other_restaurant = Restaurant.objects.create(tenant=self.tenant, code='R2', name='NH 2', brand='Kampong')
        seed_competency_framework(self.tenant)
        self.group = CompetencyGroup.objects.get(tenant=self.tenant, code='A2')
        self.comp_a = Competency.objects.get(tenant=self.tenant, group=self.group, name='Quy trình phục vụ chuẩn')
        self.comp_b = Competency.objects.get(tenant=self.tenant, group=self.group, name='Xử lý order & POS')

    def _snapshot(self, code, ci, restaurant=None):
        e = Employee.objects.create(tenant=self.tenant, code=code, name=code, employee_status='active')
        CompetencySnapshot.objects.create(tenant=self.tenant, employee=e, restaurant=restaurant, ci=Decimal(str(ci)))
        return e

    def test_no_snapshot_returns_none(self):
        result = _competency_aggregate_from_snapshot(self.tenant)
        self.assertIsNone(result['ci_avg'])
        self.assertIsNone(result['ready_rate'])
        self.assertEqual(result['top_gaps'], [])
        self.assertEqual(result['group_avg'], [])

    def test_ci_avg_and_ready_rate(self):
        self._snapshot('NV1', 90)  # >= 80 -> ready
        self._snapshot('NV2', 60)  # < 80 -> khong ready
        result = _competency_aggregate_from_snapshot(self.tenant)
        self.assertEqual(result['ci_avg'], 75.0)
        self.assertEqual(result['ready_rate'], 50.0)

    def test_restaurant_filter(self):
        self._snapshot('NV1', 90, restaurant=self.restaurant)
        self._snapshot('NV2', 50, restaurant=self.other_restaurant)
        result = _competency_aggregate_from_snapshot(self.tenant, restaurant=self.restaurant)
        self.assertEqual(result['ci_avg'], 90.0)

    def test_target_rate_and_top_gaps_and_group_avg_from_score_snapshot(self):
        e = self._snapshot('NV1', 80)
        CompetencyScoreSnapshot.objects.create(
            tenant=self.tenant, employee=e, competency=self.comp_a, group=self.group,
            score=Decimal('90'), target=80, gap=Decimal('-10'),
        )
        CompetencyScoreSnapshot.objects.create(
            tenant=self.tenant, employee=e, competency=self.comp_b, group=self.group,
            score=Decimal('50'), target=80, gap=Decimal('30'),
        )
        result = _competency_aggregate_from_snapshot(self.tenant)
        self.assertEqual(result['target_rate'], 50.0)  # 1/2 dat muc tieu (gap<=0)
        self.assertEqual(len(result['top_gaps']), 1)
        self.assertEqual(result['top_gaps'][0]['name'], self.comp_b.name)
        self.assertEqual(result['top_gaps'][0]['avg_gap'], 30.0)
        group_row = next(g for g in result['group_avg'] if g['code'] == 'A2')
        self.assertEqual(group_row['avg_score'], 70.0)  # (90+50)/2

    def test_query_count_fixed_regardless_of_employee_count(self):
        """Nguyen nhan OOM cu: goi compute_competency_scores() cho TUNG nhan su (24 nang luc x 5
        nguon = 120 truy van/nhan su). Sau khi sua, so truy van phai LA HANG SO du bao nhieu
        nhan su co snapshot."""
        self._snapshot('NV1', 90)
        with self.assertNumQueries(5):
            _competency_aggregate_from_snapshot(self.tenant)

        for i in range(2, 22):
            e = self._snapshot(f'NV{i}', 70)
            CompetencyScoreSnapshot.objects.create(
                tenant=self.tenant, employee=e, competency=self.comp_a, group=self.group,
                score=Decimal('70'), target=80, gap=Decimal('10'),
            )
        with self.assertNumQueries(5):
            _competency_aggregate_from_snapshot(self.tenant)


class AggregateDashboardQueryCountTests(TestCase):
    """Prompt_Fix_OOM_DashboardTongHop.md, nghiem thu: so truy van cua man tong hop KHONG tang
    ti le voi tong so nhan su trong tenant (chi tang theo nhom da loc - thang/nha hang - vi du
    cohort thang nay, khong phai toan bo roster)."""

    def setUp(self):
        from accounts.services import get_grading_config

        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        seed_dashboard_indicators(self.tenant)
        seed_competency_framework(self.tenant)
        # UI dot 3: GradingConfig la ban ghi tao-luoi-lan-dau-cham-vao (giong BrandSettings/
        # CompetencyScoringConfig) - trong THUC TE, tenant da tung tao ban ghi nay truoc do (vd
        # mo man Cai dat) truoc khi co nhieu nhan su de xem dashboard tong hop. "Cham" san o day
        # de phep do query-count nay chi do dung bat bien "khong tang theo so nhan su", khong
        # lan ca chi phi tao ban ghi lan dau (mot lan duy nhat trong doi tenant).
        get_grading_config(self.tenant)
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')

    def _add_noise_employee(self, code):
        """Nhan su 'nhieu' - da lam lau, da Pass tu lau - KHONG thuoc cohort thang nay, KHONG con
        thu viec (bi loai khoi bang canh bao boi WHERE o DB) - chi de kiem tra ho KHONG lam tang
        so truy van (truoc day se lam, vi engine cu duyet QUA TAT CA nhan su dang lam)."""
        import datetime

        old_start = datetime.date(2020, 1, 1)
        e = Employee.objects.create(
            tenant=self.tenant, code=code, name=code, restaurant=self.restaurant,
            operation_unit='restaurant', start_date=old_start, pass_date=datetime.date(2020, 1, 20),
            employee_status='active',
        )
        CompetencySnapshot.objects.create(tenant=self.tenant, employee=e, restaurant=self.restaurant, ci=Decimal('85'))
        return e

    def test_query_count_stable_as_total_employees_grow(self):
        with CaptureQueriesContext(connection) as ctx_small:
            compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026, restaurant_id=self.restaurant.id)
        queries_small = len(ctx_small)

        for i in range(20):
            self._add_noise_employee(f'NOISE{i}')

        with CaptureQueriesContext(connection) as ctx_large:
            compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026, restaurant_id=self.restaurant.id)
        queries_large = len(ctx_large)

        self.assertEqual(
            queries_small, queries_large,
            f'So truy van phai KHONG doi khi them nhan su "nhieu" (khong thuoc cohort) - '
            f'{queries_small} (truoc) vs {queries_large} (sau, +20 nhan su).',
        )


class DungLoTrinhMatchesKpiServiceTests(TestCase):
    """Prompt_Fix_DungLoTrinh_Dashboard.md: chi so '% NV đúng lộ trình' (the tong + xep hang nha
    hang) tren man tong hop PHAI khop CHINH XAC voi kpi.services.kpi_bql_report_data (dung
    logic "pass_date trong han theo cap" da co san cua module KPI, khong tinh lai cong thuc
    khac). Da dieu tra ky: dashboard hien tai DA goi dung kpi_bql_report_data (xem
    _aggregate_context/_resolve_aggregate_indicator_value key='dung_lo_trinh') - cac test nay
    khoa lai su dung khop do, ca truong hop co nguoi dung han LAN truong hop CA NHOM tre han
    (dung y kich ban thuc te thang 7/2026 tren production: cohort 20 nguoi, 0 nguoi dung han -
    gan nhat tre 1 ngay so voi han 15 ngay - day la SO LIEU THAT, khong phai loi phan mem)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        seed_dashboard_indicators(self.tenant)
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='R1', name='NH 1', brand='Kampong')
        self.restaurant2 = Restaurant.objects.create(tenant=self.tenant, code='R2', name='NH 2', brand='Kampong')

    def _employee(self, code, restaurant, start_date, pass_date, position='NV Phục vụ'):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name=code, position=position, restaurant=restaurant,
            operation_unit='restaurant', start_date=start_date, pass_date=pass_date, employee_status='active',
        )

    def test_total_matches_kpi_service_when_some_on_time(self):
        import datetime

        # Han cap S = 15 ngay. 1 nguoi dung han (10 ngay), 1 nguoi tre han (20 ngay).
        self._employee('P1', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 11))
        self._employee('P2', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 21))

        kpi_totals = kpi_bql_report_data(self.admin, 7, 2026)['totals']
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        by_key = {i['key']: i for i in result['indicators']}

        self.assertEqual(kpi_totals['on_rate'], 50)
        self.assertEqual(by_key['dung_lo_trinh']['value'], float(kpi_totals['on_rate']))
        self.assertEqual(by_key['dung_lo_trinh']['pending'], False)

    def test_restaurant_ranking_matches_kpi_rows_per_restaurant(self):
        import datetime

        # NH1: 1/1 dung han (100%). NH2: 0/1 dung han (0%).
        self._employee('P1', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 11))
        self._employee('P2', self.restaurant2, datetime.date(2026, 7, 1), datetime.date(2026, 7, 21))

        kpi_rows = {r['restaurant_id']: r for r in kpi_bql_report_data(self.admin, 7, 2026)['rows']}
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)

        for row in result['restaurant_ranking']:
            self.assertEqual(row['on_rate'], kpi_rows[row['restaurant_id']]['on_rate'])
        ranking_by_id = {r['restaurant_id']: r for r in result['restaurant_ranking']}
        self.assertEqual(ranking_by_id[self.restaurant.id]['on_rate'], 100)
        self.assertEqual(ranking_by_id[self.restaurant2.id]['on_rate'], 0)

    def test_restaurant_filtered_indicator_matches_that_restaurant_row(self):
        import datetime

        self._employee('P1', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 11))
        self._employee('P2', self.restaurant2, datetime.date(2026, 7, 1), datetime.date(2026, 7, 21))

        kpi_rows = {r['restaurant_id']: r for r in kpi_bql_report_data(self.admin, 7, 2026)['rows']}
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026, restaurant_id=self.restaurant2.id)
        by_key = {i['key']: i for i in result['indicators']}

        self.assertEqual(by_key['dung_lo_trinh']['value'], float(kpi_rows[self.restaurant2.id]['on_rate']))
        self.assertEqual(by_key['dung_lo_trinh']['value'], 0.0)

    def test_all_late_cohort_correctly_shows_zero_matching_kpi_not_a_bug(self):
        """Tai hien dung kich ban thuc te da bao cao: CA cohort tre han (gan nhat tre 1 ngay so
        voi han 15 ngay) -> dashboard PHAI khop kpi_bql_report_data (ca hai deu = 0%), vi day la
        so lieu dung theo dinh nghia "dung lo trinh" (khong phai loi phan mem)."""
        import datetime

        self._employee('P1', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 17))  # tre 1 ngay
        self._employee('P2', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 22))  # tre 6 ngay

        kpi_totals = kpi_bql_report_data(self.admin, 7, 2026)['totals']
        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        by_key = {i['key']: i for i in result['indicators']}

        self.assertEqual(kpi_totals['on_num'], 0)
        self.assertEqual(kpi_totals['on_den'], 2)  # cohort co du lieu (khong phai "chua wire")
        self.assertEqual(by_key['dung_lo_trinh']['value'], 0.0)
        self.assertEqual(by_key['dung_lo_trinh']['pending'], False)  # co du lieu, gia tri that = 0, khong phai "Cho du lieu"

    def test_not_read_from_competency_snapshot(self):
        """'dung_lo_trinh' KHONG phu thuoc CompetencySnapshot (khac voi ci_tong_hop/san_sang_
        nhan_luc/...) - khong can chay refresh_competency_snapshots de chi so nay co du lieu."""
        import datetime

        self._employee('P1', self.restaurant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 11))
        self.assertEqual(CompetencySnapshot.objects.filter(tenant=self.tenant).count(), 0)

        result = compute_aggregate_dashboard(self.admin, 'ceo', 7, 2026)
        by_key = {i['key']: i for i in result['indicators']}
        self.assertEqual(by_key['dung_lo_trinh']['value'], 100.0)


class AggregateDashboardApiTests(TestCase):
    """GET /api/dashboard/overview/ - man tong hop CEO/GDDT."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.bod = User.objects.create_user(username='bod1', password='x', tenant=self.tenant, role='bod')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        seed_dashboard_indicators(self.tenant)
        self.client = APIClient()

    def test_admin_can_view_ceo_overview(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-overview'), {'scope': 'ceo', 'month': 7, 'year': 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('indicators', resp.data)
        self.assertIn('restaurant_ranking', resp.data)
        self.assertIn('trend', resp.data)

    def test_bod_can_view_gdt(self):
        self.client.force_authenticate(self.bod)
        resp = self.client.get(reverse('dashboard-overview'), {'scope': 'gdt', 'month': 7, 'year': 2026})
        self.assertEqual(resp.status_code, 200)

    def test_trainer_forbidden(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.get(reverse('dashboard-overview'), {'scope': 'ceo'})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_scope_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-overview'), {'scope': 'xyz'})
        self.assertEqual(resp.status_code, 400)

    def test_defaults_to_current_month_when_not_given(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('dashboard-overview'), {'scope': 'ceo'})
        self.assertEqual(resp.status_code, 200)


class TrainingCostSourceApiTests(TestCase):
    """GET/PUT /api/dashboard/training-cost-source/ + POST .../sync/ (co che nhu RecruitmentSource)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.client = APIClient()

    def test_get_empty_by_default(self):
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('training-cost-source'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['csv_url'], '')

    def test_admin_can_set_url(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put(reverse('training-cost-source'), {'csv_url': 'https://example.com/costs.csv'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            TrainingCostSource.objects.filter(tenant=self.tenant, csv_url='https://example.com/costs.csv').exists()
        )

    def test_om_cannot_set_url(self):
        self.client.force_authenticate(self.om)
        resp = self.client.put(reverse('training-cost-source'), {'csv_url': 'https://example.com/costs.csv'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_sync_without_url_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('training-cost-sync'))
        self.assertEqual(resp.status_code, 400)

    def test_sync_service_raises_without_url(self):
        with self.assertRaises(ValidationError):
            sync_training_costs(self.tenant)

    def test_om_cannot_sync(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post(reverse('training-cost-sync'))
        self.assertEqual(resp.status_code, 403)


class TrainingCostImportFileApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()

    def test_admin_imports_csv_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        csv_content = (
            'Tháng,Năm,Loại chi phí,Đơn vị áp dụng,Mã đơn vị,Số tiền (VND),Ghi chú\r\n'
            '7,2026,Khác,Toàn hệ thống,,500000,\r\n'
        )
        f = SimpleUploadedFile('costs.csv', csv_content.encode('utf-8'), content_type='text/csv')
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('training-cost-import-file'), {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['written'], 1)


class TrainingCostCrudApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.client = APIClient()

    def test_admin_can_create(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('training-cost-list'), {
            'month': 7, 'year': 2026, 'cost_type': 'other', 'scope': 'system', 'amount': '1000',
        })
        self.assertEqual(resp.status_code, 201)

    def test_om_cannot_create(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post(reverse('training-cost-list'), {
            'month': 7, 'year': 2026, 'cost_type': 'other', 'scope': 'system', 'amount': '1000',
        })
        self.assertEqual(resp.status_code, 403)

    def test_om_can_list(self):
        TrainingCost.objects.create(
            tenant=self.tenant, month=7, year=2026, cost_type='other', scope='system', amount=Decimal('1000'),
        )
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('training-cost-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
