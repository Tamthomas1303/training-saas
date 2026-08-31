from rest_framework import serializers

from checklist.models import Document

from .models import Commission, KpiHourTarget, KpiParticipant, KpiSession


class KpiTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        # Muc 11 muc 4 - standard_minutes de KpiPage.jsx tu dien thoi luong khi chon chu de nay
        # o che do kpi_mode='hours'.
        fields = ['id', 'name', 'category', 'file_url', 'standard_minutes']


class KpiParticipantSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_position = serializers.CharField(source='employee.position', read_only=True)

    class Meta:
        model = KpiParticipant
        fields = ['id', 'employee', 'employee_name', 'employee_position', 'sign_url']


class KpiSessionSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')
    participants = KpiParticipantSerializer(many=True, read_only=True)
    participant_count = serializers.IntegerField(source='participants.count', read_only=True)

    class Meta:
        model = KpiSession
        fields = [
            'id', 'restaurant', 'restaurant_name', 'trainer', 'trainer_name', 'topic', 'document',
            'date', 'note', 'img_tailieu', 'img_lythuyet', 'img_thuchanh', 'pdf_url',
            'duration_minutes', 'participants', 'participant_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'trainer', 'trainer_name', 'pdf_url', 'participants', 'participant_count', 'created_at',
        ]


class KpiHourTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = KpiHourTarget
        fields = ['id', 'position', 'target_minutes_per_month']

    def validate_position(self, value):
        value = (value or '').strip()
        request = self.context.get('request')
        tenant = getattr(request.user, 'tenant', None) if request else None
        qs = KpiHourTarget.objects.filter(tenant=tenant, position=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if tenant and qs.exists():
            label = value or '(mặc định)'
            raise serializers.ValidationError(f'Đã có mục tiêu giờ cho "{label}".')
        return value


class CommissionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_code = serializers.CharField(source='employee.code', read_only=True)
    restaurant_name = serializers.CharField(source='employee.restaurant.name', read_only=True, default='')
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')

    class Meta:
        model = Commission
        fields = [
            'id', 'employee', 'employee_name', 'employee_code', 'restaurant_name',
            'trainer', 'trainer_name', 'amount', 'cond_lms', 'cond_exam', 'cond_training',
            'cond_skill_eval', 'cond_worked_1month', 'status', 'retrain_deadline',
            'month', 'year', 'updated_at',
        ]
        read_only_fields = fields
