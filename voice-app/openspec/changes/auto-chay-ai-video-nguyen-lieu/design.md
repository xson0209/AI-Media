## Context

AI Video phase 2 hiện đã có pipeline thủ công trong `AIVideoAssistant`: tạo project/source blocks, phát triển story, approve story, tạo segment/shot, tạo prompt video, tạo voice theo shot, tạo subtitle `.srt`, kiểm tra package readiness và tạo ZIP. Backend đã có service riêng cho từng phần (`video_phase2`, `video_voice`, `video_subtitles`, `video_packages`) và TTS generation đang đi qua hàng đợi serial để tránh tranh GPU.

Người dùng muốn nhập yêu cầu một lần rồi hệ thống tự chạy đến khi có prompt + voice + SRT. Tuy nhiên story/prompt là nội dung sáng tạo có rủi ro lệch ý, còn voice là bước tốn thời gian. Vì vậy auto-run cần hai mode rõ ràng: dừng để duyệt trước khi tạo artifact tốn kém, hoặc tự chạy hết khi người dùng chấp nhận autopilot.

## Goals / Non-Goals

**Goals:**
- Thêm orchestration backend bền vững cho AI Video phase 2, có thể poll, resume, cancel và retry.
- Hỗ trợ 2 mode duyệt: `review_gated` dừng ở các điểm duyệt, và `full_auto` tự approve các bước trung gian.
- Tự chạy tới trạng thái có prompt video, voice và subtitle `.srt`; ZIP package vẫn là workflow thủ công riêng sau khi auto-run hoàn tất.
- Chỉ tạo hoặc tạo lại artifact thiếu/stale, tránh chạy lại toàn bộ project khi đã có artifact hợp lệ.
- Tôn trọng `target_language`, voice profile, prompt segment config, locked shots và readiness hiện có.
- Hiển thị tiến độ trong UI bằng tiếng Việt, gồm bước đang chạy, lỗi, shot còn thiếu voice, trạng thái cần duyệt và nút tiếp tục.
- Hiển thị diễn giải tiến trình thân thiện cho người không code mà không lưu nhật ký diễn giải chi tiết vào database.

**Non-Goals:**
- Không tích hợp provider tạo video ngoài hoặc tự tạo clip video.
- Không render MP4 trong change này; render timeline vẫn là workflow riêng.
- Không thay đổi thuật toán AI planning, prompt generation, subtitle timing hoặc TTS engine lõi ngoài việc điều phối chúng.
- Không thêm chế độ song ngữ nhiều audio/subtitle track.
- Không bỏ các nút thủ công hiện có; auto-run là đường nhanh, còn người dùng vẫn có thể can thiệp từng bước.

## Decisions

### 1. Dùng backend persisted auto-run job thay vì chain mutation ở frontend

Quyết định: thêm model/service auto-run, ví dụ `video_auto_runs`, với các field chính: `id`, `project_id`, `mode`, `status`, `current_step`, `review_stage`, `progress`, `force`, `step_results_json`, `failure_reason`, `error_code`, `created_at`, `started_at`, `updated_at`, `completed_at`.

Frontend chỉ start/poll/continue/cancel/retry. Backend giữ state machine và tự gọi các service hiện có.

Phương án khác đã cân nhắc: frontend tự gọi lần lượt `developVideoStory`, `generateVideoShots`, `generateVideoPromptPack`, `createVideoShotVoice`, `generateVideoSubtitle`, `createVideoPackage`. Cách này nhanh hơn để code nhưng dễ mất tiến độ khi app refresh, khó resume, khó debug và dễ chạy trùng voice nếu user bấm lại.

### 2. State machine idempotent, chạy tiếp từ artifact hiện có

Auto-run không coi mỗi lần bấm là một project mới. Runner luôn đọc trạng thái thật của project trước khi chạy từng bước:

```
validate
  -> develop_story nếu story thiếu/stale hoặc force
  -> review_story nếu mode review_gated và story chưa được duyệt trong run
  -> approve_story nếu full_auto hoặc user continue
  -> generate_shots nếu shot thiếu/stale hoặc config mismatch
  -> generate_prompts nếu prompt thiếu/stale
  -> review_prompts nếu mode review_gated và prompt vừa tạo/cần duyệt
  -> generate_voice cho shot có narration và voice thiếu/stale/failed retryable
  -> wait_voice cho tới khi mọi generation terminal
  -> generate_subtitle nếu subtitle thiếu/stale
  -> completed
```

Step runner phải skip artifact đã `completed` và còn mới, nhưng phải dừng rõ ràng nếu artifact cần thiết thiếu input không thể tự suy ra, ví dụ chưa chọn voice profile.

