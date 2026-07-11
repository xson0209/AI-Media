## Kiểm kê runtime config

### Cổng và URL đã chuẩn hóa

- Backend Python runtime đọc `VOICEBOX_BACKEND_HOST`, `VOICEBOX_BACKEND_PORT`, legacy `VOICEBOX_PORT` qua `backend.core.config`.
- Frontend URL helper đọc `VITE_SERVER_URL`, `VITE_BACKEND_PORT`, current origin production và fallback `http://127.0.0.1:17493`.
- `start.sh`, `package.json`, `justfile`, `Dockerfile`, `docker-compose.yml` dùng biến cấu hình với default `17493`.
- Tauri Rust bridge đọc `VOICEBOX_BACKEND_PORT` hoặc `VOICEBOX_PORT` qua `server_port()`.
- Vite web/Tauri đọc `VOICEBOX_FRONTEND_PORT` với default `5173`.

### Hardcode còn giữ có chủ đích

- `17493` và `5173` trong `backend/core/config.py` là default contract.
- `17493`/`5173` trong tests là assertion cho default compatibility.
- `tauri/src-tauri/tauri.conf.json` vẫn giữ `devUrl` mặc định `http://localhost:5173` vì Tauri config JSON cần default tĩnh; Vite config vẫn hỗ trợ `VOICEBOX_FRONTEND_PORT`.
- README/docs có thể nhắc default `17493`/`5173` như tài liệu, không phải nguồn cấu hình runtime.

### Thư mục dữ liệu/model/cache

- `VOICEBOX_DATA_DIR`, `VOICEBOX_MODELS_DIR`, `VOICEBOX_CACHE_DIR` được gom vào `backend.core.config`.
- `backend.config` là wrapper tương thích cho `get_data_dir`, `get_db_path`, `get_profiles_dir`, `get_generations_dir`, `get_captures_dir`, `get_cache_dir`, `get_models_dir`, `to_storage_path`, `resolve_storage_path`.
