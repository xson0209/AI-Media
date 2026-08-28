## ADDED Requirements

### Requirement: Năm mode nguồn lời

Hệ thống SHALL cho phép project và từng shot chọn một trong năm giá trị `veo_narration`, `veo_dialogue`, `voicebox_co_context`, `voicebox_khong_context`, `none`. Shot SHALL có override nullable; response SHALL trả cả `speech_mode` và `effective_speech_source`.

#### Scenario: Mặc định an toàn

- **WHEN** người dùng tạo project News Video mà không chọn nguồn lời
- **THEN** hệ thống SHALL dùng `voicebox_khong_context`, ánh xạ canonical `project_audio`, và hiển thị rằng Voicebox sẽ đọc ở hậu kỳ

#### Scenario: Tiếng Việt không tự ép native

- **WHEN** project có `target_language=vi` nhưng người dùng chọn mode Voicebox
- **THEN** hệ thống SHALL giữ mode đã chọn và SHALL NOT áp fallback legacy đổi sang `veo_native`

#### Scenario: Override theo shot

- **WHEN** project mặc định Voicebox nhưng shot presenter chọn `veo_dialogue`
- **THEN** shot SHALL trả `effective_speech_source=veo_native` với `dialogue_mode=character_lines`, các shot khác vẫn dùng Voicebox

#### Scenario: Hai mode Voicebox khác nhau

- **WHEN** shot presenter chọn `voicebox_co_context` và shot b-roll chọn `voicebox_khong_context`
- **THEN** provider content của shot presenter SHALL có lời làm ngữ cảnh canh nhịp nhưng cấm Veo đọc; shot b-roll SHALL không có lời trong prompt

### Requirement: Ánh xạ canonical không phá model hiện tại

Adapter SHALL ánh xạ `veo_narration`/`veo_dialogue` → `veo_native`; `voicebox_co_context`/`voicebox_khong_context`/`none` → `project_audio`. Alias API `text_vi` SHALL normalize về `VideoShotSpeechCue.text`; role `visible_presenter`/`character` SHALL normalize về canonical `visible_character`.

#### Scenario: Chỉ hai canonical value tồn tại

- **WHEN** adapter map mode News sang canonical
- **THEN** giá trị SHALL là `veo_native` hoặc `project_audio`; SHALL NOT giả định tồn tại canonical `none`

#### Scenario: Cue hiện có được giữ

- **WHEN** shot có `speech_cues[].text` và role `visible_character`
- **THEN** News API SHALL trả nội dung tiếng Việt tương đương và SHALL không làm mất cue khi regenerate prompt

#### Scenario: Legacy project không explicit

- **WHEN** project không có row `news_video_workflows` và không có override
- **THEN** resolver SHALL giữ `video_speech.speech_source_for_language` hiện tại và các route cũ SHALL không đổi hành vi

### Requirement: Provider content có audio contract đầy đủ

Hệ thống SHALL sinh provider content mặc định bằng tiếng Việt cho từng shot, gồm visual contract, duration/aspect, continuity, safe area, negative prompt và audio contract. Audio contract SHALL do code sinh từ `speech_cues`. Provider content SHALL được compose lúc đọc; `video_shot_prompts.prompt` SHALL chỉ chứa visual prompt.

#### Scenario: Prompt Veo narration

- **WHEN** effective mode là `veo_narration` và shot có narration
- **THEN** provider content SHALL chứa exact Vietnamese line, speaker ngoài khung hình, voice/delivery/emotion/pronunciation, timing tương đối, yêu cầu nói đúng một lần và cấm paraphrase/dịch/lời thừa/subtitle

#### Scenario: Prompt Veo dialogue

- **WHEN** effective mode là `veo_dialogue`
- **THEN** provider content SHALL nêu visible speaker, identity/wardrobe continuity, exact Vietnamese line, lip-sync và context hành động; MUST cấm đổi speaker, thêm lời hoặc tạo chữ

#### Scenario: Prompt Voicebox có ngữ cảnh

- **WHEN** effective mode là `voicebox_co_context`
- **THEN** provider content SHALL đưa lời làm ngữ cảnh để canh nhịp và diễn xuất, MUST cấm spoken words/narration/voiceover/lip-sync, và SHALL ghi rõ Voicebox đọc hậu kỳ

#### Scenario: Prompt Voicebox không ngữ cảnh

- **WHEN** effective mode là `voicebox_khong_context`
- **THEN** provider content SHALL NOT chứa lời, MUST cấm mọi spoken audio, và SHALL yêu cầu không tự thêm người đang nói

#### Scenario: Prompt không lời

