## ADDED Requirements

### Requirement: Dự án tiếng Việt dùng Veo-native speech

Hệ thống SHALL dùng audio do Veo tạo trực tiếp cho shot có lời khi `target_language = vi`, và SHALL không yêu cầu hoặc overlay Voicebox TTS cho cùng shot.

#### Scenario: Tiếng Việt không có voice profile

- **GIVEN** project phase 2 có `target_language = vi`
- **AND** các shot có narration và prompt completed
- **WHEN** auto-run tạo clip, subtitle và render
- **THEN** workflow không bị chặn vì thiếu `voice_profile_id`
- **AND** clip Veo có audio được dùng làm speech audio chính

#### Scenario: Tiếng Anh giữ luồng hiện tại

- **GIVEN** project có `target_language = en`
- **WHEN** workflow tạo voice và render
- **THEN** hệ thống vẫn yêu cầu Voicebox TTS completed
- **AND** audio gốc của clip không thay thế TTS

### Requirement: Mỗi shot có speech cues theo nhân vật và bối cảnh

Hệ thống SHALL lưu speech cues có speaker, exact text, voice description, delivery, emotion, context và lip-sync requirement.

#### Scenario: Nhân vật Series có hồ sơ giọng

- **GIVEN** visible character trỏ tới SeriesCharacterProfile có `speech_style`
- **WHEN** hệ thống tạo context thoại Veo
- **THEN** prompt nêu tên nhân vật, speech style, personality liên quan, hành động/biểu cảm và bối cảnh shot
- **AND** không sửa canon profile bằng cảm xúc tạm thời của shot

#### Scenario: Planner thiếu speech cues

- **GIVEN** shot có narration nhưng output planner không có speech cues
- **WHEN** backend normalize output
- **THEN** backend tạo cue fallback từ narration, dialogue mode và visible character phù hợp
- **AND** workflow không mất câu thoại

### Requirement: Prompt Veo tiếng Việt giữ visual prompt và thêm spoken dialogue

Hệ thống SHALL giữ provider-safe visual prompt hiện tại và nối thêm section spoken dialogue cho tiếng Việt sau bước compaction.

#### Scenario: Gửi prompt tiếng Việt

- **GIVEN** project `target_language = vi`
- **WHEN** orchestrator gửi prompt shot sang Veo/Flow
- **THEN** prompt chứa exact quoted Vietnamese dialogue, character voice profile và scene context
- **AND** prompt không chứa lệnh cấm spoken audio
- **AND** prompt vẫn cấm subtitle, caption và text overlay

#### Scenario: Gửi prompt tiếng Anh

- **GIVEN** project `target_language = en`
- **WHEN** orchestrator gửi prompt shot sang Veo/Flow
- **THEN** narration chỉ là context hình ảnh
- **AND** prompt tiếp tục cấm spoken audio như trước

### Requirement: Readiness yêu cầu audio stream của clip Veo tiếng Việt

Hệ thống SHALL coi active provider clip audio là voice dependency của project tiếng Việt.

#### Scenario: Clip tiếng Việt có audio

- **GIVEN** shot có narration, active clip ready, `has_audio = true` và duration hợp lệ
- **WHEN** tính render readiness
- **THEN** shot không bị đánh dấu thiếu TTS voice

#### Scenario: Clip tiếng Việt không có audio

- **GIVEN** shot có narration và active clip ready nhưng `has_audio = false`
- **WHEN** tính render readiness
- **THEN** readiness fail với lý do tiếng Việt yêu cầu tạo lại clip Veo có lời thoại

### Requirement: Render dùng đúng một nguồn speech

Hệ thống SHALL build mỗi audio segment từ đúng nguồn speech hiệu lực và SHALL không mix Veo speech với TTS của cùng shot.

#### Scenario: Render project tiếng Việt

- **WHEN** render một shot có narration trong project tiếng Việt
- **THEN** FFmpeg extract audio từ active clip, trim/apad theo timeline và dùng audio đó trong final mux

#### Scenario: Render project tiếng Anh

- **WHEN** render một shot có narration trong project tiếng Anh
- **THEN** FFmpeg dùng `shot.audio_path` như hiện tại

### Requirement: Subtitle và package nhận biết Veo-native speech

Hệ thống SHALL tạo subtitle/package tiếng Việt mà không yêu cầu file TTS riêng.

#### Scenario: Tạo subtitle tiếng Việt sau khi clip sẵn sàng

- **WHEN** shot tiếng Việt có clip audio ready
- **THEN** subtitle text lấy từ speech cues hoặc narration và timing dùng duration clip

#### Scenario: Đóng gói project tiếng Việt

- **WHEN** package readiness được tính
- **THEN** provider clip audio hợp lệ thỏa dependency speech
- **AND** manifest ghi rõ speech source là Veo-native

