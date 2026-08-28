## 1. Giai đoạn A — Gate thoại (chặn thiệt hại đang tiếp diễn)

- [ ] 1.1 Thêm kiểm tra vào `_quality_check()` (`video_phase2.py:3553-3577`): shot có `speech_cues_json` hoặc `english_narration` không rỗng mà provider content không chứa thoại → `needs_review`.
- [ ] 1.2 Chặn Copy/Download cho shot `needs_review` vì thiếu thoại; trả lý do tiếng Việt kèm số shot.
- [x] 1.3 Thêm endpoint/script audit liệt kê shot có cue nhưng prompt thiếu thoại, theo project.
- [ ] 1.4 Chạy audit trên 30 project Cartoon, xác nhận đúng 24 shot và 7 shot đã có clip.
- [ ] 1.5 Test gate: shot có cue + prompt thiếu thoại → chặn; shot không cue → không chặn; shot đủ thoại → pass.

## 2. Giai đoạn B — Shared prompt/audio builder

- [ ] 2.1 Sửa instruction planner: bỏ mâu thuẫn `video_phase2.py:2688` vs `:3795`; field `prompt` chỉ mô tả hình ảnh, cấm viết lời thoại.
- [x] 2.2 Tạo `build_provider_prompt(visual, speech_mode, cues, negative, continuity)` trả `provider_prompt`, `negative_prompt`, `audio_contract`, `input_fingerprint`.
- [x] 2.3 Implement audio contract `veo_narration`: exact line, off-screen speaker, voice/delivery/emotion/pronunciation, timing, nói một lần, cấm lời thừa.
- [x] 2.4 Implement `veo_dialogue`: visible speaker, identity/wardrobe continuity, exact line, lip-sync, cấm đổi speaker/paraphrase.
- [x] 2.5 Implement `voicebox_co_context`: giữ lời làm ngữ cảnh canh nhịp nhưng cấm Veo phát ra tiếng nói/lip-sync.
- [x] 2.6 Implement `voicebox_khong_context`: không đưa lời vào prompt, cấm mọi spoken audio.
- [x] 2.7 Implement `none`: cấm mọi speech/dialogue/voiceover; ambience/SFX chỉ khi policy cho phép.
- [x] 2.8 Compose provider content **lúc đọc** cho Copy, Download, prompt pack và provider automation; không lưu cột `provider_ready_prompt`.
- [x] 2.9 Xoá `FLOW_PROVIDER_POST_RENDER_CUE_REPLACEMENTS[2]` (`video_clip_generation.py:138-140`) và `_strip_provider_spoken_audio_blockers` (`:262-272`).
- [x] 2.10 Thêm `pronunciation_notes` vào `VideoShotSpeechCue` (`backend/models.py:469-485`); giữ tương thích cue cũ.
- [x] 2.11 Thêm word-budget theo thời lượng; vượt ngưỡng trả lỗi tiếng Việt yêu cầu rút ngắn/chia shot, không tự cắt câu.
- [ ] 2.12 Ghép negative prompt bằng khối `NEGATIVE PROMPT`/`Avoid:` khi provider không có ô riêng.
- [ ] 2.13 Spike đối chiếu word-budget (2,5–3,0 từ/giây) với timing TTS tiếng Việt thật trước khi khóa ngưỡng.

## 3. Giai đoạn C — Override nguồn lời năm mode

