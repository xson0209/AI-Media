## Context

Ứng dụng có hai luồng xử lý dài:

1. AI Video auto-run đã chạy nền và có planning pool, nhưng chưa có giới hạn chung theo số dự án và việc hủy chưa dọn voice đã xếp hàng.
2. Video Inspiration analyze/rewrite vẫn thực hiện nhiều bước nặng ngay trong HTTP request. Analyze có các bước trích khung hình, nhận dạng lời nói và hai lần gọi Codex; rewrite có bốn lần gọi Codex nối tiếp. Vì vậy một request có thể kéo dài nhiều phút và làm polling/UI phản hồi chậm.

Generation queue hiện mặc định có 2 worker nhưng có thể bị nâng lên 4 bằng môi trường, đường `/generate/stream` bỏ qua queue, và voice vừa enqueue đã bị ghi là `generating`. Do đó giới hạn 2 chưa phải giới hạn tuyệt đối và UI chưa phân biệt được đang chờ với đang chạy thật.

Ứng dụng hiện là local desktop/server, một backend process, SQLite và artifact storage local. Thiết kế này tối ưu cho mô hình đó.

## Goals / Non-Goals

**Goals:**

- Tối đa 3 workflow AI Video hoặc Video Inspiration được xử lý cùng lúc.
- Dự án thứ tư tự chờ theo FIFO và tự tiếp tục khi có slot.
- Video Inspiration analyze/rewrite chạy nền và endpoint trả nhanh.
- Tối đa 3 Codex planning operations toàn app, nhưng cùng một project/job không chạy planning trùng.
- Tối đa 2 voice inferences toàn app, kể cả streaming.
- Tối đa 1 STT inference mặc định.
- Hiển thị trạng thái tài nguyên và hàng đợi bằng tiếng Việt.
- Cancel/retry/restart không làm rò slot và không để job treo vô hạn.
- Giữ prompt pack của một AI Video project là một full-pack Codex call.

**Non-Goals:**

- Không làm một lần gọi Codex đơn lẻ nhanh hơn.
- Không chia prompt pack theo shot để chạy song song trong cùng project.
- Không thêm Redis, distributed queue, nhiều worker process hoặc nhiều máy.
- Không tiếp tục một subprocess Codex/TTS đang chạy dở sau khi ứng dụng bị tắt đột ngột.
- Không tạo engine voice mới hoặc thay đổi chất lượng giọng.

## Decisions

### 1. Một workflow pool FIFO, tối đa 3 dự án

Thêm một coordinator in-memory dùng chung với `max_concurrency = 3`. Mỗi đơn vị công việc có khóa ổn định:

- `ai-video:<project_id>`
- `video-inspiration:<job_id>`

Pool lưu số đang chạy, số đang chờ và work keys để API/UI có thể hiển thị. Cùng một key không thể được chạy hai lần. Việc lấy và trả slot dùng context manager/finally để slot luôn được trả sau success, error hoặc cancel.

AI Video auto-run giữ slot khi nó đang tự xử lý. Khi run chuyển sang trạng thái cần người dùng duyệt/nhập thêm hoặc trạng thái kết thúc, slot được trả. Continue/retry sẽ xin slot lại. Video Inspiration analyze/rewrite giữ slot trong thời gian background operation đang xử lý.

FIFO được dùng để project thứ tư không bị bỏ đói. Đây là fairness ở mức workflow; generation queue tiếp tục FIFO ở mức voice.

### 2. Planning pool dùng chung, tối đa 3 Codex operations

Planning pool hiện có được tổng quát hóa để nhận `work_key`, `workflow_type`, `project_id?`, `job_id?` thay vì giả lập Video Inspiration thành AI Video project. Global concurrency mặc định là 3, và mỗi work key có một lock riêng.

Mọi AI Video manual/auto planning và mọi Codex call của Video Inspiration đều đi qua boundary này. Các retry của cùng một planning step nằm trong cùng slot. Debug events chỉ lưu id, step, thời lượng và số lượng; không lưu full prompt/source/narration.

### 3. Video Inspiration dùng background runner và DB session riêng

Analyze/rewrite endpoint thực hiện validate, đặt trạng thái `queued`, tạo background task và trả response ngay. Background runner mở DB session riêng, xin workflow slot, cập nhật trạng thái và chạy pipeline.

Các phần blocking như FFmpeg/frame extraction/Codex subprocess được đưa sang worker thread bằng `asyncio.to_thread` để event loop vẫn phục vụ health check, polling và thao tác dự án khác. SQLAlchemy session không được dùng đồng thời giữa các thread.

Analyze vẫn là pipeline async vì có STT. Rewrite được cung cấp async background core; wrapper đồng bộ cũ chỉ được giữ nếu test/đường gọi tương thích còn cần.

### 4. Voice có hard cap 2 trên mọi đường tạo giọng

Generation queue luôn clamp concurrency vào `1..2`; biến môi trường không thể nâng vượt 2. Thêm một inference gate dùng chung, được acquire bởi:

- Worker của generation queue.
- `/generate/stream` và mọi direct generation path còn lại.

Nhờ vậy tổng số voice inference thật không vượt 2 trong một backend process. Gate được trả trong `finally` sau success, lỗi hoặc hủy.

Trạng thái voice được tách:

