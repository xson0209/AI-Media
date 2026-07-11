## 1. Data Model Và API Contract

- [x] 1.1 Thêm ORM model `VideoAutoRun` với các field run id, project id, mode, status, current step, review stage, progress, force flag, step results JSON, error code, failure reason và timestamps.
- [x] 1.2 Thêm migration tạo bảng `video_auto_runs`, index theo project/status/created_at và cột JSON/text cần cho step results.
- [x] 1.3 Thêm Pydantic models cho auto-run request/response: start, status detail, continue, cancel, retry và summary counts.
- [x] 1.4 Thêm type frontend tương ứng trong `app/src/lib/api/types.ts` cho mode, status, step, review stage và response payload.
- [x] 1.5 Cập nhật `apiClient` với endpoint start, latest, get status, continue, cancel và retry auto-run.

## 2. Backend Auto-Run Service

- [x] 2.1 Tạo service `video_auto_runs` để quản lý tạo run, tìm active/latest run, transition trạng thái và serialize summary.
- [x] 2.2 Implement guard chỉ cho một auto-run active trên mỗi project và trả lỗi tiếng Việt khi request tạo run trùng không được phép.
- [x] 2.3 Implement validation đầu vào: project tồn tại, phase 2, source content hợp lệ, prompt segment config hợp lệ, planning provider khả dụng khi cần.
- [x] 2.4 Implement state machine idempotent cho các bước validate, develop story, review story, approve story, generate shots, generate prompts, review prompts, generate voice, wait voice, generate subtitle và completed.
- [x] 2.5 Implement logic skip artifact đã completed/còn mới và chỉ tạo lại artifact missing, stale hoặc failed retryable.
- [x] 2.6 Implement `review_gated` dừng ở `review_stage = story` và `review_stage = prompts`, sau đó resume từ trạng thái project mới nhất khi user continue.
- [x] 2.7 Implement `full_auto` tự approve các bước trung gian nhưng vẫn dừng `needs_input` hoặc `failed` khi thiếu voice profile, provider, language support hoặc input bắt buộc.
- [x] 2.8 Implement voice orchestration: enqueue voice cho shot cần narration, chuyển `waiting_voice`, sync/poll voice status và chỉ tạo subtitle sau khi voice bắt buộc completed.
- [x] 2.9 Implement failure handling cho voice/prompt/subtitle, lưu danh sách shot lỗi và summary nguyên liệu lõi đã sẵn sàng.
- [x] 2.10 Implement cancel và retry không tạo run trùng, không tự tạo subtitle/package sau cancel và không force regenerate story/prompt khi retry lỗi voice/subtitle.

## 3. Routes Và Observability

- [x] 3.1 Thêm routes `/ai-video/projects/{project_id}/auto-runs` để start auto-run và `/auto-runs/latest` để restore UI.
- [x] 3.2 Thêm routes get run detail, continue, cancel và retry theo `{run_id}` với lỗi tiếng Việt nhất quán qua `video_errors`.
- [x] 3.3 Chạy auto-run qua background task an toàn, cập nhật DB theo từng bước và xử lý app restart hoặc run treo bằng trạng thái retry/failure rõ ràng.
- [x] 3.4 Ghi debug event cho từng transition quan trọng, gồm run id, project id, step, status, duration/error code và technical details đã redaction.
- [x] 3.5 Đảm bảo technical details không lưu toàn bộ source text, narration dài hoặc prompt đầy đủ.

## 4. Frontend Auto Panel

