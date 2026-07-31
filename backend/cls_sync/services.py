from django.conf import settings
from django.db.models import Max, Q

from .models import CourseResult


def onboarding_eligible(employee, threshold=None):
    """Điểm Hội nhập cao nhất (CourseResult) >= threshold → đủ điều kiện thi.

    Port của ProbationService.gs::_hoiNhapScore + eligible (giữ đúng ngưỡng 80).

    Fallback: neu chua co diem dat nguong (vd cot diem chua dong bo dung tu CLS), van coi la
    du dieu kien neu co khoa "hoi nhap" da co status='Đạt' HOAC progress=100 - phong khi khoa
    thuc te da hoan thanh nhung diem/status chua kip cap nhat dung luc sync.
    """
    threshold = settings.CLS_ONBOARDING_PASS_SCORE if threshold is None else threshold
    onboarding_courses = CourseResult.objects.filter(employee=employee, course_name__icontains='hội nhập')

    best = onboarding_courses.aggregate(best=Max('score'))['best']
    if best is not None and best >= threshold:
        return True

    return onboarding_courses.filter(Q(status='Đạt') | Q(progress=100)).exists()
