## 1. Worker và runtime boundary

- [x] 1.1 Tạo standalone Python watermark worker có `--check`, JSON stdin/stdout và cưỡng bức `include_invisible=false`.
- [x] 1.2 Tạo backend adapter tìm package root/Python, truyền PYTHONPATH/PATH FFmpeg, lấy runtime revision và chuẩn hóa lỗi/timeout.
- [x] 1.3 Thêm setup/documentation cho development worker mà không auto-install dependency trong readiness.

## 2. Settings và readiness

- [x] 2.1 Mở rộng Pydantic render settings/readiness với cleanup default off, backend `cv2|migan` và runtime status/revision.
- [x] 2.2 Mở rộng render readiness để chỉ probe worker khi cleanup bật và trả lỗi tiếng Việt khi runtime thiếu.
- [x] 2.3 Mở rộng FastAPI readiness query để nhận và validate cleanup settings.

## 3. Cache và pipeline render

- [x] 3.1 Implement watermark derivative cache versioned theo source identity, mark/backend/policy và worker revision.
- [x] 3.2 Tích hợp cleanup per clip trước normalize, explicit `veo` cho provider Veo và `auto` cho source không xác định.
- [x] 3.3 Giữ audio builder dùng active source clip, publish temp output atomically và fail strict khi worker/output lỗi.
- [x] 3.4 Ghi cleanup settings, per-shot results, worker revision và cache hit/miss vào timeline manifest/cache summary.

## 4. Frontend và API client

- [x] 4.1 Mở rộng TypeScript render settings/readiness types và API query serialization.
- [x] 4.2 Thêm UI tiếng Việt trong render panel: toggle mặc định tắt, backend selector và thông báo quyền sử dụng/giữ source.
- [x] 4.3 Hiển thị trạng thái worker/readiness trung thực và không cung cấp invisible/auto/LaMa trong UI.

## 5. Verification tự động

- [x] 5.1 Thêm unit tests cho worker protocol, runtime discovery, FFmpeg PATH và lỗi dependency/timeout.
- [x] 5.2 Thêm tests cache hit/miss/invalidation, source preservation và cleanup result parsing.
- [x] 5.3 Thêm backend render/readiness/API tests cho cleanup off, worker unavailable, Veo routing, no-signal và strict failure.
- [x] 5.4 Chạy backend targeted tests, Ruff/compile checks liên quan và sửa lỗi.
- [x] 5.5 Chạy frontend typecheck/build cho API types và render panel, sửa lỗi nếu có.

## 6. OpenSpec verify

- [x] 6.1 Validate OpenSpec artifacts và đối chiếu implementation với mọi requirement/scenario.
- [x] 6.2 Ghi residual risks hoặc manual checks chưa thể chạy, bảo đảm không archive change trong command `feat` này.

## Verification notes — 2026-08-02

- `openspec validate tich-hop-lam-sach-watermark-ai-khi-dung-mp4` pass; proposal/design/spec/tasks đều complete.
- Backend targeted suite pass 31 tests, gồm worker/cache/readiness/API/render/Veo native speech; worker-specific Ruff và Python compile pass.
- Frontend TypeScript typecheck, lint-only Biome check và production Vite build pass.
- Local `cv2` worker đã được setup tại checkout sibling, readiness pass với exact revision `94730f77d3d2499d74bac406f49a373cc9847c1f`; real no-signal MP4 smoke pass, giữ source và tạo derivative hợp lệ.
- Chưa chạy real MI-GAN render vì local setup hiện chỉ cài extra `video`; cần chạy `scripts/setup-watermark-worker.ps1 -Backend migan` và chấp nhận model download ở lần xử lý đầu nếu muốn manual-check backend này.
- Chưa chạy full PyInstaller binary build do chi phí build lớn; `backend/build_binary.py` đã compile và worker script được thêm bằng `--add-data` đúng đường dẫn runtime.
- Full-repo Ruff/Biome formatting vẫn có baseline violations từ worktree đang phát triển; kiểm tra scoped cho file mới, lint-only frontend, typecheck/build và targeted regressions đều pass. Không sửa hàng loạt các file bẩn ngoài phạm vi change.
- Change được giữ ở trạng thái active theo `$osf feat`; không archive.
