# Load test v2.1 (k6) — Dashboard tổng hợp CEO/GĐĐT

Kịch bản: `k6_v21_loadtest.js`. Mô phỏng 10 → 35 → 50 người dùng đồng thời trong ~8 phút,
tập trung vào `GET /api/dashboard/overview/` (màn Dashboard tổng hợp CEO/GĐĐT — endpoint từng
OOM trên Render, đã sửa ở commit "fix: sua OOM man Dashboard tong hop"), xen kẽ các endpoint
thật khác (`/auth/me/`, `/kpi/report/`, `/employees/`) để mô phỏng 1 phiên làm việc thật.

## 0. KHÔNG chạy vào giờ cao điểm

Tránh khung giờ nhân viên/quản lý dùng hệ thống nhiều nhất (chấm công, nhập đánh giá, xem
KPI cuối ngày) — ước tính khoảng **7:30–9:00, 11:00–13:00, 17:00–19:30** giờ Việt Nam các ngày
làm việc. Nên chạy **buổi tối muộn (sau ~21h) hoặc cuối tuần**, và báo trước cho người đang
dùng hệ thống nếu có.

## 1. Tạo tài khoản test (1 lần, idempotent)

```bash
cd backend
python manage.py create_loadtest_users --tenant "Demo Tenant" --count 5 --password "<mật khẩu mạnh, tự đặt>"
```

Tạo/đảm bảo có sẵn `k6_test_01`..`k6_test_05`, vai trò `om` (xem được cả Dashboard tổng hợp lẫn
Báo cáo KPI BQL, không có quyền ghi/xoá dữ liệu). Chạy lại lệnh này an toàn — không tạo trùng,
chỉ cập nhật mật khẩu/role nếu đổi tham số. Nếu chạy nhắm vào DB production (Render/Supabase),
chạy qua GitHub Actions (tương tự `.github/workflows/fix_admin_tenant.yml`) hoặc `DATABASE_URL`
trỏ đúng production — **cân nhắc kỹ trước khi trỏ máy cá nhân thẳng vào DB production**.

## 2. Cài k6

```powershell
winget install k6.k6
```

(hoặc tải binary tại https://k6.io/docs/get-started/installation/)

## 3. Theo dõi log Render song song lúc chạy test

Mở **song song** một trong hai cách, ngay trước khi bấm chạy k6:

- **Dashboard**: render.com → chọn service backend → tab **Logs** → lọc theo `Out of memory`,
  `SIGKILL`, hoặc `exit code 137` (mã thoát chuẩn khi Linux OOM-killer giết process).
- **CLI** (nếu đã cài & đăng nhập `render` CLI): `render logs -r <service-id> --tail`

Ghi lại **mốc thời gian** log xuất hiện SIGKILL/OOM — sẽ đối chiếu với số VU (người dùng đồng
thời) tại đúng thời điểm đó trong báo cáo k6 (k6 in log tiến trình theo `stages`, có thể suy ra
đang ở mức 10/35/50 VU dựa vào thời gian đã chạy).

## 4. Chạy k6

```bash
k6 run \
  -e BASE_URL="https://<ten-service-that>.onrender.com/api" \
  -e TEST_USER_PREFIX="k6_test_" \
  -e TEST_USER_COUNT=5 \
  -e TEST_PASSWORD="<mật khẩu đã đặt ở bước 1>" \
  loadtest/k6_v21_loadtest.js
```

Không có giá trị mặc định cho `BASE_URL`/`TEST_PASSWORD` — bắt buộc truyền tay, tránh nhầm sang
môi trường khác hoặc lộ mật khẩu trong file được commit.

Tuỳ chọn thêm: `-e REPORT_MONTH=8 -e REPORT_YEAR=2026` (mặc định tháng/năm hiện tại).

## 5. Đọc báo cáo

Sau khi chạy xong (~8 phút), k6 in báo cáo ra màn hình và ghi ra 2 file:
- `loadtest/k6_report.txt` — bảng tóm tắt tiếng Việt: p95 latency, tỷ lệ lỗi, đạt/không đạt
  ngưỡng, số request bị 502/503/504 (dấu hiệu OOM ở tầng gateway Render).
- `loadtest/k6_summary.json` — dữ liệu đầy đủ (mọi metric, mọi threshold) để phân tích thêm.

**Xác định OOM xảy ra ở mức bao nhiêu người**: đối chiếu mốc thời gian log Render ghi được ở
bước 3 với lịch `stages` trong `k6_v21_loadtest.js` (phút 0–1: ramp 10, phút 1–3: giữ 10, phút
3–4: ramp 35, phút 4–6: giữ 35, phút 6–7: ramp 50, phút 7–8: giữ 50). k6 tự nó KHÔNG đọc được
log Render — hai nguồn phải được đọc thủ công cùng lúc và ghép mốc thời gian.

## Ngưỡng mặc định trong kịch bản (có thể chỉnh trong `options.thresholds`)

| Metric | Ngưỡng |
|---|---|
| p95 toàn bộ request | < 3000 ms |
| p95 riêng `/dashboard/overview/` | < 5000 ms |
| Tỷ lệ lỗi toàn bộ | < 5% |
| Tỷ lệ lỗi riêng `/dashboard/overview/` | < 5% |
| Số request 502/503/504 | 0 |

Ngưỡng không làm dừng test giữa chừng (`abortOnFail: false`) — mục đích là thấy toàn bộ đường
cong đến 50 người, không dừng sớm khi vừa chớm vượt ngưỡng.
