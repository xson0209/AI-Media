## 1. Xác nhận contract và capability provider

- [ ] 1.1 Thu thập response mẫu cho `POST /v1/videos/generations`, gồm response thành công, lỗi, operation bất đồng bộ và video URL.
- [ ] 1.2 Xác nhận endpoint/status/download/cancel, auth khi tải video, idempotency support và thời hạn signed URL của htmustc.
- [ ] 1.3 Xác nhận capability matrix cho `gemini-veo-3-1` và `gemini-omni-flash`: seconds, resolution, aspect ratio, audio và reference input.
- [ ] 1.4 Đóng gói contract fixture đã redaction để unit test adapter; không đưa API key hoặc URL nhạy cảm vào repository.

## 2. Cấu hình và secret

- [ ] 2.1 Thêm cấu hình provider htmustc (base URL, generation path, timeouts, concurrency và retry defaults) với feature flag bật/tắt.
- [ ] 2.2 Thêm cách đọc API key từ backend secret store hoặc environment, bảo đảm key không xuất hiện trong response/log.
- [ ] 2.3 Thêm capability/config response đã redaction để frontend biết model và tham số được hỗ trợ trước khi chạy.
- [ ] 2.4 Thêm preflight kiểm tra key, model, duration, resolution, aspect ratio, FFmpeg/ffprobe, disk space và active-job conflict.

## 3. Database và API model cho generation job

- [ ] 3.1 Thêm model database cho Product Video generation job với provider/model/config snapshot, prompt revision/fingerprint, policy, progress và lifecycle timestamps.
- [ ] 3.2 Thêm model database cho generation item theo shot với operation id, retry, lease, staging/final paths, hash, media metadata và failure state.
- [ ] 3.3 Thêm migration additive, index theo project/status và ràng buộc ngăn nhiều active auto-run trên cùng project.
- [ ] 3.4 Thêm Pydantic request/response models cho start, status, pause/resume, cancel, retry item và retry render.
- [ ] 3.5 Thêm API client types tương ứng và redacted serialization cho job/item status.

## 4. Provider adapter và HTTP lifecycle

- [ ] 4.1 Tạo adapter htmustc tách khỏi Product Video service, serialize đúng payload và chuyển `seconds` sang chuỗi.
- [ ] 4.2 Chuẩn hóa response đồng bộ và bất đồng bộ thành operation/status nội bộ theo contract fixture.
- [ ] 4.3 Implement poll/reconcile operation với timeout, heartbeat và trạng thái `unknown_provider_state`.
- [ ] 4.4 Phân loại lỗi retryable/non-retryable; thêm backoff cho 429/5xx/network và không retry mù cho 4xx/auth/capability.
- [ ] 4.5 Lưu operation id ngay sau submit và redaction provider metadata trước khi ghi event/log.

## 5. Queue và worker orchestration

- [ ] 5.1 Implement tạo generation job/item từ prompt snapshot với idempotency key và kiểm tra prompt không stale.
- [ ] 5.2 Implement global/project bounded queue, worker lease, heartbeat và giới hạn generation/download concurrency.
- [ ] 5.3 Implement scheduler lấy item queued, submit theo thứ tự, giải phóng slot khi item terminal và hỗ trợ fairness giữa project.
- [ ] 5.4 Implement pause/resume/cancel, không submit item mới khi paused/cancelled và bảo toàn item đã ready.
- [ ] 5.5 Implement recovery khi backend restart: resume operation có id hoặc chuyển paused để reconcile; không tạo duplicate submit.
- [ ] 5.6 Implement retry item lỗi, retry toàn bộ item lỗi và giới hạn max attempts theo policy snapshot.

## 6. Download, validation và import render bridge

- [ ] 6.1 Implement tải video vào staging có timeout, giới hạn kích thước, content-type check và cleanup an toàn.
- [ ] 6.2 Tính SHA-256 và probe duration, width, height, fps, codec, audio bằng công cụ hiện có.
- [ ] 6.3 Chỉ atomic-promote file sau khi validation đạt; đánh dấu item failed nếu media hỏng hoặc sai policy.
- [ ] 6.4 Import clip đã validated vào `VideoShotClip`/render bridge đúng shot và provider metadata.
- [ ] 6.5 Chặn render khi thiếu item ready hoặc có item failed/unknown; giữ clip thành công để retry item khác.

## 7. Auto-run Product Video và render handoff

- [ ] 7.1 Mở rộng auto-run state machine cho `prompts_only`, `video_clips`, `render_ready`, `review_gated` và `full_auto`.
- [ ] 7.2 Nối pipeline hiện tại plan shots → generate prompts với provider preflight và generation job; giữ prompt-only behavior tương thích.
- [ ] 7.3 Thêm prompt gate và clip gate theo profile, đảm bảo full-auto vẫn chạy validation bắt buộc.
- [ ] 7.4 Tạo `VideoRenderJob` từ render bridge khi mọi item ready và dùng cấu hình render snapshot của project.
- [ ] 7.5 Tách generation completed khỏi render failed; retry render không gọi lại provider.
- [ ] 7.6 Thêm render quality gate kiểm tra output bằng ffprobe, duration, aspect ratio, codec, audio và timeline completeness.

## 8. Frontend Product Video

- [ ] 8.1 Thêm panel chọn model, resolution, seconds, concurrency, max attempts, failure policy và output target.
- [ ] 8.2 Hiển thị preflight summary gồm model, số shot, duration thực tế, queue policy và auto-render trước khi bắt đầu.
- [ ] 8.3 Thêm mutation/query cho start, latest status, pause/resume, cancel, retry item, retry failed items và retry render.
- [ ] 8.4 Hiển thị trạng thái job, queue position, current item, progress từng shot, lỗi redacted và thời gian retry.
- [ ] 8.5 Thêm review gate cho prompt/clip và nút mở/tải MP4 sau quality gate.
- [ ] 8.6 Chặn đổi model trong job active và hướng người dùng tạo generation revision mới.

## 9. Kiểm thử và quan sát

- [ ] 9.1 Test schema/migration, active-job uniqueness, idempotency và prompt fingerprint revision.
- [ ] 9.2 Test provider adapter bằng contract fixture cho success, async operation, 4xx, 401/403, 429, 5xx, malformed response và timeout.
- [ ] 9.3 Test queue concurrency, fairness, lease expiry, pause/resume/cancel, restart recovery và không duplicate operation.
- [ ] 9.4 Test download staging, hash/ffprobe validation, atomic import, partial success và retry item.
- [ ] 9.5 Test auto-run profiles, prompt/clip/render gates, render failure độc lập và quality gate với fixture MP4.
- [ ] 9.6 Test frontend state transitions, redacted errors, disabled controls khi active job và final download.
- [ ] 9.7 Thêm event/metric redacted cho job duration, provider latency, retry count, queue wait, download failure và render outcome.

## 10. Rollout và kiểm chứng thực tế

- [ ] 10.1 Chạy migration additive trên database test và kiểm tra rollback bằng feature flag.
- [ ] 10.2 Chạy end-to-end với provider mock cho project 2–3 shot, gồm generation → download → import → render → quality gate.
- [ ] 10.3 Chạy thử provider thật với một project ngắn sau khi xác nhận key/contract, ghi lại operation id, latency và lỗi redacted.
- [ ] 10.4 Chỉ tăng concurrency từ 1 lên 2/3 sau khi quan sát rate limit và duplicate safety.
- [ ] 10.5 Xác nhận luồng Product Video prompt-only, AI Video/Flow Chrome và render hiện có không bị hồi quy.
