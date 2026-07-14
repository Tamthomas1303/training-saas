# HƯỚNG DẪN DEPLOY (0đ) — Vercel + Render + Supabase

Kiến trúc: **Frontend React → Vercel** · **Backend Django → Render** · **Database + ảnh → Supabase** (đã có). Tất cả bản miễn phí. Cả Vercel và Render đều deploy **từ GitHub**, nên bước đầu là đưa code lên GitHub.

> Lưu ý bản free: **Render ngủ sau 15 phút** không dùng → lần mở đầu chậm ~30–60s (chấp nhận cho pilot). **Supabase free tạm dừng sau 7 ngày** không hoạt động → mở lại trong dashboard là chạy tiếp.

---

## PHẦN 0 — Chuẩn bị code cho production (giao Claude Code)
Dán cho Claude Code:

> "Chuẩn bị backend cho deploy Render, KHÔNG đổi nghiệp vụ:
> - Thêm `gunicorn` và `whitenoise` vào `requirements.txt`.
> - Trong `config/settings.py`: thêm `STATIC_ROOT = BASE_DIR / 'staticfiles'`; thêm `whitenoise.middleware.WhiteNoiseMiddleware` ngay sau `SecurityMiddleware`; cấu hình `STORAGES` static dùng WhiteNoise; đọc `CSRF_TRUSTED_ORIGINS` từ biến môi trường (danh sách, phân tách dấu phẩy); đảm bảo `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DEBUG` đều đọc từ env (đã có phần lớn).
> - Tạo file `backend/build.sh` (hoặc ghi rõ trong README) chạy: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`.
> - Start command dùng: `gunicorn config.wsgi:application`.
> - Frontend: xác nhận `VITE_API_BASE_URL` đọc từ env (đã đúng), không hard-code localhost.
> - Cập nhật `.env.example` (backend + frontend) liệt kê đủ biến cần cho production. KHÔNG commit `.env` thật.
> Chạy thử `python manage.py collectstatic --noinput` ở máy để chắc không lỗi, rồi commit."

---

## PHẦN 1 — Đưa code lên GitHub
1. Tạo tài khoản **github.com** (miễn phí) nếu chưa có.
2. Tạo repo mới (Private): nút **New** → đặt tên ví dụ `training-saas` → **Create repository** (KHÔNG tích thêm README).
3. Trong VS Code, mở **terminal thứ 3**, tại thư mục gốc `Training_SaaS_Python`:
   ```
   git add -A
   git commit -m "Ready for deploy"
   git branch -M main
   git remote add origin https://github.com/<tên-của-anh>/training-saas.git
   git push -u origin main
   ```
   (Nếu đã có `origin` thì bỏ dòng `remote add`, chỉ `git push`.)
4. **Kiểm tra quan trọng:** vào repo trên GitHub, đảm bảo **KHÔNG thấy file `backend/.env`** (chứa mật khẩu/khóa). Nếu lỡ thấy → dừng lại, báo tôi để xử lý trước khi tiếp.

---

## PHẦN 2 — Deploy BACKEND lên Render (làm trước để lấy URL)
1. Tạo tài khoản **render.com** → **Sign in with GitHub**.
2. **New +** → **Web Service** → chọn repo `training-saas` → **Connect**.
3. Cấu hình:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
   - **Start Command**: `gunicorn config.wsgi:application`
   - **Instance Type**: **Free**
4. Mục **Environment Variables** — thêm lần lượt (Add Environment Variable):
   - `DJANGO_SECRET_KEY` = (một chuỗi ngẫu nhiên dài, khác bản dev)
   - `DJANGO_DEBUG` = `False`
   - `DATABASE_URL` = chuỗi Session pooler Supabase (giống trong `.env`)
   - `DJANGO_ALLOWED_HOSTS` = tạm để `.onrender.com` (sẽ chỉnh lại đúng tên sau bước 6)
   - `CORS_ALLOWED_ORIGINS` = (để trống tạm, điền URL Vercel ở Phần 4)
   - `CSRF_TRUSTED_ORIGINS` = (để trống tạm, điền URL Vercel ở Phần 4)
   - `CLS_SECRET_KEY`, `CLS_API_BASE`, `CLS_EXAM_START_DATE`, `CLS_PROBATION_EXAM_TYPES`, `CLS_ONBOARDING_PASS_SCORE` = như trong `.env`
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` = như trong `.env`
   - (tùy chọn) `RECRUITMENT_SOURCE_CSV_URL`
