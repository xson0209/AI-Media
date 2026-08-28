## ADDED Requirements

### Requirement: Publishing dùng asset snapshot riêng
Hệ thống SHALL tạo asset bất biến trong kho Automation Hub từ file upload hoặc output video hiện có trước khi tạo publishing job.

#### Scenario: Upload file video
- **WHEN** người dùng upload file video có định dạng và kích thước được hỗ trợ
- **THEN** Hub SHALL lưu file dưới asset id riêng, tính SHA-256 và trả metadata an toàn

#### Scenario: File không hợp lệ
- **WHEN** file rỗng, vượt giới hạn, path traversal hoặc không phải định dạng video cho phép
- **THEN** Hub SHALL từ chối trước khi tạo publishing job
- **AND** MUST NOT ghi file ngoài storage root của Hub

#### Scenario: Dùng output video hiện có
- **WHEN** người dùng chọn một render/output MP4 hợp lệ
- **THEN** Hub SHALL import/copy hoặc hard-link an toàn thành asset riêng
- **AND** publishing job MUST NOT sửa row/status của render nguồn

### Requirement: Connection nền tảng chỉ công bố metadata an toàn
Hệ thống SHALL cho phép tạo/cập nhật/xóa/check connection YouTube, Facebook Page và TikTok bằng secret store mã hóa.

#### Scenario: Tạo YouTube connection
- **WHEN** người dùng cung cấp access/refresh credential và public channel label
- **THEN** Hub SHALL lưu secret mã hóa và trả connection không có token rõ

#### Scenario: Tạo Facebook connection không có Page id
- **WHEN** request Facebook thiếu Page id hoặc dùng personal profile
- **THEN** Hub SHALL từ chối với thông báo chỉ hỗ trợ Facebook Page

#### Scenario: Check connection hết hạn
- **WHEN** provider trả token expired, invalid hoặc thiếu scope
- **THEN** connection SHALL chuyển `needs_auth`
- **AND** failure reason SHALL không chứa bearer token

### Requirement: Job publishing có state machine và idempotency riêng
Hệ thống SHALL persist publishing job với trạng thái queued, scheduled, preparing, uploading, finalizing, completed, failed, interrupted hoặc cancelled và dùng idempotency key duy nhất.

#### Scenario: Tạo job lặp
- **WHEN** client gửi cùng idempotency key lần thứ hai
- **THEN** API SHALL trả job hiện có hoặc conflict rõ ràng
- **AND** MUST NOT tạo bài đăng thứ hai

#### Scenario: Upload hoàn tất
- **WHEN** provider xác nhận upload/post thành công
- **THEN** job SHALL lưu provider post id, URL nếu có, completed time và result metadata đã redaction

#### Scenario: Backend restart khi upload
- **WHEN** backend khởi động và còn job ở trạng thái active nhưng không còn runtime task
- **THEN** job SHALL chuyển interrupted
- **AND** hệ thống MUST NOT tự upload lại nếu outcome ở provider chưa xác định

### Requirement: Worker publishing độc lập và có giới hạn
Hệ thống SHALL xử lý job qua queue/scheduler riêng với concurrency thấp được cấu hình và MUST NOT dùng workflow, planning, voice hoặc render slot hiện có.

#### Scenario: Nhiều job được xếp hàng
- **WHEN** số job ready vượt concurrency publishing
- **THEN** job dư SHALL giữ queued theo FIFO và tự chạy khi có slot

#### Scenario: Hủy job chưa chạy
- **WHEN** người dùng hủy job queued hoặc scheduled
- **THEN** job SHALL chuyển cancelled ngay và MUST NOT gọi provider

#### Scenario: Hủy job đang upload
- **WHEN** người dùng hủy job active
- **THEN** worker SHALL ghi nhận cancel và dừng ở checkpoint an toàn
- **AND** UI SHALL cảnh báo provider có thể đã nhận một phần hoặc toàn bộ upload

### Requirement: YouTube dùng Data API upload chính thức
Hệ thống SHALL upload YouTube qua resumable `videos.insert`, hỗ trợ privacy và native scheduling khi credential/scope hợp lệ.

#### Scenario: Upload YouTube ngay
- **WHEN** job YouTube hợp lệ không có lịch tương lai
- **THEN** adapter SHALL tạo resumable session, upload video và lưu video id trả về

