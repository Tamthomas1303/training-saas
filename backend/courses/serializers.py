from rest_framework import serializers

from .models import Course, CourseModule, Enrollment, Lesson, LessonProgress, ScormPackage


class ScormPackageSerializer(serializers.ModelSerializer):
    version_display = serializers.CharField(source='get_version_display', read_only=True)

    class Meta:
        model = ScormPackage
        fields = ['id', 'lesson', 'version', 'version_display', 'launch_path', 'title', 'created_at', 'updated_at']
        read_only_fields = fields


class LessonSerializer(serializers.ModelSerializer):
    scorm_package = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'module', 'title', 'type', 'content_url', 'content_html', 'duration_sec',
            'anti_seek', 'complete_rule', 'pass_watch_pct', 'order', 'scorm_package',
        ]

    def get_scorm_package(self, obj):
        package = getattr(obj, 'scorm_package', None)
        return ScormPackageSerializer(package).data if package else None


class CourseModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = CourseModule
        fields = ['id', 'course', 'title', 'order', 'lessons']


class CourseSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    modules_count = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'cover_url', 'objective', 'target_audience',
            'est_minutes', 'status', 'status_display', 'created_by', 'created_by_name',
            'competency_tag', 'sync_course_code', 'modules_count', 'lessons_count',
            'enrolled_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_modules_count(self, obj):
        return obj.modules.count()

    def get_lessons_count(self, obj):
        return Lesson.objects.filter(module__course=obj).count()

    def get_enrolled_count(self, obj):
        return obj.enrollments.count()


class CourseDetailSerializer(CourseSerializer):
    """Course + cay chuong->bai day du - dung cho man quan tri sua 1 khoa (dot tab Chuong/Bai)."""

    modules = CourseModuleSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ['modules']


class EnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True, default='')
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'course_title', 'employee', 'employee_code', 'employee_name',
            'assigned_by', 'assigned_by_name', 'due_date', 'status', 'status_display', 'source',
            'progress_percent', 'created_at',
        ]
        read_only_fields = ['id', 'assigned_by', 'status', 'source', 'created_at']

    def get_progress_percent(self, obj):
        total = Lesson.objects.filter(module__course_id=obj.course_id).count()
        if not total:
            return 0
        done = obj.progresses.filter(status=LessonProgress.Status.DONE).count()
        return round(done / total * 100)


class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = [
            'id', 'enrollment', 'lesson', 'status', 'watched_pct', 'last_position_sec',
            'completed_at', 'completed_offline',
        ]
        read_only_fields = fields
