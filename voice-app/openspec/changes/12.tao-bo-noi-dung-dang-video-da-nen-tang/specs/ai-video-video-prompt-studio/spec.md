## ADDED Requirements

### Requirement: Prompt Studio hiển thị bộ nội dung đăng ở vị trí có thể copy
Hệ thống SHALL hiển thị khu Nội dung đăng video ngay sau khu Prompt video và trước khu Voice và phụ đề trong AI Video Assistant.

#### Scenario: Hiển thị đúng vị trí workflow
- **WHEN** người dùng mở project đã có prompt video
- **THEN** UI SHALL hiển thị thứ tự Prompt video, Nội dung đăng video, Voice và phụ đề
- **AND** người dùng MUST NOT cần mở debug panel hoặc file export để tìm tiêu đề video

#### Scenario: Chọn nền tảng bằng tab
- **WHEN** bộ nội dung đăng có dữ liệu
- **THEN** UI SHALL hiển thị ba tab YouTube, TikTok và Facebook
- **AND** tab đang chọn SHALL chỉ hiển thị nội dung của nền tảng tương ứng

#### Scenario: Mỗi nền tảng có bốn ô riêng
- **WHEN** người dùng chọn một tab nền tảng
- **THEN** UI SHALL hiển thị bốn ô độc lập có nhãn Tiêu đề video, Mô tả, Hashtag và Prompt tạo ảnh thumbnail
- **AND** UI MUST NOT gộp bốn giá trị thành một ô duy nhất

#### Scenario: Tổng cộng mười hai đầu ra có thể truy cập
- **WHEN** bộ nội dung của cả ba nền tảng hoàn tất
- **THEN** người dùng SHALL truy cập được đúng bốn trường cho mỗi nền tảng
- **AND** việc chuyển tab MUST NOT làm mất hoặc ghi đè dữ liệu của tab khác

### Requirement: Người dùng copy riêng từng trường
Hệ thống SHALL cung cấp nút copy riêng cho từng ô tiêu đề, mô tả, hashtag và prompt thumbnail.

#### Scenario: Copy tiêu đề
- **WHEN** người dùng bấm copy tại ô Tiêu đề video
- **THEN** clipboard SHALL nhận đúng tiêu đề đang hiển thị của nền tảng đang chọn
- **AND** clipboard MUST NOT kèm label, mô tả, hashtag hoặc ký tự định dạng ngoài giá trị tiêu đề

#### Scenario: Copy mô tả
- **WHEN** người dùng bấm copy tại ô Mô tả
- **THEN** clipboard SHALL nhận đúng mô tả đang hiển thị, giữ xuống dòng có chủ ý

#### Scenario: Copy hashtag
- **WHEN** người dùng bấm copy tại ô Hashtag
- **THEN** UI SHALL nối danh sách hashtag bằng một khoảng trắng theo thứ tự đã lưu
- **AND** clipboard SHALL nhận chuỗi như "#hashtag1 #hashtag2 #hashtag3"

#### Scenario: Copy prompt thumbnail
- **WHEN** người dùng bấm copy tại ô Prompt tạo ảnh thumbnail
- **THEN** clipboard SHALL nhận đúng prompt thumbnail của nền tảng đang chọn
- **AND** clipboard MUST NOT nhận prompt video của shot hoặc prompt thumbnail của nền tảng khác

#### Scenario: Copy thành công
- **WHEN** clipboard ghi dữ liệu thành công
- **THEN** UI SHALL hiển thị phản hồi ngắn bằng tiếng Việt tại đúng trường vừa copy

#### Scenario: Copy thất bại
- **WHEN** trình duyệt hoặc hệ điều hành từ chối clipboard
- **THEN** UI SHALL hiển thị lỗi inline bằng tiếng Việt
- **AND** nội dung trong ô MUST được giữ để người dùng chọn thủ công

### Requirement: UI hỗ trợ tạo lại và hiển thị trạng thái metadata
Hệ thống SHALL hiển thị trạng thái loading, completed, stale và failed của bộ nội dung đăng, đồng thời cung cấp action tạo lại phù hợp.

#### Scenario: Chưa có bộ nội dung đăng
- **WHEN** project đã có prompt hợp lệ nhưng chưa có publishing metadata
- **THEN** UI SHALL hiển thị action Tạo nội dung đăng video
- **AND** các nút copy SHALL bị vô hiệu hóa cho trường chưa có giá trị

#### Scenario: Đang tạo
- **WHEN** request tạo bộ nội dung đăng đang chạy
- **THEN** UI SHALL hiển thị trạng thái loading ổn định
- **AND** UI MUST ngăn người dùng gửi trùng cùng một request tạo lại

#### Scenario: Tạo lại một nền tảng
- **WHEN** người dùng bấm Tạo lại nền tảng
- **THEN** UI SHALL gửi đúng platform key đang chọn
- **AND** dữ liệu hai tab còn lại MUST được giữ nguyên trong lúc request chạy

#### Scenario: Tạo lại tất cả
- **WHEN** người dùng bấm Tạo lại tất cả
- **THEN** UI SHALL yêu cầu backend tạo lại đủ ba biến thể và refresh artifact sau khi thành công

#### Scenario: Artifact stale
- **WHEN** backend trả bộ nội dung đăng stale
- **THEN** UI SHALL hiển thị cảnh báo rõ rằng nội dung có thể không còn khớp video
- **AND** UI SHALL cung cấp action tạo lại
- **AND** UI MUST NOT trình bày artifact stale như output đã sẵn sàng xuất bản

