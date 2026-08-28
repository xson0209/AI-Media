## Why

Các bước AI planning (tạo shot, prompt pack, story studio) thường xuyên timeout: một lời gọi logic tới Codex CLI có thể tốn tới **4 × 600s = 2400s** trước khi UI nhận về một cục 502, vì `_looks_like_model_config_failure` coi `CODEX_EXEC_TIMEOUT` là lý do hợp lệ để đổi profile model và chạy lại y nguyên request đã quá to (`backend/services/ai_planning.py:337-339`). Lần thử thứ hai gần như chắc chắn cũng chết, vì nguyên nhân là kích thước request chứ không phải cấu hình model.

Trần timeout 600s là **cứng, người dùng không nâng được** — `min(..., 600)` tại `ai_planning.py:775`, `Field(le=600)` tại `models.py:364`, env cũng bị clamp tại `settings.py:100-105`. Nên hướng duy nhất là làm request nhỏ lại, chứ không phải mua thêm thời gian.

## What Changes

Chia làm 3 pha, cố tình xếp thứ tự để pha rẻ và đo được đi trước.

Một lần timeout thật (2026-08-24) đã cho số đo, và nó thu hẹp phạm vi lại: bước chết là `generate_video_prompt_pack` — **bước đã được xé lô sẵn ở batch size 5**. Prompt 78KB, output 202KB streamed, `output_file_exists=False`, chết ở 600.5s khi đã tới segment cuối. Nên xé lô là đúng hướng nhưng **5 là quá to**, và nút thắt nằm ở lượng output mỗi lần gọi chứ không ở input.

**Pha 1 — sửa thang fallback + trần reasoning effort (không đổi kiến trúc)**

- Loại `CODEX_EXEC_TIMEOUT` khỏi điều kiện leo thang fallback model, cắt ngay một nửa thời gian chờ tệ nhất: 4×600 → 2×600.

```
Trước: timeout(600) → đổi profile → timeout(600) → [+ inline schema ×2] = 2400s
Sau:   timeout(600) → dừng, báo lỗi kèm gợi ý xé nhỏ                     =  600s
```

- Cho mỗi bước khai báo **mức trần** reasoning effort, effort thực thi = `min(người dùng chọn, trần của bước)`. Không phải chèn thêm một bậc ưu tiên: DB thật đang có `model_reasoning_effort = 'xhigh'` đặt tường minh, nên nếu để settings thắng thì tính năng thành no-op ngay trên máy người dùng. Bước cơ học (prompt pack, publishing metadata) trần `medium`; bước sáng tạo không trần.
- Hạ batch size của `generate_video_prompt_pack` xuống dưới 5 — bước duy nhất đã có bằng chứng timeout — thành hằng riêng độc lập với shot breakdown. Đây là fix trực tiếp nhất và không cần chờ persistence của pha 2.
- Ghi metrics đủ để **đo được trước/sau**: `prompt_chars`, `output_chars`, `elapsed_ms`, `effective_reasoning_effort`, `batch_index` vào `video_observability`.
- Sửa thông báo lỗi đang trỏ vào một control không tồn tại: `ai_planning.py:889` và `routes/ai_video.py:64` khuyên "tăng timeout trong Settings", nhưng `AIPlanningPage.tsx:230` chỉ render read-only và trần 600 không vượt được.
- Chặn đường làm thất bại trở nên vô hình: `_safe_json_output` (`ai_planning.py:1228`) đang lặng lẽ biến JSON hỏng/bị cắt thành `{"text": raw}`, sau đó fallback boilerplate được phục vụ như kết quả thật. Khi đã truyền schema thì phải raise, không được bọc im lặng.

**Pha 2 — xé lô `generate_shots` kèm commit từng lô**

