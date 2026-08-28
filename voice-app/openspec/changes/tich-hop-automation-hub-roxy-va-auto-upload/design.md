## Context

`voice-app` là ứng dụng local FastAPI + SQLite + React/Tauri. Repo hiện đã có các workflow dài cho AI Video, Video Inspiration, voice, render và Veo/Chrome; các workflow này có state machine, queue và giới hạn tài nguyên riêng. Change `12.tao-bo-noi-dung-dang-video-da-nen-tang` đã tạo metadata YouTube/TikTok/Facebook nhưng chủ ý không tự đăng. Change `3.tu-dong-tao-clip-veo-chrome` đã có Chrome/CDP automation dành riêng cho Veo nhưng không phải lớp quản lý anti-detect browser tổng quát.

Ba repo RoxyBrowser có vai trò khác nhau:

- `local-API` là tài liệu/mẫu client; Local API server thật nằm trong RoxyBrowser Desktop tại loopback, mặc định `http://127.0.0.1:50000`.
- `roxybrowser-mcp-server` quản lý workspace/profile/proxy/account và mở profile qua Local API.
- `roxybrowser-playwright-mcp` điều khiển trang sau khi kết nối endpoint CDP/BiDi, có thể chạy HTTP sidecar tại loopback.

Upload video phải ưu tiên API chính thức. YouTube hỗ trợ resumable upload và scheduling; Facebook chỉ hỗ trợ Page/Page Reels qua API; TikTok hỗ trợ Draft và Direct Post nhưng Direct Post/audience có ràng buộc audit. Không được dùng RoxyBrowser để né audit, CAPTCHA, 2FA, quota hoặc restriction của nền tảng.

Worktree hiện có nhiều thay đổi người dùng. Implementation phải thêm module/file mới và chỉ sửa tối thiểu các registry/model/migration/router/client/sidebar cần thiết.

## Goals / Non-Goals

**Goals:**

- Tạo Automation Hub độc lập về route, DB state, queue, concurrency, UI và lifecycle.
- Cho phép cấu hình an toàn Roxy Local API và Playwright MCP sidecar, kiểm tra health, xem/mở/đóng profile và lấy connection endpoint đã redaction.
- Cho phép upload file video vào kho riêng hoặc chọn output MP4 hiện có mà không sửa trạng thái workflow nguồn.
- Cho phép cấu hình kết nối YouTube, Facebook Page và TikTok bằng secret được mã hóa, sau đó tạo job upload ngay hoặc theo lịch.
- Dùng adapter API chính thức, retry có kiểm soát, idempotency và startup recovery.
- Cung cấp script setup ba repo RoxyBrowser vào data directory bị Git-ignore và kiểm tra prerequisite.
- Giữ secret, browser profile và cookie ngoài API response, log, debug export và package project.

**Non-Goals:**

- Không tự nhập username/password, giải CAPTCHA/2FA hoặc đọc cookie từ profile cá nhân.
- Không hỗ trợ Facebook profile cá nhân hoặc Instagram personal account.
- Không bật TikTok Direct Post nếu chưa có feature flag và quyền/audit phù hợp.
- Không bảo đảm bài đăng được duyệt, viral, có lượt xem hoặc hoàn tất đúng giờ khi API/provider bị gián đoạn.
- Không gộp publishing job vào AI Video auto-run, render job, voice queue hoặc Veo clip generation job.
- Không vendoring source, `.git`, `node_modules` hoặc build artifact của ba repo RoxyBrowser vào Git của `voice-app`.

## Decisions

### 1. Automation Hub là bounded context riêng

Thêm route namespace `/automation-hub`, service package `backend/services/automation_hub/`, frontend route `/automation-hub` và các bảng có prefix `automation_`. Hub chỉ nhận một asset path/id đã snapshot tại lúc tạo job.

Không thêm bước `publish` vào `VideoAutoRun.STEP_ORDER`. Lý do: upload có OAuth, quota, scheduling và failure semantics khác hoàn toàn với tạo media. Một publishing failure không được làm project video hoặc render đã hoàn tất chuyển failed.

### 2. Feature flag và runtime tách biệt

Backend action ghi/mở browser/upload chỉ hoạt động khi `VOICEBOX_FEATURE_AUTOMATION_HUB=true`. API status đọc được ngay cả khi disabled để UI hiển thị hướng dẫn cấu hình. Publishing worker có concurrency riêng, mặc định 1 và hard cap nhỏ; không dùng workflow/planning/voice queue hiện tại.

