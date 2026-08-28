## ADDED Requirements

### Requirement: Người dùng chủ động bật làm sạch watermark khi dựng MP4
Hệ thống SHALL cung cấp setting render để bật hoặc tắt xử lý visible AI watermark và verified AI metadata; setting MUST mặc định tắt và pipeline cũ MUST không gọi watermark worker khi setting tắt.

#### Scenario: Render khi cleanup tắt
- **WHEN** người dùng dựng MP4 với watermark cleanup tắt
- **THEN** hệ thống SHALL dùng source clip trực tiếp cho normalize và giữ readiness/render behavior hiện có

#### Scenario: Render khi cleanup bật
- **WHEN** người dùng bật watermark cleanup và worker sẵn sàng
- **THEN** hệ thống SHALL xử lý từng active clip trước normalize và dùng derivative hợp lệ cho video path

#### Scenario: Auto-render không có preference cleanup
- **WHEN** auto-render tạo render settings mặc định mà không có lựa chọn cleanup đã lưu hoặc truyền vào
- **THEN** hệ thống MUST giữ watermark cleanup tắt thay vì tự động xóa dấu AI

### Requirement: Worker watermark cô lập và có readiness
Hệ thống SHALL chạy video watermark API qua Python worker cô lập có protocol JSON, package root/Python cấu hình được, exact runtime revision và FFmpeg path được truyền từ Voicebox.

#### Scenario: Worker đầy đủ dependency
- **WHEN** cleanup được bật và configured worker import được package video runtime cùng FFmpeg cần thiết
- **THEN** readiness SHALL báo worker sẵn sàng và trả revision dùng cho cache/report

#### Scenario: Worker thiếu dependency hoặc executable
- **WHEN** cleanup được bật nhưng Python, package root, OpenCV, PyAV hoặc FFmpeg cần thiết không sẵn sàng
- **THEN** readiness MUST báo không sẵn sàng bằng lỗi tiếng Việt và MUST không bắt đầu render job trừ khi force policy hiện có cho phép rõ ràng

#### Scenario: Cleanup tắt khi worker không tồn tại
- **WHEN** cleanup tắt và worker không được cài
- **THEN** readiness SHALL không chặn render MP4 cơ bản

### Requirement: Định tuyến visible mark theo clip provider
Hệ thống SHALL xử lý mỗi clip độc lập, dùng detector explicit cho provider được hỗ trợ và chỉ dùng bounded auto-detection khi provider không xác định.

#### Scenario: Clip provider Veo
- **WHEN** active clip có `provider=veo` và cleanup được bật
- **THEN** worker MUST gọi visible cleanup với mark `veo`

#### Scenario: Clip upload không rõ provider
- **WHEN** active clip là upload hoặc provider không ánh xạ được vào registry hỗ trợ
- **THEN** worker SHALL dùng mark `auto` có giới hạn của thư viện

#### Scenario: Project có clip từ nhiều provider
- **WHEN** timeline chứa nhiều clip có provider khác nhau
- **THEN** hệ thống SHALL xử lý và ghi kết quả riêng theo từng shot thay vì chỉ quét final compilation một lần

### Requirement: Chỉ xử lý visible mark và verified metadata trong MVP
Hệ thống MUST dùng product video cleanup với invisible regeneration bị tắt và MUST không tải diffusion/GPU model trong capability này.

#### Scenario: Worker nhận request hợp lệ
- **WHEN** backend gửi request cleanup cho worker
- **THEN** worker MUST gọi API với `include_invisible=false` và SHALL từ chối hoặc bỏ qua mọi request cố bật invisible processing

#### Scenario: Không có visible mark được hỗ trợ
- **WHEN** detector không tìm thấy stable visible mark nhưng cleanup API hoàn tất
- **THEN** render SHALL tiếp tục bằng output same-container và report MUST ghi no supported mark thay vì báo đã xóa

### Requirement: Giữ nguyên source clip và cache derivative an toàn
Hệ thống MUST không ghi đè hoặc xóa source clip, SHALL publish derivative/cache report atomically và SHALL invalidate cache khi source, policy hoặc worker revision thay đổi.

#### Scenario: Cache miss
- **WHEN** chưa có derivative hợp lệ cho source identity, mark, backend, policy và worker revision hiện tại
- **THEN** hệ thống SHALL tạo temp output, validate file, atomic replace vào watermark cache và ghi cache miss

#### Scenario: Cache hit
- **WHEN** derivative và report hợp lệ tồn tại cho cùng cache key
- **THEN** hệ thống SHALL reuse output mà không chạy worker lại và ghi cache hit

#### Scenario: Source clip hoặc worker revision thay đổi
- **WHEN** source size/mtime/path hoặc worker revision/policy/backend thay đổi
- **THEN** hệ thống MUST tạo cache key mới và không reuse derivative cũ

#### Scenario: Worker thất bại giữa chừng
- **WHEN** worker timeout, trả protocol invalid, encode fail hoặc không tạo output hợp lệ
- **THEN** hệ thống MUST xóa temp artifact, giữ source/cache cũ và fail render bằng error code rõ ràng

### Requirement: Cleanup không làm thay đổi audio/subtitle source
Hệ thống SHALL chỉ dùng watermark derivative cho video normalize path; audio timeline và subtitle timing MUST tiếp tục dùng source contract hiện có.

#### Scenario: Veo native Vietnamese speech
- **WHEN** project tiếng Việt dùng audio nhúng trong active Veo clip và cleanup được bật
- **THEN** audio builder SHALL tiếp tục extract audio từ active source clip, còn normalized video SHALL dùng derivative đã xử lý

#### Scenario: Burn-in subtitle
- **WHEN** render bật burn-in subtitle và watermark cleanup
- **THEN** cleanup MUST hoàn tất trước khi subtitle được burn để worker không inpaint text overlay của Voicebox

### Requirement: Reporting trung thực và có thể audit
Hệ thống SHALL ghi setting, runtime revision, cache summary và kết quả từng shot vào timeline manifest hoặc render diagnostics mà không khẳng định quá mức.

#### Scenario: Visible mark được xử lý
- **WHEN** worker trả visible mark cùng detected/removed frame counts
- **THEN** manifest SHALL lưu provider, mark, frame counts, backend, revision và cache status cho shot đó

#### Scenario: No-signal
- **WHEN** worker trả `visible_mark=null`
- **THEN** UI/report SHALL dùng wording tương đương “không tìm thấy dấu AI được hỗ trợ” và MUST không ghi “video hoàn toàn sạch watermark”

### Requirement: UI tiếng Việt và quyền sử dụng
Hệ thống SHALL cung cấp UI tiếng Việt để bật cleanup, chọn backend hỗ trợ và hiểu tác động xử lý trước khi render.

#### Scenario: Mở panel dựng MP4
- **WHEN** người dùng mở thiết lập dựng
- **THEN** UI SHALL hiển thị công tắc cleanup mặc định tắt, mô tả giữ file gốc và nhắc chỉ dùng cho nội dung người dùng có quyền chỉnh sửa

#### Scenario: Chọn backend
- **WHEN** cleanup được bật
- **THEN** UI SHALL cho chọn `cv2` hoặc `migan`, không cung cấp `auto`, `lama` hoặc invisible/SynthID trong change này

#### Scenario: Worker không sẵn sàng
- **WHEN** readiness báo watermark worker không sẵn sàng
- **THEN** UI SHALL hiển thị lý do tiếng Việt trong checklist và không cho bắt đầu render bình thường

