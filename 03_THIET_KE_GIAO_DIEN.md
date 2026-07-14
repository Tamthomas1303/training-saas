# BẢN ĐẶC TẢ GIAO DIỆN v1 — Lush forest, khớp app Apps Script cũ

Mục tiêu: React app trông **giống hệt** hệ thống Apps Script cũ (login, dashboard, thanh tiến độ, báo cáo admin, nút thêm/sửa/xóa, popup, các màn theo từng vai trò), và áp **bảng màu Lush forest**. Nguồn tham chiếu: `AppsScript Ver 2.0/styles.html`, `scripts.html`, `Code.gs`.

---

## 1. Bảng màu Lush forest → design tokens
Định nghĩa CSS variables (đặt ở `:root`, dùng xuyên suốt, KHÔNG hard-code màu trong component):

```css
:root{
  --forest:      #2E6F40;  /* PRIMARY: nút chính, link, nav active, số liệu nổi bật */
  --forest-dark: #253D2C;  /* chữ đậm/tiêu đề, hover nút, gradient tối */
  --green:       #68BA7F;  /* phụ/nhấn: đuôi gradient thanh tiến độ, viền nhấn */
  --mint:        #CFFFDC;  /* nền nhạt: badge-soft, nền nav active, vùng nhấn nhẹ */
  --page-bg:     #F2F7F3;  /* nền trang (mint pha rất nhạt) */
  --card:        #FFFFFF;
  --card-border: #E4EFE7;
  --text:        #23302A;
  --muted:       #7C8A82;
  --danger:      #C0392B;
  --amber:       #C88A3C;  /* CHỈ dùng cho số tiền/hoa hồng/cúp (tùy chọn, giữ dễ đọc) */
}
```

Quy tắc (theo hướng dẫn palette): **màu nhạt (mint) cho nền & nhấn nhẹ; màu đậm (forest/forest-dark) cho nút chính và chữ.**

Ánh xạ từ app cũ → mới:
- `--amg-primary #1e6f5c` → `--forest #2E6F40`
- `--amg-primary-dark #16513f` → `--forest-dark #253D2C`
- gradient thanh tiến độ `#1e6f5c→#2a9d8f` → `#2E6F40→#68BA7F`
- gradient auth/banner → `#2E6F40→#68BA7F` (hoặc `#253D2C→#2E6F40`)
- `badge-soft` nền `rgba(30,111,92,.12)` → `--mint`, chữ `--forest-dark`
- nav active nền `rgba(...,.12)` → `--mint`, chữ `--forest`
- accent cam `#f4a259` (tiền/cúp) → `--amber` (giữ tối thiểu) hoặc `--forest-dark`

---

## 2. Thành phần dùng lại (component library)
Dựng các component React tái sử dụng, style theo tokens trên:

- **Button**: `.btn-primary` nền `--forest`, hover `--forest-dark`, bo 8px; `.btn-outline` viền `--forest`, chữ `--forest`; kích thước `sm` cho nút trong bảng.
- **StatCard**: nền trắng, bo 14px, viền `--card-border`, padding 18px. Có biến thể tiêu đề nhỏ (`text-muted`) + số lớn `--forest` (class `stat-num`, 1.8rem, đậm).
- **ProgressBar `bar(percent)`**: khung cao 8px nền `#EEF3EF` bo 6px; thanh trong gradient `--forest → --green`, rộng = percent%. Dùng ở dashboard, thẻ học viên, chi tiết, KPI.
- **Badge trạng thái/kết quả**:
  - Trạng thái đào tạo: Chưa bắt đầu (xám), Đang thực hiện (mint/forest), Hoàn thành (xanh đạt).
  - Kết quả thử việc: Đạt (nền `--mint`, chữ `--forest-dark`), Không đạt (nền hồng nhạt, chữ `--danger`), Chờ (xám).
- **Table**: header chữ muted nhỏ, hàng có avatar/tên + phụ đề mã; nút "Chi tiết" outline ở cột cuối.
- **Filter bar**: ô tìm kiếm + các select lọc (brand/vai trò/trạng thái) — như màn Nhà hàng/Nhân sự.
- **Pagination `Pager`**: phân trang client, đã có `usePaginatedList`.
- **Modal/Popup**: form thêm/sửa (người dùng, nhà hàng, tài liệu, phân vùng KCS) mở dạng popup, nền mờ, thẻ trắng bo 16px; nút Lưu (`--forest`) + Hủy (outline).
- **Avatar**: tròn 34px, có huy hiệu camera nhỏ (đổi ảnh); mặc định ảnh person.
- **SignaturePad**: canvas ký tên (đã có ở màn Đào tạo/Đánh giá) — giữ nguyên, viền nét đứt.
- **Mini calendar** (dashboard): bảng lịch tháng, ô hôm nay nền `--forest` chữ trắng bo tròn.
- **Empty/Loading state**: chữ muted "Đang tải..." / "Chưa có dữ liệu".

