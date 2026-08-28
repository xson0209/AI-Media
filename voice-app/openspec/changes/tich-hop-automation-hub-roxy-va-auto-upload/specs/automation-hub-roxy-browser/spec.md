## ADDED Requirements

### Requirement: Automation Hub hoạt động độc lập với workflow media hiện có
Hệ thống SHALL cung cấp Automation Hub bằng route, state, queue và UI riêng, và MUST NOT thay đổi trạng thái của AI Video, Video Inspiration, voice, subtitle, render hoặc Veo clip generation khi một tác vụ Hub thành công hay thất bại.

#### Scenario: Publishing job thất bại
- **WHEN** một upload trong Automation Hub thất bại do mạng, token hoặc provider
- **THEN** job Hub SHALL chuyển trạng thái lỗi riêng
- **AND** project video hoặc render nguồn MUST NOT bị chuyển failed hoặc stale chỉ vì lỗi upload đó

#### Scenario: Workflow media đang chạy
- **WHEN** AI Video hoặc Video Inspiration đang chạy và người dùng mở Automation Hub
- **THEN** Hub SHALL vẫn tải/poll trạng thái riêng
- **AND** Hub MUST NOT dùng cờ busy toàn trang của workflow media đó

### Requirement: Feature phải có guard cấu hình
Hệ thống SHALL chặn action có side effect của Automation Hub khi feature flag backend chưa bật, đồng thời trả trạng thái và hướng dẫn cấu hình an toàn.

#### Scenario: Feature chưa bật
- **WHEN** client gọi action lưu secret, mở browser hoặc tạo upload job trong khi feature disabled
- **THEN** API SHALL từ chối bằng error code ổn định và thông báo tiếng Việt
- **AND** hệ thống MUST NOT khởi động sidecar hoặc ghi publishing job

#### Scenario: Chỉ đọc status khi disabled
- **WHEN** client đọc Automation Hub status trong khi feature disabled
- **THEN** API SHALL trả `enabled = false` cùng danh sách prerequisite thiếu
- **AND** response MUST NOT chứa secret hoặc path nhạy cảm

### Requirement: Secret của Hub được mã hóa và redaction
Hệ thống SHALL mã hóa API key/access token/refresh token/client secret trước khi ghi storage và MUST NOT trả lại secret rõ qua API, log hoặc debug.

#### Scenario: Lưu Roxy API key
- **WHEN** người dùng lưu Roxy API key hợp lệ
- **THEN** database SHALL chỉ lưu ciphertext và fingerprint rút gọn
- **AND** response SHALL chỉ cho biết secret đã được cấu hình

#### Scenario: Cập nhật connection không gửi secret mới
- **WHEN** người dùng chỉ đổi label hoặc public config
- **THEN** hệ thống SHALL giữ secret ciphertext hiện có
- **AND** MUST NOT ghi secret thành null hoặc chuỗi mask

#### Scenario: Không giải mã được secret
- **WHEN** encryption key bị mất hoặc ciphertext hỏng
- **THEN** connection SHALL chuyển `needs_auth` hoặc lỗi cấu hình
- **AND** hệ thống MUST NOT log ciphertext, key hoặc secret đoán được

### Requirement: Hub quản lý RoxyBrowser qua Local API chính thức
Hệ thống SHALL dùng Local API loopback với header `token` để kiểm tra health, đọc workspace/profile, mở/đóng profile và đọc connection info.

#### Scenario: Local API sẵn sàng
- **WHEN** RoxyBrowser Desktop đang mở, API enabled và key hợp lệ
- **THEN** Hub SHALL hiển thị health, workspace và danh sách profile đã redaction

#### Scenario: Mở profile
- **WHEN** người dùng chọn workspace và profile hợp lệ rồi yêu cầu mở
- **THEN** Hub SHALL gọi Local API với `workspaceId`, `dirId` và option đã cho phép
- **AND** response SHALL trả trạng thái cùng endpoint CDP/BiDi cần thiết mà không trả API key

#### Scenario: Desktop chưa chạy
- **WHEN** Local API không kết nối được
- **THEN** Hub SHALL hiển thị lỗi tiếng Việt yêu cầu mở RoxyBrowser và bật API
- **AND** hệ thống MUST NOT tự kill hoặc sửa process khác trên máy

#### Scenario: Key không hợp lệ
- **WHEN** Local API từ chối token
- **THEN** connection SHALL chuyển trạng thái cần cấu hình lại
- **AND** log MUST NOT chứa token đã gửi

### Requirement: Playwright MCP chạy như sidecar tách biệt
Hệ thống SHALL quản lý status của `roxybrowser-playwright-mcp` qua loopback health endpoint và MAY start process chỉ khi entry path hợp lệ cùng feature flag đã bật.

#### Scenario: Sidecar đang chạy
- **WHEN** health endpoint trả thành công
- **THEN** Hub SHALL hiển thị MCP runtime ready
- **AND** SHALL phân biệt ready của process với trạng thái đã kết nối browser

#### Scenario: Start sidecar bằng cấu hình
- **WHEN** người dùng yêu cầu start và entry file tồn tại trong data directory hoặc path được cấu hình
- **THEN** backend SHALL start process ẩn, dùng artifact directories riêng của Hub và theo dõi PID runtime

#### Scenario: Entry path không hợp lệ
- **WHEN** entry file thiếu hoặc nằm ngoài phạm vi path được cho phép
- **THEN** backend SHALL từ chối start bằng lỗi cấu hình
- **AND** MUST NOT chạy command tùy ý từ client input

### Requirement: Setup ba repo RoxyBrowser không làm bẩn source tree
Hệ thống SHALL cung cấp script setup để clone/build `local-API`, `roxybrowser-mcp-server` và `roxybrowser-playwright-mcp` trong data directory hoặc target ngoài Git đã xác nhận.

#### Scenario: Setup lần đầu
- **WHEN** người dùng chạy script với prerequisite Git, Node, npm và pnpm hợp lệ
- **THEN** script SHALL clone ba repo, cài dependency/build hai MCP repo và báo đường dẫn runtime

#### Scenario: Setup chạy lại
- **WHEN** target repo đã tồn tại
- **THEN** script SHALL kiểm tra target chính xác trước khi update/build
- **AND** MUST NOT xóa hoặc reset thay đổi local không liên quan

#### Scenario: local-API repo
- **WHEN** setup hoàn tất clone `local-API`
- **THEN** tài liệu SHALL nói rõ repo này không phải server cần khởi động
- **AND** Local API runtime thật SHALL vẫn là RoxyBrowser Desktop

### Requirement: Browser automation không được vượt cơ chế bảo vệ nền tảng
Hệ thống MUST NOT dùng RoxyBrowser hoặc Playwright MCP để bypass CAPTCHA, 2FA, quota, audit, paywall, private-only restriction hoặc policy của provider.

#### Scenario: Trang yêu cầu CAPTCHA hoặc xác minh
- **WHEN** browser task gặp CAPTCHA, 2FA, consent hoặc login cần người dùng
- **THEN** task SHALL pause ở trạng thái cần người dùng thao tác
- **AND** automation MUST NOT tự giải hoặc né bước bảo vệ đó

#### Scenario: API chính thức bị hạn chế vì chưa audit
- **WHEN** TikTok hoặc nền tảng khác giới hạn audience/quyền do app chưa audit
- **THEN** Hub MUST giữ restriction chính thức
- **AND** MUST NOT chuyển sang browser automation để đăng công khai trái restriction
