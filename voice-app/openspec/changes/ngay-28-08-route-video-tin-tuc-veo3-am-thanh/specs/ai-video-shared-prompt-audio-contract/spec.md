## ADDED Requirements

### Requirement: Gate chặn prompt thiếu thoại

Hệ thống SHALL chặn phát hành prompt khi shot có dữ liệu speech nhưng provider content không chứa thoại tương ứng. Gate SHALL hoạt động ở tầng prompt, không dựa vào probe audio của clip.

#### Scenario: Shot có cue nhưng prompt thiếu thoại

- **WHEN** shot có `speech_cues_json` không rỗng hoặc `english_narration` không rỗng, mà provider content không chứa thoại
- **THEN** hệ thống SHALL đặt `needs_review`, SHALL chặn Copy/Download và SHALL nêu shot cùng lý do bằng tiếng Việt

#### Scenario: Shot không có dữ liệu speech

- **WHEN** shot không có cue và không có narration
- **THEN** gate SHALL không chặn và shot SHALL đi tiếp bình thường

#### Scenario: Không dùng probe audio làm bằng chứng

- **WHEN** clip đã upload có audio stream và mức âm bình thường
- **THEN** hệ thống SHALL NOT coi đó là bằng chứng clip có lời, vì nhạc/ambience/SFX làm mức âm không phân biệt được

### Requirement: Provider content do code sinh, không phó mặc planner

Audio contract SHALL được sinh bằng code từ `speech_cues`, không phụ thuộc việc planner có viết thoại vào prompt hay không. Planner SHALL bị cấm viết lời thoại vào field `prompt`; `prompt` SHALL chỉ mô tả hình ảnh.

Yêu cầu này áp cho prompt sinh **từ sau change này**. Prompt sinh trước đó SHALL giữ nguyên hành vi đọc/copy hiện tại và SHALL NOT bị migrate tự động.

#### Scenario: Prompt cũ vẫn đọc được

- **WHEN** người dùng mở hoặc copy prompt sinh trước change này
- **THEN** hệ thống SHALL trả nội dung như hiện tại và SHALL NOT lỗi; hệ thống SHALL NOT tự sinh lại hoặc tự strip thoại khỏi prompt đó

#### Scenario: Instruction planner không mâu thuẫn

- **WHEN** hệ thống sinh instruction cho planner
- **THEN** instruction SHALL nói rõ `prompt` chỉ mô tả hình ảnh và thoại nằm ở `speech_cues`, SHALL NOT vừa yêu cầu viết thoại vừa nói voice tạo ở bước sau

#### Scenario: Cùng builder cho mọi consumer

- **WHEN** Copy, Download, prompt pack hoặc provider automation cần provider content
- **THEN** tất cả SHALL gọi cùng một builder và SHALL nhận cùng audio contract cho cùng input

#### Scenario: Compose lúc đọc

- **WHEN** người dùng sửa speech cue hoặc đổi nguồn lời
- **THEN** provider content SHALL được compose lại lúc đọc và SHALL NOT tồn tại bản provider prompt đã lưu bị lệch

### Requirement: Không viết lại prose của prompt đã lưu

Hệ thống SHALL NOT dùng regex sửa văn xuôi prompt đã lưu để thêm hoặc bỏ chỉ dẫn thoại. Audio contract SHALL là khối do code sinh.

#### Scenario: Bỏ regex xoá voiceover

- **WHEN** provider automation chuẩn bị prompt cho project không phải tiếng Việt
- **THEN** hệ thống SHALL NOT xoá câu voiceover khỏi prompt rồi nối lệnh cấm spoken audio, và SHALL NOT phát hành prompt vừa cấm spoken audio vừa trích lời nhân vật

#### Scenario: Prompt lưu chỉ cấm chữ trên hình

- **WHEN** hệ thống nối quy tắc loại trừ vào prompt lưu
- **THEN** quy tắc SHALL chỉ cấm subtitle/caption/text overlay/logo/watermark và SHALL NOT cấm spoken audio

### Requirement: Override nguồn lời tách khỏi ngôn ngữ

Hệ thống SHALL cho phép chọn nguồn lời ở mức project và override ở mức shot, độc lập với `target_language`. Giá trị `NULL` SHALL giữ nguyên hành vi legacy.

#### Scenario: Project tiếng Anh cho Veo tự đọc

- **WHEN** project `target_language=en` chọn `veo_narration` hoặc `veo_dialogue`
- **THEN** hệ thống SHALL đưa exact line vào provider content, SHALL NOT tạo TTS và SHALL dùng audio clip làm speech chính

#### Scenario: Project tiếng Việt dùng voice project

- **WHEN** project `target_language=vi` chọn `voicebox_khong_context`
- **THEN** hệ thống SHALL dùng TTS Voicebox, SHALL mute audio clip mặc định và SHALL NOT ép sang `veo_native`

#### Scenario: Override NULL giữ hành vi cũ

- **WHEN** project và shot đều không có override
- **THEN** resolver SHALL dùng `speech_source_for_language` hiện tại và các route cũ SHALL không đổi hành vi

#### Scenario: Manifest ghi đúng nguồn lời

- **WHEN** hệ thống ghi package/render manifest cho project có override
- **THEN** manifest SHALL ghi nguồn lời đã resolve, SHALL NOT ghi giá trị suy từ ngôn ngữ

### Requirement: Dẫn xuất mức âm và dialogue mode

`speech_mode` SHALL là input duy nhất; `dialogue_mode` và `clip_audio_mode` SHALL được suy ra từ nó. Hệ thống SHALL NOT cho phép set ba field độc lập.

#### Scenario: Không biểu diễn được double voice

- **WHEN** nguồn lời là Voicebox
- **THEN** provider content SHALL cấm Veo phát ra lời nói và mức âm clip SHALL được suy ra là `drop`; tổ hợp vừa dùng TTS vừa yêu cầu Veo đọc SHALL NOT biểu diễn được

#### Scenario: Không đổi default toàn cục

- **WHEN** hệ thống suy `clip_audio_mode` cho project có nguồn lời tường minh
- **THEN** giá trị mặc định `clip_audio_mode` của project không dùng nguồn lời tường minh SHALL giữ nguyên