- [x] 4.1 Thêm panel Auto tạo nguyên liệu trong `AIVideoAssistant` với mode selector `Duyệt từng chặng` và `Tự chạy hết`, không kèm tùy chọn tạo ZIP trong luồng auto.
- [x] 4.2 Thêm mutation/query để start, poll latest/detail, continue, cancel và retry auto-run; restore latest run khi đổi hoặc mở lại project.
- [x] 4.3 Hiển thị progress checklist theo step, current step, completed/pending counts, waiting voice state và summary output prompt/voice/SRT/package.
- [x] 4.4 Khi run `needs_review`, hiển thị review stage bằng tiếng Việt, đưa action tiếp tục gần nội dung cần duyệt và vẫn cho user dùng nút thủ công để chỉnh.
- [x] 4.5 Khi run `needs_input` hoặc `failed`, hiển thị lỗi inline, action retry/cancel phù hợp và không che mất controls cần để sửa voice profile/source/project.
- [x] 4.6 Disable hoặc guard các action thủ công có thể gây chạy trùng trong lúc auto-run active, nhưng vẫn cho phép đọc, copy và duyệt nội dung.
- [ ] 4.7 Kiểm tra layout responsive, text không overlap, không dùng emoji, không thêm dependency UI/motion mới khi chưa kiểm tra `app/package.json`.
- [x] 4.8 Redesign progress panel thành timeline/summary thân thiện cho người không code, dựng từ `current_step`, `status`, `summary`, `completed_steps`, `pending_steps` và session React thay vì lưu event log chi tiết mới vào DB. ← (verify: no backend persistence is added for UI-only progress narration, and reload still shows a useful fallback from latest auto-run status)

## 5. Backend Tests

- [x] 5.1 Thêm test tạo auto-run hợp lệ, project không tồn tại, thiếu source và chặn active run trùng.
- [x] 5.2 Thêm test `review_gated` dừng ở story, continue sang shots/prompts, dừng ở prompts và chỉ tạo voice sau continue.
- [x] 5.3 Thêm test `full_auto` tự approve story/prompts và chạy qua review gates nhưng dừng khi thiếu voice profile hoặc planning provider.
- [x] 5.4 Thêm test idempotent skip story/prompt/voice đã completed và retry không force regenerate artifact hợp lệ.
- [x] 5.5 Thêm test voice orchestration chờ generation terminal, tạo subtitle sau khi mọi voice completed và fail nếu một shot voice failed.
- [x] 5.6 Thêm test auto-run không gọi tạo ZIP package, kể cả khi request hoặc dữ liệu legacy còn flag package.
- [x] 5.7 Thêm test cancel/continue/retry sai trạng thái trả lỗi tiếng Việt và không đổi step sai.
- [x] 5.8 Thêm test debug redaction không lưu full prompt/narration/source text trong technical details.

## 6. Frontend Tests Và Type Checks

- [x] 6.1 Cập nhật hoặc thêm test/type coverage cho `apiClient` auto-run methods và TypeScript types.
- [ ] 6.2 Thêm UI test hoặc component-level check cho mode selector, start button, progress state, needs-review state, failed/needs-input state và retry/cancel actions.
- [ ] 6.2a Thêm hoặc cập nhật check frontend cho progress panel session-only: running, needs-review, failed, completed và reload/fallback từ latest run status.
- [x] 6.3 Chạy frontend type/build checks liên quan đến AI Video Assistant.
- [x] 6.4 Chạy focused backend tests cho AI Video auto-run, voice, subtitle và package readiness.

## 7. Manual QA Và Docs

- [ ] 7.1 Manual QA mode `Duyệt từng chặng`: tạo project mới, dừng ở story, chỉnh/duyệt, dừng ở prompt, tiếp tục, tạo voice, tạo SRT và xác nhận không tự tạo ZIP.
- [ ] 7.2 Manual QA mode `Tự chạy hết`: tạo project mới có voice profile, chạy đến prompt + voice + SRT không cần thao tác trung gian.
- [ ] 7.3 Manual QA resume: start auto-run, refresh app hoặc đổi project rồi quay lại, xác nhận panel khôi phục latest run đúng.
- [ ] 7.4 Manual QA lỗi: thiếu voice profile, voice fail, provider fail, cancel giữa waiting voice và retry sau khi sửa cấu hình.
- [x] 7.5 Cập nhật tài liệu AI Video hoặc README liên quan để giải thích hai chế độ duyệt và giới hạn không tự render MP4 trong change này.
