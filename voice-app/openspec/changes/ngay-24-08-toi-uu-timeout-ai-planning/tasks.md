## 1. Pha 1 — Sửa thang fallback (rẻ, đo được ngay)

- [ ] 1.1 Bỏ nhánh `if error_code == "CODEX_EXEC_TIMEOUT": return True` ở đầu `_looks_like_model_config_failure` (`backend/services/ai_planning.py:337-339`). Giữ nguyên nhánh HTTP status code và nhánh `_TRANSIENT_PROVIDER_MARKERS` — chỉ bỏ đúng nhánh `error_code`.
- [ ] 1.2 Rà lại `_should_retry_user_connected_config` (`ai_planning.py:352-357`) xác nhận không còn đường nào khác cho timeout leo thang profile fallback.
- [ ] 1.3 Test: timeout ở lần thử đầu chỉ tạo **đúng một** subprocess run, và raise `CODEX_EXEC_TIMEOUT`. Đếm số lần gọi `_run_command` bằng monkeypatch. Thêm vào `backend/tests/test_video_phase2_timeout.py`.
- [ ] 1.4 Test: lỗi config model thật (provider text chứa `unknown model`) **vẫn** fallback sang profile `user_connected_fallback` — chống hồi quy cho 1.1.
- [ ] 1.5 Test: lỗi transient (HTTP 503) vẫn fallback như trước.

## 2. Pha 1 — Reasoning effort theo bước (mức trần, không phải mức ưu tiên)

- [ ] 2.1 Thêm thang bậc effort tường minh `low < medium < high < xhigh < max < ultra`. `CODEX_REASONING_EFFORTS` (`ai_planning.py:28`) là `set` nên không có thứ tự — cần một tuple/dict riêng.
- [ ] 2.2 Thêm tham số `step_effort_cap: str | None = None` vào `run_codex_exec` (`ai_planning.py:739`). Effort thực thi = `min(effort_người_dùng_chọn, step_effort_cap)` theo thang ở 2.1. **Không** chèn vào chuỗi `or` của `resolve_codex_model_policy` (`:253-270`) — làm vậy sẽ bị `settings_effort` che và tính năng thành no-op, xem D2.
- [ ] 2.3 Trần không hợp lệ ⇒ coi như không có trần (dùng `_normalize_reasoning_effort` tại `:247`), không được làm lệnh Codex thất bại.
- [ ] 2.4 Cho `_run_structured_codex` (`services/video_phase2.py:2733`) nhận và chuyển tiếp `step_effort_cap`.
- [ ] 2.5 Khai báo bảng trần theo `step_name` theo D2, ở một hằng tập trung: `video_prompt_generation` → `medium`, `publishing_metadata` → `medium`; `shot_breakdown`, `story_development`, story synthesis → không trần.
- [ ] 2.6 Test: settings `xhigh` + bước trần `medium` ⇒ argv chứa `model_reasoning_effort="medium"`. Assert trên argv theo khuôn `tests/test_ai_planning_schema.py:26`.
- [ ] 2.7 Test: settings `xhigh` + bước không trần ⇒ argv giữ `xhigh`.
- [ ] 2.8 Test: settings `low` + bước trần `medium` ⇒ argv là `low`, trần **không** nâng lên `medium`.
- [ ] 2.9 Test: không có settings/env + bước trần `medium` ⇒ effort là `medium`, không phải `DEFAULT_CODEX_REASONING_EFFORT`.

## 3. Pha 1 — Metrics và thông báo lỗi

- [ ] 3.1 Ghi `prompt_chars`, `output_chars`, `elapsed_ms`, `effective_reasoning_effort`, `attempt` vào observability tại mọi điểm kết thúc lời gọi trong `run_codex_exec` (thành công `:926`, các nhánh thất bại `:956`, `:1120`).
- [ ] 3.2 Cho phép kèm `batch_index` và `batch_total` khi lời gọi thuộc một lô (dùng đường `technical_context` đã có của `_run_structured_codex`).
- [ ] 3.3 Sửa thông báo timeout tại `ai_planning.py:889` và `routes/ai_video.py:64`: bỏ hướng dẫn "tăng timeout trong Settings", thay bằng cách giảm khối lượng (giảm thời lượng mục tiêu, giảm số segment, rút ngắn nguồn nội dung).
- [ ] 3.4 `_safe_json_output` (`ai_planning.py:1228`): khi **có** truyền `output_schema` mà output không parse được thì raise kèm `output_chars`; khi **không** có schema thì giữ nguyên `{"text": raw}` cho các caller research.
- [ ] 3.5 Test: có schema + output bị cắt ⇒ raise, không trả `{"text": ...}`. Không schema ⇒ vẫn trả `{"text": ...}`.
- [ ] 3.6 Ghi `batch_index` / `batch_total` vào **cả** `video_errors.log_error` ở nhánh timeout (`ai_planning.py:862-882`), không chỉ `video_observability`. Log timeout thật đang không cho biết lô nào chết — đó là lý do phải suy đoán khi chẩn đoán.
- [ ] 3.7 Chạy một bước planning thật trên project 21 segment, ghi lại `elapsed_ms` / `prompt_chars` / `output_chars` theo `step_name` làm **số đo nền** để so sánh sau khi tối ưu.

