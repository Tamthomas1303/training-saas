from rest_framework import serializers

from .models import Checklist, Document, TrainingProgress


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            'id', 'name', 'code', 'brand', 'position', 'category', 'version', 'status',
            'file_url', 'uploaded_at',
        ]
        read_only_fields = ['id', 'uploaded_at']


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
