## 1. Schema và Migration

- [x] 1.1 Rà `VideoProject`, `VideoShot`, `VideoShotPrompt`, migration AI Video hiện có và chọn phương án lưu JSON/Text cuối cùng cho creative direction.
- [x] 1.2 Thêm nullable fields project-level cho retention map và sound design plan, hoặc một field `creative_direction_json` nếu chọn gộp.
- [x] 1.3 Thêm nullable fields shot-level cho retention metadata, transition pack và sound design metadata.
- [x] 1.4 Thêm nullable fields prompt-level cho retention notes, transition notes và sound design notes nếu không gộp vào `quality_check`.
- [x] 1.5 Thêm migration SQLite idempotent trong `_migrate_ai_video_assistant` và đảm bảo project cũ load được khi các field mới rỗng.
- [x] 1.6 Cập nhật Pydantic response/update models cho project, shot và prompt để API trả được creative direction metadata.
- [x] 1.7 Cập nhật stale helpers để thay đổi creative direction có thể đánh stale prompt, package và render output.

## 2. Planning Schemas và Normalization

- [x] 2.1 Thêm Pydantic models cho `RetentionDirectionPlan`, retention beat, pattern interrupt, drop-off risk và payoff plan.
- [x] 2.2 Thêm Pydantic models cho `TransitionPackPlan` gồm type, trigger, timing, edit reason, transition SFX và continuity risk.
- [x] 2.3 Thêm Pydantic models cho `SoundDesignPlan` gồm music mood, energy curve, ambience, sound cues, silence drops và mixing notes.
- [x] 2.4 Mở rộng `StoryDevelopmentPlan` hoặc thêm bước creative direction riêng để Codex trả retention map và sound design project-level.
- [x] 2.5 Mở rộng `ShotPlan` với retention role, open loop, visual surprise, cut reason, transition pack và shot-level sound design.
- [x] 2.6 Mở rộng `VideoPromptPlan` với retention notes, transition notes và sound design notes.
- [x] 2.7 Thêm normalize alias cho `beat_curve`, `retention_beats`, `viewer_question`, `sfx`, `sound_cues`, `transition`, `edit_transition`, `camera_movement` và các alias phổ biến khác.
- [x] 2.8 Đảm bảo normalize output giữ `target_language` cho narration/speech/subtitle và giữ review/explanation tiếng Việt riêng.

## 3. Strict Validation và Quality Gate

- [x] 3.1 Thêm validator bắt buộc hook 0-2s, viewer question, beat curve, pattern interrupt, payoff và drop-off risks cho retention map.
- [x] 3.2 Thêm validator transition pack cho mọi shot không phải shot cuối và final hold/payoff cho shot cuối.
- [x] 3.3 Thêm validator sound design bắt buộc mixing notes khi shot có narration hoặc dialogue.
- [x] 3.4 Mở rộng camera variation validation để xét retention role, visual surprise và static span risk.
- [x] 3.5 Thêm retainability quality check với weak hook, repeated camera risk, long static span risk, missing transition risk và audio clutter risk.
- [x] 3.6 Đảm bảo validation fail không xóa artifact cũ, không commit dữ liệu mới và không đánh project/shot/prompt là ready sai.
- [x] 3.7 Cập nhật debug logging để ghi step name, raw field types, normalized field types, validation errors và retry count khi Codex trả sai định dạng.
- [x] 3.8 Cập nhật lỗi tiếng Việt cho invalid JSON, thiếu field bắt buộc, lặp camera quá nhiều và sound cue che narration.

## 4. Story và Creative Direction Flow

- [x] 4.1 Cập nhật prompt story development hoặc thêm bước creative direction sau story để yêu cầu retention map và sound design project-level.
- [x] 4.2 Lưu retention map và sound design plan vào project sau khi toàn bộ schema và quality gate pass.
- [x] 4.3 Đảm bảo story review UI/API có thể đọc bản tiếng Việt của retention map.
- [x] 4.4 Khi source blocks, continuity bible hoặc target duration đổi, đánh stale retention map, shot chưa khóa, prompt, package và render output.
- [x] 4.5 Đảm bảo project phase 2 cũ chưa có creative direction vẫn mở được và có action regenerate phù hợp.

## 5. Shot Breakdown và Regenerate

- [x] 5.1 Cập nhật prompt shot breakdown để mỗi shot/segment có retention role, open loop, visual surprise và cut reason.
- [x] 5.2 Cập nhật prompt shot breakdown để mỗi shot/segment có transition pack và sound design cue theo timeline.
- [x] 5.3 Lưu retention, transition và sound design metadata vào shot rows sau validation.
- [x] 5.4 Cập nhật regenerate shot để tạo lại metadata mới cho shot chưa khóa và giữ nguyên metadata của shot đã khóa.
- [x] 5.5 Cập nhật update shot API để thay đổi transition hoặc sound design đánh stale prompt/package/render nhưng không bắt tạo lại voice/subtitle nếu narration không đổi.
- [x] 5.6 Đảm bảo segment 10s có ít nhất một pattern interrupt hoặc visual surprise và transition rõ sang segment kế tiếp.
- [x] 5.7 Đảm bảo shot cuối có final hold, payoff frame, CTA hoặc kết thúc âm thanh thay vì transition sang shot không tồn tại.

