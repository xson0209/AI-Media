## 1. Cấu trúc, cấu hình và bảo mật

- [x] 1.1 Tạo package `backend/services/automation_hub` với boundary config, security, assets, Roxy, sidecar, publishers và jobs độc lập.
- [x] 1.2 Thêm feature flag/backend config cho Automation Hub, publishing concurrency, giới hạn file, Roxy Local API và Playwright MCP loopback.
- [x] 1.3 Thêm dependency mã hóa chuẩn và secret store Fernet dùng env key hoặc local key file trong data directory.
- [x] 1.4 Bảo đảm secret API key/token/client secret chỉ được lưu ciphertext, có fingerprint và không xuất hiện trong response/log/error.
- [x] 1.5 Thêm storage helpers cho assets, sidecar logs và ba repo RoxyBrowser ngoài source tree.

## 2. Database và schema API

- [x] 2.1 Thêm ORM models `AutomationConnection`, `AutomationAsset`, `AutomationPublishJob` và `AutomationPublishAttempt`.
- [x] 2.2 Thêm migration idempotent, foreign key và indexes cho platform/status/schedule cùng unique idempotency key.
- [x] 2.3 Export models qua `backend.database` và thêm Pydantic request/response không lộ secret.
- [x] 2.4 Thêm startup recovery để job active mất runtime chuyển interrupted mà không tự upload lại.
- [x] 2.5 Thêm delete lifecycle riêng cho connection/asset/job, chặn xóa asset/connection đang được job active dùng.

## 3. RoxyBrowser và MCP sidecar

- [x] 3.1 Implement Local API client với health, workspaces, profiles, open, close và connection info; header token luôn được redaction.
- [x] 3.2 Implement connection CRUD/check cho Roxy Local API và map lỗi desktop/key/profile bằng tiếng Việt.
- [x] 3.3 Implement Playwright MCP health/status và sidecar process manager chỉ chạy entry path đã cấu hình, không nhận command tùy ý từ client.
- [x] 3.4 Thêm API `/automation-hub/status`, `/connections`, `/roxy/*` và `/sidecar/*` dưới feature guard phù hợp.
- [x] 3.5 Thêm script PowerShell setup/update/build ba repo RoxyBrowser trong data directory và tài liệu prerequisite/runtime.

## 4. Asset và publishing adapters

- [x] 4.1 Implement upload/import asset an toàn, validate extension/size, hash SHA-256 và snapshot vào kho Hub.
- [x] 4.2 Implement interface publisher canonical và error/result types đã redaction.
- [x] 4.3 Implement YouTube token refresh, resumable `videos.insert`, privacy và `publishAt` scheduling.
- [x] 4.4 Implement Facebook Page video upload và scheduling bằng Graph Video API; từ chối personal profile.
- [x] 4.5 Implement TikTok Draft init, chunk upload và publish-id/status contract.
- [x] 4.6 Thêm TikTok Direct Post guard feature flag/audit và từ chối trước upload khi chưa bật.

## 5. Publishing queue, API và phục hồi

- [x] 5.1 Implement tạo/list/get job với idempotency key, asset/connection validation và metadata canonical.
- [x] 5.2 Implement worker/scheduler FIFO concurrency riêng, scheduled-at và transaction ngắn không giữ DB session trong network upload.
- [x] 5.3 Implement attempts, bounded retry cho lỗi an toàn và trạng thái outcome mơ hồ không tự đăng lại.
- [x] 5.4 Implement cancel queued/scheduled, cancel checkpoint active và retry thủ công có duplicate guard.
- [x] 5.5 Thêm API asset upload/list/delete và publishing job create/list/get/cancel/retry.
- [x] 5.6 Thêm resource snapshot Hub riêng mà không sửa workflow/planning/voice resource counters hiện có.

## 6. Frontend Automation Hub

- [x] 6.1 Thêm TypeScript types và API client cho status, connection, Roxy, sidecar, asset và publishing job.
- [x] 6.2 Thêm route `/automation-hub`, wide workspace mode và sidebar entry độc lập.
- [x] 6.3 Tạo màn Automation Hub hiển thị feature/security/runtime prerequisite và hướng dẫn bật cấu hình.
- [x] 6.4 Thêm panel RoxyBrowser để lưu key, kiểm tra health, chọn workspace/profile, mở/đóng và xem MCP sidecar status.
- [x] 6.5 Thêm panel connection YouTube/Facebook/TikTok; input secret không được điền lại sau khi lưu.
- [x] 6.6 Thêm asset upload và form tạo job gồm platform, title, description, tags, privacy/mode và lịch.
- [x] 6.7 Thêm bảng job polling riêng, trạng thái tiếng Việt và action cancel/retry không khóa workflow khác.
- [x] 6.8 Kiểm tra responsive, keyboard focus, lỗi inline và không để secret xuất hiện trong DOM sau khi request hoàn tất.

## 7. Kiểm thử và xác minh

- [x] 7.1 Test migration/model/index/idempotency và project/database cũ vẫn mở được khi feature disabled.
- [x] 7.2 Test secret encryption/redaction/key-loss và update public config giữ secret cũ.
- [x] 7.3 Test Roxy client bằng `httpx.MockTransport`: health/workspace/list/open/close/connection info và token không lộ.
- [x] 7.4 Test asset path traversal, extension/size/hash và snapshot độc lập với file nguồn.
- [x] 7.5 Test YouTube/Facebook/TikTok adapters bằng mock transport, scheduling fields, chunk range và lỗi scope/token.
- [x] 7.6 Test queue FIFO, concurrency, cancel, retry, restart interrupted và outcome mơ hồ không duplicate.
- [x] 7.7 Test API feature guard, connection/job CRUD và response không có secret/ciphertext.
- [x] 7.8 Chạy focused backend pytest, Python compile, frontend typecheck/build và OpenSpec strict validation.
- [ ] 7.9 Manual smoke test RoxyBrowser Desktop health, danh sách profile, open/close và Playwright MCP health mà không kill process người dùng.
- [ ] 7.10 Manual upload thật YouTube/Facebook Page/TikTok Draft chỉ khi người dùng cung cấp credential/scope hợp lệ; ghi limitation/audit thực tế.