#### Scenario: Lỗi tạo metadata
- **WHEN** tạo hoặc tạo lại thất bại
- **THEN** UI SHALL giữ nội dung hợp lệ cũ nếu có, hiển thị lỗi inline bằng tiếng Việt và cung cấp action retry

#### Scenario: Responsive không làm mất nút copy
- **WHEN** UI hiển thị trên màn hình mobile hoặc cửa sổ hẹp
- **THEN** label, nội dung và nút copy SHALL xuống dòng hoặc co giãn mà không chồng lấp
- **AND** mọi nút copy MUST vẫn thao tác được

### Requirement: Subtitle phase 2 dùng cùng timeline duration với render
Hệ thống SHALL tính offset phụ đề phase 2 theo cùng thứ tự shot và cùng quy tắc duration với timeline render để shot không lời không làm phụ đề phía sau xuất hiện sớm.

#### Scenario: Shot có narration
- **WHEN** shot có narration và voice completed
- **THEN** cursor subtitle SHALL tăng theo audio_duration hợp lệ của shot đó
- **AND** cue của narration SHALL nằm trong khoảng timeline của shot

#### Scenario: Shot không có narration
- **WHEN** shot không có narration nhưng có duration_seconds hợp lệ
- **THEN** hệ thống SHALL không tạo cue rỗng cho shot đó
- **AND** cursor subtitle MUST tăng thêm duration_seconds trước khi tạo cue cho shot tiếp theo

#### Scenario: Nhiều shot im lặng liên tiếp
- **WHEN** có nhiều shot không narration nằm trước một shot có narration
- **THEN** start time của cue narration tiếp theo SHALL bao gồm tổng duration của mọi shot im lặng trước đó

#### Scenario: Duration timeline bắt buộc bị thiếu
- **WHEN** shot im lặng cần xuất hiện trên timeline nhưng không có duration hợp lệ
- **THEN** hệ thống SHALL trả lỗi validation rõ ràng hoặc dùng đúng duration resolver fallback đã được timeline render xác nhận
- **AND** hệ thống MUST NOT âm thầm coi shot đó có duration bằng không nếu render vẫn dành thời gian cho shot

#### Scenario: Timing dựa trên audio và timeline
- **WHEN** subtitle được tạo
- **THEN** hệ thống SHALL mô tả timing là khớp duration audio và timeline
- **AND** UI MUST NOT tuyên bố có forced alignment từng từ nếu hệ thống chưa tạo word timestamps thực

### Requirement: Tạo lại voice làm stale subtitle cấp project
Hệ thống SHALL đánh dấu cả trạng thái subtitle của shot hoặc scene và artifact subtitle cấp project là stale khi voice hoặc timing nguồn của phụ đề thay đổi.

#### Scenario: Tạo lại voice của một shot
- **WHEN** voice của một shot được enqueue tạo lại
- **THEN** shot.subtitle_status SHALL chuyển stale
- **AND** row subtitle cấp project SHALL chuyển stale
- **AND** package và render output phụ thuộc SHALL được đánh dấu stale theo workflow hiện có

#### Scenario: Tạo lại voice của một scene
- **WHEN** voice của một scene được enqueue tạo lại
- **THEN** scene.subtitle_status SHALL chuyển stale
- **AND** row subtitle cấp project SHALL chuyển stale

#### Scenario: Thay narration hoặc duration
- **WHEN** narration text, audio duration hoặc duration của shot im lặng thay đổi
- **THEN** subtitle cấp project SHALL được đánh dấu stale vì nội dung hoặc offset cue có thể đã thay đổi

#### Scenario: Không tải SRT cũ
- **WHEN** subtitle cấp project đang stale
- **THEN** endpoint download và package readiness MUST từ chối coi file SRT cũ là completed
- **AND** UI SHALL yêu cầu người dùng tạo lại phụ đề

#### Scenario: Tạo lại subtitle thành công
- **WHEN** mọi voice bắt buộc đã completed và hệ thống tạo lại SRT thành công
- **THEN** row subtitle cấp project cùng trạng thái subtitle của các shot hoặc scene liên quan SHALL chuyển completed
- **AND** file tải về SHALL chứa cue theo timeline mới nhất

### Requirement: Voice và subtitle chỉ chạy sau khi nội dung đăng được duyệt trong full workflow
Hệ thống SHALL giữ voice generation và subtitle generation hiện có, nhưng trong full_materials SHALL chỉ chạy chúng sau khi prompt và bộ nội dung đăng đã vượt qua gate tương ứng.

#### Scenario: Review-gated chưa duyệt
- **WHEN** auto-run đang needs_review tại gate prompt và nội dung đăng
- **THEN** UI SHALL giữ khu Voice và phụ đề ở trạng thái chưa chạy
- **AND** hệ thống MUST NOT enqueue voice tự động

#### Scenario: Đã duyệt và voice profile hợp lệ
- **WHEN** người dùng approve gate và project có voice profile hỗ trợ target_language
- **THEN** hệ thống SHALL tạo voice bằng workflow AI Video hiện có, chờ voice terminal rồi mới tạo subtitle

#### Scenario: Voice profile không hỗ trợ ngôn ngữ
- **WHEN** project đã duyệt metadata nhưng voice profile không hỗ trợ target_language
- **THEN** hệ thống SHALL dừng với lỗi tiếng Việt rõ ràng
- **AND** hệ thống MUST NOT tạo subtitle giả hoặc fallback ngầm sang ngôn ngữ khác

#### Scenario: Workflow thủ công cũ vẫn dùng được
- **WHEN** người dùng không chạy auto-run hoặc dùng prompts_only hay publishing_kit
- **THEN** các action voice và subtitle thủ công hiện có SHALL tiếp tục hoạt động theo contract hiện tại