## 6. Prompt Video, Download và Package

- [x] 6.1 Cập nhật prompt video generation để kế thừa retention notes, transition pack và sound design notes từ shot.
- [x] 6.2 Đảm bảo field prompt gốc không trộn bản giải thích tiếng Việt hoặc review text tiếng Việt.
- [x] 6.3 Cập nhật `prompt_explanation_vi` để giải thích visual, camera, transition, sound cue, retention purpose và ngôn ngữ người xem.
- [x] 6.4 Mở rộng negative prompt để tránh các lỗi visual/audio-caption làm giảm retention như flicker, camera shake bất thường, watermark, subtitle sai và extra people.
- [x] 6.5 Cập nhật prompt download text với section `Retention`, `Chuyển cảnh`, `Âm thanh/SFX`, `Prompt gốc`, `Negative prompt` và `Bản giải thích tiếng Việt`.
- [x] 6.6 Cập nhật package ZIP để xuất retention map, creative direction summary, shot list có transition pack và sound design cues.
- [x] 6.7 Cập nhật package readiness hoặc warnings cho project thiếu creative direction mà không crash project cũ.

## 7. Render Metadata và Readiness

- [x] 7.1 Cập nhật render timeline manifest để include retention role, transition pack và sound design cue theo shot.
- [x] 7.2 Cập nhật render readiness để hiển thị warning khi sound design chỉ là metadata và chưa có asset SFX/BGM được mix thật.
- [x] 7.3 Đảm bảo thay đổi creative direction đánh stale render output nhưng không xóa MP4 completed cũ.
- [x] 7.4 Đảm bảo render MP4 hiện tại vẫn hoạt động khi creative direction field rỗng.
- [x] 7.5 Ghi rõ trong manifest hoặc debug rằng SFX/BGM là chỉ dẫn dựng nếu chưa có audio asset.

## 8. Frontend UI

- [x] 8.1 Kiểm tra `app/package.json` trước khi import icon/motion/UI dependency mới và ưu tiên dependency hiện có.
- [x] 8.2 Cập nhật API types/client cho creative direction fields trên project, shot và prompt.
- [x] 8.3 Hiển thị retention map trong story review bằng tiếng Việt, gồm hook, curiosity gap, beat curve, pattern interrupts và payoff.
- [x] 8.4 Hiển thị badge hoặc panel theo shot cho retention role, visual surprise, transition type, transition SFX và sound cues.
- [x] 8.5 Hiển thị checklist retainability quality bằng tiếng Việt cho weak hook, repeated camera, static span, missing transition và audio clutter.
- [x] 8.6 Thêm trạng thái thiếu creative direction cho project cũ kèm action tạo lại story/shot/prompt phù hợp.
- [x] 8.7 Giữ UI app bằng tiếng Việt, không làm thay đổi ngôn ngữ video đã chọn bởi `target_language`.
- [x] 8.8 Đảm bảo layout responsive không overlap text, không dùng `h-screen`, không thêm hero/landing và không biến màn hình thành timeline editor phức tạp.

## 9. Tests và Verification

- [x] 9.1 Thêm backend migration tests cho các field creative direction mới và project cũ không có field.
- [x] 9.2 Thêm tests cho normalize alias retention, transition, sound design và camera movement từ output Codex.
- [x] 9.3 Thêm tests cho Codex trả markdown/prose/JSON sai định dạng: không commit artifact mới, giữ artifact cũ và trả lỗi tiếng Việt.
- [x] 9.4 Thêm tests cho Codex trả thiếu field bắt buộc: fail validation, log validation errors và không đánh ready sai.
- [x] 9.5 Thêm tests cho retention map theo `target_duration_seconds`, gồm hook 0-2s và beat không vượt thời lượng mục tiêu.
- [x] 9.6 Thêm tests cho shot breakdown có retention role, cut reason, transition pack và sound design cue.
- [x] 9.7 Thêm tests cho locked shot không bị regenerate creative direction metadata.
- [x] 9.8 Thêm tests cho retainability quality gate weak hook, repeated camera, long static span và audio clutter.
- [x] 9.9 Thêm tests cho prompt video không trộn tiếng Việt vào prompt gốc nhưng có `prompt_explanation_vi` đầy đủ.
- [x] 9.10 Thêm tests cho package export có retention map, transition pack và sound design cues.
- [x] 9.11 Thêm tests cho render manifest include creative direction metadata và render vẫn hoạt động khi metadata rỗng.
- [x] 9.12 Chạy focused backend tests AI Video, migration tests và package/render tests liên quan.
- [x] 9.13 Chạy frontend typecheck/build phù hợp với repo và kiểm tra manual UI AI Video phase 2 cho project mới và project cũ.

## 10. Documentation

- [x] 10.1 Cập nhật docs AI Video để giải thích retention map, transition pack và sound design plan.
- [x] 10.2 Ghi rõ SFX/BGM trong change này là chỉ dẫn dựng nếu chưa có audio asset thật được mix vào MP4.
- [x] 10.3 Cập nhật changelog hoặc release notes nếu repo yêu cầu ghi nhận thay đổi user-facing.
