## Why

AI Video hiện có thể tải clip Veo theo từng shot và dựng thành MP4, nhưng các clip provider có thể còn nhãn AI nhìn thấy hoặc metadata provenance. Người dùng cần một bước làm sạch có kiểm soát ngay trong lúc dựng, giữ nguyên clip gốc, không làm hỏng phụ đề/audio và không tuyên bố quá mức về các watermark ẩn không thể xác minh cục bộ.

## What Changes

- Thêm tùy chọn render để xử lý watermark AI nhìn thấy và metadata đã xác minh trên từng clip trước bước normalize/concat; mặc định tắt và không chạy khi người dùng chưa chọn.
- Định tuyến detector theo provider của clip, ưu tiên `veo` cho clip do luồng Veo/Flow tạo và dùng auto-detection có giới hạn cho clip upload khi được bật.
- Chạy thư viện remove-watermark qua worker Python cô lập có readiness, timeout, JSON result và FFmpeg path do Voicebox cung cấp; không import dependency diffusion vào backend chính.
- Lưu derivative đã xử lý trong cache versioned riêng, giữ nguyên file nguồn và ghi kết quả/fallback theo shot vào timeline manifest và render job diagnostics.
- Khi cleanup được yêu cầu, lỗi worker/encode là lỗi render rõ ràng; trường hợp không tìm thấy watermark được hỗ trợ là no-op hợp lệ, không được báo sai là đã xóa.
- Mở rộng API/types/UI tiếng Việt cho thiết lập, readiness, progress và cảnh báo quyền sử dụng; manual render và auto-render dùng cùng contract cấu hình.
- Không bật hoặc tích hợp xóa watermark ẩn/SynthID trong change này.

## Capabilities

### New Capabilities

- `ai-video-watermark-cleanup`: Cấu hình, readiness, xử lý watermark AI nhìn thấy/metadata theo clip, worker isolation, cache, manifest, lỗi và hành vi UI/auto-render.

### Modified Capabilities

- Không có capability chính đã sync dưới `openspec/specs/`; change mới mở rộng pipeline render hiện hữu nhưng giữ contract cũ khi cleanup tắt.

## Impact

- Backend render/settings/API: `backend/models.py`, `backend/routes/ai_video.py`, `backend/services/video_rendering.py` và một adapter/worker service mới.
- Auto-render/provider: `backend/services/video_auto_runs.py`, `backend/services/video_clip_generation.py` nếu cần truyền hoặc lưu render preference.
- Frontend: `app/src/lib/api/types.ts`, `app/src/lib/api/client.ts`, `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx`.
- Storage/cache: project subdirectory cho watermark derivatives và JSON reports; cache key phải gồm source identity, provider/mark, backend, policy version và worker revision.
- External dependency: checkout `D:/AI Media/AI Media Project/remove watermark` hiện có video API chưa phát hành theo tag ổn định; development dùng đường dẫn cấu hình, production phải pin exact revision hoặc artifact build tương đương.
- Verification: backend unit/API tests, cache/readiness/failure tests, frontend typecheck/build và hồi quy render/audio/subtitle.
