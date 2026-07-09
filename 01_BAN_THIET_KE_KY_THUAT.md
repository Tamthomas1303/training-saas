# BẢN THIẾT KẾ KỸ THUẬT v1 — SaaS đa tenant (Python + React)

Tài liệu blueprint để **Claude Code** (trong VS Code) dựng dự án. Người mới chỉ cần ra lệnh cho Claude Code làm theo từng bước ở mục "Lộ trình sprint".

## 0. Quyết định đã chốt (GĐ dự án)
- **Mô hình:** SaaS đa tenant (1 hệ thống, nhiều doanh nghiệp, tách dữ liệu theo tenant).
- **Frontend:** React.
- **Backend:** Python — **Django + Django REST Framework (DRF)**.
- **Phạm vi v1:** đúng các tác vụ đang có trên Apps Script, **chưa mở rộng LMS**. LMS vẫn dùng **CLS**, kéo dữ liệu học/thi về qua **API CLS** (giữ logic hiện có).
- **Ngân sách hạ tầng:** 0đ (dùng free tier).

## 1. Stack cụ thể (đều có bản miễn phí)
| Thành phần | Công nghệ | Host free |
|---|---|---|
| Backend API | Django + DRF | Render Free |
| Frontend | React + Vite | Vercel Free |
| CSDL | PostgreSQL | Supabase Free |
| Xác thực | JWT (djangorestframework-simplejwt) | — |
| Lưu file (ảnh, chữ ký, PDF) | Supabase Storage / Cloudflare R2 | Free |
| Tác vụ nền (PDF, email, đồng bộ CLS) | Django management command + cron (Render Cron / GitHub Actions) | Free |
| Sinh PDF | WeasyPrint hoặc ReportLab | — |
| Email | Resend / Brevo | Free tier |

> Giai đoạn 0đ: **không dùng Redis/Celery** (tốn tiền/phức tạp) — dùng lệnh nền + cron miễn phí là đủ.

## 2. Đa tenant (đơn giản cho v1)
- Mọi bảng có cột **`tenant_id`**.
- **Middleware** xác định tenant hiện tại (theo subdomain hoặc theo tenant của user đăng nhập) → mọi truy vấn tự lọc theo `tenant_id`.
- Chưa cần Row-Level Security phức tạp ở v1; nâng cấp sau khi có nhiều khách.

## 3. Cấu trúc thư mục
```
Training_SaaS_Python/
├── backend/            # Django project + apps (accounts, employees, training, evaluation, kpi, reports, cls_sync)
├── frontend/           # React (Vite) + các trang tương ứng
├── docs/               # ERD, ghi chú
├── .gitignore
└── README.md
```

## 4. Phạm vi v1 — port nguyên nghiệp vụ Apps Script
- **Tenant + Người dùng & Phân quyền**: Admin, OM, BOD, AM, KCS, BQL, Trainer + `job_title` (QLNH/Giám sát/Bếp trưởng/Bếp phó) + Nhà hàng.
- **Nhân sự (Onboarding)**: bảng Postgres thật (bỏ cơ chế snapshot/app_employees — DB thật đã nhanh).
- **Checklist đào tạo + Tiến độ**: 3 ảnh (tài liệu/lý thuyết/thực hành) + 2 chữ ký + **biên bản PDF**.
- **Đánh giá kỹ năng + Hội đồng** (nhiều giám khảo, tính trung bình).
- **KPI đào tạo** (buổi + biên bản PDF) + **Phụ cấp/Hoa hồng trainer**.
- **Kết quả thử việc**: nhân bản logic cột T (Sản xuất → Pass; Văn phòng/Bếp TT & cấp O → 60 ngày; NV nhà hàng S/P → 15 ngày; điểm thi/thực hành…), tính trong Python.
- **Báo cáo PDF** (KPI BQL, phụ cấp) + **Email tự động** (NV mới → nhà hàng; Pass → nhà hàng + CC + đính kèm PDF).
- **Đồng bộ CLS**: kéo kết quả **học (DB_KetQuaHoc)** & **thi (DB_KetQuaThi)** về Postgres qua **API CLS** (giữ logic: Hội nhập ≥80 → đủ đk thi; thi lần 1 (J/K), lần 2/3 cao nhất (L/M)).

## 5. Mô hình dữ liệu (ERD sơ bộ — Claude Code chi tiết hóa)
- **Tenant**(id, name, plan, status)
- **User**(id, tenant_id, username, password_hash, full_name, role, job_title, trainer_zone, restaurant_id, google_email, status)
- **Restaurant**(id, tenant_id, code, name, brand, city, district, region, email, status)
- **Employee**(id, tenant_id, code, name, position, operation_unit, job_level, level_group, start_date, restaurant_id, employee_status, probation_days, skill_score, skill_result, shift_ops, office_result, final_result, trainer_id, commission_status, retrain_deadline)
- **Checklist**(id, tenant_id, brand, position, day, category, task_name, description, doc_url, level_group, order)
- **TrainingProgress**(id, tenant_id, employee_id, checklist_id, trainer_id, status, img_tailieu, img_lythuyet, img_thuchanh, sign_trainer, sign_trainee, pdf_url, completed_at)
- **Evaluation** / **EvaluationDetail** / **Council** (giám khảo, điểm 3 khía cạnh)
- **KpiSession** / **KpiParticipant**
- **Commission**
- **Document**
- **ExamResult** / **CourseResult** (từ CLS)

## 6. Lộ trình sprint (ra lệnh cho Claude Code lần lượt)
1. **Khởi tạo**: tạo backend Django + frontend React (Vite); nối Supabase Postgres; auth JWT; model Tenant + User; đăng nhập/phân quyền.
2. **Nhân sự & Nhà hàng & Checklist**: model + API + màn React (danh sách + lọc + phân trang + popup — như bản Apps Script hiện tại).
3. **Đào tạo**: tiến độ + upload ảnh/chữ ký + sinh biên bản PDF.
4. **Đánh giá + Hội đồng**.
5. **KPI + Phụ cấp + Báo cáo PDF + Email**.
6. **Đồng bộ CLS + tính kết quả thử việc**.
7. **Multi-tenant hoàn thiện + onboarding khách + Deploy** (Vercel + Render + Supabase, 0đ).

## 7. Di trú dữ liệu
- Khi sẵn sàng: viết script ETL **export Google Sheets → import PostgreSQL** (gắn `tenant_id` cho doanh nghiệp đầu tiên).
- Trong lúc chuyển tiếp: **giữ CLS sync qua API** như hiện tại.

## 8. Nguyên tắc bắt buộc
- **KHÔNG đụng code Apps Script.** Dự án này độc lập trong `Training_SaaS_Python`.
- Không tắt hệ Apps Script cho tới khi bản Python phục vụ ổn ≥ 1 khách thật.
