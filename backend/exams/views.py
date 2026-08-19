import io

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.permissions import ROLES_CAN_EVALUATE

from .models import Assessment, AssessmentAssignment, AssessmentQuestion, Attempt, ExamSession, Question, QuestionBank
from .serializers import (
    AssessmentAssignmentSerializer,
    AssessmentDetailSerializer,
    AssessmentQuestionSerializer,
    AssessmentSerializer,
    AttemptSerializer,
    ExamSessionSerializer,
    QuestionBankSerializer,
    QuestionSerializer,
)
from .services import (
    ValidationError,
    assign_assessment,
    attempt_detail_payload,
    attempt_result_payload,
    create_exam_session,
    exam_session_tracking,
    grade_attempt,
    my_assessments,
    reorder_assessment_questions,
    save_answers,
    start_attempt,
    submit_attempt,
)


def _require_admin_write(request):
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
        raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa dữ liệu thi.')


def _require_evaluator(request):
    if (request.user.role or '').lower() not in ROLES_CAN_EVALUATE:
        raise PermissionDenied('Bạn không có quyền chấm bài.')


def _require_learner(request):
    """Employee cua request.user, hoac None neu chua lien ket - dung quy uoc courses.views."""
    return getattr(request.user, 'employee', None)


class QuestionBankViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD ngan hang cau hoi. Ghi: chi Admin."""

    serializer_class = QuestionBankSerializer
    queryset = QuestionBank.objects.all()
    pagination_class = DefaultPagination
    search_fields = ['name', 'category']
    ordering = ['name']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class QuestionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD cau hoi (+ options long trong body). Loc theo bank=<id>, type=<...>. Ghi: chi Admin."""

    serializer_class = QuestionSerializer
    queryset = Question.objects.prefetch_related('options').all()
    pagination_class = DefaultPagination
    filterset_fields = ['bank', 'type', 'difficulty']
    search_fields = ['stem_html']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class AssessmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD de thi. Doc: moi role dang nhap. Ghi: chi Admin."""

    queryset = Assessment.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['status']
    search_fields = ['title']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AssessmentDetailSerializer
        return AssessmentSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)


class AssessmentQuestionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Cau CHON TAY trong 1 de. Loc theo assessment=<id>. Ghi: chi Admin."""

    serializer_class = AssessmentQuestionSerializer
    queryset = AssessmentQuestion.objects.select_related('question').all()
    pagination_class = DefaultPagination
    filterset_fields = ['assessment']
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class AssessmentAssignmentViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Danh sach gan de - chi doc, chi Admin. Tao qua AssessmentAssignView."""

    serializer_class = AssessmentAssignmentSerializer
    queryset = AssessmentAssignment.objects.select_related('assessment', 'employee').all()
    pagination_class = DefaultPagination
    filterset_fields = ['assessment', 'employee', 'status']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.user.role or '').lower() != 'admin':
            raise PermissionDenied('Chỉ Admin được xem danh sách gán đề.')


# ==================================================================== Ky thi (Dot 4: ExamSession)


class ExamSessionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD Ky thi. Chi Admin (giong quy uoc cac man quan tri khac). create() KHONG dung
    serializer.save() truc tiep - goi services.create_exam_session (chon De + giao ai + dat lich
    -> sinh AssessmentAssignment cung luc, dung y prompt 'Tao Ky thi = ...')."""

    serializer_class = ExamSessionSerializer
    queryset = ExamSession.objects.select_related('assessment').all()
    pagination_class = DefaultPagination
    filterset_fields = ['assessment', 'status']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.user.role or '').lower() != 'admin':
            raise PermissionDenied('Chỉ Admin được quản lý Kỳ thi.')

    def create(self, request, *args, **kwargs):
        try:
            session, assigned_count = create_exam_session(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        data = self.get_serializer(session).data
        data['assigned_count_created'] = assigned_count
        return Response(data, status=201)


class ExamSessionTrackingView(APIView):
    """GET /api/exams/sessions/<id>/tracking/ — man theo doi 1 Ky thi: tung nhan su da/chua thi,
    diem, dat/khong. Chi Admin."""

    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xem theo dõi kỳ thi.'}, status=403)
        session = get_object_or_404(ExamSession, pk=pk, tenant=request.user.tenant)
        return Response(exam_session_tracking(session))


class ExamSessionTrackingExportView(APIView):
    """GET /api/exams/sessions/<id>/tracking/export/ — xuat Excel man theo doi. Chi Admin."""

    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xuất báo cáo.'}, status=403)
        session = get_object_or_404(ExamSession, pk=pk, tenant=request.user.tenant)
        rows = exam_session_tracking(session)

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = 'Theo dõi kỳ thi'
        ws.append(['Mã NV', 'Họ tên', 'Đã thi', 'Điểm', 'Tổng điểm', '%', 'Đạt'])
        for r in rows:
            ws.append([
                r['employee_code'], r['employee_name'], 'Có' if r['done'] else 'Chưa',
                float(r['score']) if r['score'] is not None else None,
                float(r['max_score']) if r['max_score'] is not None else None,
                float(r['percent']) if r['percent'] is not None else None,
                'Đạt' if r['passed'] else ('Chưa đạt' if r['passed'] is False else ''),
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="theo_doi_ky_thi_{session.id}.xlsx"'
        return response


class ReorderView(APIView):
    """POST /api/exams/reorder/ — body {items: [{id, order}, ...]}. Chi Admin. Sap thu tu cau
    chon tay trong 1 de (keo-tha o man quan tri, giong courses.ReorderView)."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được sắp xếp lại thứ tự.'}, status=403)
        items = request.data.get('items') or []
        if not items:
            return Response({'detail': "Cần 'items'."}, status=400)
        updated = reorder_assessment_questions(request.user.tenant, items)
        return Response({'updated': updated})


class AssessmentAssignView(APIView):
    """POST /api/exams/assessments/<id>/assign/ — body {employee_ids:[...]} HOAC
    {position?, restaurant_id?, group?}. Chi Admin."""

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được gán đề thi.'}, status=403)
        assessment = get_object_or_404(Assessment, pk=pk, tenant=request.user.tenant)
        try:
            created = assign_assessment(request.user, assessment, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'created': created})


class AssessmentResultsView(APIView):
    """GET /api/exams/assessments/<id>/results/ — danh sach cac lan lam bai cua 1 de. Chi Admin."""

    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xem báo cáo.'}, status=403)
        assessment = get_object_or_404(Assessment, pk=pk, tenant=request.user.tenant)
        attempts = Attempt.objects.filter(assessment=assessment).select_related('employee')
        return Response(AttemptSerializer(attempts, many=True).data)


class AssessmentResultsExportView(APIView):
    """GET /api/exams/assessments/<id>/results/export/ — xuat Excel danh sach ket qua. Chi Admin."""

    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xuất báo cáo.'}, status=403)
        assessment = get_object_or_404(Assessment, pk=pk, tenant=request.user.tenant)
        attempts = Attempt.objects.filter(assessment=assessment).select_related('employee').order_by('employee__code')

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = 'Kết quả'
        ws.append(['Mã NV', 'Họ tên', 'Lần', 'Điểm', 'Tổng điểm', '%', 'Đạt', 'Trạng thái', 'Nộp lúc'])
        for a in attempts:
            ws.append([
                a.employee.code, a.employee.name, a.attempt_no,
                float(a.score) if a.score is not None else None,
                float(a.max_score) if a.max_score is not None else None,
                float(a.percent) if a.percent is not None else None,
                'Đạt' if a.passed else ('Chưa đạt' if a.passed is False else ''),
                a.get_status_display(),
                a.submitted_at.strftime('%d/%m/%Y %H:%M') if a.submitted_at else '',
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="ket_qua_{assessment.id}.xlsx"'
        return response


class MyAssessmentsView(APIView):
    """GET /api/exams/my/ — danh sach de duoc gan cho request.user (map qua Employee.user)."""

    def get(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        return Response(my_assessments(employee))


class StartAttemptView(APIView):
    """POST /api/exams/my/<assessment_id>/start/ — bat dau 1 lan lam bai moi, tra ve danh sach
    cau hoi (khong kem dap an dung)."""

    def post(self, request, assessment_id):
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        assessment = get_object_or_404(Assessment, pk=assessment_id, tenant=employee.tenant)
        try:
            attempt = start_attempt(employee, assessment)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(attempt_detail_payload(attempt))


class AttemptDetailView(APIView):
    """GET /api/exams/attempts/<id>/ — chi tiet 1 lan lam bai: cau hoi + dap an da luu. Dung cho
    2 luong: (1) chinh nguoi thi bam 'Tiếp tục làm bài' - tra ve lai giong het response cua
    StartAttemptView; (2) ROLES_CAN_EVALUATE xem bai de cham tay (doc cau essay + dap an nguoi
    thi da nop, khong gioi han attempt cua rieng minh vi nguoi cham khong co Employee lien ket)."""

    def get(self, request, pk):
        if (request.user.role or '').lower() in ROLES_CAN_EVALUATE:
            attempt = get_object_or_404(Attempt, pk=pk, tenant=request.user.tenant)
            return Response(attempt_detail_payload(attempt))
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        attempt = get_object_or_404(Attempt, pk=pk, tenant=employee.tenant, employee=employee)
        return Response(attempt_detail_payload(attempt))


class AnswerSaveView(APIView):
    """POST /api/exams/attempts/<id>/answer/ — tu luu tam dap an. Body: {question, response} HOAC
    {items: [{question, response}, ...]}. Chi chinh chu attempt, con IN_PROGRESS."""

    def post(self, request, pk):
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        attempt = get_object_or_404(Attempt, pk=pk, tenant=employee.tenant, employee=employee)
        items = request.data.get('items')
        if items is None:
            items = [{'question': request.data.get('question'), 'response': request.data.get('response')}]
        try:
            save_answers(attempt, items)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'saved': len(items)})


class SubmitAttemptView(APIView):
    """POST /api/exams/attempts/<id>/submit/ — nop bai, tu cham cac cau khach quan."""

    def post(self, request, pk):
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        attempt = get_object_or_404(Attempt, pk=pk, tenant=employee.tenant, employee=employee)
        try:
            attempt = submit_attempt(attempt)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(attempt_result_payload(attempt))


class GradingListView(APIView):
    """GET /api/exams/grading/ — danh sach bai cho cham tay (co cau essay, status=submitted).
    Chi ROLES_CAN_EVALUATE."""

    def get(self, request):
        _require_evaluator(request)
        attempts = Attempt.objects.filter(
            tenant=request.user.tenant, status=Attempt.Status.SUBMITTED,
        ).select_related('employee', 'assessment')
        return Response(AttemptSerializer(attempts, many=True).data)


class GradeAttemptView(APIView):
    """POST /api/exams/attempts/<id>/grade/ — body {scores: {question_id: diem, ...}} cho cac
    cau essay. Chi ROLES_CAN_EVALUATE."""

    def post(self, request, pk):
        _require_evaluator(request)
        attempt = get_object_or_404(Attempt, pk=pk, tenant=request.user.tenant)
        try:
            attempt = grade_attempt(attempt, request.user, request.data.get('scores') or {})
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(attempt_result_payload(attempt))
