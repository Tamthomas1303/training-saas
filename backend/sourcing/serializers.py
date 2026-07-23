from rest_framework import serializers

from .models import Cohort, CohortSession, Enrollment, Program, ProgramContent


class ProgramContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramContent
        fields = ['id', 'program', 'session_no', 'topic', 'content', 'doc_url', 'order']


class ProgramSerializer(serializers.ModelSerializer):
    audience_label = serializers.CharField(source='get_audience_display', read_only=True)
    mode_label = serializers.CharField(source='get_mode_display', read_only=True)
    content_count = serializers.IntegerField(source='contents.count', read_only=True)
    cohort_count = serializers.IntegerField(source='cohorts.count', read_only=True)

    class Meta:
        model = Program
        fields = [
            'id', 'name', 'audience', 'audience_label', 'mode', 'mode_label', 'source_url',
            'description', 'is_active', 'content_count', 'cohort_count', 'created_at',
        ]


class CohortSessionSerializer(serializers.ModelSerializer):
    attendance_count = serializers.IntegerField(source='attendances.count', read_only=True)

    class Meta:
        model = CohortSession
        fields = [
            'id', 'cohort', 'session_no', 'title', 'date', 'start_time', 'end_time',
            'location', 'qr_token', 'attendance_count', 'created_at',
        ]
        read_only_fields = ['qr_token']


class CohortSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    audience = serializers.CharField(source='program.audience', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    session_count = serializers.IntegerField(source='sessions.count', read_only=True)
    enrollment_count = serializers.IntegerField(source='enrollments.count', read_only=True)

    class Meta:
        model = Cohort
        fields = [
            'id', 'program', 'program_name', 'audience', 'name', 'location',
            'start_date', 'end_date', 'status', 'status_label',
            'session_count', 'enrollment_count', 'created_at',
        ]


class EnrollmentSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    restaurant_name = serializers.CharField(source='employee.restaurant.name', read_only=True, default='')
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'cohort', 'employee', 'employee_code', 'employee_name', 'restaurant_name',
            'status', 'status_label', 'result', 'created_at', 'completed_at',
        ]
        read_only_fields = ['status', 'result', 'created_at', 'completed_at']
