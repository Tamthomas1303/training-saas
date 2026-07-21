"""API Hội đồng đánh giá cấp O (Phase 2). Gồm cả endpoint khách mời (không cần đăng nhập)."""
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from employees.models import Employee

from . import council_service as cs
from .models import Council, CouncilMember, EvaluationCriteria
from .serializers import EvaluationCriteriaSerializer


class CouncilCriteriaViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD bộ tiêu chí đánh giá cấp O (Phase 4). Sửa/thêm/xóa chỉ Admin/OM. Lọc theo
    eval_type (ShiftOps/Council_Skill/Council_Interview) + position_group (FOH/BOH) + dept_role."""

    serializer_class = EvaluationCriteriaSerializer
    queryset = EvaluationCriteria.objects.all().order_by('eval_type', 'position_group', 'dept_role', 'order')
    filterset_fields = ['eval_type', 'position_group', 'dept_role', 'brand', 'position', 'level_group']
    pagination_class = None

    def _guard(self):
        if (self.request.user.role or '').lower() not in {'admin', 'om'}:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin/OM được sửa tiêu chí đánh giá.')

    def create(self, request, *args, **kwargs):
        self._guard()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._guard()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._guard()
        return super().destroy(request, *args, **kwargs)


def _b(value):
    return str(value).strip().lower() in ('true', '1', 'yes', 'x', 'có')


class CriteriaImportView(APIView):
    """POST /api/evaluation/council-criteria/import-file/ (multipart 'file') — nhập bộ tiêu chí
    từ Excel/CSV (cột: Brand, Position, Level_Group, Eval_Type, Section, Content, Max_Score,
    Is_Mandatory, Require_Photo, Order). Admin/OM. Chạy lại không nhân đôi."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if (request.user.role or '').lower() not in {'admin', 'om'}:
            return Response({'detail': 'Chỉ Admin/OM được nhập tiêu chí.'}, status=403)
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Chưa chọn file.'}, status=400)
        from employees.recruitment import load_rows_from_upload

        try:
            rows = load_rows_from_upload(f)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Không đọc được file: {exc}'}, status=400)

        tenant = request.user.tenant
        created = updated = skipped = 0

        def g(row, *names):
            for n in names:
                if row.get(n) not in (None, ''):
                    return str(row.get(n)).strip()
            return ''

        def num(v):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return 0

        for r in rows:
            content = g(r, 'Content', 'content', 'Noi_Dung')
            if not content:
                skipped += 1
                continue
            _, was_created = EvaluationCriteria.objects.update_or_create(
                tenant=tenant,
                brand=g(r, 'Brand'), position=g(r, 'Position'),
                eval_type=g(r, 'Eval_Type'), content=content,
                defaults={
                    'level_group': g(r, 'Level_Group'),
                    'section': g(r, 'Section'),
                    'max_score': num(g(r, 'Max_Score')),
                    'is_mandatory': _b(g(r, 'Is_Mandatory')),
                    'require_photo': _b(g(r, 'Require_Photo')),
                    'order': num(g(r, 'Order')),
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        return Response({'created': created, 'updated': updated, 'skipped': skipped, 'total': len(rows)})


def _err(exc):
    return Response({'detail': str(exc)}, status=400)


class ShiftOpsFormView(APIView):
    def get(self, request):
        employee = get_object_or_404(Employee, pk=request.query_params.get('employee'), tenant=request.user.tenant)
        data = cs.shiftops_form(employee)
        data['employee'] = {'name': employee.name, 'position': employee.position}
        return Response(data)


class ShiftOpsSaveView(APIView):
    def post(self, request):
        employee = get_object_or_404(Employee, pk=request.data.get('employee'), tenant=request.user.tenant)
        try:
            r = cs.submit_shiftops(request.user, employee, request.data.get('scores') or {}, request.data.get('sign') or '')
        except cs.CouncilError as e:
            return _err(e)
        return Response(r)


class CouncilCreateView(APIView):
    def post(self, request):
        employee = get_object_or_404(Employee, pk=request.data.get('employee'), tenant=request.user.tenant)
        try:
            council = cs.create_council(request.user, employee, request.data.get('kind'))
        except cs.CouncilError as e:
            return _err(e)
        return Response(cs.council_detail(council))


class CouncilAddMemberView(APIView):
    def post(self, request):
        council = get_object_or_404(Council, pk=request.data.get('council'), tenant=request.user.tenant)
        try:
            cs.add_member(
                request.user, council,
                user_id=request.data.get('user_id'),
                guest_name=request.data.get('guest_name', ''),
                guest_dept=request.data.get('guest_dept', ''),
                dept_role=request.data.get('dept_role', ''),
            )
        except cs.CouncilError as e:
            return _err(e)
        return Response(cs.council_detail(council))


class CouncilDetailView(APIView):
    def get(self, request):
        cid = request.query_params.get('council')
        if cid:
            council = get_object_or_404(Council, pk=cid, tenant=request.user.tenant)
        else:
            employee = get_object_or_404(Employee, pk=request.query_params.get('employee'), tenant=request.user.tenant)
            kind = request.query_params.get('kind')
            council = (Council.objects.filter(tenant=request.user.tenant, employee=employee, kind=kind)
                       .order_by('-created_at').first())
            if not council:
                return Response({'council_id': None, 'kind': kind, 'members': [], 'exists': False})
        data = cs.council_detail(council)
        data['exists'] = True
        return Response(data)


class CouncilMemberFormView(APIView):
    def get(self, request):
        member = get_object_or_404(CouncilMember, pk=request.query_params.get('member'), tenant=request.user.tenant)
        role = (request.user.role or '').lower()
        if member.user_id != request.user.id and role not in cs.COUNCIL_ADMIN_ROLES:
            return Response({'detail': 'Không phải phần chấm của bạn.'}, status=403)
        return Response(cs.member_form(member))


class CouncilSubmitView(APIView):
    def post(self, request):
        member = get_object_or_404(CouncilMember, pk=request.data.get('member'), tenant=request.user.tenant)
        role = (request.user.role or '').lower()
        if member.user_id != request.user.id and role not in cs.COUNCIL_ADMIN_ROLES:
            return Response({'detail': 'Không phải phần chấm của bạn.'}, status=403)
        try:
            r = cs.submit_member_score(
                member, request.data.get('scores') or {}, dish_name=request.data.get('dish_name', ''),
                sign=request.data.get('sign', ''), evaluator_user=member.user or request.user,
            )
        except cs.CouncilError as e:
            return _err(e)
        return Response(r)


class CouncilFinalizeOView(APIView):
    def post(self, request):
        council = get_object_or_404(Council, pk=request.data.get('council'), tenant=request.user.tenant)
        try:
            r = cs.finalize_council(request.user, council)
        except cs.CouncilError as e:
            return _err(e)
        return Response(r)


class CouncilPdfView(APIView):
    def get(self, request):
        council = get_object_or_404(Council, pk=request.query_params.get('council'), tenant=request.user.tenant)
        try:
            url = cs.export_council_pdf(council)
        except cs.CouncilError as e:
            return _err(e)
        return Response({'pdf_url': url})


# ---------------- Khách mời (không cần đăng nhập) ----------------
class GuestFormView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        member = get_object_or_404(CouncilMember, token=token)
        return Response(cs.member_form(member))


class GuestSubmitView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        member = get_object_or_404(CouncilMember, token=token)
        try:
            r = cs.submit_member_score(
                member, request.data.get('scores') or {}, dish_name=request.data.get('dish_name', ''),
                sign=request.data.get('sign', ''), evaluator_user=None,
            )
        except cs.CouncilError as e:
            return _err(e)
        return Response(r)
