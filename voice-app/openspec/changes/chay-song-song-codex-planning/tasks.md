## 1. Planning Pool Và Cấu Hình

- [ ] 1.1 Thêm service quản lý Codex planning pool dùng chung cho AI Video, với global `max_concurrency = 2` mặc định.
- [ ] 1.2 Thêm cách đọc override concurrency  từ env/config nội bộ, validate giá trị hợp lệ và fallback an toàn về 2 khi cấu hình thiếu hoặc sai.
- [ ] 1.3 Implement acquire/release slot bằng context manager hoặc helper tương đương để đảm bảo release trong mọi path success, validation fail, timeout và exception.
- [ ] 1.4 Implement per-project active planning registry đểchặn nhiều planning jobs cùng lúc trên một project.
- [ ] 1.5 Thêm lỗi domain tiếng Việt cho trường hợp project đang có planning job active và không được tạo job trùng.

## 2. Tích Hợp Vào Codex Planning Calls

- [ ] 2.1 Bọc `_run_structured_codex` của `video_phase2` bằng planning pool, truyền `project_id`, `step_name`, provider/model và metadata đã redaction.
- [ ] 2.2 Bọc các AI Video planning calls legacy trong `video_planning` để manual project plan, scene regenerate và prompt ảnh không bypass pool.
- [ ] 2.3 Đảm bảo `generate_video_prompt_pack` vẫn build một full prompt pack call cho toàn bộ shot/segment cần prompt trong project, không chia batch theo shot.
- [ ] 2.4 Đảm bảo retry hiện có của Codex planning vẫn hoạt động bên trong một acquired slot, không release/re-acquire giữa các retry của cùng step.
- [ ] 2.5 Không đưa planning jobs vào `task_queue.enqueue_generation` và không thay đổi TTS generation queue serial hiện có.

## 3. Auto-Run Và Manual API Behavior

- [ ] 3.1 Cập nhật auto-run để khi planning pool đầy thì run hiển thị current step tiếng Việt rõ ràng là đang chờ slot Codex/planning.
- [ ] 3.2 Đảm bảo auto-run đang chờ slot tiếp tục đúng step sau khi có slot, không skip validation và không tạo artifact giả.
- [ ] 3.3 Đảm bảo cancel/retry/failure của auto-run không để rò rỉ project lock hoặc global planning slot.
- [ ] 3.4 Cập nhật các manual AI Video endpoints dùng Codex để đi qua pool và trả lỗi tiếng Việt khi request trùng project đang planning.
- [ ] 3.5 Đảm bảo nhiều project auto-run khác nhau có thể cùng tiến tới planning song song trong giới hạn 2 job toàn app.

## 4. Observability Và Debug

- [ ] 4.1 Ghi debug event khi planning job bắt đầu chờ slot, lấy slot, release slot, hoàn tất hoặc lỗi.
- [ ] 4.2 Log wait duration, active count hoặc thông tin queue an toàn nếu có, project id, step name, provider/model và error code.
- [ ] 4.3 Đảm bảo technical details không lưu full prompt, source text dài, narration dài hoặc secret; chỉ lưu count, ids, text length hoặc preview rút gọn.
- [ ] 4.4 Cập nhật summary/status frontend nếu cần để auto-run panel hiển thị trạng thái chờ planning tự nhiên bằng tiếng Việt.

## 5. Backend Tests

- [ ] 5.1 Thêm unit tests cho planning pool: default concurrency 2, override hợp lệ, override sai fallback an toàn.
- [ ] 5.2 Thêm test hai project planning chạy song song và project thứ ba không chạy Codex trước khi slot được release.
- [ ] 5.3 Thêm test chặn request planning trùng cùng project và đảm bảo không tạo Codex subprocess thứ hai.
- [ ] 5.4 Thêm test release slot/project lock sau Codex timeout, invalid output, validation error và exception bất ngờ.
- [ ] 5.5 Thêm test `generate_video_prompt_pack` vẫn gọi Codex đúng một lần cho full pack của project và validate/ghi prompt như hiện tại.
- [ ] 5.6 Thêm test auto-run nhiều project: tối đa 2 planning jobs active cùng lúc, run thứ ba chờ và tiếp tục sau khi có slot.
- [ ] 5.7 Thêm test manual endpoint không bypass pool và trả lỗi tiếng Việt khi cùng project đang có auto-run planning active.
- [ ] 5.8 Thêm regression test chứng minh TTS generation queue vẫn serial và planning pool không enqueue vào generation queue.
- [ ] 5.9 Thêm test debug redaction cho planning concurrency event, không chứa full prompt/source/narration.

## 6. Frontend, Type Check Và QA

- [ ] 6.1 Cập nhật frontend types/labels nếu auto-run current step hoặc status mới được thêm cho trạng thái chờ planning.
- [ ] 6.2 Chạy frontend type/build checks liên quan đến AI Video Assistant và api client.
- [ ] 6.3 Chạy focused backend tests cho AI Video planning, auto-run, prompt generation và task queue.
- [ ] 6.4 Manual QA với 3 project auto-run: xác nhận 2 project chạy Codex cùng lúc, project thứ ba chờ slot rồi tiếp tục.
- [ ] 6.5 Manual QA một project bị bấm manual prompt trong lúc auto-run planning: xác nhận không tạo job trùng và lỗi/status tiếng Việt rõ ràng.
- [ ] 6.6 Manual QA rollback/config: đặt concurrency 1 để xác nhận behavior quay về gần tuần tự và vẫn hoàn tất project.