## 3b. Pha 1b — Giảm batch size cho bước đã chứng minh timeout

Bước `generate_video_prompt_pack` đã xé lô ở 5 mà vẫn timeout 600s (đo được 2026-08-24). Đây là fix trực tiếp nhất, không cần chờ persistence của pha 2.

- [ ] 3b.1 Tách kích thước lô prompt pack thành hằng riêng, độc lập với kích thước lô của shot breakdown. Không dùng chung `VIDEO_PROMPT_BATCH_SIZE` cho cả hai.
- [ ] 3b.2 Hạ giá trị xuống 3, chạy đo trên project 21 segment. Nếu `elapsed_ms` vẫn trên ~400s thì hạ tiếp xuống 2. Không hạ dưới 2 — phần cố định ~48KB/lô sẽ áp đảo (xem D3b).
- [ ] 3b.3 Test: project 21 shot ⇒ nhiều hơn 5 lô, mỗi lô ít hơn 5 prompt.
- [ ] 3b.4 Đo lại và so với số đo nền của 3.7. Kết hợp trần effort `medium` của 2.5, đây là hai cần gạt đánh trực tiếp vào lời gọi đang chết.

## 4. Pha 2 — Persistence tiến độ lô

- [ ] 4.1 Thêm cột `shot_batch_state_json` (JSON, nullable) vào `VideoProject` (`backend/database/models.py`, vùng `class VideoProject` từ `:544`).
- [ ] 4.2 Thêm migration theo khuôn `_add_column` (`backend/database/migrations.py:62`), nối vào danh sách cột `video_projects` tại `:1130`. Xác nhận idempotent khi chạy hai lần.
- [ ] 4.3 Hàm tính `run_key` fingerprint từ các input chi phối output theo D3: scene đã duyệt, `target_duration_seconds`, `prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt`, `dialogue_mode`, `target_language`, style/character bible, `locked_count`.
- [ ] 4.4 Hàm đọc/ghi/xóa state với shape theo D3 (`run_key`, `target_count`, `locked_count`, `batch_size`, `completed`, `batch_keys`, `updated_at`).
- [ ] 4.5 Test: `run_key` đổi khi bất kỳ input chi phối nào đổi, và **không** đổi khi sửa thứ không ảnh hưởng output (ví dụ `title`).

## 5. Pha 2 — Xé lô generate_shots

- [ ] 5.1 Thêm hằng batch size riêng cho shot breakdown (không dùng chung `VIDEO_PROMPT_BATCH_SIZE` — xem Open Questions của design), mặc định 5, cấu hình được ở một chỗ.
- [ ] 5.2 Dựng prompt theo khuôn placeholder + `.replace()` như `generate_video_prompt_pack` (`video_phase2.py:3835-3838`), thay vì dựng lại prompt mỗi lô.
- [ ] 5.3 Sửa `segment_instruction` (`video_phase2.py:3208-3215`) thành số shot của **lô**, kèm dải `shot_order` tuyệt đối trên tổng `target_segment_count` để model không mất định vị.
- [ ] 5.4 Vòng lặp lô dùng `_prompt_pack_batches` (`:3669`) với `_validate_shot_order_output` (`:945`) theo từng lô — truyền `expected_count` = số shot của lô, `first_shot_order` = order đầu của lô. Hàm này **không cần sửa**, đã chấp nhận cả dải cục bộ `1..N` (`:961-963`).
- [ ] 5.5 Retry mỗi lô theo khuôn `VIDEO_PROMPT_BATCH_MAX_ATTEMPTS` (`:51`) với `max_attempts=1` ở lời gọi trong.
- [ ] 5.6 Carry-over continuity cho lô N>1 theo D5, đọc **từ DB** (đã commit) chứ không từ biến RAM: `transition_to_next`, appearance/wardrobe, setting/lighting của shot cuối lô trước.
- [ ] 5.7 Giữ toàn bộ `scene_lines` (`:3183-3186`) và continuity/style bible cho **mọi** lô, không chỉ lô đầu.
- [ ] 5.8 Commit sau **mỗi** lô: `db.add` các shot của lô rồi `db.commit()`, sau đó cập nhật state và commit lần nữa.
- [ ] 5.9 Chỉ chuyển `project.status`/`planning_status` sang `shots_ready` và đánh dấu stale các artifact phụ thuộc (`:3443-3453`) khi **tất cả** lô hoàn tất.

