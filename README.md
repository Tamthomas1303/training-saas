# Training SaaS (Python) — Sprint 1: Khởi tạo

SaaS đa tenant: Django + DRF (backend) — React + Vite (frontend) — Supabase Postgres — JWT.

## Cấu trúc
```
backend/    Django project (config) + app accounts (Tenant, User, JWT auth)
frontend/   React + Vite (login, dashboard, JWT auth flow)
docs/       ERD, ghi chú
```

## Backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py seed_admin   # tạo tenant demo + user admin/admin12345
python manage.py runserver 8000
```

Cấu hình ở `backend/.env` (copy từ `.env.example`):
- `DATABASE_URL` — connection string Supabase Postgres (Project Settings → Database → Connection string → URI). Nếu bỏ trống, backend tự dùng SQLite cục bộ để phát triển.
- `DJANGO_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, ...

API:
- `POST /api/auth/login/` — đăng nhập, trả `access` + `refresh` + `user`.
- `POST /api/auth/login/refresh/` — làm mới access token.
- `GET /api/auth/me/` — thông tin user đang đăng nhập (cần Bearer token).
- `/admin/` — Django admin để quản lý Tenant/User.

> Nếu chạy lệnh Django trên PowerShell mà lỗi `UnicodeEncodeError` do tiếng Việt, chạy `$env:PYTHONUTF8 = "1"` trước.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Cấu hình ở `frontend/.env`: `VITE_API_BASE_URL` (mặc định `http://127.0.0.1:8000/api`).

Chạy xong mở `http://localhost:5173`, đăng nhập bằng tài khoản đã seed (`admin` / `admin12345`).

## Mô hình dữ liệu (sprint 1)
- **Tenant**: name, plan, status.
- **User** (custom, kế thừa `AbstractUser`): tenant, full_name, role (Admin/OM/BOD/AM/KCS/BQL/Trainer), job_title, trainer_zone, google_email, status.

## Đồng bộ dữ liệu ngoài (sprint model + sync)

App theo ERD (`restaurants`, `employees`, `checklist`, `evaluation`, `kpi`, `cls_sync`) — xem `01_BAN_THIET_KE_KY_THUAT.md` mục 5.

### sync_cls — kéo kết quả học/thi từ CLS

```powershell
cd backend
python manage.py sync_cls --tenant "Demo Tenant"
```

Cấu hình `.env`: `CLS_SECRET_KEY`, `CLS_API_BASE`, `CLS_EXAM_START_DATE`, `CLS_PROBATION_EXAM_TYPES`, `CLS_ONBOARDING_PASS_SCORE`. Logic port từ `AppsScript Ver 2.0/CLS_Sync_*_FIX.gs` + `ProbationService.gs`:
- Khóa Hội nhập (`HOINHAP_...`) chỉ lấy học viên đã hoàn thành; khóa Lên Level (`LEVEL_...`) lấy tất cả.
- Điểm Hội nhập cao nhất ≥ 80 → đủ điều kiện thi (`cls_sync/services.py::onboarding_eligible`).
- Kỳ thi thử việc: CLS không trả số lần thi trực tiếp → suy ra theo thứ tự thời gian mỗi loại thi (tiền tố trước `_` trong tên topic, vd `10N_...`, `15N_...`, `30N_...`, `NV_...`). Lần 1 giữ nguyên; lần 2–3 chỉ giữ điểm cao nhất.
- Chỉ ghi nhận nhân sự đã tồn tại trong `Employee` (khớp theo `code` = mã CLS); người chưa có trong hệ thống sẽ bị bỏ qua (chạy `sync_recruitment` trước).

### sync_recruitment — kéo nhân sự mới từ nguồn tuyển dụng

```powershell
python manage.py sync_recruitment --tenant "Demo Tenant"
```

Nguồn dữ liệu: CSV export của Google Sheet tuyển dụng (`File > Share > Publish to web > CSV`), cấu hình qua `.env`: `RECRUITMENT_SOURCE_CSV_URL` (hoặc `--csv-url <path>` để trỏ tới 1 file CSV cục bộ khi test). Cột CSV bắt buộc: `Employee_ID, Employee_Name, Restaurant_Name, Restaurant_ID (tùy chọn), Job_Position, Operation_Unit, Job_Level, Start_Date, Employee_Status`. Nhà hàng được suy ra từ `Restaurant_Name` khi `Restaurant_ID` trống (khớp tên chính xác trước, sau đó bỏ tiền tố thương hiệu — port từ `SnapshotService.gs::_restIdResolver`).

### Đặt lịch chạy tự động

- **Production (0đ)**: `.github/workflows/sync_cls.yml` — GitHub Actions chạy mỗi 6 giờ. Cần khai báo Repository secrets: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `CLS_SECRET_KEY`, `RECRUITMENT_SOURCE_CSV_URL`.
- **Local/dev (Windows)**: tạo Task Scheduler trỏ tới lệnh sau (chạy định kỳ, ví dụ mỗi 6 tiếng):
  ```powershell
  schtasks /create /tn "SyncCLS" /sc hourly /mo 6 /tr "'F:\...\backend\.venv\Scripts\python.exe' 'F:\...\backend\manage.py' sync_cls --tenant \"Demo Tenant\"" /st 00:00
  ```
  (thay đường dẫn thực tế; `sync_recruitment` tạo task tương tự).

Xem chi tiết lộ trình sprint tiếp theo ở `01_BAN_THIET_KE_KY_THUAT.md`.