Playwright MCP là sidecar loopback. Backend chỉ start sidecar khi người dùng yêu cầu và executable/entry path đã cấu hình; không auto-start khi app boot. stdout/stderr ghi vào data directory riêng và process được quản lý theo PID runtime, không đưa vào state machine media.

### 3. Tích hợp Roxy qua contract thay vì copy code

Python adapter gọi trực tiếp các Local API contract đã được hai repo sử dụng:

- `GET /health`
- `GET /browser/workspace`
- `GET /browser/list_v3`
- `POST /browser/open`
- `POST /browser/close`
- `GET /browser/connection_info`

Header `token` lấy từ secret store. Adapter chỉ trả workspace/profile/endpoint metadata cần thiết và loại bỏ token/cookie/path nhạy cảm.

`roxybrowser-mcp-server` và `roxybrowser-playwright-mcp` vẫn được build/chạy như sidecar chính chủ. Script setup clone/update đúng ba repo vào `<data>/automation_hub/roxybrowserlabs`, chạy `npm ci && npm run build` và `pnpm install --frozen-lockfile && pnpm build`, rồi in đường dẫn cấu hình. `local-API` được clone để giữ tài liệu/examples nhưng không khởi động như server.

Alternative: copy toàn bộ repo vào source tree. Loại vì tạo nested Git, dependency khổng lồ và khó cập nhật upstream.

### 4. Secret store mã hóa at rest

Bảng connection lưu `public_config_json`, `secret_ciphertext`, `secret_fingerprint`, scopes/status và timestamps. Mã hóa dùng Fernet từ thư viện `cryptography`; key ưu tiên `VOICEBOX_AUTOMATION_SECRET_KEY`, nếu không có thì tạo một local key file dưới data directory với quyền truy cập hạn chế tốt nhất có thể.

API create/update nhận secret nhưng response chỉ có `has_secret`, fingerprint rút gọn và public config. Không có endpoint đọc secret rõ. Key/token không được ghi log; exception từ provider phải được sanitize.

Alternative: lưu token plain JSON hoặc `.env` chung. Loại vì dễ lộ qua DB/debug và khó quản lý nhiều account.

### 5. Mô hình dữ liệu publishing độc lập

Các bảng chính:

```text
automation_connections
  id, kind, platform, label, status, public_config_json,
  secret_ciphertext, secret_fingerprint, scopes_json,
  last_checked_at, failure_reason, created_at, updated_at

automation_assets
  id, source_type, source_ref, stored_path, filename, mime_type,
  size_bytes, sha256, created_at

automation_publish_jobs
  id, asset_id, connection_id, platform, publish_mode, status,
  title, description, tags_json, privacy, scheduled_at,
  idempotency_key, attempt_count, provider_post_id, provider_url,
  result_json, error_code, failure_reason,
  started_at, completed_at, created_at, updated_at

automation_publish_attempts
  id, job_id, attempt_number, status, request_meta_json,
  response_meta_json, error_code, failure_reason,
  started_at, completed_at, created_at
```

Unique index trên `idempotency_key` ngăn click/start lặp tạo bài đăng trùng. Attempt chỉ lưu metadata đã redaction, không lưu bearer token hoặc full response không kiểm soát.

### 6. Asset được snapshot vào kho Hub

Hub hỗ trợ:

- Upload file trực tiếp qua multipart vào `<data>/automation_hub/assets/<asset_id>/`.
- Import một output video hiện có bằng backend resolver; file được copy hoặc hard-link an toàn vào kho Hub và hash trước khi tạo job.

Job luôn tham chiếu `automation_assets`, không đọc một path tùy ý do client gửi. Điều này tránh path traversal và bảo đảm video nguồn không đổi giữa lúc xếp hàng và upload.

### 7. Adapter API chính thức theo platform

- YouTube: refresh access token khi cần, tạo resumable session `videos.insert`, upload file, hỗ trợ `privacyStatus` và `status.publishAt`; thumbnail là bước tùy chọn riêng khi có asset.
- Facebook: upload video lên Page qua Graph Video API, dùng Page access token và hỗ trợ `scheduled_publish_time` khi cấu hình hợp lệ. Không nhận personal profile.
- TikTok Draft: gọi init endpoint với `FILE_UPLOAD`, upload chunk theo URL được cấp và lưu `publish_id`; polling status tách khỏi upload.
- TikTok Direct Post: adapter code path có guard feature flag, scope `video.publish` và xác nhận user/audit; default disabled. Scheduling dùng scheduler nội bộ vì TikTok không có native scheduling contract tương đương YouTube/Facebook.

