## Context

Product Video hiện có project, shot, prompt pack và `render_project_id` trỏ tới một AI Video render bridge. Route Product Video dừng ở prompt; người dùng phải tự đưa prompt sang provider, tải clip và bắt đầu render. AI Video đã có `VideoShotClip`, `VideoRenderJob`, storage, FFmpeg normalization/concat và các kiểm tra render readiness. Luồng tạo clip Veo hiện tại dùng Chrome/Flow với browser session, nên không phù hợp để tái sử dụng nguyên trạng cho htmustc API.

Provider mới dùng một endpoint gateway:

```text
POST https://htmustc.id.vn/v1/videos/generations
Authorization: Bearer <secret>
Content-Type: application/json
```

Request đã biết gồm `model`, `prompt`, `seconds` (chuỗi), `resolution` và `aspect_ratio`. Response, polling, download, cancel và capability matrix vẫn phải xác nhận trước implementation.

## Goals / Non-Goals

**Goals:**

- Cho một Product Video project chọn đúng một model htmustc (`gemini-veo-3-1` hoặc `gemini-omni-flash`) cho một generation revision.
- Chạy auto-run có các profile prompt-only, clips-only và full-auto.
- Thực hiện preflight, snapshot prompt/config, idempotency, queue giới hạn concurrency, retry có backoff, pause/resume/cancel và recovery sau restart.
- Tạo clip theo từng shot, tải về staging, kiểm tra hash/ffprobe, import đúng shot và chỉ render khi đủ clip hợp lệ.
- Tái sử dụng render bridge và `VideoRenderJob` hiện có để tạo MP4.
- Giữ secret ở backend và cung cấp trạng thái có thể quan sát, retry item lỗi và retry render độc lập.

**Non-Goals:**

- Không gọi đồng thời hai model cho cùng một shot và không tự động chuyển model trong một generation job.
- Không thay thế luồng Veo/Flow Chrome của AI Video.
- Không tự động đăng video lên mạng xã hội.
- Không tự suy đoán response/polling/download endpoint hoặc capability của htmustc khi chưa có contract xác nhận.
- Không thêm TTS riêng cho Product Video trong change này; audio do provider trả về hoặc cấu hình render hiện có quyết định.

## Decisions

### 1. Tạo provider adapter htmustc và chuẩn hóa operation

Tạo một adapter phía backend chịu trách nhiệm submit, poll/reconcile và download. Orchestrator chỉ nhận trạng thái chuẩn hóa (`queued`, `running`, `completed`, `failed`, `unknown`) và không phụ thuộc tên field raw của htmustc. Adapter phải hỗ trợ cả response đồng bộ có video URL và response bất đồng bộ có operation id; endpoint cụ thể được cấu hình sau khi contract được xác nhận.

Phương án thay thế là gọi HTTP trực tiếp trong Product Video service. Phương án đó đơn giản lúc đầu nhưng trộn provider protocol với nghiệp vụ, khó retry/reconcile và không mở rộng được.

### 2. Job riêng cho Product Video API

Thêm generation job/item riêng cho Product Video thay vì mở rộng nguyên trạng `VideoClipGenerationJob`. Model hiện tại bắt buộc `session_id` và chứa trạng thái Chrome/Flow, provider project binding và credit approval. Job mới lưu model, cấu hình snapshot, prompt fingerprint, provider operation id, retry và staging path. Khi item ready, kết quả được đưa vào bảng `VideoShotClip` dùng chung.

Phương án thay thế là biến `VideoClipGenerationJob` thành provider-neutral bằng nhiều cột nullable. Cách đó giảm bảng mới nhưng tạo breaking semantics, migration phức tạp và làm lẫn Flow với API.

### 3. Một model bất biến cho mỗi generation revision

Model, resolution, aspect ratio, seconds, prompt revision và chính sách retry được snapshot khi tạo job. Thay đổi model hoặc prompt tạo revision/job mới. Không có fallback model tự động và không trộn Omni Flash với Veo 3.1 trong cùng job.

Lựa chọn này ưu tiên khả năng truy vết chi phí, tính nhất quán hình ảnh và tránh duplicate generation; comparison mode hoặc fallback có thể là change riêng sau này.

### 4. Queue có giới hạn ở hai cấp

Mỗi project chỉ có một auto-run active. Worker lấy item `queued` theo lease, với giới hạn concurrency toàn hệ thống và theo project. Mặc định bắt đầu ở concurrency 1; có thể cấu hình 2/3 sau khi xác nhận rate limit provider. Download và render có giới hạn riêng. Queue phải dùng backoff cho 429/5xx và giữ item đã thành công khi item khác lỗi.

Phương án fire-and-forget tất cả request cùng lúc bị loại vì khó pause, khó đối soát timeout và có nguy cơ vượt rate/chi phí.

### 5. Fail-closed và idempotency

