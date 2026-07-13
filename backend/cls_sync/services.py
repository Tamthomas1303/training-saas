from django.conf import settings
from django.db.models import Max

from .models import CourseResult


def onboarding_eligible(employee, threshold=None):
    """Điểm Hội nhập cao nhất (CourseResult) >= threshold → đủ điều kiện thi.

    Port của ProbationService.gs::_hoiNhapScore + eligible (giữ đúng ngưỡng 80).
    """
    threshold = settings.CLS_ONBOARDING_PASS_SCORE if threshold is None else threshold
    best = CourseResult.objects.filter(
        employee=employee, course_name__icontains='hội nhập'
    ).aggregate(best=Max('score'))['best']
    return best is not None and best >= threshold
