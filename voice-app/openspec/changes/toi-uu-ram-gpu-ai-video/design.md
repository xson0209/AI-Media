## Context

AI Video hiện dùng nhiều tài nguyên local trong cùng một phiên làm việc:

- TTS/voice chạy qua `backend/services/task_queue.py`, queue đã serialize inference để tránh tranh GPU.
- Model backend được giữ trong các singleton/global map ở `backend/backends/__init__.py`; mỗi engine có thể giữ model loaded cho đến khi unload thủ công hoặc shutdown.
- Voice prompt cache hiện có memory dict không giới hạn trong `backend/utils/cache.py`, đồng thời có disk cache.
- Render MP4 tạo thư mục `render_intermediates/<job_id>` riêng cho từng job trong `backend/services/video_rendering.py`, nên render lại có thể normalize clip lại dù source/settings không đổi.
- Trên Apple Silicon, MLX/Metal dùng unified memory nên người dùng thấy RAM và GPU cùng tăng.

Ràng buộc chính: cleanup tài nguyên không được làm hỏng job đang chạy. Ưu tiên là giảm memory giữ lâu sau job và giảm việc xử lý lại khi render nhiều vòng, không phải tối đa hóa benchmark đơn lẻ.

## Goals / Non-Goals

**Goals:**

- Có một lớp quản lý tài nguyên local để biết model/cache/job nào đang active hoặc idle.
- Tự unload model idle và giới hạn số model nặng loaded đồng thời.
- Giới hạn voice prompt memory cache bằng LRU/TTL nhưng vẫn giữ disk cache.
- Quản lý MLX cache trên Apple Silicon khi queue idle hoặc memory pressure cao.
- Tái sử dụng render intermediate hợp lệ giữa các lần render.
- Hiển thị resource status và cleanup thủ công cho người dùng.
- Có test cho safety: không unload/clear tài nguyên đang active.

**Non-Goals:**

- Không thay đổi chất lượng model, thuật toán TTS/STT/LLM hoặc prompt generation.
- Không thêm engine mới, quantization mới hoặc dependency nặng mới.
- Không chạy nhiều TTS inference song song trên GPU.
- Không xóa model HuggingFace disk cache tự động nếu người dùng không yêu cầu.
- Không thay thế toàn bộ render pipeline; chỉ thêm cache/reuse quanh pipeline hiện có.

## Decisions

### 1. Tạo ResourceManager trung tâm

Thêm service backend mới, ví dụ `backend/services/resource_manager.py`, chịu trách nhiệm:

- ghi nhận model load/use/unload theo key `kind:engine:model_size`;
- đọc trạng thái active từ generation queue, task manager, render jobs và auto-run;
- quyết định cleanup theo policy;
- cung cấp snapshot cho API/UI.

Lý do: policy cần nhìn xuyên qua TTS/STT/LLM/render. Nếu mỗi backend tự cleanup riêng, sẽ khó biết model nào đang được queue cần dùng tiếp.

Alternatives considered:

- Cleanup trong từng backend: đơn giản hơn nhưng dễ race với queue và khó áp dụng giới hạn global.
- Chỉ thêm nút unload thủ công: ít rủi ro nhưng không giải quyết phiên làm việc dài.

### 2. Model lifecycle dùng idle timeout + heavy-model limit

ResourceManager phân loại model nặng dựa trên metadata registry (`size_mb`, engine, model_size). Khi load model mới, manager kiểm tra giới hạn model nặng loaded đồng thời và unload model idle ít dùng gần đây nhất nếu cần.

Các backend vẫn giữ method `load_model`/`unload_model`; thay đổi là route/service gọi qua wrapper hoặc hook để update `last_used_at`.

Policy mặc định đề xuất:

- `idle_unload_seconds`: 600 giây.
- `max_loaded_heavy_models`: 1 trên máy local mặc định.
- `heavy_model_threshold_mb`: 1000 MB.
- Cleanup chỉ chạy khi không có active job dùng model đó.

### 3. Voice prompt memory cache chuyển sang bounded LRU

Giữ disk cache `.prompt` hiện có, nhưng memory cache trong `backend/utils/cache.py` chuyển từ dict không giới hạn sang LRU có metadata:

