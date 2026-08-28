## Why

AI Media đã tạo được video và bộ metadata đăng cho YouTube, TikTok và Facebook nhưng chưa có một workflow độc lập để quản lý RoxyBrowser, chọn file video đầu ra và xuất bản tự động. Việc gắn upload trực tiếp vào auto-run hiện có sẽ làm tăng rủi ro OAuth, lỗi mạng hoặc thay đổi giao diện nền tảng ảnh hưởng các luồng tạo nội dung đang hoạt động bình thường.

## What Changes

- Thêm workspace **Automation Hub** riêng, bị ẩn/tắt mặc định cho tới khi feature flag và cấu hình bảo mật được bật.
- Tích hợp RoxyBrowser qua Local API chính thức để kiểm tra health, đọc workspace/profile, mở/đóng profile và lấy endpoint CDP/BiDi; không vendoring `node_modules` hoặc sao chép cookie/profile vào project.
- Tích hợp `roxybrowser-mcp-server` và `roxybrowser-playwright-mcp` dưới dạng sidecar/configurable runtime, có health/status riêng và thư mục artifact riêng trong data directory.
- Thêm kho kết nối được mã hóa cho RoxyBrowser và tài khoản xuất bản; API/UI không bao giờ trả lại secret dạng rõ.
- Thêm hàng đợi publishing riêng với job/attempt/result độc lập, giới hạn concurrency riêng, retry/cancel/recovery sau restart và idempotency để không đăng trùng.
- Cho phép chọn một file video local hoặc output MP4 hiện có làm input bất biến; trạng thái publishing không sửa state machine AI Video, Video Inspiration, voice, subtitle hoặc render.
- Thêm adapter API chính thức cho YouTube upload/scheduling, Facebook Page video upload/scheduling và TikTok Draft upload; TikTok Direct Post nằm sau feature flag và chỉ dùng khi ứng dụng/tài khoản đã được phê duyệt.
- Browser automation chỉ là fallback có giám sát cho tác vụ được người dùng cho phép; không dùng để vượt CAPTCHA, 2FA, audit, quota, private-only restriction hoặc chính sách nền tảng.
- Thêm tài liệu setup PowerShell để clone/build ba repo RoxyBrowser vào data directory bị Git-ignore, cấu hình biến môi trường và chạy sidecar tách khỏi tiến trình frontend.

## Capabilities

### New Capabilities

- `automation-hub-roxy-browser`: Quản lý cấu hình, trạng thái và thao tác profile RoxyBrowser/Playwright MCP trong một workflow độc lập và an toàn.
- `social-video-publishing`: Quản lý kết nối nền tảng, hàng đợi upload video chính thức, scheduling, retry/cancel, kết quả và chống đăng trùng.

### Modified Capabilities

- Không có. Automation Hub chỉ đọc output hiện có như input và không thay đổi contract trạng thái của các workflow sản xuất media đang chạy.

## Impact

- Backend: route namespace `/automation-hub`, service package mới, bảng kết nối/job/attempt mới, worker queue riêng, startup recovery và HTTP adapters cho RoxyBrowser cùng API nền tảng.
- Frontend: route và sidebar entry riêng cho Automation Hub, màn hình cấu hình RoxyBrowser, tài khoản, chọn video, tạo job và theo dõi tiến độ.
- Runtime: RoxyBrowser Desktop phải đang mở và Local API phải được bật; Playwright MCP có thể chạy sidecar HTTP riêng. Feature không tự khởi động khi chưa bật/cấu hình.
- Security: token/API key được mã hóa at rest, secret bị redaction khỏi API/log/debug, không lưu mật khẩu tài khoản và không export browser profile/cookie vào package.
- Dependencies: dùng `httpx` hiện có; thêm thư viện mã hóa chuẩn nếu runtime chưa có. Ba repo RoxyBrowser được setup ngoài source tree theo script, không copy dependency/build artifact vào Git.
- Verification: backend unit/integration tests bằng mock transport, frontend typecheck/build, OpenSpec validation và manual smoke test với RoxyBrowser Desktop cùng tài khoản nền tảng do người dùng sở hữu.
