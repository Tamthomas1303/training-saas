"""
history_import.py — nạp DỮ LIỆU LỊCH SỬ của nhân sự cũ (M4.1). Hai mẫu:

  2) Kết quả thi BQL/lịch sử (CLS): Employee_ID, Exam_Name, Exam_Date, Score, Result, Position
  3) Đánh giá lịch sử:              Employee_ID, Eval_Type, Position, Percent, Result, Date

Nạp dưới dạng bản ghi "đã có" để báo cáo/điều kiện phản ánh đúng thực tế. Dùng lại
recruitment.load_rows_from_upload để đọc file Excel/CSV.
"""
from datetime import datetime

from cls_sync.models import ExamResult
from employees.models import Employee
from evaluation.models import Evaluation

DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d')


def _parse_date(value):
    value = (value or '').strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(value):
    try:
        return float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _is_pass(result_text, score, threshold=80):
    t = (result_text or '').strip().lower()
    if 'đạt' in t or 'pass' in t or t in ('true', '1', 'ok'):
        return True
    if 'không' in t or 'fail' in t or 'trượt' in t:
        return False
    return score is not None and score >= threshold


def _employee_map(tenant):
    return {e.code: e for e in Employee.objects.filter(tenant=tenant)}


def ingest_exam_history(tenant, rows):
    """Mẫu 2 — kết quả thi lịch sử → ExamResult (upsert theo employee+exam_name+attempt=1)."""
    emp_by_code = _employee_map(tenant)
    created = updated = skipped = 0
    for row in rows:
        code = (row.get('Employee_ID') or '').strip()
        exam_name = (row.get('Exam_Name') or '').strip()
        employee = emp_by_code.get(code)
        if not employee or not exam_name:
            skipped += 1
            continue
        score = _to_float(row.get('Score'))
        passed = _is_pass(row.get('Result'), score)
        _, was_created = ExamResult.objects.update_or_create(
            tenant=tenant, employee=employee, exam_name=exam_name, attempt=1,
            defaults={'score': score, 'passed': passed, 'cls_id': 'history'},
        )
        created += int(was_created)
        updated += int(not was_created)
    return {'created': created, 'updated': updated, 'skipped': skipped, 'total': len(rows)}


def ingest_evaluation_history(tenant, rows):
    """Mẫu 3 — đánh giá lịch sử → Evaluation (status done, đánh dấu [Import lịch sử])."""
    emp_by_code = _employee_map(tenant)
    created = skipped = 0
    for row in rows:
        code = (row.get('Employee_ID') or '').strip()
        employee = emp_by_code.get(code)
        if not employee:
            skipped += 1
            continue
        eval_type = (row.get('Eval_Type') or 'Skill_BQL').strip()
        percent = _to_float(row.get('Percent')) or 0
        passed = _is_pass(row.get('Result'), percent, threshold=85)
        date = _parse_date(row.get('Date'))
        Evaluation.objects.create(
            tenant=tenant, employee=employee, evaluator=None, eval_type=eval_type,
            percent=percent, total_score=percent, max_score=100,
            result=Evaluation.Result.PASS if passed else Evaluation.Result.FAIL,
            status=Evaluation.Status.DONE, date=date,
            note=f"[Import lịch sử]{(' vị trí ' + row.get('Position')) if row.get('Position') else ''}",
        )
        created += 1
    return {'created': created, 'skipped': skipped, 'total': len(rows)}
