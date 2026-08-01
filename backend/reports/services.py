"""Dung hop 4 khoi so lieu thanh 1 bao cao dao tao tuan/thang: tinh ky, goi tung khoi, dung
HTML (template Django), va gui email (SMTP cua Django, settings EMAIL_*). Tat ca so lieu deu
tinh bang code (metrics_training.py/metrics_csv.py) - GPT (gpt.py) CHI viet loi nhan xet cho
khoi 4 tu so lieu da tinh san, khong duoc tu tinh/bia so lieu.
"""
import base64

from django.conf import settings
from django.template.loader import render_to_string

from .chart import render_service_score_chart
from .gpt import build_service_audit_analysis
from .metrics_csv import service_audit_block, training_org_block
from .metrics_training import exam_block, new_hires_block
from .period import compute_period, previous_period


def build_report_context(tenant, kind, ref_date):
    start, end, label = compute_period(kind, ref_date)

    context = {
        'tenant_name': tenant.name,
        'kind': kind,
        'kind_label': 'Tuần' if kind == 'week' else 'Tháng',
        'period_label': label,
        'generated_at': ref_date.strftime('%d/%m/%Y'),
        'block1': new_hires_block(tenant, start, end, ref_date),
        'block2': exam_block(tenant, start, end),
        'block3': training_org_block(settings.TRAINING_DATA_CSV_URL, start, end),
        'block4': service_audit_block(settings.SERVICE_AUDIT_CSV_URL, start, end, kind),
    }

    if context['block4'] is not None:
        prev_start, prev_end = previous_period(kind, start)
        previous_block4 = service_audit_block(settings.SERVICE_AUDIT_CSV_URL, prev_start, prev_end, kind)
        context['block4_analysis'] = build_service_audit_analysis(label, context['block4'], previous_block4)
        context['chart_png'] = render_service_score_chart(context['block4']['restaurants'])
    else:
        context['block4_analysis'] = None
        context['chart_png'] = None

    return context


def render_report_html(context, chart_src):
    """chart_src: chuoi da san sang dua vao <img src="..."> (data: URI cho preview web, hoac
    'cid:chart.png' cho email) - None neu khong co chart (chua cau hinh SERVICE_AUDIT_CSV_URL)."""
    ctx = dict(context, chart_src=chart_src)
    return render_to_string('reports/training_report.html', ctx)


def report_subject(context):
    return f"[Báo cáo đào tạo] {context['kind_label']} - {context['tenant_name']} - {context['period_label']}"


def preview_report(tenant, kind, ref_date):
    """Dung cho web xem truoc - anh nhung base64 (data URI) de hien truc tiep trong <img>/iframe."""
    context = build_report_context(tenant, kind, ref_date)
    chart_src = None
    if context['chart_png']:
        chart_src = 'data:image/png;base64,' + base64.b64encode(context['chart_png']).decode('ascii')
    html = render_report_html(context, chart_src)
    return {'subject': report_subject(context), 'html': html}


def send_report_email(tenant, kind, ref_date):
    """Dung dinh dang cid: cho anh (attach kem email) - tuong thich client email tot hon
    data URI (nhieu client email chan data URI). Tra ve {'sent', 'to', 'cc', 'subject'}."""
    from django.core.mail import EmailMultiAlternatives

    to = list(settings.REPORT_TO)
    cc = list(settings.REPORT_CC)
    if not to:
        raise ValueError('REPORT_TO chưa được cấu hình trong .env - không có người nhận.')

    context = build_report_context(tenant, kind, ref_date)
    chart_src = 'cid:chart.png' if context['chart_png'] else None
    html = render_report_html(context, chart_src)
    subject = report_subject(context)

    msg = EmailMultiAlternatives(
        subject=subject, body='Vui lòng xem email ở định dạng HTML.',
        from_email=settings.DEFAULT_FROM_EMAIL, to=to, cc=cc or None,
    )
    msg.attach_alternative(html, 'text/html')
    if context['chart_png']:
        from email.message import MIMEPart

        inline_image = MIMEPart()
        inline_image.set_content(
            context['chart_png'],
            maintype='image', subtype='png',
            disposition='inline', cid='<chart.png>',
        )
        msg.attach(inline_image)
    msg.send(fail_silently=False)

    return {'sent': True, 'to': to, 'cc': cc, 'subject': subject}
