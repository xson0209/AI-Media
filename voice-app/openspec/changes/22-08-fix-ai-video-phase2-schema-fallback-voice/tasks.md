# Công việc triển khai

## 1. Khóa contract schema strict

- [x] 1.1 Tạo model có cấu trúc cho `related_characters` và cập nhật `StoryScenePlan`.
- [x] 1.2 Tạo model có cấu trúc cho `visible_characters` và cập nhật `MicroScenePlan`/`ShotPlan`.
- [x] 1.3 Tạo model có cấu trúc cho `quality_check` và cập nhật `VideoPromptPlan`.
- [x] 1.4 Rà toàn bộ schema Phase 2 để tìm `dict`, `dict[str, Any]`, object không có `properties` và `$ref` chưa được chuẩn hóa.
- [x] 1.5 Nâng cấp `_strict_response_format_schema()` để từ chối object tự do không có contract thay vì tạo object strict rỗng.
- [x] 1.6 Bổ sung test assert mọi object strict có `properties`, `additionalProperties=false` và `required == properties.keys()`.
- [x] 1.7 Bổ sung regression test cho lỗi `related_characters` và `quality_check` với thông báo provider 400 tương ứng.

## 2. Cải thiện Codex/provider fallback

- [x] 2.1 Lưu provider status, stderr đã redaction và schema context của attempt `--output-schema` trước khi retry.
- [ ] 2.2 Phân biệt audit event của schema fallback, model/config fallback và fallback nội bộ.
- [ ] 2.3 Giữ nguyên `request_id`, `project_id`, `step_name`, attempt và retry reason qua toàn bộ chuỗi retry.
- [ ] 2.4 Đặt budget prompt/source cho story, shot và prompt pack; ghi `source_chars`, `prompt_chars`, `truncated_block_ids`.
- [x] 2.5 Tách prompt pack thành batch nhỏ, giữ stable order, batch index và idempotency key.
- [ ] 2.6 Không retry inline schema vô hạn khi prompt đã vượt budget; chuyển sang fallback nội bộ có cảnh báo rõ.
- [ ] 2.7 Bổ sung test timeout cho cả provider error ban đầu và lỗi cuối sau fallback.

## 3. Tách provenance khỏi nội dung sáng tạo

- [ ] 3.1 Rà source compiler/handoff để tách creative text, provenance, constraints và style notes thành trường riêng.
- [x] 3.2 Sửa `_fallback_source_snippets()` không lấy metadata handoff làm creative snippet.
- [x] 3.3 Thêm bộ lọc phòng thủ cho provenance marker, URL, path, job ID, checksum và artifact reference.
- [x] 3.4 Không dùng `project.topic` nguyên khối làm narration source nếu có metadata handoff.

## 4. Sửa fallback story/shot/prompt theo ngôn ngữ video

- [x] 4.1 Fallback story tạo `english_narration`/narration theo `target_language`, không nối câu tiếng Việt review vào production field.
- [ ] 4.2 Giữ tiếng Việt trong `vietnamese_description`, review và technical details.
- [ ] 4.3 Fallback shot không sao chép mù `scene.dialogue`; phải dùng narration đã validate hoặc tạo cờ `needs_review`.
- [x] 4.4 Bổ sung validator nội dung production chống provenance, URL/path/job ID và metadata handoff.
- [x] 4.5 Bổ sung validator ngôn ngữ nhẹ cho narration; với `target_language=en` phải chặn text tiếng Việt rõ ràng.
- [x] 4.6 Bổ sung test fallback `target_language=en` không tạo narration tiếng Việt/metadata.

## 5. Chặn downstream artifact sai

- [x] 5.1 Gọi validator narration trước `create_shot_narration()` và enqueue auto-run voice.
- [x] 5.2 Ghi event `VIDEO_VOICE_NARRATION_INVALID` với field, marker và shot order đã redaction.
- [x] 5.3 Chuyển shot lỗi sang `needs_review`/`voice_blocked`, không tạo generation.
- [ ] 5.4 Subtitle/package/render readiness phải coi narration invalid là blocking error.
- [ ] 5.5 Bảo đảm sửa narration làm stale generation, audio, subtitle, package và render artifact.
- [ ] 5.6 Thêm test TTS không nhận text provenance và không tạo generation khi language/content invalid.

