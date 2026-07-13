from rest_framework import serializers

from .models import Checklist, TrainingProgress


class ChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Checklist
        fields = [
            'id', 'brand', 'position', 'day', 'category', 'task_name', 'description',
            'doc_url', 'level_group', 'order',
        ]


class TrainingProgressSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source='trainer.full_name', read_only=True, default='')

    class Meta:
        model = TrainingProgress
        fields = [
            'id', 'employee', 'checklist', 'trainer', 'trainer_name', 'status',
            'img_tailieu', 'img_lythuyet', 'img_thuchanh',
            'sign_trainer', 'sign_trainee', 'note', 'pdf_url', 'completed_at',
        ]
        read_only_fields = ['id', 'trainer', 'trainer_name', 'status', 'pdf_url', 'completed_at']