- `generate_shots` (`video_phase2.py:3288`) hiện sinh **toàn bộ N segment trong một lời gọi**; video 10 phút là ~375 object lồng sâu 4 với 22 field mỗi shot. Xé theo khuôn `VIDEO_PROMPT_BATCH_SIZE` đã có sẵn (`video_phase2.py:50`, `_prompt_pack_batches` tại `:3669`).
- **Commit sau mỗi lô** cùng một bản ghi tiến độ, để chạy lại chỉ tốn phần còn thiếu. Đây là điều kiện bắt buộc, không phải tùy chọn: xé 10 lô mà mỗi lô fail 5% độc lập thì xác suất mất cả job là ~40%, **cao hơn** one-shot.
- Truyền continuity carry-over giữa các lô, vì one-shot đang cho sự mạch lạc toàn cục miễn phí. Xé lô mà không mang ngữ cảnh sang là đánh đổi timeout bằng lỗi continuity.

**Pha 3 — cắm dây resume cho `generate_video_prompt_pack`**

- Đây chính là kịch bản "mất nửa công việc" đã tồn tại: hàm này đã xé lô (`:3812`) nhưng kết quả tích lũy trong RAM (`:3809`) rồi `db.commit()` **một lần duy nhất** ở `:4140` — fail ở lô 7/10 mất trắng 6 lô đầu.
- Hạ tầng đã viết một nửa mà không cắm dây: `_prompt_pack_batch_idempotency_key` (`:3679`) tính uuid5 ổn định nhưng **chỉ dùng làm field log** (`:3821`), không lưu, không tra.

## Capabilities

### New Capabilities

- `on-dinh-timeout-ai-planning`: hành vi timeout, thang fallback, phân tầng reasoning effort và metrics của tầng gọi Codex CLI; bao gồm cả việc không được che giấu output bị cắt.
- `xe-lo-tao-shot-va-resume`: xé lô cho các bước planning sinh nhiều phần tử, kèm persistence tiến độ theo lô, khóa idempotency, resume và continuity carry-over.

### Modified Capabilities

Chưa có spec nào trong `openspec/specs/` (thư mục rỗng), nên không có capability nào bị sửa yêu cầu.

## Impact

**Backend**

- `backend/services/ai_planning.py` — thang fallback (`:337-357`), tham số effort (`:247-294`, `:804-805`), `_safe_json_output` (`:1228`), thông báo lỗi (`:889`).
- `backend/services/video_phase2.py` — `generate_shots` (`:3288`, persistence `:3441-3454`, dọn shot chưa khóa `:3201-3203`), `_run_structured_codex` (`:2733`), `generate_video_prompt_pack` (`:3843`, commit `:4140`).
- `backend/services/video_observability.py` — thêm field metrics.
- `backend/database/` — cột/bảng lưu tiến độ lô. **Cần migration.**
- `backend/routes/ai_video.py` — thông báo lỗi timeout (`:62-65`).

**Ràng buộc phải tôn trọng**

- Trần 600s giữ nguyên; change này **không** nâng trần. Nâng trần cần sửa đồng thời `ai_planning.py:27/775`, `models.py:364/380`, `video_phase2.py:52-53` và nằm ngoài phạm vi.
- `locked` là lock do người dùng bấm, shot chưa khóa bị xóa khi vào lại (`:3201-3203`), nên **không được** dùng `locked` làm mốc tiến độ lô. Cần persistence riêng.
- Concurrency chốt cứng ở 3 (`video_planning_pool.py:19-20`, `MAX_CONFIGURED_CONCURRENCY = 3`); các lô chạy tuần tự trong phạm vi này, không chạm pool.
- Request vẫn đồng bộ trong một POST (`routes/ai_video.py:48-55`), frontend `client.ts:272` gọi `fetch` trần không `AbortSignal`. Change này **không** đổi hợp đồng API sang async; xé lô tuần tự làm tổng thời gian có thể *tăng* nhưng gần như không timeout.

**Không nằm trong phạm vi**

- Chuyển sang job + polling (tiền lệ `video_auto_runs.py:365`).
- Chặn cap input cho `video_planning.py:286` `scene_lines` và tỉa `*_history` tại `video_inspiration.py:2080`.
- Sửa mojibake trong `_variant_score_prompt` / `_variant_synthesis_prompt` (`video_inspiration.py:2117`, `:2131`).
