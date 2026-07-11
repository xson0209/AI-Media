## Context

AI Video phase 2 hiện đã có source blocks, story strategy, continuity bible, detailed script, scene/shot breakdown, prompt video, voice theo shot, subtitle, ZIP package và render MP4 upload-first. Backend đang dùng các Pydantic plan trong `video_phase2.py`, normalize alias từ Codex output, validate schema rồi mới lưu dữ liệu; đây là pattern đúng cần tiếp tục mở rộng.

Điểm yếu hiện tại là creative direction còn nằm rải rác trong prompt tự do: hook, camera variation và transition note đã có, nhưng chưa có retention map, sound design plan, transition pack có cấu trúc hoặc quality gate chuyên kiểm tra khả năng giữ chân người xem. Nếu chỉ thêm câu “make it more cinematic” vào prompt, Codex có thể trả output thiếu field, lặp góc máy, thiếu sound cue hoặc không dùng được trong package/render.

## Goals / Non-Goals

**Goals:**

- Tạo retention map có cấu trúc cho toàn video: hook, curiosity gap, beat curve, pattern interrupt, payoff và drop-off risks.
- Mở rộng shot/segment planning với camera grammar, retention role, cut reason, visual surprise và transition pack.
- Tạo sound design plan cho từng shot/segment và toàn project, gồm music mood, energy curve, ambience, SFX cue, silence drop, impact/riser/whoosh và mixing notes.
- Đưa retention, transition và sound design vào prompt video, bản giải thích tiếng Việt, package/export và render manifest/readiness khi phù hợp.
- Chặn việc lưu artifact khi Codex trả JSON sai định dạng hoặc thiếu field bắt buộc; lỗi phải rõ bằng tiếng Việt và có debug event đủ truy vết.
- Giữ tương thích với project phase 2 hiện có và các change ngôn ngữ video đang in-progress.

**Non-Goals:**

- Không tích hợp provider video trực tiếp như Runway, Kling, Veo, Pika, Luma.
- Không bắt buộc tự tạo hoặc tải thư viện SFX/BGM trong change này.
- Không làm timeline editor nhiều track kéo-thả.
- Không đổi field tương thích `english_narration`; field đó vẫn là narration theo `target_language`.
- Không làm video song ngữ nhiều track audio/subtitle.

## Decisions

### 1. Thêm creative direction artifact có cấu trúc, không nhồi vào prompt text

Tạo các Pydantic plan mới hoặc mở rộng plan hiện có:

- `RetentionDirectionPlan`: project-level hook, viewer question, curiosity gap, beat curve, pattern interrupts, payoff plan, drop-off risks.
- `ShotRetentionPlan`: retention role, open loop, pattern interrupt, visual surprise, cut reason, expected viewer emotion.
- `TransitionPackPlan`: transition type, trigger, timing, edit reason, transition SFX, continuity risk.
- `SoundDesignPlan`: music mood, energy curve, ambience bed, SFX cues, silence drops, mixing notes.
- `RetainabilityQualityCheck`: missing fields, repeated camera risk, long static span risk, weak hook risk, audio clutter risk.

Phương án khác đã cân nhắc: chỉ thêm instruction vào prompt hiện tại. Cách đó ít migration nhưng không test được, không export được có cấu trúc và không giúp UI chỉ rõ thiếu gì. Artifact có schema giúp validate, retry và quality gate rõ hơn.

### 2. Lưu dữ liệu mới bằng nullable JSON/Text theo hướng backward-compatible

Thêm các cột nullable, idempotent migration:

- `video_projects.retention_plan_json` và `video_projects.sound_design_plan_json` hoặc một cột `creative_direction_json` nếu implementation chọn gộp.
- `video_shots.retention_json`, `video_shots.transition_json`, `video_shots.sound_design_json` để giữ metadata theo shot/segment mà không làm bảng phình quá nhiều cột nhỏ.
- `video_shot_prompts.retention_notes`, `video_shot_prompts.transition_notes`, `video_shot_prompts.sound_design_notes` hoặc gộp vào `quality_check` nếu chỉ dùng cho prompt/export.

Phương án khác đã cân nhắc: tạo bảng mới `video_creative_direction_artifacts`. Bảng riêng sạch hơn cho versioning, nhưng change này chủ yếu gắn metadata vào project/shot/prompt hiện có; nullable columns đơn giản hơn và khớp migration SQLite idempotent đang dùng.

### 3. Planning pipeline giữ thứ tự story trước, creative direction trước shot/prompt

Pipeline đề xuất:

```text
source blocks
  -> story strategy + continuity bible + detailed script
  -> retention/sound direction
  -> shot/segment breakdown enriched with retention + transition + sound
  -> video prompt pack enriched with visual/audio/editing notes
  -> voice/subtitle/package/render
```

Implementation có thể gộp retention/sound direction vào `develop_story` để giảm số lần Codex call, nhưng schema/lưu trữ phải tách rõ để regenerate và quality check không phụ thuộc vào text tự do.

Phương án khác đã cân nhắc: tạo retention sau khi đã có shot. Cách đó dễ vá shot hiện có nhưng yếu hơn vì shot breakdown không biết beat curve từ đầu. Retention direction nên được tạo trước để shot kế thừa nhịp dựng.

### 4. Output Codex phải qua normalize và strict validation trước khi commit

Mọi bước mới phải đi qua cùng pattern:

