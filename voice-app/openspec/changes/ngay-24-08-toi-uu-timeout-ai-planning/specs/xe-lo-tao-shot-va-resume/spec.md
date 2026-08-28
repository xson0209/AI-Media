## ADDED Requirements

### Requirement: Tạo shot theo lô thay vì một lời gọi duy nhất

`generate_shots` SHALL chia số segment cần tạo thành nhiều lô và gọi Codex một lần cho mỗi lô, thay vì yêu cầu toàn bộ segment trong một lời gọi. Kích thước lô SHALL theo cùng khuôn với `VIDEO_PROMPT_BATCH_SIZE` đã dùng cho prompt pack.

#### Scenario: Video dài cần nhiều segment

- **WHEN** một project cần tạo 40 segment mới
- **THEN** hệ thống SHALL thực hiện `ceil(40 / batch_size)` lời gọi Codex tuần tự
- **AND** mỗi lời gọi SHALL chỉ yêu cầu số shot của đúng lô đó

#### Scenario: Số segment nhỏ hơn một lô

- **WHEN** số segment cần tạo nhỏ hơn hoặc bằng `batch_size`
- **THEN** hệ thống SHALL thực hiện đúng một lời gọi, giữ hành vi tương đương trước change

#### Scenario: Thứ tự shot liên tục qua các lô

- **WHEN** các lô lần lượt hoàn tất
- **THEN** `shot_order` của toàn bộ shot SHALL liên tục và không trùng, tiếp nối đúng sau số segment đã khóa

### Requirement: Commit sau mỗi lô

Hệ thống SHALL ghi bền vững kết quả của mỗi lô ngay khi lô đó hoàn tất, không được tích lũy toàn bộ trong bộ nhớ rồi commit một lần ở cuối. Đây là điều kiện bắt buộc đi kèm việc xé lô.

#### Scenario: Lô giữa chuỗi thất bại

- **WHEN** lô thứ 7 trong 10 lô thất bại vì timeout
- **THEN** kết quả của 6 lô đầu SHALL đã được ghi bền vững và còn nguyên sau khi request trả lỗi
- **AND** hệ thống SHALL báo rõ đã hoàn tất bao nhiêu trên tổng bao nhiêu lô

#### Scenario: Toàn bộ lô hoàn tất

- **WHEN** tất cả các lô hoàn tất
- **THEN** trạng thái project SHALL chuyển sang `shots_ready` và các artifact phụ thuộc SHALL được đánh dấu stale đúng như hành vi hiện tại

### Requirement: Tiến độ lô lưu riêng, không dùng cờ locked

Tiến độ lô SHALL được lưu ở một trường riêng, KHÔNG được suy ra từ cột `locked` của shot. `locked` là lock do người dùng bấm, và shot chưa khóa bị xóa khi vào lại bước tạo shot, nên không thể dùng làm mốc tiến độ.

#### Scenario: Vào lại sau khi một phần lô đã xong

- **WHEN** người dùng gọi lại `generate_shots` sau khi 6 trong 10 lô đã xong, với cùng bộ input
- **THEN** hệ thống SHALL giữ lại shot của 6 lô đó dù chúng chưa được người dùng khóa
- **AND** SHALL chỉ tạo 4 lô còn thiếu

#### Scenario: Shot do người dùng khóa vẫn được tôn trọng

- **WHEN** project có shot người dùng đã khóa
- **THEN** hành vi khóa hiện tại SHALL không đổi, và các lô mới SHALL tiếp nối sau số segment đã khóa

### Requirement: Resume theo khóa idempotency

Mỗi lô SHALL có một khóa idempotency ổn định tính từ input của lô, được lưu bền vững và tra cứu trước khi gọi Codex, để lần chạy lại bỏ qua các lô đã hoàn tất.

#### Scenario: Chạy lại với input không đổi

- **WHEN** người dùng chạy lại một bước đã hoàn tất một phần và input của các lô đã xong không đổi
- **THEN** hệ thống SHALL bỏ qua các lô đó mà không gọi Codex
- **AND** SHALL ghi log cho biết lô nào được bỏ qua nhờ resume

#### Scenario: Input thay đổi làm tiến độ cũ không còn hợp lệ

- **WHEN** input đầu vào (kịch bản, thời lượng mục tiêu, cấu hình segment) đã thay đổi so với lần chạy dở
- **THEN** hệ thống SHALL coi tiến độ cũ là không hợp lệ và tạo lại từ đầu
- **AND** SHALL không trộn kết quả của hai lần chạy khác input

### Requirement: Continuity carry-over giữa các lô

Mỗi lô sau lô đầu SHALL nhận được ngữ cảnh kết thúc của lô liền trước, để việc xé lô không đánh đổi timeout bằng lỗi mạch truyện. Một lời gọi duy nhất đang cho sự mạch lạc toàn cục miễn phí, xé lô làm mất tính chất đó.

#### Scenario: Lô thứ hai trở đi

- **WHEN** hệ thống gọi Codex cho lô thứ N với N lớn hơn 1
- **THEN** prompt SHALL chứa ngữ cảnh kết thúc của lô N-1, tối thiểu gồm `transition_to_next`, mô tả nhân vật và bối cảnh của shot cuối
- **AND** prompt SHALL nêu rõ dải `shot_order` mà lô này phải sinh trên tổng số segment toàn video

#### Scenario: Continuity bible vẫn áp dụng cho mọi lô

- **WHEN** project có continuity bible
- **THEN** mọi lô SHALL nhận cùng ràng buộc continuity bible đó

### Requirement: Kích thước lô prompt pack phải nhỏ hơn hiện tại

Kích thước lô của `generate_video_prompt_pack` SHALL nhỏ hơn giá trị 5 hiện tại, vì đã có bằng chứng đo được rằng lô 5 shot vẫn timeout ở 600 giây. Giá trị này SHALL là một hằng riêng, độc lập với kích thước lô của shot breakdown.

#### Scenario: Project 21 segment

- **WHEN** `generate_video_prompt_pack` chạy trên project có 21 shot
- **THEN** số lời gọi Codex SHALL nhiều hơn 5 lô
- **AND** mỗi lời gọi SHALL yêu cầu ít hơn 5 prompt

#### Scenario: Kích thước lô độc lập với shot breakdown

- **WHEN** cần điều chỉnh kích thước lô của prompt pack
- **THEN** thay đổi đó SHALL không làm đổi kích thước lô của shot breakdown

### Requirement: Prompt pack không được mất kết quả lô đã xong

`generate_video_prompt_pack` SHALL commit theo từng lô và tra khóa idempotency đã lưu, thay vì tích lũy trong bộ nhớ và commit một lần ở cuối.

#### Scenario: Prompt pack thất bại giữa chuỗi lô

- **WHEN** `generate_video_prompt_pack` thất bại ở một lô giữa chuỗi
- **THEN** prompt của các lô trước đó SHALL còn nguyên sau khi request trả lỗi

#### Scenario: Chạy lại prompt pack sau thất bại

- **WHEN** người dùng chạy lại `generate_video_prompt_pack` với các shot không đổi
- **THEN** hệ thống SHALL chỉ gọi Codex cho các lô còn thiếu prompt

### Requirement: Xé lô không được nâng concurrency

Các lô SHALL chạy tuần tự trong phạm vi một request. Change này SHALL không nâng giới hạn concurrency của planning pool đang chốt ở 3.

#### Scenario: Nhiều lô trong một request

- **WHEN** một request cần chạy nhiều lô
- **THEN** các lô SHALL chạy lần lượt và SHALL không chiếm thêm slot của planning pool ngoài slot mà request đó đã giữ
