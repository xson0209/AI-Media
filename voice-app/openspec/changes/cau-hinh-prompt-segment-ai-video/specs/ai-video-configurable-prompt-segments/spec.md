## ADDED Requirements

### Requirement: Cấu hình prompt segment theo project
Hệ thống SHALL cho phép project AI Video phase 2 cấu hình số lượng prompt segment, thời gian mỗi prompt segment và số cảnh nhỏ trong mỗi prompt segment.

#### Scenario: Tạo project với cấu hình 6 prompt 10 giây 3 cảnh nhỏ
- **WHEN** người dùng tạo project phase 2 với `prompt_segment_count = 6`, `prompt_segment_duration_seconds = 10` và `micro_scenes_per_prompt = 3`
- **THEN** hệ thống lưu cấu hình đó, tính `target_duration_seconds = 60` và tính tổng số cảnh nhỏ là 18

#### Scenario: UI hiển thị preview cấu trúc video
- **WHEN** người dùng nhập số prompt, thời gian mỗi prompt và số cảnh nhỏ mỗi prompt trong AI Video Assistant
- **THEN** UI hiển thị preview tổng thời lượng và tổng số cảnh nhỏ trước khi tạo project

#### Scenario: Không cho nhập thời lượng mâu thuẫn với cấu hình prompt
- **WHEN** người dùng đang dùng cấu hình prompt segment trực tiếp
- **THEN** hệ thống SHALL tính thời lượng video từ `prompt_segment_count * prompt_segment_duration_seconds` thay vì nhận một thời lượng độc lập có thể mâu thuẫn

#### Scenario: Chặn cấu hình không hợp lệ
- **WHEN** người dùng nhập số prompt, thời gian mỗi prompt hoặc số cảnh nhỏ ngoài giới hạn hợp lệ
- **THEN** hệ thống từ chối tạo project và hiển thị lỗi tiếng Việt nói rõ field cần sửa

### Requirement: Tạo đúng số prompt và cảnh nhỏ theo cấu hình
Hệ thống SHALL tạo segment breakdown theo đúng số prompt segment và đúng số cảnh nhỏ trong mỗi prompt segment đã cấu hình.

#### Scenario: Segment breakdown tạo đúng 6 prompt và 18 cảnh nhỏ
- **WHEN** AI tạo segment breakdown cho project có `prompt_segment_count = 6`, `prompt_segment_duration_seconds = 10` và `micro_scenes_per_prompt = 3`
- **THEN** hệ thống lưu đúng 6 prompt segment theo thứ tự và mỗi prompt segment có đúng 3 cảnh nhỏ

#### Scenario: Timeline của cảnh nhỏ khớp thời lượng prompt
- **WHEN** một prompt segment có `prompt_segment_duration_seconds = 8` và `micro_scenes_per_prompt = 4`
- **THEN** hệ thống tạo hoặc normalize timeline cảnh nhỏ phủ đủ 0-8 giây, ví dụ 0-2s, 2-4s, 4-6s và 6-8s

#### Scenario: Prompt gốc chứa timeline cảnh nhỏ
- **WHEN** hệ thống tạo prompt video cho một prompt segment đã có cảnh nhỏ có cấu trúc
- **THEN** prompt gốc dùng để copy SHALL chứa timeline theo số cảnh nhỏ và thời lượng prompt đã cấu hình

#### Scenario: Mô tả tiếng Việt phản ánh đủ cảnh nhỏ
- **WHEN** hệ thống hiển thị prompt segment trong UI
- **THEN** bản tiếng Việt để duyệt SHALL nêu đủ các cảnh nhỏ, mốc thời gian, hành động chính, camera/chuyển cảnh và continuity của segment

### Requirement: Normalize output Codex lệch format nhưng đủ dữ liệu
Hệ thống SHALL normalize các biến thể output phổ biến từ Codex trước khi validate schema, để output đủ dữ liệu hợp lệ không bị lỗi chỉ vì khác tên field hoặc cấu trúc lồng.

#### Scenario: Nhận danh sách segment bằng alias phổ biến
- **WHEN** Codex trả segment breakdown trong field `segments`, `prompt_segments`, `video_segments` hoặc `segment_breakdown` thay vì `shots`
- **THEN** hệ thống normalize thành danh sách prompt segment hợp lệ và tiếp tục lưu dữ liệu

