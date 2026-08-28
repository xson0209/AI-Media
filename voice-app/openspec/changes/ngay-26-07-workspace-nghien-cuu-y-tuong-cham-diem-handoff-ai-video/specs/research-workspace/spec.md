## ADDED Requirements

### Requirement: Route workspace nghiên cứu độc lập
Hệ thống SHALL cung cấp route `/research` với giao diện tiếng Việt cho Research Project và SHALL không thay đổi route, redirect mặc định hoặc hành vi request của các workspace hiện có.

#### Scenario: Mở route nghiên cứu
- **WHEN** người dùng truy cập `/research`
- **THEN** hệ thống hiển thị workspace "Nghiên cứu ý tưởng" với danh sách project, trạng thái, filter và hành động tạo project

#### Scenario: Route cũ vẫn hoạt động
- **WHEN** người dùng truy cập `/ai-video`, `/video-inspiration`, `/comic-series-analysis` hoặc `/story-studio`
- **THEN** hệ thống mở đúng workspace cũ với component và API contract tương thích trước khi change được bật

### Requirement: Quản lý nhiều Research Project
Hệ thống SHALL cho phép tạo, sửa tên/mô tả, lưu trữ, mở lại và lọc nhiều Research Project; DB SHALL là nguồn chuẩn cho trạng thái, revision, liên kết và lựa chọn project.

#### Scenario: Tạo project nghiên cứu
- **WHEN** người dùng nhập tên và brief rồi bấm tạo
- **THEN** hệ thống tạo project trạng thái `draft`, revision ban đầu, manifest và memory file rỗng có schema marker

#### Scenario: Chọn nhiều project làm ngữ cảnh
- **WHEN** người dùng chọn nhiều Research Project trong danh sách
- **THEN** UI hiển thị số lượng đã chọn, các action tổng hợp hợp lệ và không thay đổi memory của project chưa được mở chỉnh sửa

#### Scenario: Project không còn hợp lệ
- **WHEN** project bị archive hoặc không tồn tại trong lúc compile context
- **THEN** hệ thống bỏ project đó khỏi context, trả cảnh báo rõ ràng và không làm hỏng các project còn lại

### Requirement: Memory bền vững có revision
Hệ thống SHALL compile phần đã duyệt của mỗi Research Project thành `research-memory.md` và `manifest.json`; raw run, item bị loại và draft chưa duyệt SHALL không được đưa vào memory chuẩn.

#### Scenario: Duyệt một ý tưởng
- **WHEN** người dùng approve một idea hoặc script
- **THEN** hệ thống tăng revision, ghi accepted id vào manifest, tạo revision history và compile lại memory file có provenance

#### Scenario: Mở lại memory
- **WHEN** người dùng mở phần Memory hoặc export project
- **THEN** hệ thống hiển thị bản memory hiện tại có mục tiêu, quyết định, accepted content, nguồn, điều tránh, câu hỏi mở và giới hạn phân tích

#### Scenario: Raw output chưa duyệt
- **WHEN** một run chứa output dài, candidate bị loại hoặc draft chat
- **THEN** hệ thống chỉ lưu trong thư mục run/lịch sử tương ứng và không dùng nó làm memory chuẩn mặc định

### Requirement: Cô lập UI và trạng thái với các luồng khác
Hệ thống SHALL tải Research Workspace qua component/router riêng, SHALL không dùng state toàn cục để ghi đè state của AI Video/Story Studio và SHALL hỗ trợ tắt menu/job research bằng feature flag.

#### Scenario: Tắt feature flag nghiên cứu
- **WHEN** feature flag Research Workspace bị tắt
- **THEN** route/menu/job nghiên cứu mới bị chặn hoặc ẩn theo policy nhưng các project AI Video và route cũ vẫn mở bình thường

#### Scenario: Reload hoặc deep-link
- **WHEN** người dùng reload `/research?projectId=<id>` hoặc quay lại từ route khác
- **THEN** hệ thống khôi phục đúng project, filter và tab hợp lệ mà không reset sang AI Video