- [x] 3.1 Thêm cột nullable `video_projects.speech_source` vào `project_column_defaults` (`migrations.py:~1104`) và `video_shots.speech_source_override` vào `shot_column_defaults` (`:1140`).
- [x] 3.2 Sửa `uses_veo_native_speech()` (`video_speech.py:34-39`) đọc override trước; `NULL` giữ `speech_source_for_language`.
- [x] 3.3 Tạo resolver shot override → project override → legacy; trả cả `speech_mode` và `effective_speech_source`.
- [x] 3.4 Sửa ba chỗ gọi `speech_source_for_language` trực tiếp (`video_packages.py:284,328,411`) để đọc override.
- [ ] 3.5 Implement derive `dialogue_mode` và `clip_audio_mode` từ `speech_mode`; không cho set độc lập.
- [ ] 3.6 Refactor `build_veo_native_speech_section()` nhận explicit source/cue thay vì suy từ ngôn ngữ.
- [ ] 3.7 Thêm `speech_source` vào danh sách field làm stale prompt (`video_phase2.py:3517`).
- [ ] 3.8 API: PATCH project/shot nhận `speech_mode`; validate năm giá trị, lỗi tiếng Việt.
- [ ] 3.9 UI dropdown nguồn lời mức project và override mức shot cho `/ai-video`; hiển thị mode hiệu lực.
- [ ] 3.10 Migration chạy được trên DB mới, DB legacy và chạy lặp; row `NULL` fallback đúng.

## 4. Giai đoạn D — Route `/news-video` parity đầy đủ

- [x] 4.1 Tạo `app/src/components/NewsVideo/NewsVideo.tsx`, đăng ký route `/news-video` trong `router.tsx` theo pattern hiện có (import trực tiếp, không lazy).
- [x] 4.2 Thêm `/news-video` vào `isWideWorkspace` (`router.tsx:83-89`) và mục Sidebar “Video tin tức”.
- [x] 4.3 Tạo `backend/routes/news_video.py` prefix `/news-video`, `route_class=video_errors.AIVideoRoute`; đăng ký trong `backend/routes/__init__.py`.
- [x] 4.4 Tạo bảng `news_video_workflows` (1 dòng/project, FK `video_projects.id`) cho `visual_format`, `source_note`, `default_speech_source`.
- [ ] 4.5 Dùng nguyên `STEP_ORDER` (`video_auto_runs.py:73-91`) và `material_target` (`:59-62`) cho auto-run News; không tạo stepper riêng.
- [x] 4.6 CRUD project/shot và `POST /projects/{id}/plan` với input tin tức, 9:16, thời lượng shot; response/error tiếng Việt.
- [x] 4.7 `POST /projects/{id}/prompts`, `GET /prompt-pack`, `GET /shots/{shot_id}/prompt` dùng cùng builder giai đoạn B.
- [ ] 4.8 Facade upload clip, probe metadata, speech-review và voice/TTS; mọi thao tác nhận `shot_id` explicit.
- [ ] 4.9 Readiness theo effective source; native cần audio + approved, Voicebox cần TTS completed, none không cần speech.
- [ ] 4.10 Tái dùng `AIVideoRenderPanel.tsx` để **dựng MP4 tại chỗ** ở `/news-video`; truyền `effective_speech_source` vào render manifest.
- [ ] 4.11 Xác nhận panel render mang theo đủ **xoá logo/watermark** (`settings.watermark_cleanup`, chọn backend, trạng thái worker, cảnh báo model chưa cache) và **tải MP4 về**; không viết lại panel.
- [ ] 4.12 Hiển thị tiến trình bước xoá watermark rõ ràng, kèm cảnh báo lần đầu phải tải model, để người dùng không tưởng treo.
- [ ] 4.13 Tái dùng `AIVideoPublishingMetadataPanel.tsx` cho bước hoàn thiện.
- [ ] 4.14 Bước “Nguồn tin & chủ đề”: bài/transcript, ghi chú nguồn, `visual_format`, 9:16, thời lượng shot.
- [ ] 4.15 Nhận URL làm **ghi chú nguồn**, sanitize scheme; helper text nói rõ hệ thống KHÔNG tự đọc bài và người dùng phải dán nội dung.
- [ ] 4.16 Bước “Shot & âm thanh”: default mode + override năm mode theo shot, helper audio policy, word-budget warning.
- [ ] 4.17 Bước “Prompt Veo 3”: hiển thị riêng visual/audio/negative/provider content, Copy từng shot, Copy đủ điều kiện, tải pack UTF-8.
- [ ] 4.18 Bước upload clip: chọn shot explicit, filename `news_<slug>_s01_v1.mp4`, probe duration/aspect/audio, mapping review.
- [ ] 4.19 Editorial gate: source note/narration/disclosure/`asset_mode` tối thiểu; cô lập prompt injection trong input.
- [ ] 4.20 Set `language` tường minh cùng `target_language="vi"` khi tạo News project.
- [ ] 4.21 Dịch toàn bộ label/helper/error/toast/empty state sang tiếng Việt; không tuyên bố Veo chính xác tuyệt đối.

