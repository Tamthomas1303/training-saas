from rest_framework import serializers

from .models import (
    Answer,
    Assessment,
    AssessmentAssignment,
    AssessmentQuestion,
    Attempt,
    Question,
    QuestionBank,
    QuestionOption,
)


class QuestionBankSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = ['id', 'name', 'category', 'description', 'questions_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_questions_count(self, obj):
        return obj.questions.count()


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'question', 'order', 'content_html', 'is_correct', 'media_url']
        read_only_fields = ['id']
        extra_kwargs = {'question': {'required': False}}


class QuestionSerializer(serializers.ModelSerializer):
    """Nhan them 'options' (list dict) khi tao/sua cau single/multiple/truefalse - dong bo
    thay the toan bo QuestionOption cua cau (don gian cho form dong o FE, dung quy uoc giong
    CourseDetailSerializer long CourseModuleSerializer)."""

    options = QuestionOptionSerializer(many=True, required=False)
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Question
        fields = [
            'id', 'bank', 'type', 'type_display', 'stem_html', 'points', 'difficulty',
            'explanation_html', 'media_url', 'competency_tag', 'position', 'config', 'options',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        options_data = validated_data.pop('options', None)
        question = Question.objects.create(**validated_data)
        self._sync_options(question, options_data)
        return question

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._sync_options(instance, options_data)
        return instance

    def _sync_options(self, question, options_data):
        if options_data is None:
            return
        question.options.all().delete()
        QuestionOption.objects.bulk_create([
            QuestionOption(
                tenant=question.tenant, question=question, order=i,
                content_html=opt.get('content_html', ''), is_correct=bool(opt.get('is_correct')),
                media_url=opt.get('media_url', ''),
            )
            for i, opt in enumerate(options_data)
        ])


class AssessmentQuestionSerializer(serializers.ModelSerializer):
    question_detail = QuestionSerializer(source='question', read_only=True)

    class Meta:
        model = AssessmentQuestion
        fields = ['id', 'assessment', 'question', 'question_detail', 'order', 'points_override']
        read_only_fields = ['id']
        extra_kwargs = {'assessment': {'required': False}}


class AssessmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')
    questions_count = serializers.SerializerMethodField()
    assigned_count = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'title', 'description', 'time_limit_min', 'pass_mark', 'max_attempts',
            'shuffle_questions', 'shuffle_options', 'show_result_mode', 'random_pool_config',
            'competency_tag', 'sync_exam_type', 'status', 'status_display', 'created_by',
            'created_by_name', 'questions_count', 'assigned_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_questions_count(self, obj):
        return obj.assessment_questions.count()

    def get_assigned_count(self, obj):
        return obj.assignments.count()


class AssessmentDetailSerializer(AssessmentSerializer):
    assessment_questions = AssessmentQuestionSerializer(many=True, read_only=True)

    class Meta(AssessmentSerializer.Meta):
        fields = AssessmentSerializer.Meta.fields + ['assessment_questions']


class AssessmentAssignmentSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True, default='')
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AssessmentAssignment
        fields = [
            'id', 'assessment', 'assessment_title', 'employee', 'employee_code', 'employee_name',
            'assigned_by', 'due_date', 'status', 'status_display', 'created_at',
        ]
        read_only_fields = ['id', 'assigned_by', 'status', 'created_at']


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = [
            'id', 'attempt', 'question', 'response_json', 'auto_score', 'manual_score',
            'is_correct', 'graded_by', 'updated_at',
        ]
        read_only_fields = fields


class AttemptSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True, default='')
    employee_code = serializers.CharField(source='employee.code', read_only=True, default='')
    employee_name = serializers.CharField(source='employee.name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attempt
        fields = [
            'id', 'assessment', 'assessment_title', 'employee', 'employee_code', 'employee_name',
            'attempt_no', 'started_at', 'submitted_at', 'score', 'max_score', 'percent', 'passed',
            'status', 'status_display',
        ]
        read_only_fields = fields
