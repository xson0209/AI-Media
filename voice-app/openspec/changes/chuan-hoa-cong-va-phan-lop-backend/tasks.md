## 1. Chuẩn hóa cấu hình runtime backend

- [x] 1.1 Kiểm kê toàn bộ nơi đang dùng cổng `17493`, cổng `5173`, backend URL, CORS origins, data directory, model directory và cache directory.
- [x] 1.2 Tạo lớp cấu hình backend tập trung cho host/cổng, CORS, thư mục dữ liệu, thư mục model/cache và cờ tính năng với default tương thích hiện tại.
- [x] 1.3 Giữ `backend/config.py` làm wrapper tương thích cho các helper path/import cũ trong giai đoạn chuyển tiếp.
- [x] 1.4 Thêm test backend cho default config, env override, path resolution và CORS origins.

## 2. Đồng bộ cổng frontend/backend ở script, Docker và Tauri

- [x] 2.1 Cập nhật `package.json`, `start.sh`, `justfile`, `Dockerfile` và `docker-compose.yml` để đọc cổng/backend URL từ cùng contract hoặc cùng biến cấu hình.
- [x] 2.2 Cập nhật Tauri Rust bridge để dùng cấu hình cổng backend thống nhất thay vì hardcode phân tán.
- [x] 2.3 Đảm bảo default vẫn là frontend `5173` và backend `17493` khi không có override.
- [x] 2.4 Kiểm chứng health check, shutdown và phát hiện backend local vẫn hoạt động trong dev/desktop.

## 3. Chuẩn hóa URL backend ở frontend

- [x] 3.1 Tạo hoặc củng cố helper/store duy nhất để resolve backend URL cho web, desktop và production served-by-backend.
- [x] 3.2 Cập nhật API client, web lifecycle và web platform để dùng helper/store chung thay vì fallback riêng.
- [x] 3.3 Giữ hỗ trợ `VITE_SERVER_URL`, URL do Tauri trả về, URL người dùng đã lưu và fallback `http://127.0.0.1:17493`.
- [x] 3.4 Chạy typecheck frontend và thêm test/coverage nếu codebase đã có harness phù hợp cho URL resolution.

## 4. Tách lõi ứng dụng backend

- [x] 4.1 Tạo skeleton `backend/core/` cho cấu hình, logging, lifecycle và lỗi dùng chung.
- [x] 4.2 Tách CORS setup, frontend static mount và startup/shutdown khỏi `backend/app.py` theo từng module nhỏ.
- [x] 4.3 Giữ `backend.main:app` và app factory hiện có tương thích với command dev/test cũ.
- [x] 4.4 Thêm regression test cho health/startup và route registration sau khi tách lõi.

## 5. Phân lớp API và tính năng AI Video

- [x] 5.1 Tạo skeleton `backend/api/routes/` và `backend/features/ai_video/` với wrapper để route registry cũ không bị gãy.
- [x] 5.2 Đưa phần AI Video projects qua module feature bridge riêng, giữ schema và endpoint public tương thích.
- [x] 5.3 Đưa phần AI Video auto-runs qua module feature bridge riêng, giữ trạng thái run và API response tương thích.
- [x] 5.4 Đưa phần render qua module feature bridge riêng, giữ output path, readiness check và job behavior tương thích.
- [x] 5.5 Đưa phần phụ đề/caption qua module feature bridge riêng nếu đang nằm chung với route/service lớn.
- [x] 5.6 Tách resource management hoặc helper dùng chung sang lớp lõi/tính năng phù hợp, tránh import vòng.

## 6. Tách schema, model và truy cập dữ liệu thận trọng

- [x] 6.1 Kiểm kê các model/schema trong `backend/models.py` theo domain và caller hiện có.
- [x] 6.2 Tách schema AI Video sang module feature khi không làm đổi JSON public.
- [x] 6.3 Tách truy cập database/session vào boundary rõ ràng, giữ helper cũ nếu caller chưa chuyển.
- [x] 6.4 Thêm test mở lại dự án AI Video đã lưu để xác nhận path/media/metadata/render state không bị ảnh hưởng.

## 7. Kiểm thử tương thích và dọn dẹp

- [x] 7.1 Chạy test backend liên quan CORS, health, config, AI Video projects, auto-runs, render và phụ đề/caption.
- [x] 7.2 Chạy typecheck/lint frontend và backend theo command hiện có trong repo.
- [x] 7.3 Tìm lại hardcode `17493`, `5173` và backend URL để phân loại: giữ có chủ đích, đổi sang config hoặc cập nhật test.
- [x] 7.4 Cập nhật README/dev docs cho cách override cổng và cấu trúc backend mới.
- [x] 7.5 Giữ wrapper tạm khi vẫn còn caller cũ và test chứng minh public behavior không đổi.