Adapter interface nhận file path + metadata canonical và trả provider result canonical. Network client có timeout, bounded retries chỉ cho lỗi retryable và không tự retry sau khi provider có thể đã tạo post nếu không xác định được idempotency/result.

### 8. Worker queue, scheduling và recovery

Worker polling riêng lấy job `queued` hoặc `scheduled` đến hạn theo FIFO, chuyển trạng thái bằng transaction ngắn và xử lý tối đa concurrency cấu hình. Cancel job queued/scheduled là tức thời; active job nhận cancel flag và dừng ở checkpoint an toàn nhưng không hứa hủy một HTTP upload đã được provider nhận.

Khi backend restart, job `preparing/uploading/finalizing` được đánh dấu `interrupted` và cho retry thủ công. Job đã có `provider_post_id` không tự upload lại; người dùng phải xác nhận retry để tránh duplicate.

### 9. Browser automation là supervised fallback

MVP cung cấp quản lý profile và sidecar status/connection, không triển khai bot đăng bài chung cho ba mạng xã hội. Một browser action sau này phải là job riêng, hiển thị URL/profile đang dùng, pause khi cần login/CAPTCHA/consent và không được dùng để né hạn chế API.

### 10. UI là một workspace riêng

Màn Automation Hub gồm bốn vùng:

1. Trạng thái feature, secret store và runtime.
2. RoxyBrowser: Local API, workspace/profile, mở/đóng và Playwright MCP health.
3. Kết nối xuất bản: YouTube, Facebook Page, TikTok; form chỉ ghi secret và không hiển thị lại.
4. Publishing jobs: chọn/upload asset, metadata, mode, lịch, tạo/cancel/retry và bảng kết quả.

UI poll Hub jobs riêng và không poll/chặn AIVideoAssistant hoặc Video Inspiration.

## Risks / Trade-offs

- [API/provider thay đổi] → Tách adapter, version endpoint bằng config, trả error code ổn định và test bằng mock transport.
- [Token hết hạn hoặc thiếu scope] → Connection check, refresh token khi có, status `needs_auth` và lỗi tiếng Việt không lộ token.
- [Upload tạo post nhưng response timeout] → Lưu attempt/correlation metadata, không retry tự động khi outcome mơ hồ và yêu cầu xác nhận.
- [Roxy Desktop chưa chạy hoặc RAM quá cao] → Health check rõ ràng, không tự kill process, không coi sidecar health là browser-connected health.
- [Sidecar path phụ thuộc máy] → Setup script và config runtime; UI hiển thị từng prerequisite còn thiếu.
- [SQLite contention] → Worker concurrency thấp, transaction ngắn và không giữ DB session trong lúc upload mạng dài.
- [Secret key mất] → Connection chuyển `needs_auth`; không cố giải mã hoặc log ciphertext. Backup key là trách nhiệm local của người dùng.
- [Platform policy/audit] → Official API primary, Direct Post/browser fallback bị guard, tài liệu nêu rõ unsupported account types và restriction.

## Migration Plan

1. Thêm dependency mã hóa, model và migration idempotent; feature flag mặc định disabled.
2. Thêm config/security/asset/Roxy adapters và API status read-only.
3. Thêm connection CRUD/check và publishing adapters.
4. Thêm worker queue, scheduling, retry/cancel/startup recovery.
5. Thêm frontend Automation Hub và client types.
6. Thêm setup script/tài liệu cho ba repo RoxyBrowser.
7. Chạy unit tests, typecheck/build và mock integration tests.
8. Bật feature flag local để smoke test Roxy Desktop; chỉ test upload thật khi người dùng cung cấp account/token hợp lệ.

Rollback: tắt feature flag và dừng sidecar/worker. Các bảng/file Hub là bổ sung, không ảnh hưởng project media hiện có. Không xóa dữ liệu/token tự động trong rollback; người dùng có thể xóa connection/asset bằng action Hub.

## Open Questions

- OAuth consent full-flow trong app chưa bắt buộc cho vertical slice; MVP nhận credential/token do người dùng lấy từ developer console hoặc flow chính thức. Có thể bổ sung callback OAuth từng platform trong change riêng.
- Facebook Reels và Instagram Professional có thể dùng cùng nền tảng Meta nhưng không nằm trong vertical slice đầu; thiết kế adapter cho phép bổ sung sau mà không đổi queue/job schema.