#### Scenario: Output sau normalize có contract chuẩn
- **WHEN** hệ thống normalize output Codex cho shot breakdown thành công
- **THEN** mỗi prompt segment đã normalize SHALL có thứ tự segment, duration, mô tả tiếng Việt, action chính và danh sách `micro_scenes` gồm `order`, `start_seconds`, `end_seconds`, `description_vi`, `visual_action` và `camera_note`

#### Scenario: Nhận cảnh nhỏ bằng alias phổ biến
- **WHEN** Codex trả cảnh nhỏ trong field `micro_scenes`, `microScenes`, `scenes`, `beats`, `timeline` hoặc `timeline_beats`
- **THEN** hệ thống normalize thành danh sách cảnh nhỏ có cấu trúc cho từng prompt segment

#### Scenario: Nhận segment lồng trong scene
- **WHEN** Codex trả output dạng `scenes[].segments` hoặc `scenes[].shots`
- **THEN** hệ thống flatten các segment đó theo thứ tự scene/segment và vẫn tạo đúng số prompt segment theo cấu hình

#### Scenario: Nhận timeline dạng text có mốc thời gian
- **WHEN** Codex không trả mảng cảnh nhỏ nhưng có mô tả text chứa mốc thời gian như `0-3s`, `3-6s`, `6-10s`
- **THEN** hệ thống parse các mốc thời gian đó thành cảnh nhỏ có cấu trúc nếu số lượng khớp `micro_scenes_per_prompt`

#### Scenario: Thiếu mốc thời gian nhưng có đủ mô tả tổng thể
- **WHEN** Codex trả đủ mô tả visual/action/camera cho segment nhưng thiếu mảng cảnh nhỏ và thiếu mốc thời gian rõ ràng
- **THEN** hệ thống chia đều timeline theo `micro_scenes_per_prompt`, tạo cảnh nhỏ có cấu trúc từ mô tả tổng thể và không fail validation chỉ vì thiếu shape mong muốn

#### Scenario: Output thiếu dữ liệu cốt lõi
- **WHEN** Codex output thiếu dữ liệu cốt lõi để tạo prompt segment như mô tả visual/action chính
- **THEN** hệ thống retry hoặc trả lỗi tiếng Việt rõ ràng thay vì lưu segment rỗng hoặc sai cấu hình

### Requirement: Tương thích project cũ
Hệ thống SHALL giữ tương thích với project AI Video phase 2 cũ chưa có cấu hình prompt segment trực tiếp.

#### Scenario: Project cũ chỉ có target duration
- **WHEN** project phase 2 không có `prompt_segment_count` và có `target_duration_seconds`
- **THEN** hệ thống tiếp tục tính số prompt segment bằng logic legacy dựa trên thời lượng mục tiêu và thời lượng prompt mặc định 10 giây

#### Scenario: Project cũ vẫn render trong UI
- **WHEN** người dùng mở project cũ chưa có `micro_scenes_per_prompt`
- **THEN** UI vẫn hiển thị prompt segment hiện có bằng dữ liệu legacy và không yêu cầu cấu hình mới để đọc/copy/download prompt

#### Scenario: Project mới dùng cấu hình mới thay vì legacy hardcode
- **WHEN** project có đủ `prompt_segment_count`, `prompt_segment_duration_seconds` và `micro_scenes_per_prompt`
- **THEN** hệ thống SHALL dùng các field này để tính segment, timeline, prompt text và export thay vì hardcode 10 giây

### Requirement: Đánh stale khi đổi cấu hình prompt segment
Hệ thống SHALL đánh stale các artifact phụ thuộc khi cấu hình prompt segment thay đổi sau khi đã có segment, prompt, voice, subtitle hoặc package.

#### Scenario: Đổi số prompt sau khi đã tạo segment
- **WHEN** người dùng đổi `prompt_segment_count` của project đã có segment breakdown
- **THEN** hệ thống đánh dấu segment/prompt/package liên quan là cần tạo lại hoặc chặn đổi cho đến khi người dùng xác nhận regenerate

#### Scenario: Đổi thời lượng mỗi prompt sau khi đã tạo prompt video
- **WHEN** người dùng đổi `prompt_segment_duration_seconds` của project đã có prompt video
- **THEN** hệ thống đánh dấu prompt video, voice/subtitle timeline và package là stale vì timeline cũ không còn khớp

#### Scenario: Đổi số cảnh nhỏ mỗi prompt sau khi đã có prompt video
- **WHEN** người dùng đổi `micro_scenes_per_prompt` của project đã có prompt video
- **THEN** hệ thống đánh dấu prompt video và package là stale vì timeline cảnh nhỏ trong prompt cần tạo lại
