from rest_framework import serializers

from .models import Checklist


class ChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Checklist
        fields = [
            'id', 'brand', 'position', 'day', 'category', 'task_name', 'description',
            'doc_url', 'level_group', 'order',
        ]
