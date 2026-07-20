"""API Hội đồng đánh giá cấp O (Phase 2). Gồm cả endpoint khách mời (không cần đăng nhập)."""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee

from . import council_service as cs
from .models import Council, CouncilMember


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
