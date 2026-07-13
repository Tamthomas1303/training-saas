from rest_framework import serializers

from .models import Evaluation, EvaluationCriteria, EvaluationDetail


class EvaluationCriteriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationCriteria
        fields = [
            'id', 'brand', 'position', 'level_group', 'eval_type', 'section',
            'content', 'max_score', 'is_mandatory', 'require_photo', 'order',
        ]


class EvaluationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationDetail
        fields = [
            'id', 'criteria_id', 'content', 'max_score', 'is_mandatory',
            'require_photo', 'score', 'photo_url', 'note',
        ]


class EvaluationSerializer(serializers.ModelSerializer):
    evaluator_name = serializers.CharField(source='evaluator.full_name', read_only=True, default='')
    details = EvaluationDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            'id', 'employee', 'evaluator', 'evaluator_name', 'eval_type', 'date',
            'total_score', 'max_score', 'percent', 'result', 'note',
            'sign_evaluator', 'sign_trainee', 'pdf_url', 'status', 'completed_at', 'details',
        ]
        read_only_fields = [
            'id', 'evaluator', 'evaluator_name', 'total_score', 'max_score', 'percent',
            'result', 'pdf_url', 'status', 'completed_at', 'details',
        ]
