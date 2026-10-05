## ADDED Requirements

### Requirement: Auto-run cung cấp ba output target và review gate
Product Video MUST cung cấp các profile `prompts_only`, `video_clips` và `render_ready`. Hệ thống MUST hỗ trợ chế độ `review_gated` để dừng sau prompt hoặc sau clip theo cấu hình, và `full_auto` để tự tiếp tục sau preflight trong khi vẫn chạy validation bắt buộc.

#### Scenario: Chỉ sinh prompt
- **WHEN** người dùng chọn `prompts_only`
- **THEN** auto-run lập shot và sinh prompt rồi kết thúc mà không gọi htmustc hoặc render

#### Scenario: Sinh clip nhưng chưa render
- **WHEN** người dùng chọn `video_clips`
- **THEN** auto-run gọi provider, tải/validate/import đủ clip rồi dừng ở trạng thái clip sẵn sàng

#### Scenario: Full auto
- **WHEN** người dùng chọn `render_ready` và `full_auto`, preflight đạt và mọi clip đã ready
- **THEN** auto-run tạo render job và tiếp tục tới MP4 thành phẩm

#### Scenario: Review gate
- **WHEN** người dùng chọn `review_gated`
- **THEN** auto-run dừng ở gate đã cấu hình, hiển thị prompt hoặc clip để người dùng duyệt trước khi tiếp tục

### Requirement: Auto-run có một pipeline tuần tự cho mỗi project
Hệ thống MUST điều phối một auto-run active duy nhất cho mỗi project theo thứ tự: validate project, plan shots, generate prompts, prompt gate, provider preflight, generate clips, download/validate/import, render gate và quality gate. Hệ thống MUST không chạy đồng thời hai pipeline ghi vào cùng project.

#### Scenario: Pipeline chạy tuần tự
- **WHEN** một bước chưa đạt trạng thái terminal thành công
- **THEN** bước phụ thuộc phía sau không được bắt đầu và UI hiển thị current step/item

#### Scenario: Bắt đầu trùng project
- **WHEN** người dùng bắt đầu auto-run mới trong lúc project đã có auto-run active
- **THEN** hệ thống trả job active hoặc yêu cầu resume/cancel, không tạo pipeline thứ hai

### Requirement: Auto-run cho phép kiểm soát lỗi và thao tác item
UI và API MUST hiển thị trạng thái job, queue position, current item, lỗi đã redaction và số lần thử; MUST hỗ trợ pause, resume, cancel, retry một item lỗi, retry toàn bộ item lỗi và retry render mà không tạo lại clip ready.

#### Scenario: Retry riêng shot lỗi
- **WHEN** một item failed còn các item khác ready
- **THEN** người dùng có thể retry item đó, các item ready không bị submit lại và render vẫn bị block cho tới khi item đạt ready

#### Scenario: Pause queue
- **WHEN** người dùng pause auto-run
- **THEN** hệ thống không lấy item queued mới, giữ operation đang theo dõi và bảo toàn clip đã import

#### Scenario: Cancel queue
- **WHEN** người dùng cancel auto-run
- **THEN** hệ thống dừng submit mới, xử lý cancel provider nếu contract hỗ trợ, ghi trạng thái cancelled và giữ artifacts đã hoàn tất

### Requirement: Render gate và quality gate bảo vệ MP4 thành phẩm
Auto-run MUST chỉ render khi tất cả clip thuộc prompt snapshot đều ready và render settings/FFmpeg readiness đạt. Sau render, hệ thống MUST kiểm tra output tồn tại, metadata video, duration, aspect ratio, codec và điều kiện audio theo project trước khi đánh dấu completed.

#### Scenario: Render khi đủ clip
- **WHEN** mọi item ready và render readiness đạt
- **THEN** hệ thống tạo `VideoRenderJob`, dùng render bridge hiện có và chỉ đánh dấu auto-run hoàn tất sau quality gate

#### Scenario: Render thất bại
- **WHEN** FFmpeg hoặc quality gate thất bại sau generation thành công
- **THEN** generation vẫn giữ completed, render chuyển failed và người dùng có thể retry render mà không gọi provider lại

### Requirement: Auto-run bảo vệ secret và chi phí
Hệ thống MUST giữ API key ở backend secret store hoặc environment backend, MUST redaction signed URL/secret trong log và response, MUST hiển thị model, số shot, cấu hình, retry policy và auto-render trước khi chạy, và MUST không tự động đổi model.

#### Scenario: Xác nhận trước khi chạy
- **WHEN** người dùng chuẩn bị bắt đầu generation
- **THEN** UI hiển thị bản tóm tắt model, resolution, aspect ratio, seconds, số clip, concurrency, retry và output target để người dùng xác nhận

#### Scenario: Secret không bị lộ
- **WHEN** provider trả lỗi hoặc job được poll trên frontend
- **THEN** response/log chỉ chứa error code và metadata đã redaction, không chứa Bearer token hoặc signed URL nguyên văn

#### Scenario: Đổi model
- **WHEN** người dùng muốn đổi model sau khi job đã bắt đầu
- **THEN** hệ thống yêu cầu tạo generation revision mới thay vì đổi model trong job hiện tại
