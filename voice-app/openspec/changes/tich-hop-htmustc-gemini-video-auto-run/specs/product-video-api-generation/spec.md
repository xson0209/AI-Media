## ADDED Requirements

### Requirement: Project chọn một model htmustc cho một generation revision
Product Video MUST cho phép một generation revision chọn đúng một trong các model được cấu hình, gồm `gemini-veo-3-1` hoặc `gemini-omni-flash`, cùng resolution, aspect ratio và seconds hợp lệ. Hệ thống MUST snapshot các giá trị này khi tạo job và MUST NOT tự đổi model trong job đang chạy.

#### Scenario: Tạo job với model hợp lệ
- **WHEN** người dùng bắt đầu generation với một model, resolution, aspect ratio và seconds được capability matrix chấp nhận
- **THEN** hệ thống tạo job với snapshot cấu hình tương ứng và mọi item của job dùng cùng model đó

#### Scenario: Từ chối cấu hình không được provider hỗ trợ
- **WHEN** preflight phát hiện model hoặc một tham số generation không được capability matrix chấp nhận
- **THEN** hệ thống dừng trước khi gửi request provider và trả lỗi cấu hình có hành động sửa rõ ràng

### Requirement: Backend gọi htmustc bằng secret và contract chuẩn hóa
Backend MUST gửi request tới `POST https://htmustc.id.vn/v1/videos/generations` với Bearer secret, `Content-Type: application/json`, model alias, prompt, seconds ở dạng chuỗi, resolution và aspect ratio. Provider adapter MUST chuẩn hóa response đồng bộ hoặc bất đồng bộ thành operation/status nội bộ mà không để raw provider schema lan sang UI.

#### Scenario: Serialize request generation
- **WHEN** item đủ điều kiện gửi provider
- **THEN** backend gửi đúng endpoint, secret backend và payload có `model`, `prompt`, `seconds` dạng chuỗi, `resolution` và `aspect_ratio`

#### Scenario: Provider trả operation bất đồng bộ
- **WHEN** provider trả operation id thay vì video URL hoàn chỉnh
- **THEN** adapter lưu operation id và trả trạng thái chờ poll cho orchestrator

#### Scenario: Provider trả video hoàn chỉnh ngay
- **WHEN** provider trả response đã có video URL hợp lệ
- **THEN** adapter chuyển item sang bước download mà không yêu cầu endpoint poll không cần thiết

### Requirement: Generation job có queue và idempotency theo shot
Hệ thống MUST tạo một generation job cho một project/prompt revision và một generation item cho mỗi shot. Hệ thống MUST giới hạn concurrency toàn hệ thống và theo project, MUST cấp lease cho worker, và MUST đảm bảo submit trùng cùng fingerprint trả lại job/item hiện có thay vì tạo operation mới.

#### Scenario: Xếp hàng vượt quá concurrency
- **WHEN** số item pending lớn hơn số worker slot được cấu hình
- **THEN** chỉ item trong giới hạn được submit, các item còn lại giữ trạng thái queued và được lấy khi slot giải phóng

#### Scenario: Double submit cùng fingerprint
- **WHEN** người dùng bắt đầu lại cùng project, prompt fingerprint, model và generation settings trong khi job tương ứng còn active
- **THEN** hệ thống trả lại job hiện có và không gửi thêm provider operation

#### Scenario: Hai project dùng queue chung
- **WHEN** nhiều project cùng có item queued
- **THEN** global queue áp dụng giới hạn chung và scheduler không để một project chiếm vô hạn worker slot của project khác

### Requirement: Retry, pause, resume và reconcile phải fail-closed
Hệ thống MUST phân loại lỗi retryable và non-retryable. Hệ thống MUST retry có giới hạn và backoff cho lỗi tạm thời, MUST pause để người dùng xử lý lỗi auth/capability, và MUST chuyển timeout chưa rõ provider state sang reconcile thay vì gửi request mù.

#### Scenario: Retry lỗi rate limit
- **WHEN** provider trả 429 hoặc lỗi tạm thời nằm trong retry policy
- **THEN** item được đưa vào retry queue với backoff và không vượt quá max attempts

#### Scenario: Lỗi request không hợp lệ
- **WHEN** provider trả lỗi 4xx do payload hoặc capability không hợp lệ
- **THEN** item chuyển failed/paused theo policy và không tự retry cùng request

#### Scenario: Timeout chưa biết provider đã nhận request
- **WHEN** submit hoặc poll timeout trước khi xác định operation terminal
- **THEN** item chuyển `unknown_provider_state`, hệ thống đối soát operation trước khi cho phép retry và không gửi duplicate tự động

#### Scenario: Resume sau pause
- **WHEN** người dùng sửa điều kiện lỗi và bấm resume
- **THEN** hệ thống tiếp tục item chưa terminal hoặc poll operation cũ, giữ nguyên các item đã ready

### Requirement: Video tải về phải được staging và kiểm định trước khi import
Hệ thống MUST tải video vào staging, kiểm tra HTTP response, kích thước, SHA-256 và ffprobe metadata trước khi atomic move và tạo `VideoShotClip` ready. File không hợp lệ MUST NOT được import hoặc dùng để render.

#### Scenario: Download và import thành công
- **WHEN** video tải đủ, ffprobe đọc được duration/resolution/codec/audio theo policy và hash được ghi nhận
- **THEN** file được promote an toàn, item gắn đúng shot và `VideoShotClip` chuyển ready

#### Scenario: Video hỏng hoặc sai metadata
- **WHEN** file không đọc được hoặc không đạt validation
- **THEN** item chuyển failed, file staging được giữ hoặc cleanup theo policy, và render không được coi item là sẵn sàng

### Requirement: Generation tách biệt với render và hỗ trợ khôi phục
Hệ thống MUST chỉ tạo render job khi mọi item của cùng snapshot prompt đã ready. Generation thành công và render thất bại MUST là hai trạng thái độc lập; backend MUST có thể tiếp tục poll/reconcile job sau restart bằng operation id đã lưu.

#### Scenario: Đủ toàn bộ clip
- **WHEN** tất cả item của generation revision đều ready
- **THEN** hệ thống có thể tạo `VideoRenderJob` cho render bridge mà không gọi lại provider

#### Scenario: Một item thất bại
- **WHEN** ít nhất một item failed hoặc chưa ready
- **THEN** render bị block, các item ready được giữ lại và người dùng có thể retry item lỗi riêng

#### Scenario: Backend restart trong lúc provider chạy
- **WHEN** backend khởi động lại với job còn active
- **THEN** hệ thống đọc operation id/lease, tiếp tục poll operation có thể xác định hoặc chuyển paused để người dùng reconcile, không tạo request mới mù