- **WHEN** effective mode là `none`
- **THEN** provider content SHALL cấm mọi speech/dialogue/voiceover và chỉ mô tả ambience/SFX được phép

#### Scenario: Negative prompt ở provider không có ô riêng

- **WHEN** người dùng copy prompt và Veo không cung cấp ô negative prompt
- **THEN** content SHALL có khối `NEGATIVE PROMPT` hoặc tiền tố `Avoid:`, còn response vẫn trả `negative_prompt` riêng

### Requirement: Native speech có exact cue và word-budget

Shot native SHALL có tối đa một speaker và một exact line trong MVP. Cue SHALL lưu `speaker_name`, `speaker_role`, `text`, `voice_description`, `delivery`, `emotion`, `pronunciation_notes`, timing tương đối, `lip_sync_required` và source/claim refs nếu có. `pronunciation_notes` SHALL được thêm mới vào model cue hiện tại.

#### Scenario: Off-screen narration

- **WHEN** shot dùng `veo_narration`
- **THEN** cue SHALL dùng role `offscreen_narrator`, lip-sync false và yêu cầu đọc nguyên văn một lần

#### Scenario: Visible dialogue

- **WHEN** shot dùng `veo_dialogue`
- **THEN** cue SHALL dùng role canonical `visible_character`, lip-sync true và giữ identity/wardrobe continuity

#### Scenario: Role ngoài tập hợp cho phép

- **WHEN** API nhận role không thuộc `visible_character`, `offscreen_narrator`, `episode_guest`, `unknown`
- **THEN** hệ thống SHALL normalize về giá trị canonical hoặc trả lỗi validation tiếng Việt

#### Scenario: Câu vượt thời lượng

- **WHEN** số từ vượt word-budget cấu hình cho 4/6/8/10 giây
- **THEN** API SHALL trả lỗi tiếng Việt yêu cầu rút ngắn/chia shot, SHALL NOT tự cắt câu hoặc cho phép paraphrase

#### Scenario: Thiếu cue native

- **WHEN** planner trả narration nhưng không trả speech cue
- **THEN** adapter SHALL tạo cue `Narrator` từ narration, đánh dấu `review_required` nếu thiếu voice/context và SHALL không làm mất text

### Requirement: Không chồng speech và readiness theo mode

Mỗi shot SHALL có đúng một speech source chính trong MVP. `dialogue_mode` và `clip_audio_mode` SHALL được suy ra từ `speech_mode`. Thay đổi mode/line/audio contract SHALL làm stale prompt và artifact phụ thuộc.

#### Scenario: Voicebox mute audio Veo mặc định

- **WHEN** shot Voicebox upload clip có audio
- **THEN** readiness/render SHALL mặc định drop toàn bộ audio clip, dùng Voicebox TTS làm speech duy nhất; giữ ambience chỉ khi người dùng bật explicit và đã review

#### Scenario: Native không tạo TTS

- **WHEN** shot native có clip audio
- **THEN** action TTS SHALL bị vô hiệu hóa/trả lỗi nghiệp vụ, native clip là speech chính

#### Scenario: Native thiếu audio hoặc chưa duyệt

- **WHEN** clip native thiếu audio hoặc speech review chưa `approved`
- **THEN** readiness SHALL fail/giữ `review_required`, SHALL không fallback im lặng sang TTS

#### Scenario: Veo lỡ đọc ở mode có ngữ cảnh

- **WHEN** shot `voicebox_co_context` upload clip mà probe thấy có audio
- **THEN** hệ thống SHALL cảnh báo khả năng Veo đã đọc lời, mặc định drop audio và SHALL NOT coi mức âm là bằng chứng có/không có lời

#### Scenario: None

- **WHEN** shot `none` có clip hình hợp lệ
- **THEN** readiness SHALL không yêu cầu TTS, speech cue hoặc audio stream; nếu clip có lời, mặc định drop audio và cảnh báo

### Requirement: Subtitle/render dùng nguồn lời hiệu lực

Native subtitle/timeline SHALL dùng cue và duration clip sau khi người dùng duyệt; Voicebox dùng narration và audio duration Voicebox; none không tạo cue speech. Exact cue SHALL được hiển thị là transcript dự kiến, không phải bảo đảm Veo đọc đúng.

#### Scenario: Render Voicebox

- **WHEN** tất cả shot Voicebox có audio completed và clip hình hợp lệ
- **THEN** render SHALL ghép Voicebox TTS, không để speech audio Veo chồng lên

#### Scenario: Render native

- **WHEN** native shot có audio và review approved
- **THEN** render SHALL dùng audio clip Veo và SHALL không tạo/ghép TTS
