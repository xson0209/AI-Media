## 1. Khảo sát và nền tảng resource status

- [x] 1.1 Xác định các điểm load/use/unload model hiện có cho TTS, STT và LLM.
- [x] 1.2 Xác định nguồn dữ liệu active job từ generation queue, task manager, render jobs và AI Video auto-run.
- [x] 1.3 Thêm service ResourceManager hoặc module tương đương để tạo snapshot tài nguyên local.
- [x] 1.4 Thêm model/schema response cho loaded models, cache metrics, memory pressure và cleanup actions.
- [x] 1.5 Thêm endpoint đọc resource status và kiểm tra response khi không có model loaded.

## 2. Quản lý vòng đời model

- [x] 2.1 Bọc các lần load model để ghi nhận model key, engine, model size, backend type và `last_used_at`.
- [x] 2.2 Bọc các lần unload model để cập nhật trạng thái ResourceManager.
- [x] 2.3 Thêm phân loại heavy model dựa trên registry metadata và cấu hình threshold.
- [x] 2.4 Implement idle-unload policy với guard không unload model đang active hoặc queued.
- [x] 2.5 Implement giới hạn số heavy model loaded đồng thời bằng LRU idle model.
- [x] 2.6 Thêm cấu hình env/default cho idle timeout, heavy model limit và ngưỡng memory.

## 3. Voice prompt memory cache có giới hạn

- [x] 3.1 Chuyển `_memory_cache` sang cấu trúc LRU có metadata last access, created time và estimated size.
- [x] 3.2 Giữ disk cache `.prompt` hiện có và đảm bảo evict RAM không xóa disk cache.
- [x] 3.3 Thêm cấu hình giới hạn số entry, TTL hoặc dung lượng ước tính cho memory cache.
- [x] 3.4 Thêm metric cache hit từ memory, hit từ disk, miss và số entry bị evict.
- [x] 3.5 Thêm cleanup action để clear voice prompt memory cache độc lập với disk cache.

## 4. MLX cache và memory pressure

- [x] 4.1 Thêm adapter optional cho MLX memory APIs (`get_cache_memory`, `clear_cache`, `set_cache_limit`, `metal.get_active_memory` nếu có).
- [x] 4.2 Hiển thị MLX cache/active memory trong resource status khi backend là MLX.
- [x] 4.3 Áp dụng `set_cache_limit` nếu cấu hình được bật và MLX hỗ trợ API.
- [x] 4.4 Clear MLX cache khi generation queue idle và cache vượt ngưỡng.
- [x] 4.5 Đảm bảo MLX cleanup không chạy giữa generation hoặc model load đang active.

## 5. Render intermediate cache

- [x] 5.1 Thiết kế cache key cho normalized clip gồm source identity, target duration, resolution, fps, fit mode, background color, duration mode và command version.
- [x] 5.2 Thêm thư mục render cache bền vững theo project hoặc global, tách khỏi thư mục job output.
- [x] 5.3 Dùng lại normalized clip khi cache key hit và file cache còn tồn tại.
- [x] 5.4 Cache miss và tạo lại intermediate khi source clip, metadata hoặc render settings đổi.
- [x] 5.5 Thêm metric/log cho render cache hit, miss, stale và lỗi cache.
- [x] 5.6 Thêm cleanup render cache theo project và toàn cục với quota/tuổi file cấu hình được.

## 6. API và UI điều khiển cleanup

- [x] 6.1 Thêm endpoint cleanup thủ công để unload model idle, clear memory cache, clear MLX cache an toàn và trả về action summary.
- [x] 6.2 Thêm endpoint hoặc tham số để dọn render intermediate cache theo project.
- [x] 6.3 Cập nhật API client/type frontend cho resource status và cleanup actions.
- [x] 6.4 Hiển thị loaded models, memory pressure, cache metrics và render cache size trong UI phù hợp.
- [x] 6.5 Thêm nút "Giải phóng RAM/GPU" và trạng thái tài nguyên được giữ lại vì đang active.

## 7. Kiểm thử và xác minh

- [x] 7.1 Thêm unit test ResourceManager cho idle timeout, heavy-model limit và active-job guard.
- [x] 7.2 Thêm unit test voice prompt LRU cache, disk fallback và clear memory-only.
- [x] 7.3 Thêm test MLX adapter với mock API để xác minh cleanup chỉ chạy khi idle.
- [x] 7.4 Thêm test render cache key hit/miss cho đổi phụ đề, đổi clip và đổi render settings.
- [x] 7.5 Thêm API test cho resource status và cleanup thủ công.
- [x] 7.6 Chạy test backend liên quan và ghi lại các test không chạy được nếu môi trường thiếu MLX/torch/FFmpeg.