Phương án khác đã cân nhắc: luôn force regenerate toàn bộ. Cách này đơn giản nhưng tốn thời gian, dễ làm mất nội dung đã chỉnh và trái với nhu cầu “đỡ mất thời gian”.

### 3. `review_gated` có hai điểm dừng: story và prompt

Chế độ `review_gated` dừng với `status = "needs_review"` ở hai điểm:
- `review_stage = "story"`: sau khi story/continuity/detailed script đã có, trước khi tạo hoặc tạo lại segment/prompt nếu story chưa được user xác nhận trong run.
- `review_stage = "prompts"`: sau khi segment/prompt video đã có, trước khi tạo voice/SRT/package.

Khi user bấm tiếp tục, API `continue` ghi nhận review decision, approve artifact tương ứng nếu cần, rồi resume từ bước kế tiếp. User vẫn có thể dùng nút thủ công để chỉnh story/shot/prompt trước khi bấm tiếp tục; runner phải đọc lại trạng thái mới nhất khi resume.

Phương án khác đã cân nhắc: chỉ dừng một lần sau story. Cách này vẫn có rủi ro voice được tạo từ prompt/shot chưa đạt, nên chưa đủ với mục tiêu kiểm soát chi phí thời gian.

### 4. `full_auto` tự approve nhưng không bỏ qua validation

Chế độ `full_auto` tự set story approved và prompt review passed trong phạm vi run, nhưng vẫn phải dừng `failed` hoặc `needs_input` khi thiếu điều kiện bắt buộc: planning provider chưa sẵn sàng, project chưa có source hợp lệ, prompt segment config không hợp lệ, chưa có voice profile, voice engine không hỗ trợ ngôn ngữ video, hoặc TTS generation fail.

Không được silent fallback sang tiếng Anh khi project `target_language = "vi"`; logic voice vẫn dùng language resolution hiện có.

Phương án khác đã cân nhắc: cho full auto bỏ qua voice và chỉ tạo prompt/SRT rỗng nếu thiếu profile. Cách đó tạo output giả và làm readiness sai, nên phải dừng rõ để người dùng bổ sung input.

### 5. Voice generation được enqueue theo shot, nhưng chờ bằng polling trạng thái DB

Runner sẽ gọi service tạo voice cho các shot cần voice. Service này tiếp tục enqueue vào TTS generation queue serial hiện có. Auto-run không tự chạy nhiều inference song song; nó chỉ tạo request cho shot thiếu/stale, sau đó chuyển sang `waiting_voice` và poll/sync status định kỳ.

Khi mọi shot bắt buộc đã `completed`, runner mới tạo subtitle. Nếu một hoặc nhiều shot `failed`, auto-run chuyển `failed` với danh sách shot lỗi trong `step_results_json`; retry sau khi người dùng sửa cấu hình chỉ tạo lại shot còn thiếu/failed/stale.

Phương án khác đã cân nhắc: auto-run đợi từng voice xong rồi mới enqueue shot tiếp theo. Cách đó dễ hiểu nhưng chậm hơn và bỏ phí queue hiện có; enqueue hàng loạt vẫn an toàn vì TTS queue đã serialize inference.

### 6. API tách start/status/continue/cancel/retry

Các endpoint đề xuất:
- `POST /ai-video/projects/{project_id}/auto-runs`: tạo run mới hoặc trả về run active nếu request không cho phép tạo song song.
- `GET /ai-video/projects/{project_id}/auto-runs/latest`: lấy run mới nhất để restore UI.
- `GET /ai-video/projects/{project_id}/auto-runs/{run_id}`: poll trạng thái chi tiết.
- `POST /ai-video/projects/{project_id}/auto-runs/{run_id}/continue`: tiếp tục sau review hoặc sau khi user bổ sung input.
- `POST /ai-video/projects/{project_id}/auto-runs/{run_id}/cancel`: cancel run chưa terminal.
- `POST /ai-video/projects/{project_id}/auto-runs/{run_id}/retry`: retry từ bước fail gần nhất, không force toàn bộ trừ khi request bật `force`.

Chỉ cho một auto-run active trên một project tại một thời điểm để tránh chạy trùng voice/package. Run terminal vẫn giữ lại để debug và hiển thị lịch sử gần nhất.

### 7. UI là panel điều khiển thật, không thay thế workflow thủ công