5. **Create Web Service** → chờ build (vài phút). Xem tab **Logs**, khi thấy chạy gunicorn là xong.
6. Render cấp URL dạng `https://training-saas-xxxx.onrender.com`. **Copy URL này.** Quay lại **Environment** sửa `DJANGO_ALLOWED_HOSTS` = `training-saas-xxxx.onrender.com` (đúng tên vừa cấp) → **Save** (nó tự deploy lại).
7. Kiểm tra: mở `https://training-saas-xxxx.onrender.com/admin/` — thấy trang đăng nhập Django (không lỗi) là backend sống.

---

## PHẦN 3 — Deploy FRONTEND lên Vercel
1. Tạo tài khoản **vercel.com** → **Continue with GitHub**.
2. **Add New… → Project** → chọn repo `training-saas` → **Import**.
3. Cấu hình:
   - **Root Directory**: bấm **Edit** → chọn `frontend`
   - **Framework Preset**: Vite (thường tự nhận)
   - **Build Command**: `npm run build` · **Output Directory**: `dist` (mặc định)
4. Mục **Environment Variables** thêm:
   - `VITE_API_BASE_URL` = `https://training-saas-xxxx.onrender.com/api` (URL Render ở Phần 2 + `/api`)
5. **Deploy** → chờ ~1–2 phút → Vercel cấp URL dạng `https://training-saas.vercel.app`. **Copy URL này.**

---

## PHẦN 4 — Nối 2 bên (CORS) và chạy thử
1. Quay lại **Render → Environment**, điền:
   - `CORS_ALLOWED_ORIGINS` = `https://training-saas.vercel.app`
   - `CSRF_TRUSTED_ORIGINS` = `https://training-saas.vercel.app`
   → **Save** (Render deploy lại).
2. Mở URL Vercel `https://training-saas.vercel.app`, đăng nhập `admin` / `admin12345`.
   - Lần đầu có thể chờ ~30–60s vì Render vừa ngủ dậy — bình thường.
3. Nếu đăng nhập lỗi, mở **F12 → Network**, xem request `login/`:
   - Lỗi **CORS** → kiểm tra lại `CORS_ALLOWED_ORIGINS` đúng URL Vercel (có `https://`, không dấu `/` cuối).
   - **ERR/timeout** → chờ Render dậy rồi thử lại; xem Logs trên Render.
   - **400/401** → kiểm tra `VITE_API_BASE_URL` có đúng URL Render + `/api`.

---

## PHẦN 5 — Sau khi chạy được
- **Cập nhật code sau này:** chỉ cần `git push` lên `main` → Render và Vercel **tự deploy lại**. Rất tiện.
- **Tài khoản thật:** đăng nhập admin → tạo user thật cho từng vai trò; hoặc chạy seed.
- **Đồng bộ CLS tự động:** đẩy repo lên GitHub rồi vào **repo → Settings → Secrets and variables → Actions** thêm `DATABASE_URL`, `CLS_SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RECRUITMENT_SOURCE_CSV_URL`, `DJANGO_SECRET_KEY` để workflow `sync_cls.yml` tự chạy theo lịch.
- **Bảo mật:** mọi khóa bí mật chỉ đặt trong Environment Variables của Render / Secrets của GitHub — KHÔNG bao giờ trong code hay frontend.

---

## Thứ tự tóm tắt
Phần 0 (Claude Code) → Phần 1 (GitHub) → Phần 2 (Render, lấy URL backend) → Phần 3 (Vercel, dùng URL backend) → Phần 4 (điền URL Vercel vào CORS Render, test). Vướng bước nào chụp màn hình + Logs gửi tôi.