## 5. Kiểm thử và QA

- [ ] 5.1 Unit test resolver: default/override project/override shot/legacy fallback.
- [ ] 5.2 Test derive `dialogue_mode` và `clip_audio_mode` từ năm mode; tổ hợp vô nghĩa không biểu diễn được.
- [ ] 5.3 Contract snapshot test năm provider content: native có exact speech; `co_context` có lời nhưng cấm đọc; `khong_context`/`none` không có lời; negative prompt luôn có.
- [ ] 5.4 Test gate thoại trên fixture: shot có cue mà prompt thiếu thoại → chặn; shot không cue → không chặn.
- [ ] 5.5 Test không double voice: Voicebox mute clip, native không tạo TTS, none không yêu cầu audio.
- [ ] 5.6 Test word-budget, một speaker/một line, alias `text_vi`/`visible_presenter`, `pronunciation_notes`.
- [ ] 5.7 Test stale/readiness khi đổi `speech_mode`, exact line, visual prompt, upload hoặc audio review.
- [ ] 5.8 Test manifest ghi đúng nguồn lời sau khi sửa `video_packages.py:284,328,411`.
- [ ] 5.9 Regression `/ai-video`, `/video-inspiration`, `/product-video` và provider automation khi override `NULL`; xác nhận `test_veo_native_vietnamese_speech.py:122-126` vẫn pass.
- [ ] 5.10 Regression provider automation sau khi xoá regex `:138-140` cho cả EN và VI.
- [ ] 5.11 Test API validation, project/shot scoping, idempotency, probe, filename mapping và không lộ secret.
- [ ] 5.12 Xác nhận prompt cũ (sinh trước change) vẫn đọc/copy được, không crash; không yêu cầu chúng đạt gate mới.
- [ ] 5.13 Chạy backend tests, frontend typecheck/lint/build và `openspec validate --strict --no-interactive`.
- [ ] 5.14 Browser QA `/news-video` ở 375/390px và 1280/1440px; kiểm keyboard copy/upload.
- [ ] 5.15 Manual round-trip bảy bước: dán nội dung → sinh prompt → Copy S01 → dán Veo 3 → tải `news_<slug>_s01_v1.mp4` → upload đúng shot → chọn nguồn lời → **dựng MP4 có xoá logo** → tải MP4 về.

## 6. Deferred phase 2 (ghi nhận, không chặn)

- **Crawler tự đọc URL bài viết.** MVP chỉ lưu URL làm ghi chú nguồn; người dùng phải dán nội dung.
- Mode thứ sáu `hon_hop` (Voicebox lời dẫn + Veo thoại nhân vật cùng shot). **Tiên quyết:** chứng minh `CLIP_AUDIO_MODE_BED` (`video_rendering.py:2429`) chạy được trên render thật, và nới guard `clip_audio_bed_decision` (`:3016-3018`) mà không gây comb-filter. Cần routing mức cue thay vì mức shot.
- STT đối chiếu phát âm để phát hiện clip đọc sai/thiếu lời — cách duy nhất tự động hóa được, vì probe âm lượng và `has_audio` đều không phát hiện được.
- Claim ledger/audit revision đầy đủ, corroboration độc lập.
- Bulk upload nhiều file, compositor HyperFrames riêng, xuất bản mạng xã hội.
- **Migrate prompt cũ** (24 shot thiếu thoại, 7 clip đã mất lời) nếu sau này cần dùng lại 30 project cartoon.