#### Scenario: Lên lịch YouTube
- **WHEN** job có `scheduled_at` hợp lệ
- **THEN** adapter SHALL gửi `privacyStatus = private` và `status.publishAt` theo contract YouTube

#### Scenario: Project API chưa audit
- **WHEN** YouTube bắt buộc video private do project chưa audit
- **THEN** Hub SHALL giữ trạng thái/privacy do API áp dụng và hiển thị limitation
- **AND** MUST NOT dùng browser fallback để đổi công khai trái restriction

### Requirement: Facebook chỉ đăng lên Page qua API chính thức
Hệ thống SHALL upload video lên Facebook Page bằng Graph Video API và hỗ trợ scheduling khi Page token/quyền hợp lệ.

#### Scenario: Upload Page video
- **WHEN** connection có Page id và Page access token hợp lệ
- **THEN** adapter SHALL upload source video cùng title/description lên Page đã chọn

#### Scenario: Lên lịch Facebook Page
- **WHEN** job có lịch hợp lệ theo giới hạn Graph API
- **THEN** adapter SHALL dùng unpublished/scheduled fields chính thức và lưu post/video id trả về

#### Scenario: Personal profile
- **WHEN** người dùng cố cấu hình hoặc đăng lên Facebook personal profile
- **THEN** Hub SHALL từ chối vì capability chỉ hỗ trợ Page

### Requirement: TikTok Draft dùng Content Posting API chính thức
Hệ thống SHALL hỗ trợ TikTok Draft upload bằng scope `video.upload`, init upload, truyền chunk và lưu publish id/status.

#### Scenario: Tạo TikTok Draft
- **WHEN** connection có access token cùng scope `video.upload` và asset hợp lệ
- **THEN** adapter SHALL init `FILE_UPLOAD`, upload đủ byte range và lưu publish id

#### Scenario: TikTok không có native schedule
- **WHEN** TikTok Draft job có lịch tương lai
- **THEN** scheduler nội bộ SHALL giữ job scheduled và chỉ gọi TikTok khi đến hạn

#### Scenario: TikTok Direct Post chưa bật
- **WHEN** request dùng direct post nhưng feature flag hoặc audit guard chưa thỏa
- **THEN** Hub SHALL từ chối trước khi upload
- **AND** SHALL gợi ý dùng Draft nếu connection có scope phù hợp

### Requirement: Retry chỉ áp dụng khi an toàn
Hệ thống SHALL phân loại lỗi retryable và outcome mơ hồ, ghi attempt riêng và không tự tạo post trùng.

#### Scenario: Lỗi mạng trước khi provider nhận upload
- **WHEN** adapter xác định request chưa được provider chấp nhận và lỗi là retryable
- **THEN** worker MAY retry trong giới hạn cấu hình với backoff

#### Scenario: Timeout sau bước finalize
- **WHEN** response timeout xảy ra sau khi provider có thể đã tạo post nhưng chưa nhận được id
- **THEN** job SHALL chuyển failed/interrupted với outcome mơ hồ
- **AND** hệ thống MUST NOT tự retry không giới hạn

#### Scenario: Retry thủ công job có provider id
- **WHEN** job đã có provider post id
- **THEN** API SHALL không upload lại asset
- **AND** SHALL trả kết quả hiện có hoặc yêu cầu action kiểm tra status

### Requirement: UI hiển thị trạng thái publishing bằng tiếng Việt
Hệ thống SHALL cung cấp màn hình riêng để quản lý asset, connection và job, với trạng thái/limitation dễ hiểu và không lộ raw secret.

#### Scenario: Theo dõi job
- **WHEN** job chuyển queued, uploading, scheduled, completed hoặc failed
- **THEN** UI SHALL cập nhật trạng thái tiếng Việt và action hợp lệ cho trạng thái đó

#### Scenario: Secret đã lưu
- **WHEN** connection đã có secret
- **THEN** UI SHALL chỉ hiển thị trạng thái đã cấu hình và fingerprint/label an toàn
- **AND** MUST NOT điền lại token thật vào input

#### Scenario: Workflow media khác đang chạy
- **WHEN** người dùng chuyển sang Automation Hub trong lúc dự án khác đang xử lý
- **THEN** UI SHALL không dừng workflow đó
- **AND** polling Hub SHALL không khóa navigation hoặc action không xung đột
