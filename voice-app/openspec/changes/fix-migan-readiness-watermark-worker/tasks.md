## 1. Chuẩn bị môi trường worker

- [x] 1.1 Xác nhận `uv.exe` tồn tại trong venv backend của dự án và ghi lại đường dẫn dùng làm fallback
- [x] 1.2 Sync venv repo watermark kèm extra `video` và `migan` bằng `uv` trong dự án
- [x] 1.3 Xác nhận venv worker sau khi sync đã import được `onnxruntime` và `huggingface_hub` ← (verify: chạy interpreter của venv worker, cả hai module import thành công, `av`/`cv2`/`remove_ai_watermarks` vẫn còn nguyên)

## 2. Script setup phân giải `uv`

- [x] 2.1 Thêm bước phân giải `uv` theo thứ tự `PATH` trước rồi `uv.exe` trong venv backend của dự án
- [x] 2.2 Ghi rõ nguồn `uv` đang dùng ra output của script
- [x] 2.3 Cập nhật thông báo lỗi khi không tìm được `uv` để nêu cả hai vị trí đã tìm ← (verify: giả lập không có `uv` trên PATH thì script vẫn chạy được bằng `uv` trong dự án; giả lập thiếu cả hai thì lỗi nêu đủ hai vị trí)

## 3. Worker báo trạng thái cache model

- [x] 3.1 Thêm hàm tra cache model MI-GAN dựa trên cache HuggingFace cục bộ, không tải model
- [x] 3.2 Đưa trạng thái cache model vào payload `--check` cho backend `migan`
- [x] 3.3 Đảm bảo backend `cv2` không tra cache model và không trả trạng thái cache
- [x] 3.4 Xử lý lỗi ngoài dự kiến khi tra cache thành trạng thái không xác định, không làm worker báo chưa sẵn sàng ← (verify: chạy `--check --backend migan` thật trước và sau khi model được cache, payload phản ánh đúng; `--check --backend cv2` không có trường cache model)

## 4. Thông báo lỗi có hướng dẫn

- [x] 4.1 Bổ sung Python đang chạy worker vào payload lỗi thiếu dependency riêng của `migan`
- [x] 4.2 Bổ sung Python đang chạy worker vào payload lỗi thiếu dependency chung của worker
- [x] 4.3 Thêm lệnh setup cần chạy vào cả hai payload lỗi, kèm backend tương ứng ← (verify: giả lập thiếu dependency, thông báo nêu đúng module thiếu, đúng đường dẫn Python đang chạy, và lệnh setup đúng backend)

## 5. Readiness theo từng backend

- [x] 5.1 Mở rộng trạng thái runtime watermark để mang theo trạng thái cache model
- [x] 5.2 Mở rộng contract readiness dựng MP4 để báo trạng thái từng backend cleanup
- [x] 5.3 Probe cả `cv2` và `migan` khi cleanup bật, không probe khi cleanup tắt
- [x] 5.4 Giữ điều kiện chặn dựng MP4 chỉ dựa trên backend đang chọn
- [x] 5.5 Phát cảnh báo khi backend đang chọn là `migan` và model chưa cache, không chặn dựng ← (verify: cleanup tắt thì không spawn worker; chọn `cv2` khi `migan` chưa sẵn sàng vẫn dựng được; chọn `migan` chưa sẵn sàng thì bị chặn kèm lý do; model chưa cache thì có cảnh báo mà vẫn dựng được)

## 6. Contract API và UI

- [x] 6.1 Cập nhật kiểu dữ liệu readiness ở frontend theo contract mới
- [x] 6.2 Đánh dấu và vô hiệu hoá lựa chọn cách lấp vùng chưa sẵn sàng trong dropdown
- [x] 6.3 Hiển thị lý do backend chưa sẵn sàng và cảnh báo model chưa cache trong bảng dựng MP4
- [x] 6.4 Không vô hiệu hoá lựa chọn nào khi readiness chưa có dữ liệu ← (verify: `migan` chưa sẵn sàng thì option bị khoá kèm nhãn và lý do; cả hai sẵn sàng thì chọn được bình thường; trong lúc readiness đang tải không có option nào bị khoá)

## 7. Tài liệu

- [x] 7.1 Cập nhật phần chuẩn bị worker để nêu `uv` lấy từ dự án khi không có trên `PATH`
- [x] 7.2 Cập nhật ghi chú MI-GAN về trạng thái cache model, cảnh báo lần dựng đầu và chi phí thời gian dựng
- [x] 7.3 Nêu rõ backend chỉ ảnh hưởng chất lượng vùng lấp, không ảnh hưởng khả năng phát hiện dấu AI
- [x] 7.4 Giữ nguyên và làm rõ giới hạn không xử lý watermark ẩn ← (verify: tài liệu không hứa hẹn quá phạm vi, nêu đúng ba trạng thái readiness và giới hạn watermark ẩn)

## 8. Kiểm thử và xác minh

- [x] 8.1 Thêm test cho readiness báo trạng thái từng backend, gồm trường hợp chọn `cv2` khi `migan` chưa sẵn sàng
- [x] 8.2 Thêm test cho trạng thái model chưa cache sinh cảnh báo mà không chặn dựng
- [x] 8.3 Thêm test cho payload lỗi thiếu dependency có chứa Python đang chạy và lệnh setup
- [x] 8.4 Chạy toàn bộ test watermark hiện có, xác nhận không hồi quy
- [x] 8.5 Chạy kiểm tra runtime thật cho cả `cv2` và `migan`, không mock
- [x] 8.6 Chạy build/typecheck frontend ← (verify: test watermark cũ xanh, test mới phủ đủ các nhánh readiness, kiểm tra runtime thật cho hai backend cho kết quả đúng, frontend build sạch)
