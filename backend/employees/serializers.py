from rest_framework import serializers

from accounts.models import User
from restaurants.models import Restaurant

from .models import Employee, LevelUpEnrollment


class EmployeeSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')
    progress_percent = serializers.SerializerMethodField()
    lms_marks = serializers.SerializerMethodField()
    result_exported = serializers.SerializerMethodField()
    result_pdf_url = serializers.CharField(source='probation_result_pdf_url', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'code', 'name', 'position', 'operation_unit', 'job_level', 'level_group',
            'start_date', 'restaurant', 'restaurant_name', 'employee_status', 'probation_days',
            'skill_score', 'skill_result', 'shift_ops', 'office_result', 'final_result',
            'trainer', 'trainer_name', 'commission_status', 'retrain_deadline', 'progress_percent',
            'lms_marks', 'is_legacy', 'result_exported', 'result_pdf_url',
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
