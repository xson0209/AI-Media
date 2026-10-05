## Why

Product Video hiện sinh được shot và prompt nhưng dừng trước bước gọi provider, tải clip và dựng MP4. Người dùng phải tự chuyển prompt sang công cụ bên ngoài, tải từng clip về và ghép thủ công, nên luồng sản xuất thiếu tính tự động, khó tiếp tục sau lỗi và khó kiểm soát request/chi phí. Change này bổ sung tích hợp htmustc Video API để một project chọn một model Gemini, chạy generation có kiểm soát và đưa các clip hợp lệ vào pipeline render hiện có.

## What Changes

- Thêm provider adapter cho `https://htmustc.id.vn/v1/videos/generations`, hỗ trợ các model alias `gemini-veo-3-1` và `gemini-omni-flash`.
- Cho phép mỗi Product Video project chọn đúng một model, resolution, aspect ratio và thời lượng được provider hỗ trợ; không tự động đổi model trong cùng một generation job.
- Thêm preflight trước khi gọi provider để kiểm tra prompt, capability, API key, duration, FFmpeg/ffprobe, dung lượng lưu trữ và job đang chạy.
- Thêm generation job và item theo từng shot, có prompt revision/fingerprint, idempotency, queue, giới hạn concurrency, retry có backoff, pause, resume, cancel và khôi phục sau restart.
- Tải video về staging, xác minh file bằng hash và ffprobe, sau đó import clip hợp lệ vào render bridge đúng `shot_id`.
- Tự động hoặc thủ công tạo `VideoRenderJob` sau khi toàn bộ clip sẵn sàng; tái sử dụng FFmpeg render hiện có để xuất MP4 thành phẩm.
- Bổ sung các profile auto-run: chỉ sinh prompt, sinh prompt và clip, hoặc sinh prompt, clip và render; hỗ trợ review gate trước generation/render.
- Bổ sung trạng thái và thao tác UI cho queue, tiến độ từng shot, retry shot lỗi, pause/resume/cancel, render lại và tải video thành phẩm.
- Giữ nguyên luồng Product Video prompt hiện tại và luồng Veo/Flow qua Chrome của AI Video; tích hợp mới không tự động gọi hai model cho cùng một shot.
- Không đưa API key, signed URL hoặc thông tin nhạy cảm vào frontend, response hay log.

## Capabilities

### New Capabilities

- `product-video-api-generation`: Tạo clip Product Video qua htmustc với một model đã chọn, quản lý job/item, queue, download, validation, import và retry an toàn.
- `product-video-auto-run-render`: Điều phối các profile auto-run từ prompt đến clip và MP4, có review gate, render gate, pause/resume/cancel và khôi phục sau lỗi.

### Modified Capabilities

Không có spec hiện hành trong `openspec/specs/` mô tả Product Video hoặc generation provider cần sửa trực tiếp. Các thay đổi đối với Product Video prompt-only được mở rộng qua hai capability mới ở trên.

## Impact

- Backend Product Video: route, service, model Pydantic, database model/migration và worker orchestration.
- Backend provider layer: HTTP client, secret/configuration, normalized provider response, polling hoặc immediate-download handling theo response contract của htmustc.
- Backend video storage/import/render: staging download, ffprobe validation, `VideoShotClip`, render bridge và `VideoRenderJob`.
- Frontend Product Video: lựa chọn model/provider settings, auto-run profile, queue progress, item actions, review gate và final output.
- API contract mới cho generation jobs và provider configuration; cần mock contract tests và integration tests với fixture MP4/FFmpeg.
- Dependency bên ngoài: htmustc API, API key, giới hạn rate/concurrency, schema response và endpoint polling/download cần được xác nhận trước implementation.
