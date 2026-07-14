# HƯỚNG DẪN NỐI SUPABASE + TẠO BẢNG + ĐỒNG BỘ DỮ LIỆU

## Nguyên tắc quan trọng nhất (đọc trước)
**KHÔNG tự tay tạo bảng trong giao diện Supabase.** Với Django, anh chỉ **định nghĩa model (class Python)** rồi chạy `migrate` → Django **tự tạo toàn bộ bảng** trên Supabase. Đây chính là cách "tạo hàng loạt bảng" đúng chuẩn: sửa model 1 nơi, chạy 1 lệnh, DB tự đồng bộ. Tạo tay trên Supabase sẽ lệch với code và vỡ về sau.

Vậy 3 việc cần làm:
1. Lấy **connection string** → điền `DATABASE_URL` → chạy `migrate` (bảng Sprint 1 lên Postgres).
2. **Sprint 2**: viết model cho nghiệp vụ cũ (nhân sự, nhà hàng, checklist…) → `migrate` → bảng tự mọc.
3. **Đồng bộ**: viết "management command" kéo dữ liệu **tuyển dụng** & **CLS** về Postgres (chạy tay hoặc theo lịch cron).

---

## PHẦN 1 — Lấy connection string Supabase
1. Vào **supabase.com** → mở project của anh.
2. Bấm nút **Connect** (góc trên) — hoặc **Project Settings → Database**.
3. Chọn tab **Connection string → URI**.
4. Có 3 loại, **chọn "Session pooler"** (vì backend Django chạy server thường trú, và pooler dùng IPv4 — hợp với host free như Render):
   - Direct (cổng 5432): chỉ IPv6, host free thường không nối được.
   - **Session pooler (khuyên dùng)**: `...pooler.supabase.com:5432` — ổn định cho Django + migrate.
   - Transaction pooler (cổng 6543): cho serverless, KHÔNG hợp migrate.
5. Copy chuỗi dạng:
   ```
   postgresql://postgres.<project-ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
   Thay `<PASSWORD>` bằng **Database password** (đặt lúc tạo project; quên thì Reset ở Database settings).

> Lưu ý: **không** post mật khẩu này lên chat công khai/GitHub. Nó chỉ nằm trong `backend/.env` (file này đã được `.gitignore` bỏ qua).

---

## PHẦN 2 — Điền .env và migrate (đưa bảng Sprint 1 lên Postgres)
Mở `backend/.env`, bỏ dấu `#` và dán chuỗi:
```
DATABASE_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres
```
Rồi trong VS Code, mở Terminal (Ctrl+`), chạy:
```bash
cd backend
# Windows:
.venv\Scripts\activate
python manage.py migrate
python manage.py seed_admin
```
Mở lại Supabase → **Table Editor** sẽ thấy các bảng `accounts_tenant`, `accounts_user`, … → đã nối thành công.

---

## PHẦN 3 — Sprint 2: tạo hàng loạt bảng theo hệ thống cũ
Không tạo tay. Ra lệnh cho **Claude Code** trong VS Code (dán nguyên đoạn này):

> "Đọc `01_BAN_THIET_KE_KY_THUAT.md`. Tạo các Django app: `restaurants`, `employees`, `checklist`, `evaluation`, `kpi`, `cls_sync`. Viết model cho từng app theo ERD mục 5 (mọi bảng đều có `tenant` ForeignKey). Đăng ký app vào INSTALLED_APPS. Chạy `makemigrations` + `migrate`. Viết seed command tạo dữ liệu mẫu 1 tenant, vài nhà hàng, vài checklist để test."

Sau khi nó chạy `migrate`, toàn bộ bảng (nhà hàng, nhân sự, checklist, đánh giá, KPI, kết quả CLS…) **tự xuất hiện trên Supabase**. Mỗi lần đổi model chỉ cần `makemigrations` + `migrate` lại.

---

## PHẦN 4 — Đồng bộ dữ liệu Tuyển dụng + CLS về Supabase
Cùng cách như bên Apps Script (kéo qua API), nhưng viết bằng Python và lưu vào Postgres. Ra lệnh cho Claude Code:

> "Trong app `cls_sync`, viết management command `sync_cls` kéo **kết quả học** và **kết quả thi** từ API CLS (dùng SECRET_KEY trong .env) và **upsert** vào bảng `CourseResult`/`ExamResult` theo `tenant`. Giữ đúng logic bản Apps Script: Hội nhập ≥80 → đủ điều kiện thi; thi lần 1 lấy điểm/đạt, lần 2–3 lấy điểm cao nhất. Viết thêm command `sync_recruitment` kéo danh sách nhân sự mới từ nguồn tuyển dụng vào bảng `Employee` (suy ra `restaurant` từ tên nhà hàng). Cả hai chạy được bằng `python manage.py sync_cls` và đặt lịch chạy tự động."

Chạy định kỳ (0đ): dùng **Render Cron Job (free)** hoặc **GitHub Actions** gọi `python manage.py sync_cls` mỗi ngày — không cần Celery/Redis.

Bí mật CLS (`SECRET_KEY`, ID sheet CLS) để trong `backend/.env`, **không** hard-code.

---

## Thứ tự làm gọn
1. Lấy Session pooler URI → điền `.env` → `migrate` + `seed_admin`. ✅ nối xong.
2. Bảo Claude Code làm Sprint 2 (model + migrate) → bảng tự mọc trên Supabase.
3. Bảo Claude Code viết `sync_cls` / `sync_recruitment` → đổ dữ liệu về.
4. Deploy (Vercel + Render + Supabase) khi cần người ngoài truy cập.

*(Toàn bộ việc này KHÔNG đụng tới hệ Apps Script — nó vẫn chạy song song.)*
