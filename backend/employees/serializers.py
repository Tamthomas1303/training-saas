from rest_framework import serializers

from accounts.models import User
from restaurants.models import Restaurant

from .models import (
    AutomationSettings,
    Employee,
    LevelUpEnrollment,
    OnboardingCourseRule,
    ProbationExamCandidate,
    ProbationExamRule,
)


class EmployeeSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')
    progress_percent = serializers.SerializerMethodField()
    lms_marks = serializers.SerializerMethodField()
    result_exported = serializers.SerializerMethodField()
    result_pdf_url = serializers.CharField(source='probation_result_pdf_url', read_only=True)
    emp_type = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    login_username = serializers.CharField(source='user.username', read_only=True, default='')
    exam_score = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'code', 'name', 'position', 'operation_unit', 'job_level', 'level_group',
            'start_date', 'restaurant', 'restaurant_name', 'employee_status', 'probation_days',
            'skill_score', 'skill_result', 'shift_ops', 'office_result', 'final_result',
            'trainer', 'trainer_name', 'commission_status', 'retrain_deadline', 'progress_percent',
            'lms_marks', 'is_legacy', 'result_exported', 'result_pdf_url', 'emp_type', 'days_left',
            'login_username', 'exam_score',
        ]

    def get_result_exported(self, obj):
        return bool((obj.probation_result_pdf_url or '').strip())

    def get_progress_percent(self, obj):
        progress_map = self.context.get('progress_map')
        if progress_map is not None:
            return progress_map.get(obj.id, 0)
        from .services import checklist_progress_percent

        return checklist_progress_percent(obj)

    def get_lms_marks(self, obj):
        """3 dau LMS/Danh gia: hoc LMS, thi LMS, danh gia thuc hanh (ky nang) - port phan hoi
        "Phan 1" (cot LMS/Danh gia trong bang hoc vien). Doc tu context (tinh hang loat, xem
        EmployeeViewSet.list) khi co de tranh N+1; fallback tinh rieng cho serialize 1 dong."""
        lms_map = self.context.get('lms_marks_map')
        if lms_map is not None:
            return lms_map.get(obj.id, {'course': False, 'exam': False, 'skill': False})
        from .services import exam_pass, lms_done

        return {
            'course': lms_done(obj),
            'exam': exam_pass(obj),
            'skill': obj.skill_result == 'Đạt',
        }

    def get_exam_score(self, obj):
        """Nhom 1 muc A - diem thi CAO NHAT (cot 'Ket qua thi' tab Dang lam viec/Ban quan ly).
        Doc tu context (tinh hang loat, xem EmployeeViewSet.list) khi co de tranh N+1."""
        score_map = self.context.get('exam_score_map')
        if score_map is not None:
            return score_map.get(obj.id)
        from .services import best_exam_score

        return best_exam_score(obj) or None

    def get_emp_type(self, obj):
        from .services import emp_type

        return emp_type(obj)

    def get_days_left(self, obj):
        """So ngay con toi han thu viec (start_date + probation_days - hom nay). Xem
        employees/dashboard.py::_deadline_days_left (dung chung logic voi Dashboard/Home)."""
        from .dashboard import _deadline_days_left

        return _deadline_days_left(obj)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            tenant = request.user.tenant
            self.fields['restaurant'].queryset = Restaurant.objects.filter(tenant=tenant)
            self.fields['trainer'].queryset = User.objects.filter(tenant=tenant)

    # #7: khi thêm/sửa nhân sự → tự tính lại nhóm level theo vị trí/Job_Level (đổi vị trí sang
    # cấp O → tự sang danh sách Ban quản lý; giữ cấp S → ở lộ trình thăng tiến).
    def _sync_level_group(self, obj):
        from .services import derive_level_group

        lg = derive_level_group(obj.position, obj.job_level)
        if lg != (obj.level_group or ''):
            obj.level_group = lg
            obj.save(update_fields=['level_group'])

    def create(self, validated_data):
        obj = super().create(validated_data)
        self._sync_level_group(obj)
        return obj

    def update(self, instance, validated_data):
        obj = super().update(instance, validated_data)
        self._sync_level_group(obj)
        return obj


class LevelUpEnrollmentSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    restaurant_name = serializers.CharField(source='employee.restaurant.name', read_only=True, default='')
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    registered_by_name = serializers.CharField(source='registered_by.full_name', read_only=True, default='')

    class Meta:
        model = LevelUpEnrollment
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'restaurant_name',
            'target_position', 'zone', 'from_level', 'target_level', 'exam_batch',
            'status', 'status_label', 'registered_by', 'registered_by_name',
            'created_at', 'completed_at', 'proposal_pdf_url',
        ]
        read_only_fields = fields


class AutomationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationSettings
        fields = [
            'auto_create_account', 'auto_enroll_onboarding', 'send_welcome_email',
            'welcome_email_subject', 'welcome_email_body', 'sender_display_name',
            'cc_recipients',
            # Nhom 3B (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 1).
            'auto_assign_probation_exam', 'require_approval_before_exam', 'auto_send_probation_result',
            'salary_effective_rule', 'result_email_subject', 'result_email_body',
            'updated_at',
        ]
        read_only_fields = ['updated_at']


class OnboardingCourseRuleSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True, default='')

    class Meta:
        model = OnboardingCourseRule
        fields = ['id', 'position', 'course', 'course_title', 'created_at']
        read_only_fields = ['created_at']


class ProbationExamRuleSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True, default='')

    class Meta:
        model = ProbationExamRule
        fields = ['id', 'position', 'assessment', 'assessment_title', 'created_at']
        read_only_fields = ['created_at']


class ProbationExamCandidateSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    restaurant_name = serializers.CharField(source='employee.restaurant.name', read_only=True, default='')
    position = serializers.CharField(source='employee.position', read_only=True, default='')
    assessment_title = serializers.CharField(source='assessment.title', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    decided_by_name = serializers.CharField(source='decided_by.full_name', read_only=True, default='')
    exam_session_title = serializers.CharField(source='exam_session.title', read_only=True, default='')

    class Meta:
        model = ProbationExamCandidate
        fields = [
            'id', 'employee', 'employee_code', 'employee_name', 'restaurant_name', 'position',
            'assessment', 'assessment_title', 'status', 'status_display', 'exam_session',
            'exam_session_title', 'decided_by', 'decided_by_name', 'decided_at', 'reject_reason',
            'created_at',
        ]
        read_only_fields = fields
