## Why

AI Video hiện tạo narration tiếng Việt nhưng luồng Veo/Flow cố ý coi narration là context hình ảnh, cấm spoken audio và render MP4 bằng voice TTS riêng. Trong cấu hình thực tế, voice local ổn định chủ yếu phục vụ tiếng Anh; dự án tiếng Việt cần cho Veo tạo trực tiếp lời thoại trong clip để giữ được video có tiếng mà không phụ thuộc voice profile tiếng Việt thử nghiệm.

## What Changes

- Dự án AI Video có `target_language = vi` dùng Veo-native speech/audio cho các shot có lời; dự án ngôn ngữ khác giữ nguyên luồng Voicebox TTS hiện tại.
- Mỗi shot lưu `speech_cues` có người nói, câu nói chính xác, mô tả giọng, cảm xúc, delivery, bối cảnh và yêu cầu lip-sync.
- Với Series, mô tả giọng lấy từ `SeriesCharacterProfile.speech_style`, personality và episode cast; bối cảnh lấy từ nội dung/hành động/biểu cảm của shot. Episode-only guest dùng speech style trong project character flow.
- Prompt video hình ảnh hiện tại vẫn được giữ; adapter Veo chỉ nối thêm section Vietnamese spoken dialogue và không còn chèn lệnh cấm spoken audio cho dự án tiếng Việt.
- Clip Veo tiếng Việt phải có audio stream. Render tách audio từ clip làm audio segment chính, không tạo hoặc overlay TTS cho cùng shot.
- Subtitle tiếng Việt dùng text trong speech cues/narration và duration của clip Veo; tiếng Anh tiếp tục dùng duration của TTS.
- Readiness, auto-run, package và trạng thái stale nhận biết nguồn speech theo ngôn ngữ để không chặn dự án tiếng Việt vì thiếu voice profile.
- UI giải thích rõ tiếng Việt dùng giọng trực tiếp từ Veo 3 và hiển thị speech cues/giọng nhân vật để người dùng kiểm tra.

## Capabilities

### New Capabilities

- `ai-video-veo-native-vietnamese-speech`: Tạo prompt thoại tiếng Việt theo nhân vật, giữ audio Veo trong render và điều phối downstream không cần TTS.

### Modified Capabilities

- `ai-video-purpose-dialogue-workflow`: dialogue mode tạo speech cues có speaker/context.
- `ai-video-video-prompt-studio`: prompt tiếng Việt bổ sung exact spoken dialogue nhưng giữ nguyên visual prompt.
- `ai-video-veo-chrome-clip-generation`: provider prompt cho phép spoken audio khi target language là tiếng Việt.
- `ai-video-timeline-render`: audio timeline dùng audio clip Veo cho tiếng Việt và TTS cho ngôn ngữ khác.

## Impact

- Database: thêm `video_shots.speech_cues_json`.
- Backend: shot planning/normalization, character context, Veo prompt sanitizer, clip import/readiness, subtitle, render, auto-run và package.
- Frontend: API type cho speech cues và thông báo nguồn giọng tiếng Việt.
- Tests: migration/model, prompt provider, character voice context, audio readiness/render command, subtitle và auto-run.

