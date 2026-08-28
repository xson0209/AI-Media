## ADDED Requirements

### Requirement: Mapping bộ nội dung đăng phải deterministic và strict
Hệ thống SHALL dùng một lớp mapping deterministic để chuyển structured output Codex thành schema canonical của bộ nội dung đăng video trước khi ghi database.

#### Scenario: Output đầy đủ ba nền tảng
- **WHEN** request yêu cầu tạo toàn bộ bộ nội dung đăng
- **THEN** output canonical SHALL có target_language và đúng ba key youtube, tiktok, facebook
- **AND** mỗi platform SHALL có đúng các field bắt buộc title, description, hashtags và thumbnail_prompt

#### Scenario: Output tạo lại một nền tảng
- **WHEN** request chỉ yêu cầu tạo lại một platform
- **THEN** mapping SHALL chỉ chấp nhận platform được yêu cầu hoặc trích đúng platform đó từ payload đầy đủ
- **AND** mapping MUST NOT ghi đè hai platform không được yêu cầu

#### Scenario: Thiếu platform
- **WHEN** request tạo toàn bộ nhưng output thiếu YouTube, TikTok hoặc Facebook
- **THEN** validation SHALL thất bại
- **AND** hệ thống MUST NOT suy đoán hoặc sao chép một platform khác để lấp dữ liệu thiếu

#### Scenario: Platform không được hỗ trợ
- **WHEN** output dùng messenger, instagram hoặc platform key khác thay cho một key bắt buộc
- **THEN** mapping SHALL từ chối output với error code có thể debug
- **AND** hệ thống MUST NOT ánh xạ mơ hồ platform đó thành Facebook

### Requirement: Mapping validate kiểu dữ liệu và nội dung bắt buộc
Hệ thống SHALL validate kiểu dữ liệu, giá trị rỗng, giới hạn nền tảng và cấu trúc hashtag trước khi coi output Codex là hợp lệ.

#### Scenario: Field chuỗi bị thiếu hoặc sai type
- **WHEN** title, description hoặc thumbnail_prompt bị thiếu, null, là object hoặc là array
- **THEN** mapping SHALL từ chối output
- **AND** hệ thống MUST NOT ép object thành chuỗi bằng serialization ngầm

#### Scenario: Hashtag sai type
- **WHEN** hashtags không phải danh sách chuỗi hoặc chứa phần tử không phải chuỗi
- **THEN** mapping SHALL từ chối output hoặc normalize chỉ khi alias đó được hỗ trợ deterministic
- **AND** hệ thống MUST NOT lưu object hashtag hoặc chuỗi JSON làm hashtag hiển thị

#### Scenario: Normalize hashtag hợp lệ
- **WHEN** hashtag là chuỗi hợp lệ nhưng thiếu dấu #, có khoảng trắng thừa hoặc trùng nhau
- **THEN** mapper MAY trim, thêm dấu # và loại trùng theo quy tắc deterministic
- **AND** thứ tự hashtag đầu tiên MUST được giữ ổn định

#### Scenario: Field rỗng sau normalize
- **WHEN** một field bắt buộc trở thành rỗng sau trim hoặc normalize
- **THEN** validation SHALL thất bại
- **AND** artifact MUST NOT được đánh dấu completed

#### Scenario: Vượt giới hạn profile nền tảng
- **WHEN** title, description hoặc hashtags vượt giới hạn đang cấu hình cho platform
- **THEN** mapping SHALL từ chối hoặc dùng bước repair có validation lại
- **AND** hệ thống MUST NOT cắt chuỗi âm thầm theo cách làm mất ý nghĩa hoặc cắt giữa hashtag

#### Scenario: Target language mâu thuẫn
- **WHEN** payload khai báo target_language khác với project
- **THEN** mapping SHALL từ chối payload
- **AND** hệ thống MUST NOT thay đổi project.target_language dựa trên output Codex

### Requirement: Ghi bộ nội dung đăng phải atomic
Hệ thống SHALL validate toàn bộ phạm vi được yêu cầu trước khi thay thế dữ liệu hợp lệ hiện có và MUST NOT ghi partial publishing metadata.

#### Scenario: Tạo toàn bộ nhưng một platform invalid
- **WHEN** YouTube và TikTok hợp lệ nhưng Facebook invalid trong request tạo toàn bộ
- **THEN** hệ thống SHALL từ chối toàn bộ payload mới
- **AND** artifact ba platform hợp lệ trước đó, nếu có, MUST được giữ nguyên

#### Scenario: Tạo lần đầu thất bại
- **WHEN** project chưa có artifact cũ và output tạo toàn bộ không hợp lệ
- **THEN** hệ thống MAY lưu trạng thái lỗi và failure metadata đã redaction
- **AND** hệ thống MUST NOT lưu một artifact completed chỉ có một hoặc hai platform

#### Scenario: Tạo lại một platform invalid
- **WHEN** request tạo lại riêng YouTube nhưng output YouTube mới invalid
- **THEN** YouTube cũ SHALL được giữ nguyên
- **AND** TikTok cùng Facebook MUST NOT thay đổi

#### Scenario: Ghi thành công
- **WHEN** toàn bộ phạm vi output yêu cầu vượt qua mapping và validation
- **THEN** hệ thống SHALL ghi dữ liệu trong một transaction hoặc trình tự atomic tương đương
- **AND** chỉ sau khi commit thành công hệ thống mới SHALL cập nhật revision, input_fingerprint, status = "completed" và stale = false

### Requirement: Retry Codex không làm dữ liệu mất đồng bộ
Hệ thống SHALL cho phép retry output invalid nhưng chỉ ghi attempt đã vượt qua mapping và validation đầy đủ.

#### Scenario: Attempt đầu invalid, attempt sau valid
- **WHEN** attempt đầu thiếu field hoặc sai schema nhưng attempt retry trả output hợp lệ
- **THEN** hệ thống SHALL chỉ ghi output của attempt hợp lệ
- **AND** revision MUST chỉ tăng một lần cho lần ghi thành công

#### Scenario: Tất cả attempt đều invalid
- **WHEN** mọi attempt đều thất bại mapping hoặc validation
- **THEN** hệ thống SHALL trả lỗi có error code và request id
- **AND** dữ liệu hợp lệ cũ MUST NOT bị xóa hoặc ghi đè

#### Scenario: Retry sau khi auto-run thất bại
- **WHEN** auto-run retry bước generate_publishing_metadata
- **THEN** mapper SHALL dùng input project mới nhất và phạm vi platform cần retry
- **AND** mapper MUST NOT dùng payload invalid cũ làm nguồn sự thật

### Requirement: Mapping error đủ debug nhưng không lộ nội dung dài
Hệ thống SHALL ghi lỗi mapping bộ nội dung đăng với thông tin đủ xác định platform và field sai, nhưng MUST NOT persist toàn bộ nội dung xuất bản trong technical details.

#### Scenario: Mapping fail tại một field
- **WHEN** mapping thất bại tại facebook.thumbnail_prompt
- **THEN** debug metadata SHALL có request id, project id, platform, field, rule validation và error code
- **AND** debug metadata MUST NOT chứa toàn bộ prompt thumbnail hoặc source project dài

#### Scenario: Redaction dữ liệu nội dung
- **WHEN** hệ thống ghi technical details cho title, description, hashtag hoặc thumbnail prompt
- **THEN** hệ thống SHALL chỉ lưu length, count, field path, hash hoặc preview đã rút gọn khi cần
- **AND** hệ thống MUST NOT ghi secret, full source, full narration hoặc full prompt vào log lỗi
