## MODIFIED Requirements

### Requirement: Kiểm tra readiness trước khi render MP4
Hệ thống SHALL cung cấp checklist readiness riêng cho render MP4 để chỉ rõ project đã đủ clip, voice, subtitle và runtime hay chưa.

Yêu cầu về giọng đọc SHALL phụ thuộc mức âm thanh đang chọn. Ở mức chỉ dùng tiếng gốc, checklist SHALL NOT đòi giọng đọc hoàn tất cho shot có narration, vì mức đó không dùng giọng đọc.

#### Scenario: Project đủ điều kiện render
- **WHEN** project phase 2 có shot hợp lệ, mỗi shot có clip active sẵn sàng, mọi shot có narration đã có voice completed, subtitle đã completed nếu người dùng bật phụ đề, và FFmpeg/FFprobe sẵn sàng
- **THEN** render readiness trả về `ready = true` cùng danh sách reason rỗng

#### Scenario: Thiếu clip theo shot
- **WHEN** một hoặc nhiều shot chưa có clip active sẵn sàng
- **THEN** render readiness trả về `ready = false`, liệt kê `shot_id` còn thiếu và hiển thị reason tiếng Việt theo từng shot hoặc nhóm shot

#### Scenario: Thiếu voice bắt buộc
- **WHEN** một shot có narration nhưng voice chưa completed hoặc thiếu `audio_path` hoặc thiếu `audio_duration`, và mức âm thanh đang là chỉ dùng giọng đọc hoặc kết hợp
- **THEN** render readiness trả về `ready = false` và chỉ rõ shot còn thiếu giọng đọc

#### Scenario: Mức chỉ dùng tiếng gốc không đòi giọng đọc
- **WHEN** mọi shot đều có narration và chưa có giọng đọc, mỗi shot có clip active sẵn sàng đọc được thời lượng, và mức âm thanh đang là chỉ dùng tiếng gốc
- **THEN** render readiness trả về `ready = true` và không liệt kê reason nào về giọng đọc hay thời lượng render

#### Scenario: Thiếu subtitle khi bật burn-in subtitle
- **WHEN** người dùng chọn render có phụ đề burn-in nhưng project chưa có subtitle completed
- **THEN** render readiness trả về `ready = false` và yêu cầu tạo phụ đề trước khi render

#### Scenario: Shot không lời dùng duration dự kiến
- **WHEN** một shot không có narration nhưng có `duration_seconds` hợp lệ
- **THEN** render readiness coi shot đó đủ timer và không yêu cầu voice cho shot đó

#### Scenario: Shot thiếu timer
- **WHEN** một shot không có narration và cũng không có `duration_seconds` hợp lệ
- **THEN** render readiness trả về `ready = false` và chỉ rõ shot thiếu thời lượng render

#### Scenario: Mức chỉ dùng tiếng gốc mà shot không có nguồn thời lượng nào
- **WHEN** mức âm thanh đang là chỉ dùng tiếng gốc và một shot vừa không đọc được thời lượng clip vừa không có `duration_seconds` hợp lệ
- **THEN** render readiness trả về `ready = false` và chỉ rõ shot thiếu thời lượng render

### Requirement: Tạo timeline duration từ voice thật
Hệ thống SHALL dùng thời lượng thật của voice theo shot làm nguồn timer chính cho video timeline.

Ở mức chỉ dùng tiếng gốc, nguồn timer của shot có narration SHALL là thời lượng clip active, và SHALL quay về `duration_seconds` của shot khi không đọc được thời lượng clip. Timeline manifest SHALL giữ đủ mọi shot có nguồn thời lượng hợp lệ, SHALL NOT bỏ shot chỉ vì shot đó chưa có giọng đọc.

#### Scenario: Shot có narration
- **WHEN** shot có narration và voice completed
- **THEN** duration render của shot bằng `audio_duration` thật của voice đã tạo

#### Scenario: Shot không có narration
- **WHEN** shot không có narration và có `duration_seconds` hợp lệ
- **THEN** duration render của shot bằng `duration_seconds`

#### Scenario: Shot có narration ở mức chỉ dùng tiếng gốc
- **WHEN** shot có narration, chưa có giọng đọc, clip active đọc được thời lượng, và mức âm thanh đang là chỉ dùng tiếng gốc
- **THEN** duration render của shot bằng thời lượng clip active

#### Scenario: Mức chỉ dùng tiếng gốc mà clip không đọc được thời lượng
- **WHEN** mức âm thanh đang là chỉ dùng tiếng gốc, clip active không đọc được thời lượng, và shot có `duration_seconds` hợp lệ
- **THEN** duration render của shot bằng `duration_seconds`

#### Scenario: Timeline giữ đủ shot ở mức chỉ dùng tiếng gốc
- **WHEN** mọi shot đều có narration và chưa có giọng đọc, và hệ thống tạo timeline manifest ở mức chỉ dùng tiếng gốc
- **THEN** timeline manifest chứa đủ số shot của project, không thiếu shot nào

#### Scenario: Tính start/end timeline theo shot_order
- **WHEN** hệ thống tạo timeline manifest để render
- **THEN** mỗi shot có `start_seconds` và `end_seconds` được cộng dồn theo `shot_order` tăng dần, không tạo gap mặc định giữa các shot

#### Scenario: Subtitle khớp cùng timeline
- **WHEN** project có subtitle cue đã tạo từ voice duration thật
- **THEN** render timeline sử dụng cùng trục thời gian với subtitle để phụ đề không lệch voice trong MP4 cuối

