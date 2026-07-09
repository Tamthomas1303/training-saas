# BẮT ĐẦU: VS Code + Claude Code + Đưa app lên mạng

Dành cho người mới. Làm tuần tự A → B → C → D → E.
> Dự án Python này nằm ở thư mục riêng `Training_SaaS_Python`. **Hệ Apps Script cũ KHÔNG bị đụng tới** và vẫn chạy song song bình thường.

---

## A. Cài Visual Studio Code (VS Code)
1. Vào https://code.visualstudio.com → **Download for Windows** → chạy file cài (Next → Next → tick "Add to PATH" → Finish).
2. Mở VS Code. Bên trái là **Activity Bar** với các icon: Explorer (📁 file), Search (🔍), Source Control, **Extensions** (⧉).

## B. Kết nối Claude để TỰ CODE (không copy‑paste) — Claude Code
1. VS Code → bấm **Extensions** (Ctrl+Shift+X) → gõ **"Claude Code"** → chọn bản của **Anthropic** → **Install**.
2. Mở nó: bấm icon **Spark (tia sáng)** ở góc trên bên phải khi đang mở 1 file, hoặc **Ctrl+Shift+P** → gõ "Claude" → chọn lệnh mở Claude.
3. Lần đầu bấm **Sign in** bằng **chính tài khoản Anthropic** anh đang dùng Claude này. Claude Code dùng chung gói Claude (Pro/Max) anh đã có — **không tốn thêm phí**.
4. **File → Open Folder → chọn thư mục `Training_SaaS_Python`**. Từ giờ Claude Code **đọc/ghi trực tiếp file trong thư mục này** — anh chỉ gõ yêu cầu bằng tiếng Việt, nó tự tạo/sửa file.
   - Ví dụ gõ cho Claude Code: *"Đọc file 01_BAN_THIET_KE_KY_THUAT.md và dựng khung dự án theo đúng đó."*
5. Khi nó đề xuất sửa → hiện **diff (so sánh trước/sau)** → anh bấm **Accept** để áp dụng.

> "0 đồng" là nói về **hạ tầng/host miễn phí**. Gói Claude (Pro/Max) để chạy Claude Code thì anh đã có sẵn.

## C. Dùng VS Code cơ bản (người mới cần nhớ)
- **Explorer** (Ctrl+Shift+E): cây thư mục/file bên trái, click để mở.
- **Terminal** (Ctrl+`): cửa sổ dòng lệnh phía dưới — nơi chạy lệnh (cài thư viện, chạy app).
- **Command Palette** (Ctrl+Shift+P): gõ tên bất kỳ lệnh nào.
- **Lưu file**: Ctrl+S (tab có chấm ⬤ = chưa lưu).
- **Source Control** (Ctrl+Shift+G): lưu lịch sử code bằng Git.
- Nên cài thêm 2 extension: **Python** (Microsoft) và **ESLint** — Claude Code sẽ nhắc khi cần.

## D. "Chạy trên máy tôi" vs "người khác truy cập được"
Khi code xong, app chạy ở **localhost** (vd http://localhost:8000) — **chỉ máy anh thấy**. Muốn người khác vào:

### D1. Chia sẻ nhanh tạm thời (demo vài phút): Cloudflare Tunnel / ngrok
- Chạy 1 lệnh → được 1 link công khai tạm trỏ về máy anh. Hợp để cho sếp/đồng nghiệp xem nhanh. (Máy anh phải đang bật + app đang chạy.)

### D2. Đưa lên mạng thật, chạy 24/7 (MIỄN PHÍ — Phương án A)
- **Frontend React → Vercel** (free): nối GitHub, mỗi lần đẩy code Vercel tự build → link `ten-app.vercel.app`.
- **Backend Python (Django) → Render Free**: link API công khai. *(Bản free "ngủ" sau 15 phút không dùng → lần mở đầu chậm ~30s — chấp nhận được cho pilot.)*
- **CSDL → Supabase Free** (PostgreSQL 500MB) + lưu file trên Supabase/Cloudflare R2.
- Cần 1 tài khoản **GitHub** (miễn phí) để lưu code & liên kết Vercel/Render.
- Tổng = **0đ**, đủ cho pilot/demo. Khi có khách trả tiền → nâng gói trả phí (Phương án B) để hết "ngủ" + có backup.

## E. Quy trình làm việc từ đây
1. Mở thư mục `Training_SaaS_Python` trong VS Code.
2. Ra lệnh cho Claude Code (tiếng Việt) theo từng bước trong **`01_BAN_THIET_KE_KY_THUAT.md`**.
3. Claude Code tạo/sửa file → anh **Accept** → chạy thử ở **Terminal**.
4. Khi ổn → tạo repo GitHub → nối Vercel + Render + Supabase → có link công khai.

> Muốn cập nhật tính năng cho **hệ Apps Script cũ**, cứ báo tôi (Cowork) — folder `AppsScript Ver 2.0` vẫn hoạt động độc lập, không bị dự án Python ảnh hưởng.

---
### Nguồn tham khảo
- Claude Code trong VS Code: https://code.claude.com/docs/en/vs-code
- Tải VS Code: https://code.visualstudio.com
