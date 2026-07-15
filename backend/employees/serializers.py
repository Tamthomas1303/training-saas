from rest_framework import serializers

from accounts.models import User
from restaurants.models import Restaurant

from .models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')
    progress_percent = serializers.SerializerMethodField()
    lms_marks = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'code', 'name', 'position', 'operation_unit', 'job_level', 'level_group',
            'start_date', 'restaurant', 'restaurant_name', 'employee_status', 'probation_days',
            'skill_score', 'skill_result', 'shift_ops', 'office_result', 'final_result',
            'trainer', 'trainer_name', 'commission_status', 'retrain_deadline', 'progress_percent',
            'lms_marks',
        ]

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