## 6. Pha 2 — Resume cho generate_shots

- [ ] 6.1 Biến bước xóa shot chưa khóa (`video_phase2.py:3201-3203`) từ vô điều kiện thành **có điều kiện**: khi `run_key` khớp và `completed` không rỗng thì giữ shot thuộc các lô đã hoàn tất. Không làm bước này thì resume sẽ tự xóa thứ nó vừa lưu.
- [ ] 6.2 Khi `run_key` **không** khớp: xóa state, xóa shot chưa khóa, chạy từ lô 1 — đúng hành vi hiện tại.
- [ ] 6.3 Bỏ qua các lô có `batch_index` trong `completed` mà không gọi Codex; ghi log nêu rõ lô nào được bỏ qua nhờ resume.
- [ ] 6.4 Xóa state khi toàn bộ lô hoàn tất, để lần chạy sau là chạy mới.
- [ ] 6.5 Test: lô 3/5 thất bại ⇒ shot của lô 1-2 còn nguyên sau khi request raise, và state ghi `completed = [1, 2]`.
- [ ] 6.6 Test: chạy lại sau 6.5 với input không đổi ⇒ chỉ gọi Codex 3 lần (lô 3, 4, 5), không gọi lại lô 1-2.
- [ ] 6.7 Test: chạy lại sau khi đổi `target_duration_seconds` ⇒ tạo lại từ lô 1, không trộn kết quả hai lần chạy.
- [ ] 6.8 Test: shot người dùng đã khóa vẫn được tôn trọng, các lô mới tiếp nối sau `locked_segment_count`.
- [ ] 6.9 Test: số segment ≤ một lô ⇒ đúng **một** lời gọi Codex, tương đương hành vi trước change.
- [ ] 6.10 Test: `shot_order` toàn bộ liên tục, không trùng, qua nhiều lô.

## 7. Pha 3 — Resume cho generate_video_prompt_pack

- [ ] 7.1 Đổi `generate_video_prompt_pack` (`video_phase2.py:3843`) từ tích lũy RAM (`:3809-3810`) + một `db.commit()` ở `:4140` sang commit sau mỗi lô.
- [ ] 7.2 Lưu bền vững `_prompt_pack_batch_idempotency_key` (`:3679`) — hiện chỉ dùng làm field log (`:3821`) — dùng lại persistence của pha 2.
- [ ] 7.3 Tra khóa idempotency trước khi gọi Codex, bỏ qua lô đã có prompt.
- [ ] 7.4 Test: thất bại giữa chuỗi lô ⇒ prompt của các lô trước còn nguyên.
- [ ] 7.5 Test: chạy lại với shot không đổi ⇒ chỉ gọi Codex cho lô còn thiếu prompt.

## 8. Kiểm chứng

- [ ] 8.1 Chạy full test suite backend, xác nhận không hồi quy ở `test_ai_planning_schema.py`, `test_ai_video_backend.py`, `test_video_phase2_timeout.py`, `test_video_publishing_metadata.py`.
- [ ] 8.2 Chạy lại đúng bước planning của 3.7 trên cùng project 21 segment, so `elapsed_ms` / `output_chars` mỗi lời gọi với số đo nền. Xác nhận không còn lời gọi nào tiến gần trần 600s.
- [ ] 8.3b Xác nhận `generate_video_prompt_pack` — lời gọi đã chứng minh timeout — chạy xong trên project 21 segment. Đây là tiêu chí thành công cụ thể của change này.
- [ ] 8.3 So sánh chất lượng continuity thủ công giữa output one-shot cũ và output theo lô trên một project thật — đây là rủi ro chính của change, không bỏ qua bước này.
- [ ] 8.4 Xác nhận không nâng trần timeout: `ai_planning.py:27/775`, `models.py:364/380`, `video_phase2.py:52-53` không đổi.
- [ ] 8.5 Xác nhận không nâng concurrency: `video_planning_pool.py:19-20` không đổi.
- [ ] 8.6 Ghi vào CHANGELOG.md.