Preflight fail thì không gửi provider request. POST timeout khi chưa biết operation có được nhận hay không chuyển item sang `unknown_provider_state` để reconcile; không gửi lại ngay. Khóa idempotency dựa trên project, prompt fingerprint, model và generation settings; operation id được lưu ngay khi provider trả về.

Retry tự động chỉ áp dụng cho lỗi tạm thời được phân loại. Lỗi request 4xx, auth hoặc capability dừng job và yêu cầu người dùng xử lý.

### 6. Staging download và render gate

Video được tải vào staging, kiểm tra HTTP/status, kích thước, SHA-256, ffprobe duration/resolution/codec/audio rồi mới atomic move và tạo `VideoShotClip` ready. `VideoRenderJob` chỉ được tạo khi mọi shot trong snapshot đều ready. Render failure không tạo lại clip; người dùng retry render độc lập.

### 7. Auto-run profile và review gate

Giữ ba output target: `prompts_only`, `video_clips`, `render_ready`. `review_gated` dừng sau prompt hoặc sau clip theo cấu hình; `full_auto` tự chạy tiếp sau preflight nhưng không bỏ qua validation. Mỗi job phải hiển thị current step, item, queue position, lỗi và thao tác pause/resume/cancel/retry.

### 8. Secret và observability

API key chỉ nằm trong backend secret store hoặc environment được backend đọc. Log chỉ ghi provider, model, operation id đã redaction, latency, status, error code và hash; không ghi Bearer token, signed URL hoặc payload nhạy cảm. Job/event state phải đủ để khôi phục sau restart và điều tra một generation cụ thể.

## Risks / Trade-offs

- **[Response contract chưa đủ]** → Chưa chốt endpoint poll/download/cancel và tên field; adapter phải đặt seam chuẩn hóa, task implementation phải bắt đầu bằng contract fixture hoặc xác nhận docs.
- **[Provider giới hạn concurrency hoặc thay đổi capability]** → Dùng capability matrix theo model, preflight trước generation, cấu hình global/project concurrency và backoff 429.
- **[Timeout sau khi provider đã nhận request]** → Lưu operation id, dùng trạng thái `unknown_provider_state`, reconcile trước retry và cấm retry mù.
- **[Chi phí phát sinh ngoài ý muốn]** → Một model bất biến trong job, hiển thị số shot/cấu hình trước chạy, giới hạn retry, không fallback tự động và có kill switch.
- **[Clip hỏng hoặc sai metadata]** → Staging + SHA-256 + ffprobe + atomic import; render gate chặn clip chưa validated.
- **[Job chạy trùng sau restart hoặc double click]** → Idempotency key, unique active-job constraint ở cấp project và lease worker.
- **[Một shot lỗi làm project không thể render]** → Giữ clip thành công, retry item riêng, trạng thái `completed_with_failures`/`paused` và không chạy lại item ready.
- **[FFmpeg render lỗi sau khi generation thành công]** → Tách generation và render job; retry render không gọi provider lại.
- **[Không đủ dung lượng hoặc worker bị treo]** → Preflight disk, heartbeat/lease timeout, cleanup staging an toàn và recovery khi khởi động.
- **[Chất lượng giữa model khác nhau]** → Không trộn model trong revision; model change tạo revision mới và UI ghi rõ model của từng job.

## Migration Plan

1. Xác nhận response/polling/download/cancel và capability matrix của htmustc bằng contract fixture, không gọi API thật trong unit test.
2. Thêm feature flag tắt/mở provider integration; mặc định có thể tắt trong môi trường chưa cấu hình key.
3. Thêm database tables/indexes cho Product Video generation job/item theo kiểu additive; không sửa dữ liệu prompt hiện có.
4. Thêm adapter/config/secret và preflight; kiểm thử request serialization, đặc biệt `seconds` là chuỗi.
5. Thêm queue worker, recovery, download validation và import bridge.
6. Thêm auto-run route/UI cho project thử nghiệm 2–3 shot.
7. Bật auto-render sau khi generation/download fixture và render integration pass.
8. Mở rộng concurrency sau khi quan sát rate limit, latency và lỗi provider.

Rollback: tắt feature flag và dừng nhận job mới; job đang chạy chuyển `paused` sau checkpoint an toàn. Prompt-only flow và AI Video/Flow Chrome vẫn hoạt động. Không rollback bằng cách xóa clip hoặc xóa bảng generation; artifacts đã tải được giữ để điều tra hoặc render lại.

## Open Questions

- Response thành công của `POST /v1/videos/generations` trả video URL ngay hay operation id? Endpoint poll/download/cancel cụ thể là gì?
- `gemini-veo-3-1` và `gemini-omni-flash` hỗ trợ seconds, resolution, aspect ratio, audio và reference image nào?
- htmustc có idempotency header hoặc usage/cost response không? Nếu không, cơ chế reconcile operation id cần dựa vào field nào?
- Mặc định Product Video nên chạy `review_gated` hay `full_auto` sau khi prompt hoàn tất? Thiết kế hỗ trợ cả hai, nhưng production default nên cần quyết định trong implementation.
