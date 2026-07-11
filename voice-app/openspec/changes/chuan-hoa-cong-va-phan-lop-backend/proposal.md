## Why

Frontend, backend và Tauri hiện vẫn có nhiều điểm cấu hình cổng/địa chỉ máy chủ rải ở script, Docker, Rust bridge, biến môi trường Vite và FastAPI CORS. Backend cũng đã lớn nhanh theo các luồng AI Video, khiến các file định tuyến/dịch vụ/kiểu dữ liệu quá dài và khó kiểm soát khi thêm phụ đề, render, chạy tự động hoặc quản lý tài nguyên.

Thay đổi này chuẩn hóa ranh giới frontend/backend và cấu trúc backend theo cấu hình/phân lớp/tính năng để giảm phụ thuộc chéo, dễ kiểm thử và dễ mở rộng, nhưng vẫn giữ hành vi công khai hiện có cho người dùng.

## What Changes

- Tách rõ hợp đồng chạy ứng dụng giữa frontend Vite và backend FastAPI: frontend mặc định chạy cổng `5173`, backend mặc định chạy cổng `17493`, có thể ghi đè qua cấu hình/biến môi trường thống nhất.
- Gom các cấu hình backend quan trọng vào một lớp cấu hình trung tâm: máy chủ/cổng, nguồn CORS, thư mục dữ liệu, thư mục model/cache, cờ tính năng và địa chỉ công khai dùng cho frontend/Tauri.
- Chuẩn hóa client API phía frontend để lấy địa chỉ backend từ một nguồn rõ ràng, tránh hardcode trùng giữa web, Tauri và script.
- Tái cấu trúc backend theo phân lớp và tính năng: lõi cấu hình/vòng đời/lỗi, định tuyến API mỏng, tính năng gồm dịch vụ/kho dữ liệu/schema/trạng thái, database/session tách riêng.
- Ưu tiên tách dần các vùng AI Video lớn như dự án, chạy tự động, render, phụ đề/caption và quản lý tài nguyên ra khỏi các file định tuyến/dịch vụ quá dài.
- Giữ tương thích cho API route, schema phản hồi, đường dẫn lưu trữ và command/script hiện có; mọi đổi tên file/module nội bộ phải có wrapper hoặc đường chuyển tiếp khi cần.
- Không thay đổi hành vi UI, pipeline render, model backend hoặc dữ liệu dự án trong change này ngoài các điều chỉnh cần thiết để code đi qua cấu trúc mới.
- Không có **BREAKING** change dự kiến.

## Capabilities

### New Capabilities
- `chuan-hoa-cong-va-phan-lop-backend`: Định nghĩa contract cho việc tách cổng frontend/backend, cấu hình chạy ứng dụng tập trung và cấu trúc backend theo phân lớp/tính năng trong khi giữ tương thích API công khai hiện có.

### Modified Capabilities
- Không có. Hiện `openspec/specs/` chưa có spec đã archive, nên change này tạo capability mới để ràng buộc tái cấu trúc kiến trúc mà không sửa requirement của capability cũ.

## Impact

- Script chạy/dev: `package.json`, `start.sh`, `justfile`, `Dockerfile`, `docker-compose.yml`.
- Entry/cấu hình backend: `backend/app.py`, `backend/main.py`, `backend/config.py`, vòng đời startup/shutdown, thiết lập CORS và endpoint health/resource.
- Cấu trúc backend: `backend/routes/`, `backend/services/`, `backend/models.py`, `backend/database/`, `backend/utils/`, các module AI Video lớn.
- Ranh giới API frontend: `app/src/lib/api/client.ts`, `app/src/stores/serverStore.ts`, `web/src/platform/lifecycle.ts`, các biến `VITE_*` liên quan.
- Tauri bridge: `tauri/src-tauri/src/main.rs` và logic khởi chạy backend local.
- Kiểm thử: unit/API test backend cho cấu hình, tương thích route, startup health; frontend test hoặc typecheck cho client API/địa chỉ backend.