---

## 3. Vỏ ứng dụng (shell) theo thiết bị/vai trò
Xác định theo vai trò (giống `isMobileRole` cũ):

- **Mobile shell** (vai trò **Trainer, BQL, AM, KCS**): **thanh điều hướng đáy (bottom-nav)** với icon + nhãn ngắn; ẩn menu ngang trên đầu; nội dung max-width ~640px, chừa đáy cho bottom-nav. Banner chào ở đầu Home (gradient `--forest→--green`, chữ trắng, avatar).
- **Desktop shell** (vai trò **Admin, Training, OM, BOD**): **topbar** trắng dính trên cùng, brand màu `--forest`, menu ngang (`nav-link`, active nền `--mint`), avatar + chuông thông báo góc phải; nội dung max-width ~1280px.
- Chuông thông báo (badge đỏ số lượng), nút Đăng xuất — cả 2 shell.

---

## 4. Bản đồ MENU theo vai trò (đúng `Code.gs _menusForRole`)
Backend trả danh sách menu theo vai trò; frontend render đúng thứ tự:

| Vai trò | Menu | Shell | Ghi chú |
|---|---|---|---|
| **Admin, Training** | dashboard, students, kpi, documents, **users** | Desktop | Toàn quyền + quản trị người dùng |
| **OM** (Trưởng phòng VH) | dashboard, students, kpi, documents | Desktop | Không quản trị user; có chốt hội đồng + báo cáo |
| **BOD / BGĐ** | dashboard, students, kpi, documents | Desktop | **CHỈ XEM** — ẩn mọi nút thao tác/xuất/chốt |
| **AM, KCS** | home, evaluation, kpi, documents | Mobile | Theo dõi tiến độ, đánh giá, coaching KPI |
| **BQL** | home, training, evaluation, kpi, documents | Mobile | Đào tạo + đánh giá cơ sở |
| **Trainer** | home, training, documents | Mobile | Đào tạo nhân sự |

Nhãn & icon menu (Bootstrap Icons): home=house-door "Trang chủ", dashboard=speedometer2 "Dashboard/Tổng quan", students=people "Học viên", training=mortarboard "Đào tạo", evaluation=clipboard-check "Đánh giá", kpi=bar-chart-line "KPI", documents=folder2-open "Tài liệu", users=person-gear "Người dùng", commission=cash-coin "Hoa hồng".

---

## 5. Đặc tả từng màn (khớp app cũ)

### 5.1 Đăng nhập (Login)
Nền gradient `--forest→--green` full màn, thẻ trắng bo 16px giữa màn; logo tròn `--forest`; ô Tên đăng nhập + Mật khẩu (nút hiện/ẩn mật khẩu), nút "Đăng nhập" `--forest`, (tùy chọn) nút Google; vùng báo lỗi. *(Hiện React đang là form trần → cần dựng lại theo mẫu này.)*

### 5.2 Dashboard (Admin/Training/OM/BOD)
Nhiều `StatCard`:
- Hàng KPI số: ví dụ tổng NV mới, tỷ lệ đạt thử việc (số lớn `--forest` + `bar`), chi phí phụ cấp trainer (số `--amber`).
- "Tiến độ đào tạo nhân sự mới": lưới thẻ nhỏ mỗi NV (tên, vị trí, `bar` %).
- "Phân bổ nhân sự theo thương hiệu".
- "Tỷ lệ hoàn thành thử việc ≤15 ngày (cấp S)": % lớn + `bar` + danh sách.
- "Trainer xuất sắc": avatar + cúp (`--amber`).
- Mini calendar tháng.
- "Sắp đến hạn thử việc": danh sách hạn.
- BOD: hiển thị y hệt nhưng **bỏ mọi nút xuất/thao tác**.

### 5.3 Home (Trainer/BQL/AM/KCS)
- Banner chào gradient + avatar + vai trò.
- 3 thẻ số: Cần đào tạo / Đạt thử việc / Đủ ĐK hoa hồng (số `--amber` + ~tiền).
- "Tiến độ đào tạo từng nhân sự": lưới thẻ (tên, badge trạng thái, vị trí-nhà hàng, `bar` %, hạn còn/quá X ngày, nút mở chi tiết/đào tạo).
- AM/KCS: nút "Tổ chức buổi đào tạo (coaching)" mở màn KPI perform.

