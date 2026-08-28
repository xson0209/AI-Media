# Automation Hub: RoxyBrowser và tự đăng video

Automation Hub là workflow riêng của AI Media. Nó không thêm bước upload vào AI Video auto-run, không dùng chung hàng đợi voice/render và không làm project nguồn thất bại khi mạng xã hội lỗi.

## 1. Bật feature

Trong PowerShell trước khi chạy backend:

```powershell
$env:VOICEBOX_FEATURE_AUTOMATION_HUB = "true"
$env:VOICEBOX_AUTOMATION_PUBLISHING_CONCURRENCY = "1"
```

Không ghi API key hoặc access token vào Git. Automation Hub nhận secret qua UI/API, mã hóa trước khi lưu SQLite và không trả lại token thật.

Nếu muốn tự quản lý encryption key thay vì local key file:

```powershell
$env:VOICEBOX_AUTOMATION_SECRET_KEY = "MOT_SECRET_DAI_VA_RIENG_CHO_MAY_NAY"
```

Hãy sao lưu key này. Mất key đồng nghĩa các connection cũ phải cấu hình lại.

## 2. Chuẩn bị ba repo RoxyBrowser

Chạy:

```powershell
Set-Location "D:\AI Media\AI Media Project\voice-app"
.\scripts\setup-roxybrowser-automation.ps1
```

Script clone/build vào `data/automation_hub/roxybrowserlabs`, là vùng bị Git-ignore. Nếu repo có thay đổi local, script bỏ qua `git pull` thay vì reset hoặc xóa thay đổi.

Ba repo có vai trò:

- `local-API`: tài liệu và examples. Đây không phải server để chạy.
- `roxybrowser-mcp-server`: MCP quản lý workspace/profile/proxy/account qua Local API.
- `roxybrowser-playwright-mcp`: MCP điều khiển trang qua CDP/BiDi, có HTTP sidecar ở loopback.

## 3. Bật RoxyBrowser Desktop Local API

1. Mở RoxyBrowser Desktop và đăng nhập.
2. Vào `API → API Configuration`.
3. Bật API, mặc định ở `http://127.0.0.1:50000`.
4. Reset/lấy API key mới nếu key đã từng bị lộ.
5. Trong Automation Hub, tạo connection loại `RoxyBrowser`, nhập API key và bấm kiểm tra.
6. Khi xoay key, chọn connection đã lưu, nhập key mới rồi bấm `Cập nhật Roxy connection`; secret cũ không bao giờ được điền lại vào trình duyệt.

Hub hỗ trợ health, workspace, profile, open/close và connection info. Hub không đọc/copy cookie từ Chrome cá nhân và không tự giải CAPTCHA hoặc 2FA.

Playwright MCP sidecar không tự khởi động cùng app. Bấm `Khởi động sidecar` trong Hub khi cần. Health sidecar chỉ chứng minh process đang nghe; profile phải được mở và kết nối riêng trước khi automation trang hoạt động.

## 4. Connection xuất bản chính thức

### YouTube

Cần OAuth credential có scope upload video, tối thiểu access token; để tự refresh cần thêm refresh token, client id và client secret. Adapter dùng resumable `videos.insert`, hỗ trợ `privacyStatus` và `publishAt`.

Project API mới/chưa audit có thể bị YouTube giới hạn video ở private. Hub giữ nguyên restriction này.

### Facebook

Chỉ hỗ trợ Facebook Page. Cần `page_id` và Page access token có quyền phù hợp. Personal profile không được API chính thức hỗ trợ trong capability này.

### TikTok

Mặc định chỉ dùng Draft/inbox upload với scope `video.upload`. TikTok không có native scheduling tương đương YouTube/Facebook, vì vậy job Draft có lịch được giữ trong scheduler local đến đúng giờ.

Direct Post cần scope `video.publish`, audit và tuân thủ Content Sharing Guidelines. Chỉ bật khi đã đủ điều kiện:

```powershell
$env:VOICEBOX_FEATURE_AUTOMATION_HUB_TIKTOK_DIRECT_POST = "true"
```

Không dùng RoxyBrowser để né trạng thái `SELF_ONLY`, audit hoặc hạn chế quyền của TikTok.

## 5. Luồng sử dụng

1. Upload một MP4/MOV/WebM vào Hub hoặc import một render output đã completed.
2. Tạo/check connection nền tảng.
3. Điền title, description, hashtag, privacy/mode và lịch nếu cần.
4. Tạo job với idempotency key duy nhất.
5. Theo dõi trạng thái `Đang chờ`, `Đang upload`, `Đã hoàn tất`, `Lỗi`, `Bị gián đoạn` hoặc `Đã hủy`.

Nếu backend dừng giữa upload, job chuyển `interrupted` và không tự đăng lại vì provider có thể đã nhận video. Hãy kiểm tra tài khoản nền tảng trước khi retry.

## 6. Các biến cấu hình chính

```text
VOICEBOX_FEATURE_AUTOMATION_HUB
VOICEBOX_FEATURE_AUTOMATION_HUB_TIKTOK_DIRECT_POST
VOICEBOX_AUTOMATION_SECRET_KEY
VOICEBOX_AUTOMATION_PUBLISHING_CONCURRENCY
VOICEBOX_AUTOMATION_MAX_UPLOAD_BYTES
VOICEBOX_AUTOMATION_RETRY_ATTEMPTS
VOICEBOX_ROXY_API_HOST
VOICEBOX_ROXY_TIMEOUT_SECONDS
VOICEBOX_ROXY_PLAYWRIGHT_ENTRY
VOICEBOX_ROXY_PLAYWRIGHT_HOST
VOICEBOX_ROXY_PLAYWRIGHT_PORT
VOICEBOX_ROXY_PLAYWRIGHT_HEALTH_URL
VOICEBOX_META_GRAPH_API_VERSION
```

Mọi URL Roxy/MCP do Hub quản lý bị giới hạn ở loopback. Sidecar command không nhận executable hoặc command tùy ý từ request frontend.
