from rest_framework import serializers

from checklist.models import Document

from .models import Commission, KpiParticipant, KpiSession


class KpiTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'name', 'category', 'file_url']


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
            'participants', 'participant_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'trainer', 'trainer_name', 'pdf_url', 'participants', 'participant_count', 'created_at',
        ]


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
