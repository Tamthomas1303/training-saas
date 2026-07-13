from rest_framework import serializers

from accounts.models import User
from restaurants.models import Restaurant

from .models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True, default='')
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')

    class Meta:
        model = Employee
        fields = [
            'id', 'code', 'name', 'position', 'operation_unit', 'job_level', 'level_group',
            'start_date', 'restaurant', 'restaurant_name', 'employee_status', 'probation_days',
            'skill_score', 'skill_result', 'shift_ops', 'office_result', 'final_result',
            'trainer', 'trainer_name', 'commission_status', 'retrain_deadline',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            tenant = request.user.tenant
            self.fields['restaurant'].queryset = Restaurant.objects.filter(tenant=tenant)
            self.fields['trainer'].queryset = User.objects.filter(tenant=tenant)
