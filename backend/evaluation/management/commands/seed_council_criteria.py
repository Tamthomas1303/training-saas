"""
seed_council_criteria — nạp bộ tiêu chí đánh giá cấp O (mục 7) vào bảng EvaluationCriteria từ
các form thực tế: Vận hành ca (FOH/BOH, Đạt-Không), Tay nghề bếp (BOH, thang 1–4), Phỏng vấn
(FOH/BOH, mỗi vai HCNS/DaoTao/VanHanh/QC một bộ, thang 1–4).

Chạy lại không nhân đôi (update_or_create theo tenant + eval_type + position_group + dept_role +
content). Tiêu chí sửa được sau này ở màn quản trị tiêu chí (Phase 4).

Ghi chú: form FOH "tay nghề pha chế đồ uống" chưa có — sẽ bổ sung khi có.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from evaluation.models import EvaluationCriteria

# ---- Vận hành ca (Đạt/Không → max_score = 1) ----
SHIFTOPS_FOH = [
    ('Mở ca sáng', 'Kiểm tra toàn bộ nhà hàng (an ninh, tài sản, trang thiết bị)'),
    ('Mở ca sáng', 'Kiểm tra email, sổ bàn giao công việc (Logbook)'),
    ('Mở ca sáng', 'Cập nhật doanh thu hôm trước; dự báo và xác định mục tiêu doanh thu ngày/ca'),
    ('Mở ca sáng', 'Kiểm tra lịch làm việc nhân viên và phân công nhân viên trong ca'),
    ('Mở ca sáng', 'Kiểm tra hàng hóa'),
    ('Mở ca sáng', 'Kiểm tra và thực hiện quy trình nhận hàng, sử dụng hàng'),
    ('Mở ca sáng', 'Kết hợp cùng bếp trưởng/bếp phó hoàn thành kế hoạch chuẩn bị hàng hóa và sản phẩm'),
    ('Mở ca sáng', 'Đánh giá các tiêu chí tại các bộ phận trước giờ đón khách (sổ checklist nhà hàng)'),
    ('Mở ca sáng', 'Tiến hành họp ngắn đầu ca để trao đổi thông tin với nhân viên'),
    ('Vận hành trong ca', 'Điều phối nhân viên thực hiện tiêu chuẩn phục vụ giờ cao điểm, xử lý chậm trễ'),
    ('Vận hành trong ca', 'Thể hiện hình mẫu tinh thần vì khách hàng và nguyên tắc làm việc'),
    ('Vận hành trong ca', 'Chủ động thăm hỏi, giao tiếp, theo sát mức độ hài lòng và phản hồi của khách'),
    ('Vận hành trong ca', 'Động viên, hướng dẫn nhân viên (nguyên tắc 5W1H) và khen thưởng'),
    ('Vận hành trong ca', 'Áp dụng nguyên tắc L.A.S.T để giải quyết phàn nàn của khách'),
    ('Vận hành trong ca', 'Đảm bảo nhân viên tuân thủ quy trình quản lý tiền trong ca'),
    ('Vận hành trong ca', 'Hướng dẫn và thực hiện các giao dịch đặc biệt trong ca chính xác (KM, giảm giá…)'),
    ('Bàn giao/Đóng ca', 'Kiểm tra vệ sinh tại các bộ phận sau giờ cao điểm (sổ checklist nhà hàng)'),
    ('Bàn giao/Đóng ca', 'Thực hiện đúng quy trình kiểm kê và đặt hàng cuối ca/ngày (đúng biểu mẫu)'),
    ('Bàn giao/Đóng ca', 'Theo dõi hàng bỏ và chênh lệch hàng hóa; xác định nguyên nhân, hướng kiểm soát'),
    ('Bàn giao/Đóng ca', 'Hoàn tất các công tác hành chính và báo cáo cuối ca'),
    ('Bàn giao/Đóng ca', 'Thực hiện bàn giao ca hoặc viết sổ bàn giao với quản lý ca sau'),
    ('Bàn giao/Đóng ca', 'Kiểm tra an toàn, an ninh, niêm phong cuối ngày trước khi đóng cửa'),
    ('Bàn giao/Đóng ca', 'Bàn giao và ghi sổ với bảo vệ nội bộ (nếu có)'),
]

SHIFTOPS_BOH = [
    ('Mở ca sáng', 'Kiểm tra toàn bộ khu vực bếp (an ninh, tài sản, trang thiết bị)'),
    ('Mở ca sáng', 'Kiểm tra sổ bàn giao công việc/email (Logbook)'),
    ('Mở ca sáng', 'Nhận số liệu dự trù hàng hóa từ bếp trưởng'),
    ('Mở ca sáng', 'Kiểm tra lịch làm việc và phân công nhân viên trong ca'),
    ('Mở ca sáng', 'Kiểm tra tem nhãn mác, bảo quản sản phẩm, số lượng đã sơ chế hôm trước'),
    ('Mở ca sáng', 'Kiểm tra và thực hiện quy trình nhận hàng, sử dụng hàng'),
    ('Mở ca sáng', 'Điều phối hoàn thành kế hoạch chuẩn bị hàng hóa, CCDC và sản phẩm trong ca'),
    ('Mở ca sáng', 'Kiểm tra vệ sinh, sạch sẽ và tiêu chuẩn sản phẩm trước giờ đón khách'),
    ('Mở ca sáng', 'Kiểm tra tiêu chuẩn set up quầy trước giờ bán hàng'),
    ('Mở ca sáng', 'Trao đổi với QL đứng ca tình hình sản phẩm (cần upsell, hết hàng…)'),
    ('Mở ca sáng', 'Tiến hành họp ngắn đầu ca để trao đổi thông tin với nhân viên'),
    ('Vận hành trong ca', 'Nhận order và điều phối ra đồ, kiểm soát thời gian ra đồ'),
    ('Vận hành trong ca', 'Kiểm tra chất lượng, hình ảnh sản phẩm trước khi xuất đồ'),
    ('Vận hành trong ca', 'Quan sát điều phối các quầy bếp, phản hồi vấn đề không phù hợp'),
    ('Vận hành trong ca', 'Phối hợp với QL ca xử lý tình huống phát sinh; đảm bảo khách hài lòng'),
    ('Vận hành trong ca', 'Món ăn sẵn sàng phục vụ; thiếu không quá 5% món trên Menu (trừ mùa vụ)'),
    ('Vận hành trong ca', 'Đảm bảo vệ sinh, an toàn trong bếp suốt giờ vận hành'),
    ('Bàn giao/Đóng ca', 'Theo dõi hàng bỏ và chênh lệch hàng hóa; xác định nguyên nhân, hướng kiểm soát'),
    ('Bàn giao/Đóng ca', 'Thực hiện đúng quy trình kiểm kê và đặt hàng cuối ca/ngày (đúng biểu mẫu)'),
    ('Bàn giao/Đóng ca', 'Kiểm tra vệ sinh, bảo quản hàng hóa, tem nhãn hạn sử dụng tại các quầy'),
    ('Bàn giao/Đóng ca', 'Kiểm tra lịch làm việc, điều phối nhân sự cho ca kế tiếp nếu cần'),
    ('Bàn giao/Đóng ca', 'Bàn giao và ghi sổ với bộ phận bảo vệ nội bộ (nếu có)'),
    ('Bàn giao/Đóng ca', 'Kiểm tra an toàn, an ninh, niêm phong cuối ngày trước khi đóng cửa'),
    ('Kỹ năng chế biến', 'Tuân thủ vệ sinh an toàn thực phẩm khi chế biến món'),
    ('Kỹ năng chế biến', 'Nguyên liệu sử dụng chế biến đúng theo Chart'),
    ('Kỹ năng chế biến', 'Trình tự thao tác chế biến đúng các bước trên Chart'),
    ('Kỹ năng chế biến', 'Mùi thơm của sốt và nguyên liệu đạt yêu cầu'),
    ('Kỹ năng chế biến', 'Nhiệt độ món ăn đúng tiêu chuẩn'),
    ('Kỹ năng chế biến', 'Màu sắc các thành phần nguyên liệu sau chế biến đúng tiêu chuẩn'),
    ('Kỹ năng chế biến', 'Trình bày: món ăn sắp xếp đẹp mắt, dùng đúng CCDC theo Chart'),
    ('Kỹ năng chế biến', 'Kiểm tra sản phẩm đảm bảo chất lượng trước khi phục vụ (cả dụng cụ)'),
    ('Kỹ năng chế biến', 'Món ăn hoàn thành trong thời gian quy định'),
    ('Kỹ năng chế biến', 'Bộ Chart hướng dẫn chế biến được sử dụng tại khu vực làm việc'),
]

# ---- Tay nghề bếp BOH (thang 1–4 → max_score = 4) ----
SKILL_BOH = [
    ('I. Chuẩn bị', 'Hình ảnh diện mạo đúng tiêu chuẩn'),
    ('I. Chuẩn bị', 'Công cụ dụng cụ đầy đủ, đúng tiêu chuẩn'),
    ('I. Chuẩn bị', 'Nguyên liệu, gia vị đầy đủ, đúng tiêu chuẩn'),
    ('II. Thực hành', 'Sơ chế đúng tiêu chuẩn'),
    ('II. Thực hành', 'Hao hụt đúng tỷ lệ cho phép khi sơ chế'),
    ('II. Thực hành', 'Chế biến món đúng theo chart'),
    ('II. Thực hành', 'Tư thế tác phong nhanh nhẹn, dứt khoát'),
    ('II. Thực hành', 'Tuân thủ các yêu cầu về VSATTP'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng sử dụng CCDC: dao, chảo, bếp'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng làm món thành thạo'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng nhận biết, đánh giá độ tươi ngon và tiêu chuẩn nguyên liệu'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng sắp xếp tổ chức công việc khi thực hành món'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo thời gian ra món'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo món ra đúng hình ảnh, đẹp'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng mùi vị món ăn'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng màu sắc món ăn'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng trạng thái món ăn'),
    ('V. Trình bày/Kiến thức', 'Thuyết trình món ăn'),
    ('V. Trình bày/Kiến thức', 'Trả lời các câu hỏi liên quan đến kiến thức món'),
]

# ---- Tay nghề pha chế FOH (thang 1–4 → max_score = 4) ----
SKILL_FOH = [
    ('I. Chuẩn bị', 'Hình ảnh diện mạo đúng tiêu chuẩn'),
    ('I. Chuẩn bị', 'Công cụ dụng cụ đầy đủ, đúng tiêu chuẩn'),
    ('I. Chuẩn bị', 'Nguyên liệu đầy đủ, đúng tiêu chuẩn'),
    ('II. Thực hành', 'Sơ chế đúng tiêu chuẩn'),
    ('II. Thực hành', 'Hao hụt đúng tỷ lệ cho phép khi sơ chế'),
    ('II. Thực hành', 'Pha chế đồ uống đúng theo chart'),
    ('II. Thực hành', 'Tư thế tác phong nhanh nhẹn, dứt khoát'),
    ('II. Thực hành', 'Tuân thủ các yêu cầu về VSATTP'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng sử dụng CCDC: dao, máy xay'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng pha chế thành thạo: lắc, khuấy, xay'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng nhận biết, đánh giá độ tươi ngon và tiêu chuẩn nguyên liệu'),
    ('III. Đánh giá kỹ năng', 'Kỹ năng sắp xếp tổ chức công việc khi thực hành món'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo thời gian ra đồ uống'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo món ra đúng hình ảnh, đẹp'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng mùi vị đồ uống'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng màu sắc đồ uống'),
    ('IV. Tiêu chuẩn ra món', 'Đảm bảo đúng trạng thái'),
    ('V. Trình bày/Kiến thức', 'Thuyết trình đồ uống'),
    ('V. Trình bày/Kiến thức', 'Trả lời các câu hỏi liên quan đến kiến thức món'),
]

# ---- Phỏng vấn (thang 1–4 → max_score = 4), theo vai người chấm ----
INTERVIEW_FOH = {
    'HCNS': [
        'Tác phong, thái độ', 'Chịu áp lực công việc', 'Khả năng làm việc và phối hợp',
        'Kiến thức cơ chế chính sách công ty', 'Kiểm soát nhân sự', 'Kiểm soát chi phí COL',
    ],
    'DaoTao': [
        'Trình độ chuyên môn chung', 'Kỹ năng đào tạo huấn luyện nhân sự',
        'Kiến thức lộ trình thăng tiến nhân sự', 'Lập kế hoạch nhân sự',
        'Chăm sóc khách hàng và xử lý các vấn đề', 'Khả năng phối hợp trong công việc',
    ],
    'VanHanh': [
        'Trình độ chuyên môn chung', 'Kỹ năng vận hành ca và xử lý tình huống phát sinh',
        'Quản lý nhân sự và chi phí COL', 'Quản lý hàng hóa',
        'Kiểm soát tiền mặt và báo cáo, chứng từ, hồ sơ',
    ],
    'QC': [
        'Trình độ chuyên môn chung', 'Kiểm soát vệ sinh an toàn thực phẩm',
        'Quản lý hàng hóa', 'Kiểm soát chất lượng',
    ],
}

INTERVIEW_BOH = {
    'HCNS': [
        'Tác phong, thái độ', 'Chịu áp lực công việc', 'Khả năng làm việc và phối hợp',
        'Kiến thức cơ chế chính sách công ty', 'Kiểm soát nhân sự', 'Kiểm soát chi phí COL',
    ],
    'DaoTao': [
        'Trình độ chuyên môn chung', 'Kỹ năng đào tạo huấn luyện nhân sự',
        'Kiến thức lộ trình thăng tiến nhân sự', 'Lập kế hoạch nhân sự',
    ],
    'VanHanh': [
        'Trình độ chuyên môn chung', 'Kỹ năng vận hành ca và xử lý tình huống phát sinh',
        'Quản lý nhân sự và chi phí COL', 'Quản lý hàng hóa', 'Kiểm soát chất lượng',
    ],
    'QC': [
        'Trình độ chuyên môn chung', 'Kiểm soát vệ sinh an toàn thực phẩm',
        'Quản lý hàng hóa', 'Kiểm soát chất lượng',
    ],
}

DEPT_LABEL = {'HCNS': 'TP HCNS (Chủ tịch)', 'DaoTao': 'TP Đào tạo (Phó chủ tịch)',
              'VanHanh': 'TP Vận hành (Ủy viên)', 'QC': 'TP QC (Ủy viên)'}


class Command(BaseCommand):
    help = 'Nap bo tieu chi danh gia cap O (van hanh ca / tay nghe / phong van) vao EvaluationCriteria'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        n = 0

        def upsert(eval_type, position_group, dept_role, section, content, max_score, order):
            EvaluationCriteria.objects.update_or_create(
                tenant=tenant, eval_type=eval_type, position_group=position_group,
                dept_role=dept_role, content=content,
                defaults={'section': section, 'max_score': max_score, 'order': order},
            )

        # Vận hành ca
        for i, (sec, ct) in enumerate(SHIFTOPS_FOH):
            upsert('ShiftOps', 'FOH', '', sec, ct, 1, i); n += 1
        for i, (sec, ct) in enumerate(SHIFTOPS_BOH):
            upsert('ShiftOps', 'BOH', '', sec, ct, 1, i); n += 1
        # Tay nghề bếp (BOH) + pha chế (FOH)
        for i, (sec, ct) in enumerate(SKILL_BOH):
            upsert('Council_Skill', 'BOH', '', sec, ct, 4, i); n += 1
        for i, (sec, ct) in enumerate(SKILL_FOH):
            upsert('Council_Skill', 'FOH', '', sec, ct, 4, i); n += 1
        # Phỏng vấn (mỗi vai một bộ)
        for grp, mapping in (('FOH', INTERVIEW_FOH), ('BOH', INTERVIEW_BOH)):
            order = 0
            for dept, items in mapping.items():
                for ct in items:
                    upsert('Council_Interview', grp, dept, DEPT_LABEL[dept], ct, 4, order); order += 1; n += 1

        self.stdout.write(self.style.SUCCESS(
            f'Da nap {n} tieu chi cap O: van hanh ca FOH/BOH + tay nghe BOH & pha che FOH + phong van FOH/BOH.'
        ))