- `last_accessed_at`;
- `created_at`;
- `estimated_bytes`;
- `source`: memory/disk.

Khi vượt quota, chỉ evict khỏi RAM; disk cache vẫn còn. Điều này giảm RAM phình dần nhưng vẫn giữ tốc độ tốt cho profile hay dùng.

### 4. MLX cache cleanup chỉ chạy khi idle

Trên venv hiện có `mlx.core.clear_cache`, `get_cache_memory`, `set_cache_limit` và `metal.get_active_memory`. ResourceManager chỉ gọi cleanup khi:

- backend type là MLX;
- generation queue không có running job;
- không có model đang load/inference;
- MLX cache vượt ngưỡng hoặc host memory pressure cao.

Không clear MLX cache giữa một generation để tránh ảnh hưởng inference.

### 5. Render intermediate cache dùng content/settings key

Thay vì chỉ ghi intermediate theo job id, thêm cache bền vững theo project hoặc global:

`render_cache/normalized/<cache_key>.mp4`

Cache key nên gồm:

- source clip artifact path hoặc file hash/mtime/size;
- shot/timeline duration target;
- resolution;
- fps;
- fit mode;
- background color;
- duration mode/freeze behavior;
- version của normalize command.

Nếu key hit, render dùng lại normalized clip. Nếu subtitle/voice thay đổi nhưng clip/settings không đổi, bước normalize được bỏ qua. Nếu source/settings đổi, cache miss tự nhiên.

### 6. API/UI hiển thị trạng thái và cleanup an toàn

Thêm endpoint resource status và cleanup, ví dụ:

- `GET /resources/status`
- `POST /resources/cleanup`
- `POST /resources/render-cache/clear`

UI có thể đặt trong Model Management hoặc AI Video Render Panel:

- model loaded/idle;
- memory pressure;
- voice prompt memory cache;
- MLX cache nếu có;
- render cache size;
- nút "Giải phóng RAM/GPU" và "Dọn render cache".

### 7. Không dùng cache để che lỗi stale data

Mỗi cache phải có key đủ rõ hoặc invalidation rõ. Nếu không chắc key đầy đủ, ưu tiên cache miss thay vì dùng lại sai output.

## Risks / Trade-offs

- Idle unload làm lần tạo voice tiếp theo chậm hơn do phải load lại model → Dùng timeout đủ dài, chỉ unload khi idle, và hiển thị trạng thái để người dùng hiểu.
- Cleanup có thể race với job vừa được enqueue → ResourceManager phải kiểm tra cả queued/running jobs và dùng lock policy quanh cleanup.
- LRU memory cache giảm RAM nhưng có thể làm prompt load từ disk thường xuyên hơn → Disk cache vẫn nhanh hơn tạo prompt mới; quota mặc định nên đủ cho vài profile gần nhất.
- Render cache tốn disk → Cần quota/dọn cache theo project, theo tuổi, và nút clear thủ công.
- Cache key render thiếu trường có thể dùng lại video sai → Key phải gồm source identity, settings quan trọng và version command.
- MLX memory metric khác nhau theo version → Gói gọi MLX trong adapter optional, fail-open nếu API không tồn tại.

## Migration Plan

1. Thêm ResourceManager ở trạng thái quan sát trước: đọc model/cache/job status nhưng chưa cleanup tự động.
2. Bật bounded voice prompt memory cache và test disk fallback.
3. Thêm manual cleanup endpoint/UI để người dùng giải phóng RAM/GPU chủ động.
4. Bật idle unload bằng default bảo thủ sau khi có active-job guard.
5. Thêm render intermediate cache với key versioned và cache cleanup.
6. Bổ sung telemetry/log để debug cache hit/miss, model unload và MLX cleanup.

Rollback: có thể tắt auto cleanup bằng env/config, giữ manual unload hiện có và bỏ qua render cache nếu cache key hoặc file cache không hợp lệ.

## Open Questions

- UI nên đặt resource panel trong Model Management hay ngay AI Video Render Panel, hay cả hai?
- Quota mặc định cho render intermediate cache nên là bao nhiêu trên máy 16GB/ổ đĩa nhỏ?
- Có cần cấu hình riêng cho "ưu tiên tốc độ" để giữ model loaded lâu hơn khi người dùng đang tạo nhiều shot liên tục không?
