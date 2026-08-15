from rest_framework import serializers

from .models import CompetencyGroup, Competency, DashboardIndicator, PositionGroupWeight, PositionTarget


class CompetencyGroupSerializer(serializers.ModelSerializer):
    competencies_count = serializers.SerializerMethodField()

    class Meta:
        model = CompetencyGroup
        fields = ['id', 'code', 'name', 'order', 'competencies_count']
        read_only_fields = ['id']

    def get_competencies_count(self, obj):
        return obj.competencies.count()


class CompetencySerializer(serializers.ModelSerializer):
    group_code = serializers.CharField(source='group.code', read_only=True, default='')
    group_name = serializers.CharField(source='group.name', read_only=True, default='')

    class Meta:
        model = Competency
        fields = ['id', 'group', 'group_code', 'group_name', 'name', 'order']
        read_only_fields = ['id']


class PositionTargetSerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source='competency.name', read_only=True, default='')
    group_code = serializers.CharField(source='competency.group.code', read_only=True, default='')

    class Meta:
        model = PositionTarget
        fields = ['id', 'position', 'competency', 'competency_name', 'group_code', 'target_score']
        read_only_fields = ['id']


class PositionGroupWeightSerializer(serializers.ModelSerializer):
    group_code = serializers.CharField(source='group.code', read_only=True, default='')
    group_name = serializers.CharField(source='group.name', read_only=True, default='')

    class Meta:
        model = PositionGroupWeight
        fields = ['id', 'position', 'group', 'group_code', 'group_name', 'weight']
        read_only_fields = ['id']


class DashboardIndicatorSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)

    class Meta:
        model = DashboardIndicator
        fields = [
            'id', 'key', 'label', 'group_label', 'role_scope', 'enabled', 'order',
            'direction', 'direction_display', 'green_threshold', 'yellow_threshold',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'key', 'label', 'group_label', 'created_at', 'updated_at']