Trong `AIVideoAssistant`, thêm một panel hoặc vùng action gần đầu workflow: mode selector, nút `Auto tạo nguyên liệu`, progress steps, current status, lỗi và nút `Tiếp tục sau khi duyệt`. Panel phải hiển thị tiếng Việt và dùng state từ backend, không tự đoán completed chỉ từ local mutation. Tạo ZIP vẫn nằm ở khu tải nguyên liệu thủ công.

Các nút thủ công hiện có vẫn giữ nguyên để user sửa nội dung giữa hai review gate. Khi auto-run active, các nút có thể disabled theo từng bước nếu việc bấm tay gây chạy trùng, nhưng không khóa toàn bộ màn hình đọc/duyệt.

### 8. Diễn giải tiến trình chi tiết là session-only, không persist vào DB

Quyết định: không ghi nhật ký UI chi tiết kiểu "đang tạo prompt 3/8" hoặc các câu diễn giải non-code vào `video_auto_runs.step_results_json` hay bảng log mới. Database chỉ giữ trạng thái lõi cần cho resume/debug: `status`, `current_step`, `progress`, `completed_steps`, `pending_steps`, `failure_reason`, `error_code`, summary prompt/voice/subtitle và debug event đã redaction.

Frontend dựng progress panel từ dữ liệu lõi backend (`current_step`, `status`, `review_stage`, `progress`, `summary`, `completed_steps`, `pending_steps`) cộng với session state trong React để mô tả các thay đổi vừa quan sát được trong phiên hiện tại. Khi user reload hoặc tắt app, phần diễn giải tạm thời có thể mất; UI phải dựng lại trạng thái hiện tại từ backend summary thay vì hiển thị lịch sử cũ.

Phương án khác đã cân nhắc: ghi mọi progress detail vào database để restore đầy đủ sau reload. Cách đó làm DB phình nhanh, nhất là khi auto-run poll thường xuyên hoặc có nhiều project, trong khi dữ liệu này chỉ phục vụ trải nghiệm tức thời.

## Risks / Trade-offs

- Auto-run full có thể tạo voice từ nội dung chưa đúng ý -> Mặc định UI nên giới thiệu rõ hai mode; `review_gated` là lựa chọn an toàn cho project quan trọng, `full_auto` dành cho khi người dùng chấp nhận tự động hóa tối đa.
- Voice generation có thể kéo dài hoặc bị fail ở một vài shot -> Persist run state, poll DB status, lưu danh sách shot lỗi và cho retry chỉ phần thiếu/failed.
- Vì diễn giải tiến trình chi tiết là session-only, reload app sẽ mất các câu mô tả vừa phát sinh -> UI phải hiển thị fallback rõ ràng từ state lõi backend như bước hiện tại, progress tổng, prompt/voice counts và trạng thái cần duyệt/lỗi.
- State machine có thể chạy trùng nếu user bấm nhiều lần -> Chỉ cho một active run mỗi project, endpoint start trả active run hiện tại hoặc lỗi tiếng Việt rõ ràng.
- Artifact stale logic hiện có chưa bao phủ mọi cạnh -> Runner phải dựa vào status/readiness hiện có trước, và task implementation cần bổ sung test stale/resume cho các artifact auto-run dùng.
- App restart khi background run đang chạy -> Khi startup hoặc khi poll, run `running/waiting_voice` quá hạn phải sync lại từ DB; nếu không thể xác định coroutine còn sống thì chuyển `failed` hoặc `needs_retry` với thông báo tiếng Việt.
- Tự tạo ZIP trong auto-run dễ làm chậm hoặc fail sau khi nguyên liệu lõi đã sẵn sàng -> Auto-run không tạo ZIP; người dùng tạo ZIP thủ công ở khu package khi cần.

## Migration Plan

- Thêm migration tạo bảng `video_auto_runs` và index theo `project_id`, `status`, `created_at`.
- Không cần backfill cho project cũ; project chưa có auto-run vẫn hoạt động thủ công như hiện tại.
- Thêm service auto-run phía sau endpoint mới, sau đó thêm frontend panel dùng endpoint đó.
- Rollback an toàn bằng cách ẩn UI/endpoint auto-run; artifact story/shot/prompt/voice/subtitle/package đã tạo vẫn là artifact hiện có của AI Video và không phụ thuộc auto-run để đọc.

## Open Questions

- Có cần lưu lịch sử nhiều review decision chi tiết theo từng gate trong bảng riêng không, hay `step_results_json` đủ cho MVP?
- Có cần setting giới hạn thời gian chờ voice trước khi auto-run chuyển failed không, hay chỉ dựa vào generation status terminal?
- Có cần thêm action nhanh để chuyển người dùng tới khu tạo ZIP thủ công sau khi auto-run completed không?