## 6. Chế độ “Chỉ câu lệnh video” và native audio Veo 3

- [x] 6.1 Xác định rõ contract `material_target=prompts_only`: bỏ TTS/SRT riêng nhưng không bỏ thoại, speech cue hoặc sound design trong prompt Veo.
- [ ] 6.2 Chuẩn hóa field prompt audio gồm dialogue text, speaker, delivery, emotion, context và `lip_sync_required` theo từng câu.
- [x] 6.3 Bắt buộc prompt có khối `SOUND DESIGN` gồm ambience, music, SFX, timing/beat và mixing notes khi shot yêu cầu âm thanh.
- [x] 6.4 Bảo đảm thoại và audio direction dùng đúng `target_language`; không đưa provenance, URL/path/job ID hoặc review text vào production prompt.
- [x] 6.5 Cập nhật prompt builder để nói rõ Veo 3 phải render native audio trong chính clip, phân biệt dialogue on-screen với voice-over off-screen.
- [ ] 6.6 Cập nhật readiness/auto-run để `prompts_only` không chờ `audio_path` hoặc SRT riêng, nhưng chặn prompt thiếu dialogue/audio block bắt buộc.
- [ ] 6.7 Không enqueue TTS/SRT trong `prompts_only`; ghi audit rằng external voice/subtitle đã được bỏ qua có chủ đích.
- [ ] 6.8 Bổ sung regression test cho prompt-only có thoại + SFX và test không tạo generation/audio ngoài.
- [ ] 6.9 Bổ sung regression test cho prompt-only thiếu thoại hoặc sound design phải chuyển `needs_review`.
- [ ] 6.10 Cập nhật nhãn/mô tả UI tiếng Việt để “Chỉ câu lệnh video” nói rõ Veo 3 sẽ tự render thoại + âm thanh trong clip.

## 7. Khôi phục project đã bị ảnh hưởng

- [ ] 7.1 Tạo migration/script idempotent phát hiện narration chứa provenance marker hoặc URL/path metadata.
- [ ] 7.2 Đánh stale/xóa generation/audio sai của project ngày 22-08; không xóa source media gốc.
- [ ] 7.3 Đánh stale subtitle, publishing package và render artifact phụ thuộc narration sai.
- [ ] 7.4 Tạo lại story/shot narration từ creative source đã tách, chờ người dùng duyệt.
- [ ] 7.5 Chỉ enqueue lại voice sau khi narration và target language pass validation.
- [ ] 7.6 Thêm báo cáo repair gồm số shot bị ảnh hưởng, generation bị stale và trạng thái cần người dùng duyệt.

## 8. Kiểm thử và xác minh

- [x] 8.1 Chạy toàn bộ test schema AI planning và video phase 2.
- [ ] 8.2 Chạy test fallback timeout story/shot/prompt và kiểm tra không lọt metadata vào production fields.
- [ ] 8.3 Chạy test voice/subtitle/render readiness với narration hợp lệ và narration bị chặn.
- [x] 8.4 Chạy kiểm tra static schema trên mọi output schema gửi Codex/OpenAI.
- [ ] 8.5 Reproduce project fixture tương đương `Wrong Note, Right Way` và xác nhận narration tiếng Anh tự nhiên.
- [ ] 8.6 Kiểm tra audit giữ provider 400, fallback reason, truncation và kết quả repair.
- [ ] 8.7 Kiểm tra `prompts_only` tạo prompt Veo có dialogue + native sound design, không tạo TTS/SRT riêng.
- [ ] 8.8 Chạy typecheck frontend cho API response/status và nhãn chế độ đầu ra.
- [ ] 8.9 Cập nhật release notes/changelog nếu change được apply và phát hành.