- `queued`: đã vào hàng đợi, chưa dùng model.
- `loading_model`: worker đã nhận job và đang chuẩn bị model.
- `generating`: model đang tạo audio.
- `completed`, `failed`, `cancelled`: trạng thái kết thúc.

### 5. Hủy dự án truyền xuống công việc đang chờ

Khi hủy AI Video auto-run, backend tìm generation thuộc các scene/shot của project:

- Voice `queued` bị xóa/đánh dấu hủy ngay và không chạy sau đó.
- Voice đang chạy nhận cancel signal nếu engine hỗ trợ; nếu không, kết quả không được dùng để tiếp tục auto-run và run dừng ở checkpoint an toàn.
- Audio đã hoàn tất không bị xóa.

Khi hủy Video Inspiration:

- Job đang chờ workflow slot dừng ngay.
- Job đang chạy dừng trước bước nặng tiếp theo. Subprocess đang chạy có thể chỉ dừng ở checkpoint nếu chưa hỗ trợ kill an toàn.

### 6. STT mặc định 1, render giữ khóa hiện có

Thêm STT gate in-memory mặc định 1 cho Video Inspiration. Job khác hiển thị đang chờ nhận dạng lời nói. Render tiếp tục dùng global render lock hiện có; change này không tạo một cơ chế render thứ hai.

### 7. API tài nguyên là nguồn dữ liệu chung cho UI

Resource status trả về các nhóm:

- Workflow: `running`, `queued`, `max_concurrency = 3`.
- Planning: `running`, `queued`, `max_concurrency = 3`.
- Voice: `running`, `queued`, `max_concurrency = 2`.
- STT: `running`, `queued`, `max_concurrency = 1`.

Frontend chuyển các mã nội bộ sang câu tiếng Việt, ví dụ `Đang chạy 3/3 dự án`, `Tạo giọng 2/2`, `Có 4 giọng đang chờ`. Không hiển thị raw status code cho người dùng.

### 8. Polling theo danh sách tổng hợp, detail theo lựa chọn

Danh sách project/job tiếp tục poll nhanh khi có công việc active. Frontend không tạo một request detail riêng cho mọi project vô thời hạn. Detail chỉ poll cho project đang chọn và các run thực sự cần theo dõi; trạng thái tổng quát lấy từ list/resource status.

Video Inspiration bỏ cờ `busy` toàn trang. Chỉ action của đúng job đang chạy bị khóa, vì vậy người dùng có thể chọn/tạo job khác và bắt đầu dự án thứ hai hoặc thứ ba.

### 9. Restart đánh dấu interrupted và cho retry

Pool là in-memory nên không phục hồi computation đang chạy dở. Khi backend khởi động:

- Job lưu trong DB ở trạng thái active nhưng không còn task runtime được chuyển thành `interrupted`/`failed` với thông báo tiếng Việt.
- Người dùng có thể retry từ checkpoint hợp lệ.
- Không tự tạo trùng subprocess của job cũ.

### 10. Phạm vi giới hạn là một backend process

Mọi hard cap trong change này áp dụng cho một backend process local. Backend phải tiếp tục chạy một worker. Nếu sau này dùng nhiều process/replica, cần queue phân tán và semaphore dùng chung; đó là một change riêng.

## Risks / Trade-offs

- Ba Codex jobs có thể gặp rate limit hoặc làm máy chậm: giữ config có thể hạ planning về 1 hoặc 2, hiển thị rõ hàng đợi và ghi lỗi an toàn.
- Hai voice thật chạy song song có thể không phù hợp với mọi engine/GPU: cần smoke test bằng engine đang dùng; có thể hạ runtime về 1 nhưng không nâng quá 2.
- Background task in-memory mất khi app tắt: đánh dấu interrupted và hỗ trợ retry, không tuyên bố resume chính xác giữa subprocess.
- SQLite có thể tranh ghi khi nhiều job hoàn tất cùng lúc: mỗi background runner dùng session riêng và transaction ngắn.
- Cancel subprocess đang chạy không tức thời ở mọi engine: UI nói rõ `Đang dừng...`, ngăn bước tiếp theo và dọn queue ngay.
- Giữ workflow slot trong lúc chờ resource con có thể giảm throughput, nhưng bảo đảm đúng cam kết chỉ có 3 dự án active và làm trạng thái dễ hiểu.

## Migration Plan

1. Thêm workflow coordinator và mở rộng resource status.
2. Chuyển Video Inspiration analyze/rewrite sang background runner, thêm cancel/retry/recovery.
3. Đưa Video Inspiration Codex/STT qua các pool tương ứng.
4. Đặt voice hard cap 2, thêm inference gate và trạng thái queue đúng.
5. Tích hợp AI Video auto-run/cancel vào coordinator và generation cancellation.
6. Cập nhật frontend tiếng Việt, per-job busy và polling.
7. Chạy backend tests, frontend type/build, OpenSpec validate và manual smoke test.

Rollback an toàn bằng cách đặt workflow/planning/voice concurrency về 1; không cần migration database mới nếu các trạng thái hiện có đủ lưu `queued/interrupted`. Nếu cần thêm enum/string status, vẫn dùng cột text hiện có.

## Open Questions

- Không còn câu hỏi chặn implementation. Kiểm tra thực tế bằng hai voice engine/GPU sẽ quyết định runtime nên để 2 hay hạ tạm về 1 trên máy yếu; hard cap vẫn là 2.
