## Why

Dựng MP4 cho một project 18 clip mất khoảng 72 phút, trong đó bước làm sạch dấu AI chiếm 95–99% thời gian còn ffmpeg encode chỉ chiếm vài phần trăm. Đo trực tiếp trên clip thật cho thấy cấu hình đang dùng (backend `migan`, dò cả 6 hãng, chạy tuần tự) tốn 240–270 giây mỗi clip, trong khi cấu hình `cv2` + chỉ dò đúng hãng của clip + chạy song song hạ xuống 78,6 giây cho **toàn bộ** 18 clip mà chất lượng ảnh gần như không phân biệt được (PSNR 50,7 dB, SSIM 0,9965 giữa hai bản của cùng một clip).

Thêm vào đó, giao diện hiện chỉ báo tiến độ của bước chuẩn hoá clip — bước rẻ nhất — nên trong lúc chờ làm sạch dấu AI người dùng thấy một dòng chữ đứng im nhiều phút và tưởng ứng dụng bị treo.

## What Changes

- Đổi mặc định backend làm sạch dấu AI sang `cv2`, kèm nhãn tiếng Việt nói rõ đây là lựa chọn nhanh và cho kết quả tương đương.
- Truyền đúng hãng của clip vào bước làm sạch thay vì để dò tự động cả 6 hãng, dựa trên thông tin provider đã có trong dữ liệu clip.
- Chạy song song nhiều clip ở vòng lặp làm sạch dấu AI và chuẩn hoá clip, với số luồng phù hợp số nhân CPU và có thể cấu hình qua biến môi trường.
- Báo tiến độ theo từng clip trong lúc làm sạch dấu AI, và bổ sung mốc tiến độ cho giai đoạn ghép/xuất file cuối để thanh tiến độ không đứng im từ 75% đến 100%.
- Ghi lại kết luận rằng chuyển encode sang NVENC là hướng phản tác dụng trên máy mục tiêu, kèm số đo, để tránh thử lại.
- Không đổi thuật toán làm sạch, không đổi định dạng đầu ra, không đổi cấu trúc cache.

## Capabilities

### New Capabilities

- `ai-video-render-performance`: Mức song song của các bước xử lý theo từng clip trong luồng dựng MP4, quy tắc chọn backend làm sạch dấu AI mặc định, quy tắc truyền hãng clip vào bước làm sạch, và hợp đồng báo tiến độ theo bước thực tế đang chạy.

### Modified Capabilities

- Không có. `openspec/specs/` chưa sync capability nào; change này mở rộng luồng render hiện hữu và giữ nguyên kết quả đầu ra.

## Impact

- Luồng render: `backend/services/video_rendering.py` — vòng lặp theo từng clip chuyển sang chạy song song, bổ sung mốc báo tiến độ, tổng hợp kết quả cache theo cách an toàn khi có nhiều luồng.
- Làm sạch dấu AI: `backend/services/video_watermark_cleanup.py` — quy tắc suy ra hãng của clip khi gọi worker.
- Cấu hình render: `backend/models.py` — mặc định của backend làm sạch dấu AI.
- Giao diện: `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` — nhãn tiếng Việt cho lựa chọn backend, mặc định mới.
- Kiểm thử: `backend/tests/test_ai_video_backend.py` — ca cho chạy song song, thứ tự clip sau khi ghép, suy ra hãng clip, và mặc định mới.
- Phụ thuộc: không thêm gói mới. Không cần `onnxruntime-gpu`, không cần FFmpeg khác.
- Không đổi: thuật toán làm sạch dấu AI, khoá một job render tại một thời điểm, cấu trúc và khoá cache, nhánh audio, cơ chế phụ đề.