### 5.4 Học viên (students) — danh sách + chi tiết
- **Danh sách**: bộ lọc (nhà hàng/vị trí/trạng thái) + bảng: Họ tên (+mã), Nhà hàng, Vị trí, Ngày vào, Trạng thái (badge), **Tiến độ** (`bar` + % + text), Kết quả TV (badge), nút Chi tiết.
- **Chi tiết học viên**: thẻ thông tin (tên/nhà hàng/vị trí/ngày vào/kết quả TV) + tiến độ tổng (`bar`) + badge LMS + badge level/số ngày thử việc; **panel "Quản trị nhân sự"** (chỉ Admin/Training/BQL: đổi trạng thái, xuất phiếu kết quả thử việc PDF khi Đạt — ẩn với BOD); bảng **Checklist nội dung đào tạo** (trạng thái + nút Đào tạo/Xem); khối **Kết quả học & thi LMS** (khóa học %, bài thi điểm + badge); khối **Các bài đánh giá** (loại, %, badge, link PDF); khối **Hội đồng đánh giá** (số giám khảo, TB %, 3 khía cạnh, nút Chấm/Chốt).

### 5.5 Đào tạo (training) — *(đã dựng)*
Chọn nhân sự → checklist nhóm theo Ngày/Hạng mục → form: 3 ảnh (Tài liệu/Lý thuyết/Thực hành) + 2 chữ ký → Lưu nháp / Hoàn thành & xuất PDF. Giữ nguyên, chỉ áp theme.

### 5.6 Đánh giá (evaluation) — *(đã dựng)*
Bảng tiêu chí: Nội dung | Điểm tối đa | Chấm điểm | **Ảnh KN** (mọi dòng đều có nút camera; dòng bắt buộc gắn nhãn đỏ "Bắt buộc") | Ghi chú. Tổng + Đạt/Không đạt realtime (≥70% và không có mục bắt buộc =0). 2 chữ ký + xuất PDF. Hai loại phiếu: BQL và AM/KCS random. Có form Hội đồng. Áp theme.

### 5.7 KPI (kpi)
- **AM/KCS (perform)**: thẻ "Tiến độ KPI tháng" (done/target + `bar` + đạt/thiếu), danh sách buổi đã thực hiện; form ghi buổi: chọn nhà hàng, **ô chủ đề tìm kiếm được** (datalist), người tham gia, nút "Lưu buổi & ghi KPI".
- **Admin/Training/OM/BOD (report)**: theo dõi KPI + nút xuất "Báo cáo KPI BQL (PDF)" và "Phiếu phụ cấp trainer (PDF)" (ẩn với BOD); danh sách sessions.

### 5.8 Tài liệu (documents)
Danh sách tài liệu + lọc (brand/vị trí) + popup thêm/sửa (brand & vị trí là **select**), phân trang.

### 5.9 Người dùng (users) — Admin/Training
Bảng người dùng + lọc; popup thêm/sửa (tài khoản, họ tên, vai trò, chức danh, nhà hàng, trạng thái); riêng **KCS** có nút "Phân vùng" mở popup chọn nhiều nhà hàng.

### 5.10 Hoa hồng/Phụ cấp (commission)
Bảng phụ cấp trainer theo kỳ (số tiền `--amber`).

---

## 6. Hiện React ĐANG THIẾU (so với app cũ) — cần bổ sung
1. **Theme Lush forest** (hiện là style trần, không màu thương hiệu).
2. **Vỏ mobile (bottom-nav)** cho Trainer/BQL/AM/KCS; hiện chỉ có 1 kiểu topbar.
3. **Menu render theo vai trò** đúng `_menusForRole` (hiện cùng 1 menu cho mọi user).
4. **Dashboard admin** đầy đủ thẻ số/biểu đồ/lịch/hạn — hiện gần như trống.
5. **Home** cho Trainer/BQL/AM/KCS với banner + 3 thẻ + lưới tiến độ.
6. **Chi tiết học viên** đầy đủ (checklist, LMS, đánh giá, hội đồng, panel quản trị).
7. **Nút thêm/sửa/xóa + popup** cho Users/Documents/Restaurants (CRUD).
8. **Thanh tiến độ, badge, stat-card** dùng chung theo tokens.
9. **KPI report + xuất PDF**, **Commission**.
10. **BOD read-only**: ẩn mọi nút thao tác/xuất.
11. **Chuông thông báo** + Đăng xuất trên shell.

---

## 7. Nguyên tắc khi triển khai
- Tạo `frontend/src/theme.css` (hoặc tokens) với các biến ở mục 1; mọi component import dùng biến, không hard-code màu.
- Tạo component dùng chung: `StatCard`, `ProgressBar`, `Badge`, `Modal`, `FilterBar`, `BottomNav`, `TopBar`, `Table`, `Pager`.
- Menu + shell chọn theo `user.role` (lấy từ API `/auth/me` hoặc token).
- Giữ nguyên logic đã chạy (Đào tạo/Đánh giá/CLS…); đây là lớp **giao diện**, không đổi nghiệp vụ.
- KHÔNG đụng thư mục `AppsScript Ver 2.0` — chỉ tham chiếu.
