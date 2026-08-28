## ADDED Requirements

### Requirement: Nhận nhiều loại nguồn nghiên cứu
Hệ thống SHALL cho phép thêm `video_url`, `video_upload`, `story_url`, `image_upload`, `text`, `docs_url` và `series_memory` vào một Research Project; mỗi source SHALL có trạng thái, revision, provenance và giới hạn phân tích.

#### Scenario: Thêm link video
- **WHEN** người dùng nhập một link video public hợp lệ
- **THEN** hệ thống tạo source trạng thái `queued` hoặc `analyzing`, lưu URL đã redaction và không yêu cầu người dùng nhập lại brief của project

#### Scenario: Upload video hoặc ảnh
- **WHEN** người dùng upload file hợp lệ
- **THEN** hệ thống giữ original bất biến, tạo source artifact directory riêng và trả tiến trình xử lý có MIME, byte, kích thước hoặc duration đã kiểm tra

#### Scenario: Link truyện hoặc docs bị chặn
- **WHEN** URL yêu cầu login, paywall, CAPTCHA, DRM hoặc vi phạm policy truy cập
- **THEN** hệ thống trả trạng thái `needs_review` với hướng dẫn upload/dán nội dung và không cố vượt cơ chế bảo vệ

#### Scenario: Liên kết trực tiếp Series Memory
- **WHEN** người dùng chọn một Series hiện có làm nguồn nghiên cứu
- **THEN** hệ thống compile trực tiếp canon đã duyệt qua Series Brain, lưu `series_id`, revision/fingerprint và provenance, không yêu cầu dán tóm tắt và không sửa dữ liệu Series nguồn

#### Scenario: Series Memory đã thay đổi
- **WHEN** fingerprint hiện tại của Series khác fingerprint đã lưu trong source package
- **THEN** source được hiển thị `stale`, giữ snapshot cũ để truy vết và cho phép người dùng chủ động làm mới thành revision source mới

### Requirement: Chuẩn hóa source package
Hệ thống SHALL chuyển kết quả adapter thành Research Source Package có summary, observations, content lessons, evidence refs, provenance, coverage và limitations; source package SHALL có fingerprint theo revision.

#### Scenario: Phân tích video hoàn tất một phần
- **WHEN** transcript có nhưng frame/audio hoặc một bước phân tích bị thiếu
- **THEN** source package ghi rõ phần có/không có, trạng thái `partial` và không tự suy đoán dữ liệu bị thiếu

#### Scenario: Nguồn truyện hoặc ảnh hoàn tất
- **WHEN** parser/OCR/vision tạo được nội dung đã cấu trúc
- **THEN** package giữ thứ tự trang/panel, nhân vật/bối cảnh, evidence và liên kết artifact nguồn để review

### Requirement: An toàn nguồn và artifact
Hệ thống SHALL kiểm tra SSRF/redirect, giới hạn byte/pixel/duration, loại cookie/token khỏi log, coi nội dung nguồn là dữ liệu không tin cậy và SHALL không cho source text trở thành system instruction.

#### Scenario: URL nội bộ hoặc redirect nguy hiểm
- **WHEN** URL trỏ tới loopback, private network, metadata endpoint hoặc redirect vượt policy
- **THEN** hệ thống từ chối trước khi tải và trả error code có hướng dẫn khôi phục an toàn

#### Scenario: Xóa source chưa được handoff
- **WHEN** người dùng xóa source chưa được Research Handoff hoặc project AI Video tham chiếu
- **THEN** hệ thống xóa đúng derivative/DB link theo policy nhưng giữ audit/revision cần thiết và không xóa nhầm source đang được tham chiếu
