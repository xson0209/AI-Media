## 1. Điều Phối Workflow Và Planning

- [x] 1.1 Thêm workflow coordinator FIFO dùng chung, mặc định tối đa 3 work keys active và chặn chạy trùng cùng key.
- [x] 1.2 Thêm snapshot workflow gồm running, queued, max concurrency và work keys; bảo đảm release slot ở mọi success/error/cancel path.
- [x] 1.3 Tích hợp AI Video auto-run với workflow coordinator; release khi terminal hoặc dừng chờ người dùng, acquire lại khi continue/retry.
- [x] 1.4 Tổng quát hóa planning pool cho AI Video và Video Inspiration với work key/loại workflow rõ ràng, mặc định tối đa 3.
- [x] 1.5 Giữ per-work-key planning lock, retry trong cùng slot và full-pack prompt generation trong một AI Video project.
- [x] 1.6 Ghi debug event đã redaction cho lúc chờ/lấy/trả slot workflow và planning.

## 2. Video Inspiration Chạy Nền

- [x] 2.1 Chuyển analyze endpoint thành thao tác xếp lịch trả nhanh; background runner dùng DB session riêng.
- [x] 2.2 Chuyển rewrite endpoint thành thao tác xếp lịch trả nhanh và không giữ HTTP request đến khi bốn bước Codex hoàn tất.
- [x] 2.3 Đưa phần blocking của FFmpeg/frame extraction/Codex sang thread để health, polling và UI vẫn phản hồi.
- [x] 2.4 Đưa toàn bộ Codex calls của Video Inspiration qua planning pool chung.
- [x] 2.5 Thêm STT gate mặc định 1 và trạng thái chờ nhận dạng lời nói.
- [x] 2.6 Chặn analyze/rewrite trùng trên cùng job nhưng cho phép job khác sử dụng ba workflow slots.
- [x] 2.7 Thêm cancel/retry; queued job dừng ngay, active job dừng ở checkpoint an toàn.
- [x] 2.8 Khi backend restart, đánh dấu job active bị mất runtime là interrupted/failed rõ ràng và cho retry.

## 3. Voice Hard Cap Và Hủy Theo Dự Án

- [x] 3.1 Clamp generation concurrency tối đa 2, không cho env/config nâng cao hơn 2.
- [x] 3.2 Thêm inference gate dùng chung cho generation workers và `/generate/stream` để tổng voice inference không vượt 2.
- [x] 3.3 Kiểm tra và đưa mọi direct TTS path còn lại qua inference gate hoặc generation queue.
- [x] 3.4 Ghi trạng thái voice đúng theo `queued -> loading_model -> generating -> terminal` cho generation và scene/shot.
- [x] 3.5 Mở rộng resource API trả voice `running`, `queued`, `max_concurrency = 2`.
- [x] 3.6 Khi hủy AI Video auto-run, hủy các generation queued thuộc project và không dùng kết quả active generation để tiếp tục run.
- [x] 3.7 Giữ generation queue FIFO và xác nhận slot được release sau success, lỗi, timeout hoặc cancel.

## 4. API Và UI Tiếng Việt

- [x] 4.1 Mở rộng API/types cho workflow, planning, voice và STT resource snapshots.
- [x] 4.2 AI Video hiển thị số dự án đang chạy/chờ và `Tạo giọng: x/2 · N đang chờ` bằng tiếng Việt.
- [x] 4.3 Video Inspiration bỏ `busy` toàn trang; chỉ khóa action của đúng job đang xử lý.
- [x] 4.4 Video Inspiration cho phép bắt đầu/chọn job thứ hai, thứ ba trong khi job trước chạy nền.
- [x] 4.5 Thêm nút/trạng thái cancel và retry Video Inspiration bằng tiếng Việt.
- [x] 4.6 Map toàn bộ trạng thái nội bộ mới sang câu tiếng Việt dễ hiểu; không hiển thị raw status code.
- [x] 4.7 Giảm polling detail dư thừa, dùng list/resource summary cho các project không được chọn.

## 5. Backend Tests

- [x] 5.1 Test ba workflow khác nhau chạy, workflow thứ tư chờ rồi tự tiếp tục theo FIFO.
- [x] 5.2 Test cùng một project/job không chạy trùng và slot được release sau error/cancel.
- [x] 5.3 Test mixed flow gồm 2 AI Video + 1 Video Inspiration dùng đủ ba slot.
- [x] 5.4 Test Video Inspiration analyze/rewrite endpoint trả nhanh và polling/health vẫn phản hồi khi Codex giả lập đang chạy.
- [x] 5.5 Test cancel queued, cancel active checkpoint, retry và restart/interrupted cho Video Inspiration.
- [x] 5.6 Test planning pool không vượt 3 và full prompt pack vẫn chỉ dùng một Codex call.
- [x] 5.7 Test tổng voice inference không vượt 2 khi queue và streaming chạy đồng thời.
- [x] 5.8 Test voice state transitions, cancel queued generation theo project và release slot ở mọi terminal path.
- [x] 5.9 Test STT không vượt 1 và job chờ tiếp tục sau khi slot được trả.
- [x] 5.10 Chạy regression tests AI Video auto-run, Video Inspiration, generation queue và resource status.

## 6. Frontend, OpenSpec Và QA

- [x] 6.1 Chạy frontend typecheck và production web build.
- [x] 6.2 Chạy focused backend pytest và kiểm tra diff formatting.
- [x] 6.3 Validate OpenSpec change và cập nhật checklist theo kết quả thực tế.
- [ ] 6.4 Manual QA: bắt đầu 2 AI Video + 1 Video Inspiration, chuyển màn hình và xác nhận cả ba tiếp tục chạy nền.
- [ ] 6.5 Manual QA: bắt đầu dự án thứ tư và xác nhận UI báo đang chờ rồi tự chạy khi có slot.
- [ ] 6.6 Manual QA: đưa ít nhất 3 voice vào hàng đợi, xác nhận chỉ `2/2` chạy và phần còn lại hiển thị đang chờ.
- [ ] 6.7 Manual QA: hủy một dự án có voice queued, refresh ứng dụng và xác nhận voice đó không chạy lại.
- [ ] 6.8 Smoke test bằng voice engine/GPU thật; nếu engine không ổn với 2 inference, ghi rõ cấu hình tạm hạ về 1 nhưng vẫn giữ hard cap 2.
