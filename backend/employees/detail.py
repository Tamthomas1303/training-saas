"""Chi tiet 1 hoc vien (man Chi tiet hoc vien - muc 5.4). Port EmployeeService.gs::getStudentDetail.

Gop du lieu tu nhieu app (checklist/evaluation/cls_sync) - import tre trong ham de tranh
vong lap import giua cac app.
"""
from .services import checklist_progress_percent, matching_checklist_items


def student_info(employee):
    return {
        'employee_id': employee.id,
        'code': employee.code,
        'name': employee.name,
        'restaurant': employee.restaurant.name if employee.restaurant else '',
        'restaurant_id': employee.restaurant_id,
        'brand': employee.restaurant.brand if employee.restaurant else '',
        'position': employee.position,
        'level_group': employee.level_group,
        'operation_unit': employee.operation_unit,
        'start_date': employee.start_date,
        'work_status': employee.employee_status,
        'probation_days': employee.probation_days,
        'probation_result': employee.final_result,
        'skill_result': employee.skill_result,
        'shift_ops': employee.shift_ops,
        'office_result': employee.office_result,
        'trainer_name': employee.trainer.full_name if employee.trainer else '',
    }


def student_checklist(employee):
    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee)
    progress_by_checklist = {
        p.checklist_id: p
        for p in TrainingProgress.objects.filter(employee=employee).select_related('trainer')
    }
    rows = []
    for c in items:
        p = progress_by_checklist.get(c.id)
        rows.append({
            'checklist_id': c.id, 'name': c.task_name, 'category': c.category, 'day': c.day,
            'doc_url': c.doc_url,
            'status': p.status if p else 'pending',
            'trainer_name': p.trainer.full_name if p and p.trainer else '',
            'completed_at': p.completed_at if p else None,
            'pdf_url': p.pdf_url if p else '',
        })
    return rows


def student_lms(employee):
    from cls_sync.models import CourseResult, ExamResult

    courses = CourseResult.objects.filter(employee=employee).order_by('course_name')
    exams = ExamResult.objects.filter(employee=employee).order_by('exam_name', 'attempt')
    return {
        'course_done': courses.filter(status='Đạt').exists(),
        'courses': [
            {'name': c.course_name, 'score': c.score, 'status': c.status} for c in courses
        ],
        'exams': [
            {'name': e.exam_name, 'attempt': e.attempt, 'score': e.score, 'passed': e.passed} for e in exams
        ],
    }


def student_evaluations(employee):
    from evaluation.models import Evaluation
    from evaluation.serializers import EvaluationSerializer

    evals = Evaluation.objects.filter(employee=employee).order_by('-date', '-id')
    return EvaluationSerializer(evals, many=True).data


def student_council(employee):
    from evaluation.services import council_summary, is_council_position

    if not is_council_position(employee.position):
        return None
    return council_summary(employee)


def export_probation_result_pdf(employee):
    """Xuat phieu ket qua thu viec PDF - chi goi khi final_result la 'Pass thu viec' (kiem
    tra o view, khac ban goc chi kiem client-side). Diem tong = thi*0.4 + thuc hanh*0.6."""
    from django.utils import timezone

    from checklist.storage import upload_pdf_bytes
    from evaluation.models import Evaluation

    from .pdf import build_probation_result_pdf
    from .services import best_exam_score

    lms = student_lms(employee)
    score_exam = best_exam_score(employee)
    latest_skill = (
        Evaluation.objects.filter(employee=employee, eval_type='Skill_BQL', status='done')
        .order_by('-completed_at').first()
    )
    score_practice = float(latest_skill.percent) if latest_skill else None
    score_final = round(score_exam * 0.4 + score_practice * 0.6) if score_practice is not None else None

    pdf_bytes = build_probation_result_pdf({
        'record_no': f'{employee.id}/{timezone.now().year}',
        'tenant_name': employee.tenant.name,
        'employee': {
            'name': employee.name, 'position': employee.position,
            'restaurant': employee.restaurant.name if employee.restaurant else '',
            'start_date': employee.start_date.strftime('%d/%m/%Y') if employee.start_date else '',
        },
        'courses': lms['courses'], 'exams': lms['exams'],
        'score_exam': score_exam, 'score_practice': score_practice, 'score_final': score_final,
        'final_status': employee.final_result,
        'signer_name': '', 'signer_title': 'Phòng Đào tạo',
    })
    return upload_pdf_bytes(pdf_bytes, f'ketquathuviec/{employee.tenant_id}', f'KetQuaThuViec_{employee.id}')


def student_detail(employee):
    from checklist.models import TrainingProgress

    progress_percent = checklist_progress_percent(employee)
    items = matching_checklist_items(employee)
    done = TrainingProgress.objects.filter(
        employee=employee, checklist_id__in=[c.id for c in items], status=TrainingProgress.Status.DONE,
    ).count()

    return {
        'info': student_info(employee),
        'progress': {'percent': progress_percent, 'done': done, 'total': len(items)},
        'checklist': student_checklist(employee),
        'lms': student_lms(employee),
        'evaluations': student_evaluations(employee),
        'council': student_council(employee),
    }