1. Gọi Codex với `output_schema` cụ thể.
2. Parse JSON object bằng loader hiện có; chấp nhận recovery an toàn từ fenced JSON nếu loader hỗ trợ, nhưng không chấp nhận prose không parse được.
3. Normalize alias phổ biến như `retention_beats`, `beat_curve`, `sfx`, `sound_cues`, `transition`, `edit_transition` về schema chính.
4. Validate bằng Pydantic với min/max, enum hoặc pattern cho các field quan trọng.
5. Chạy semantic quality gate, ví dụ hook trong 0-2s, không có static span dài quá ngưỡng, mỗi segment có transition/cut reason, sound cue không che voice.
6. Chỉ sau khi tất cả pass mới xóa artifact cũ hoặc commit artifact mới.

Nếu validation fail, backend MUST log `raw_field_types`, `normalized_field_types`, validation errors và trả lỗi tiếng Việt. Không được lưu một nửa retention/shot/prompt mới.

Phương án khác đã cân nhắc: lưu raw output rồi cho user sửa. Điều này rủi ro vì UI/package/render sẽ đọc dữ liệu thiếu field và lỗi muộn; fail-fast phù hợp hơn.

### 5. Transition và sound design là metadata dựng, không phải bắt buộc render audio thật ngay

Trong phase đầu của change này, sound design cues được xuất cho người dùng/editor và có thể đi vào render manifest. Render MP4 vẫn chỉ mix voice/subtitle/clip như hiện tại nếu chưa có asset SFX/BGM. Nếu sau này có asset library hoặc upload audio cues, cùng schema có thể mở rộng thành track render thật.

Phương án khác đã cân nhắc: làm luôn BGM/SFX mixing trong FFmpeg. Cách đó hấp dẫn nhưng cần asset source, volume automation, licensing, UI upload/chọn âm thanh và test render phức tạp. Metadata trước giúp nâng chất lượng prompt/package ngay và mở đường cho mix thật sau.

### 6. Prompt video vẫn giữ prompt gốc sạch, bản review tiếng Việt tách riêng

Prompt copy chính phải chứa chỉ dẫn visual/editing/sound hữu ích cho tool video, nhưng không trộn bản giải thích tiếng Việt vào field `prompt`. `prompt_explanation_vi` phải giải thích retention, transition và sound cue để người dùng duyệt. Package text có thể chứa section riêng: `Retention`, `Chuyển cảnh`, `Âm thanh/SFX`.

Phương án khác đã cân nhắc: nhúng mọi thứ vào prompt chính. Cách đó dễ copy nhưng gây nhiễu provider và khó tách cho UI/export.

### 7. UI review theo lớp, không biến AI Video Assistant thành timeline editor

Frontend nên thêm các vùng đọc/duyệt gọn:

- Retention map ở project/story review.
- Badge hoặc panel nhỏ theo shot: retention role, transition, sound cue, quality risks.
- Checklist “khả năng giữ chân” cho prompt/package readiness.

Không thêm timeline kéo-thả hoặc waveform trong change này. UI vẫn tiếng Việt, workflow-first và dùng pattern component hiện có.

## Risks / Trade-offs

- Prompt/output dài hơn làm tăng khả năng Codex timeout hoặc invalid JSON -> Giới hạn số beat/cue, dùng schema nhỏ theo list, retry tối đa theo policy hiện có, log validation rõ.
- Metadata âm thanh khiến người dùng tưởng app đã mix SFX thật -> UI/package phải ghi rõ đây là chỉ dẫn sound design nếu chưa có asset audio được render.
- Thêm JSON fields có thể khó query chi tiết -> Đây là metadata theo artifact, không phải filter chính; nếu cần analytics sau này có thể tách bảng.
- Quality gate quá chặt có thể chặn project hợp lệ -> Bắt đầu với gate bắt buộc cho field cốt lõi, các cảnh báo thẩm mỹ có thể là warning trước khi thành hard fail.
- Gộp change này với `ngon-ngu-video-tuy-chon` có thể xung đột prompt wording -> Tất cả narration/speech/subtitle viewer-facing phải dùng `target_language`; review UI và explanation vẫn tiếng Việt.
- Sound cue/SFX quá nhiều có thể che voice -> Sound design schema bắt buộc có mixing notes và quality gate `audio_clutter_risk`.

## Migration Plan

1. Thêm nullable JSON/Text columns bằng migration idempotent trong `_migrate_ai_video_assistant`; project cũ load được với giá trị rỗng.
2. Mở rộng Pydantic response/update models nhưng giữ field cũ không đổi.
3. Mở rộng planning schema/normalizer/validator; không xóa artifact cũ trước khi plan mới validate xong.
4. Đánh stale prompt/package/render output khi retention, transition hoặc sound design của shot thay đổi.
5. Cập nhật package export để thêm file/section creative direction mà không chặn project cũ thiếu dữ liệu.
6. Cập nhật UI đọc field mới nếu có; fallback hiển thị trạng thái “chưa có chỉ dẫn retention/âm thanh” và action regenerate.
7. Rollback an toàn: ẩn UI và bỏ generation field mới; nullable data mới không ảnh hưởng voice/subtitle/render hiện có.

## Open Questions

- Change này có nên hard-fail package khi thiếu sound design cue, hay chỉ warning trong giai đoạn đầu?
- Có cần preset theo thể loại video như education, sports, documentary, ad để chọn camera/sound grammar khác nhau không?
- Có cần cho người dùng upload/chọn BGM/SFX asset ngay sau metadata phase này, hay để thành change render-audio-tracks riêng?
