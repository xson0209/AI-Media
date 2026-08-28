## Context

Pipeline hiện tại probe được `has_audio` của clip provider nhưng normalize video bằng `-an`, tạo audio timeline từ `shot.audio_path` của TTS và yêu cầu TTS completed trước subtitle/render. Provider sanitizer còn nối câu cấm spoken audio. Vì vậy chỉ thêm câu thoại vào prompt không đủ.

Series đã có `SeriesCharacterProfile.speech_style`, personality, episode cast và `visible_characters`; các dữ liệu này phải được tái sử dụng thay vì tạo hệ voice-canon mới.

## Decisions

### 1. Nguồn speech được resolve từ target language

- `target_language = vi`: `veo_native`.
- Các target language khác: `voicebox_tts` như hiện tại.

Quy tắc này là product rule của feature. Helper chung phải được dùng bởi prompt, auto-run, subtitle, readiness, render và package để tránh mỗi module tự suy diễn khác nhau.

### 2. Shot có speech cues có cấu trúc

`video_shots.speech_cues_json` lưu danh sách:

```text
speaker_name
character_profile_id
speaker_role
text
voice_description
delivery
emotion
context
start_seconds
end_seconds
lip_sync_required
```

`english_narration` tiếp tục là field legacy/canonical narration text để không phá API cũ. Nếu planner không trả speech cues, backend tạo một cue fallback từ narration và dialogue mode.

### 3. Voice description tái sử dụng canon nhân vật

Với character profile:

- `speech_style` là nguồn chính cho màu giọng, nhịp, độ tuổi biểu cảm và cách phát âm.
- `personality`, role và fixed traits bổ sung cách delivery.
- visible-character action/expression cùng shot description tạo context hiện tại.

Không ghi ngược cảm xúc tạm thời của shot vào profile canon. Prompt chỉ hợp nhất canon voice + context tạm thời.

### 4. Visual prompt giữ nguyên, native speech là section nối thêm

Provider-safe visual prompt tiếp tục qua sanitizer/compaction hiện có. Với tiếng Việt, adapter nối thêm một section riêng sau visual prompt:

```text
Vietnamese spoken dialogue — generate as audible clip audio
Character voice profiles
Scene and emotional context
Exact quoted lines
No English speech, no extra voices, no paraphrase, no subtitles/text overlays
```

Section này được nối sau compaction nên không bị mất. Nhánh tiếng Anh giữ nguyên context-only note và lệnh cấm spoken audio.

### 5. Render vẫn tách video và audio

Không bỏ kiến trúc intermediate video không audio. Với tiếng Việt, audio builder extract audio stream từ active provider clip, trim/apad theo duration rồi concat vào base audio timeline. Với tiếng Anh, builder tiếp tục dùng TTS. Cách này tránh codec mismatch và không tạo double voice.

### 6. Duration và subtitle

- Tiếng Việt có narration: duration ưu tiên active clip duration, fallback shot duration chỉ ở bước planning; readiness yêu cầu clip có duration và audio.
- Tiếng Anh có narration: duration tiếp tục dùng `shot.audio_duration`.
- Subtitle tiếng Việt tạo từ speech cue text (fallback narration) theo clip duration. Word-level STT alignment nằm ngoài MVP; UI không khẳng định transcript đã được xác minh tuyệt đối.

### 7. Backward compatibility

- Shot cũ không có `speech_cues_json` vẫn chạy bằng cue fallback.
- Dự án tiếng Anh, tests TTS và render hiện tại không đổi hành vi.
- `mute_clip_audio` vẫn mặc định true ở settings nhưng nguồn audio hiệu lực do speech source quyết định; không expose generic mixing có thể gây chồng giọng trong change này.

## Risks

- Veo có thể không đọc đúng tuyệt đối hoặc đổi chất giọng giữa clip: prompt khóa voice profile/context và UI yêu cầu nghe review.
- Clip Veo có ambience lẫn speech: enhanced SFX/BGM phải coi provider audio là base track và duck asset bổ sung.
- Planner có thể thiếu speaker mapping: backend fallback rõ ràng, không làm fail toàn bộ shot generation.
- Câu quá dài so với clip: prompt nêu exact duration và backend giữ narration length constraints hiện có.

