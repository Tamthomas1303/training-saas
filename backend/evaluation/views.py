from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee
from employees.permissions import can_evaluate
from employees.serializers import EmployeeSerializer
from employees.services import checklist_progress_percent

from .models import Evaluation
from .serializers import EvaluationSerializer
from .services import (
    ValidationError,
    council_summary,
    finalize_council,
    is_council_position,
    resolve_criteria,
    save_council_score,
    save_evaluation,
)

FINALIZE_ROLES = {'admin', 'om', 'am', 'kcs'}


class EvaluationCriteriaView(APIView):
    """GET /api/evaluation/criteria/?employee=<id>&eval_type=<type> — bo tieu chi (hoac fallback
    suy tu checklist), kem tinh trang du dieu kien (tien do dao tao, da qua BQL hay chua)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee_id = request.query_params.get('employee')
        eval_type = request.query_params.get('eval_type', 'Skill_BQL')
        if not employee_id:
            return Response({'detail': 'Thiếu tham số employee'}, status=400)

        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)
        source, items = resolve_criteria(employee, eval_type)

        has_bql_done = Evaluation.objects.filter(
            tenant=request.user.tenant, employee=employee, eval_type='Skill_BQL',
            status=Evaluation.Status.DONE,
        ).exists()

        return Response({
            'employee': EmployeeSerializer(employee, context={'request': request}).data,
            'source': source,
            'items': items,
            'training_progress_percent': checklist_progress_percent(employee),
            'has_bql_evaluation': has_bql_done,
            'can_evaluate': can_evaluate(request.user),
        })


class EvaluationDraftView(APIView):
    """GET /api/evaluation/draft/?employee=<id>&eval_type=<type> — ban nhap dang do (neu co)
    cua chinh nguoi dang danh nhap, de resume."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee_id = request.query_params.get('employee')
        eval_type = request.query_params.get('eval_type', 'Skill_BQL')
        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)

        evaluation = Evaluation.objects.filter(
            tenant=request.user.tenant, employee=employee, evaluator=request.user,
            eval_type=eval_type, status=Evaluation.Status.DRAFT,
        ).first()

        latest_done = Evaluation.objects.filter(
            tenant=request.user.tenant, employee=employee, eval_type=eval_type,
            status=Evaluation.Status.DONE,
        ).order_by('-completed_at').first()

        return Response({
            'draft': EvaluationSerializer(evaluation).data if evaluation else None,
            'latest_done': EvaluationSerializer(latest_done).data if latest_done else None,
        })


class EvaluationSaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            evaluation = save_evaluation(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EvaluationSerializer(evaluation).data)


class CouncilSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee_id = request.query_params.get('employee')
        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)
        summary = council_summary(employee)
        summary['employee'] = EmployeeSerializer(employee, context={'request': request}).data
        return Response(summary)


class CouncilSaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            evaluation = save_council_score(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EvaluationSerializer(evaluation).data)


class CouncilFinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee_id = request.data.get('employee')
        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)

        if (request.user.role or '').lower() not in FINALIZE_ROLES:
            return Response({'detail': 'Bạn không có quyền chốt hội đồng.'}, status=403)
        if not is_council_position(employee.position):
            return Response({'detail': 'Nhân sự này không thuộc diện đánh giá Hội đồng.'}, status=400)

        try:
            result = finalize_council(employee)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)
