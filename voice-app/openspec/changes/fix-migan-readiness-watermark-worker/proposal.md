## Why

Người dùng bật "Làm sạch dấu AI trước khi dựng" rồi chọn cách lấp vùng "Đẹp hơn — MI-GAN" thì readiness trả lỗi `Backend MI-GAN chưa sẵn sàng: No module named 'huggingface_hub'`. Nguyên nhân là venv của repo `remove-ai-watermarks` chưa được sync extra `migan`, còn script setup lại chỉ tìm `uv` trên `PATH` nên người dùng không có đường tự sửa. Thêm vào đó, readiness hiện chỉ probe backend đang chọn và không biết model ONNX đã cache hay chưa, nên báo xanh xong vẫn có thể fail giữa lúc dựng MP4.

## What Changes

- Script `setup-watermark-worker.ps1` tìm `uv` theo thứ tự: `PATH` trước, sau đó fallback sang `uv.exe` đi kèm venv backend trong dự án; chỉ báo lỗi khi cả hai đều không có.
- Worker `--check --backend migan` báo thêm trạng thái cache của model MI-GAN (`andraniksargsyan/migan` / `migan.onnx`) bằng cách tra HuggingFace cache mà không tải model.
- Readiness vẫn coi MI-GAN là sẵn sàng khi model chưa cache, nhưng phát cảnh báo rõ rằng lần dựng đầu cần mạng và tải khoảng 28 MB, thay vì để người dùng phát hiện lúc render.
- Thông báo lỗi thiếu dependency của worker nêu rõ Python/venv đang chạy và lệnh setup cần chạy, thay vì chỉ trả nguyên văn `No module named ...`.
- Readiness báo trạng thái theo từng backend cleanup (`cv2` và `migan`) thay vì chỉ backend đang chọn, và chỉ probe khi cleanup được bật.
- UI đánh dấu/khoá lựa chọn cách lấp vùng chưa sẵn sàng ngay trong dropdown, kèm lý do, thay vì để người dùng chọn rồi mới thấy lỗi.
- Tài liệu `docs/ai-video-watermark-cleanup.md` cập nhật phần chuẩn bị worker và ghi chú model MI-GAN theo hành vi mới.

## Capabilities

### New Capabilities

- `ai-video-watermark-backend-readiness`: Phát hiện và báo cáo mức sẵn sàng của từng backend lấp vùng watermark (dependency, Python/venv đang dùng, trạng thái cache model), thông báo lỗi có hướng dẫn tự sửa, và hành vi UI khi một backend chưa dùng được.

### Modified Capabilities

- Không có. `openspec/specs/` chưa có capability nào được sync; change này mở rộng readiness của pipeline watermark cleanup hiện hữu nhưng giữ nguyên contract khi cleanup tắt.

## Impact

- Script setup: `scripts/setup-watermark-worker.ps1` (phân giải `uv`).
- Worker cô lập: `backend/workers/video_watermark_worker.py` (payload `--check`, thông báo lỗi dependency, kiểm tra cache model).
- Service readiness: `backend/services/video_watermark_cleanup.py` (`WatermarkRuntimeStatus` mang thêm trạng thái cache model), `backend/services/video_rendering.py` (probe từng backend, dựng cảnh báo).
- Contract API: `backend/models.py` (`VideoRenderReadinessResponse`), `app/src/lib/api/types.ts`.
- Frontend: `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` (đánh dấu lựa chọn chưa sẵn sàng).
- Môi trường: venv của repo `remove-ai-watermarks` cần được sync extra `migan` (`onnxruntime`, `huggingface-hub`) bằng `uv` trong dự án.
- Tài liệu: `docs/ai-video-watermark-cleanup.md`.
- Không đổi: pipeline dựng video/audio, phạm vi watermark (vẫn chỉ visible mark + metadata đã xác minh, không xử lý SynthID/watermark ẩn), backend `lama`, và hành vi khi cleanup tắt.
