## Why

Luồng AI Video đang phải tải các model local nặng cho TTS/STT/LLM, giữ dữ liệu voice prompt trong RAM và chạy lại FFmpeg normalize clip khi render nhiều lần. Trên máy Apple Silicon 16GB, điều này dễ làm RAM và unified GPU memory giữ mức cao sau khi job đã xong, trong khi thao tác sửa phụ đề/voice/style vẫn phải xử lý lại media không đổi.

Thay đổi này bổ sung cơ chế quản lý tài nguyên local rõ ràng cho AI Video: vẫn giữ các đường chạy nóng đủ nhanh, nhưng tự giải phóng RAM/GPU và tái sử dụng intermediate trên disk khi an toàn.

## What Changes

- Thêm chính sách quản lý tài nguyên AI Video để theo dõi model backend đang loaded, lần dùng gần nhất, job đang chạy và áp lực RAM/GPU của máy.
- Tự unload model local khi idle quá thời gian cấu hình và giới hạn số model nặng được giữ loaded cùng lúc.
- Thêm memory cache có giới hạn cho voice prompt theo LRU/TTL, đồng thời giữ disk cache để tái sử dụng lâu dài.
- Thêm cơ chế kiểm soát cache MLX trên Apple Silicon để giới hạn hoặc clear allocator cache khi job đã idle hoặc khi memory pressure cao.
- Thêm render intermediate cache cho clip đã normalize và các bước video/audio có thể tái sử dụng, keyed theo source clip và render settings.
- Hiển thị trạng thái tài nguyên qua backend/API/UI để người dùng thấy model đang loaded, memory pressure, dung lượng cache và thao tác cleanup thủ công.
- Thêm quy tắc cleanup thận trọng để không bao giờ ngắt job TTS, transcription, LLM hoặc render đang chạy.

## Capabilities

### New Capabilities
- `quan-ly-tai-nguyen-ai-video`: Định nghĩa chính sách RAM/GPU local cho AI Video, gồm vòng đời model, cache có giới hạn, cleanup cache MLX, tái sử dụng render intermediate, telemetry và điều khiển cleanup thủ công.

### Modified Capabilities

Không có. Hiện chưa có spec đã archive dưới `openspec/specs/`, nên thay đổi này tạo contract mới về quản lý tài nguyên và tham chiếu các code path AI Video/TTS/render hiện có như vùng triển khai bị ảnh hưởng.

## Impact

- Vòng đời model backend: `backend/backends/__init__.py`, các method `load_model`/`unload_model` của từng backend, `backend/services/tts.py`, `backend/services/transcribe.py`, `backend/services/llm.py`.
- Điều phối job: `backend/services/task_queue.py`, `backend/services/video_auto_runs.py`, `backend/services/video_voice.py`, `backend/routes/llm.py`, `backend/routes/transcription.py`.
- Hành vi cache: `backend/utils/cache.py`, `backend/services/profiles.py`, các thư mục render intermediate của AI Video trong project storage.
- Pipeline render: `backend/services/video_rendering.py`, API render readiness/job và xử lý stale output.
- Observability/API/UI: health/model/task endpoints, model management UI, AI Video render panel hoặc system resource panel.
- Test: unit test backend cho policy tài nguyên/cache key, test tái sử dụng render cache và API test tập trung cho cleanup thủ công/idle-unload an toàn.
