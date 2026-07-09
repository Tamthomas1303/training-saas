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

Xem chi tiết lộ trình sprint tiếp theo ở `01_BAN_THIET_KE_KY_THUAT.md`.
