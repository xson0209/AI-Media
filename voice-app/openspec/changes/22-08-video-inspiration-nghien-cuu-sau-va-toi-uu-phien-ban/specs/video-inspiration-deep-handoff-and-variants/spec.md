## ADDED Requirements

### Requirement: Nghiên cứu sâu và mở cấu hình AI Video

Hệ thống SHALL cung cấp một hành động `Nghiên cứu sâu → Cấu hình Video AI` dùng profile phân tích sâu, xử lý nền và tự mở form cấu hình sau khi hoàn tất. Hành động này SHALL NOT tạo project hoặc chạy AI Video tự động.

#### Scenario: Bắt đầu nghiên cứu sâu

- **WHEN** người dùng có video nguồn hợp lệ và bấm `Nghiên cứu sâu → Cấu hình Video AI`
- **THEN** hệ thống SHALL chạy profile chất lượng sâu và lưu analysis package có coverage, limitations, provenance và revision
- **AND** hệ thống SHALL lưu pending handoff cho đúng job/revision
- **AND** giao diện SHALL hiển thị tiến trình tiếng Việt và không giữ một HTTP request mở cho toàn bộ workflow

#### Scenario: Tự mở form sau khi hoàn tất

- **WHEN** nghiên cứu sâu hoàn tất thành công
- **THEN** hệ thống SHALL mở `/ai-video?draft=video-inspiration`
- **AND** draft SHALL chứa transcript, ý chính, hook, visual summary, frame/shot evidence, direction, limitations và provenance
- **AND** draft MAY không có `rewritten_script` nếu người dùng chưa chạy pipeline tối ưu kịch bản

#### Scenario: Không auto-run sau deep handoff

- **WHEN** AI Video nhận draft từ nghiên cứu sâu
- **THEN** AI Video SHALL không tạo project, không chạy planning, prompt, voice, subtitle, render, Veo hoặc publishing
- **AND** AI Video SHALL không set `material_target = "full_materials"`
- **AND** draft SHALL không ghi đè market, ngôn ngữ cuối, thời lượng, tỷ lệ, voice profile hoặc run mode mà người dùng cần tự chọn

#### Scenario: Lỗi hoặc reload trong lúc chờ

- **WHEN** người dùng reload, hủy, hoặc job nghiên cứu sâu fail/stale
- **THEN** hệ thống SHALL khôi phục hoặc xóa pending intent đúng theo trạng thái job
- **AND** hệ thống SHALL không tự redirect sang AI Video nếu job chưa terminal thành công
- **AND** người dùng SHALL có hành động retry rõ ràng

### Requirement: Tạo candidate và chấm điểm theo batch

Hệ thống SHALL cho phép tạo 2–3 candidate có cùng schema, chọn candidate bằng checkbox và chấm điểm nhiều candidate trong một batch request khi provider hỗ trợ.

#### Scenario: Tạo nhiều candidate

- **WHEN** người dùng bấm tạo nhiều phiên bản nháp
- **THEN** hệ thống SHALL tạo ít nhất 2 candidate và tối đa theo giới hạn cấu hình
- **AND** mỗi candidate SHALL có variant id, hook, big idea, script, segments, retention, visual suggestions, sound design và originality note
- **AND** hệ thống SHALL lưu từng candidate với revision, provenance và fingerprint

#### Scenario: Chọn candidate để chấm điểm

- **WHEN** người dùng chọn một hoặc nhiều candidate bằng checkbox và bấm `Chấm điểm các bản đã chọn`
- **THEN** hệ thống SHALL chấm điểm theo batch rubric
- **AND** mỗi candidate SHALL có điểm hook, clarity, originality, retention, production feasibility, sound design và alignment
- **AND** hệ thống SHALL lưu lý do, strengths, weaknesses, recommendation và rubric version

#### Scenario: Chấm điểm tất cả

- **WHEN** người dùng bấm `Chấm điểm tất cả`
- **THEN** hệ thống SHALL đưa toàn bộ candidate hợp lệ vào một batch scoring request
- **AND** hệ thống SHALL không tạo request riêng không cần thiết cho từng candidate

### Requirement: Tạo một hoặc nhiều phiên bản tối ưu

Hệ thống SHALL cho phép tổng hợp một hoặc nhiều final version từ candidate và score đã chọn, giữ liên kết nguồn và không ghi đè revision cũ.

#### Scenario: Tạo bản tối ưu duy nhất

- **WHEN** người dùng chọn chiến lược bản cân bằng và bấm tổng hợp
- **THEN** hệ thống SHALL tạo một final version nhất quán về ý tưởng, ngôn ngữ, nhân vật, retention, âm thanh và hình ảnh
- **AND** final version SHALL lưu source basis tới candidate/score đã sử dụng

#### Scenario: Tạo nhiều bản tối ưu

- **WHEN** người dùng chọn tạo nhiều phiên bản theo các ưu tiên khác nhau
- **THEN** hệ thống SHALL tạo 1–N final version trong giới hạn cấu hình
- **AND** mỗi version SHALL có variant id, chiến lược, source basis, originality note và revision riêng
- **AND** người dùng SHALL chọn một final version trước khi handoff sang AI Video

### Requirement: Cache và chạy lại theo stage

Hệ thống SHALL cache kết quả theo fingerprint và SHALL chỉ chạy lại stage bị lỗi hoặc downstream bị ảnh hưởng khi input thay đổi.

#### Scenario: Cache hit

- **WHEN** analysis revision, target language, direction, candidate count, selected variants, rubric version và model không đổi
- **THEN** hệ thống SHALL tái sử dụng output stage tương ứng
- **AND** hệ thống SHALL không gọi lại AI không cần thiết

#### Scenario: Input thay đổi

- **WHEN** một thành phần fingerprint thay đổi
- **THEN** hệ thống SHALL đánh dấu stage phụ thuộc là stale
- **AND** hệ thống SHALL giữ output cũ để đối chiếu
- **AND** hệ thống SHALL chỉ chạy lại stage cần thiết cùng downstream của nó

#### Scenario: Stage lỗi một phần

- **WHEN** một candidate, scoring batch hoặc synthesis stage thất bại
- **THEN** hệ thống SHALL giữ kết quả hợp lệ đã có
- **AND** người dùng SHALL có thể retry stage đó mà không chạy lại analysis từ đầu

### Requirement: Bounded concurrency và tiến trình

Hệ thống SHALL giới hạn concurrency theo workflow/planning pool hiện có, hiển thị tiến trình tiếng Việt và cập nhật heartbeat cho stage dài.

#### Scenario: Không tạo task vô hạn

- **WHEN** người dùng yêu cầu nhiều candidate hoặc nhiều final version
- **THEN** hệ thống SHALL áp dụng giới hạn số lượng và bounded concurrency
- **AND** hệ thống SHALL không làm nghẽn các workflow AI/media khác

#### Scenario: Theo dõi tiến trình

- **WHEN** pipeline đang chạy
- **THEN** UI SHALL hiển thị các bước `Đang nghiên cứu sâu`, `Đang tạo các hướng kịch bản`, `Đang chấm điểm`, `Đang tổng hợp phiên bản` và `Đã sẵn sàng cấu hình Video AI`
- **AND** backend SHALL cập nhật heartbeat đủ thường xuyên để không đánh dấu stale giả

