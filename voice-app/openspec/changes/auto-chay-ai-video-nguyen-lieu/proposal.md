## Why

AI Video phase 2 đã có các bước tạo story, segment/prompt, voice, phụ đề và ZIP nguyên liệu, nhưng người dùng vẫn phải bấm từng bước và chờ thủ công. Cần một nút auto để đưa dữ liệu yêu cầu vào hệ thống rồi tự chạy đến khi có prompt video, voice và `.srt`, đồng thời vẫn có lựa chọn dừng để người dùng duyệt nội dung trước khi tốn thời gian tạo voice.

## What Changes

- Thêm workflow **Auto tạo nguyên liệu** cho AI Video phase 2 để điều phối các bước hiện có: phát triển story, duyệt hoặc tự duyệt, tạo segment, tạo prompt video, tạo voice, chờ voice hoàn tất và tạo phụ đề `.srt`. ZIP package vẫn được tạo thủ công khi người dùng cần.
- Hỗ trợ 2 chế độ duyệt:
  - **Duyệt từng chặng**: auto chạy đến điểm cần người dùng xem lại story/prompt, dừng với trạng thái `needs_review`, sau khi người dùng bấm tiếp thì mới tạo voice/SRT/package.
  - **Tự chạy hết**: hệ thống tự approve các bước trung gian và chạy đến khi prompt + voice + SRT sẵn sàng, nếu thiếu input bắt buộc hoặc gặp lỗi thì dừng rõ lý do.
- Thêm trạng thái auto-run có thể poll/resume/cancel/retry, để app refresh hoặc người dùng rời màn hình không làm mất tiến độ.
- Auto-run phải chạy tiếp từ artifact đã có, không bắt buộc tạo lại mọi thứ nếu project đã có story, shot, prompt, voice hoặc subtitle hợp lệ.
- Auto-run dùng `target_language`, voice profile, prompt segment config, readiness và stale status hiện có; không tự fallback sai ngôn ngữ video.
- UI AI Video thêm nút auto, mode selector, progress checklist, trạng thái đang chạy/lỗi/cần duyệt và action tiếp tục sau duyệt.
- Nâng cấp UI progress thành bảng diễn giải thân thiện cho người không code, nhưng không lưu nhật ký diễn giải chi tiết vào database; frontend dựng lại từ state lõi backend và session UI tạm thời.
- Không tích hợp provider tạo video ngoài, không tự upload/generate clip, không tự render MP4 trong change này. Render MP4 vẫn thuộc workflow riêng.

## Capabilities

### New Capabilities
- `ai-video-auto-material-run`: Điều phối AI Video phase 2 tự chạy đến bộ nguyên liệu prompt video, voice và phụ đề, với hai chế độ duyệt là dừng để người dùng duyệt hoặc tự chạy hết.

### Modified Capabilities
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Capability mới sử dụng output và readiness của các workflow AI Video hiện có.

## Impact

- Backend: thêm auto-run service/job, state model hoặc persistence tương đương, API start/status/cancel/resume/retry, orchestration cho story/shots/prompts/voice/subtitle/package và polling trạng thái voice.
- Frontend: mở rộng `AIVideoAssistant` và `apiClient` với nút Auto tạo nguyên liệu, chọn chế độ duyệt, progress panel, lỗi inline, trạng thái cần duyệt và action tiếp tục; redesign progress panel để mô tả "đang làm gì / đã xong gì / còn gì" bằng tiếng Việt dễ hiểu.
- Data/storage: chỉ lưu trạng thái lõi auto-run, mode, current step, progress tổng, summary, failure reason, timestamps và dữ liệu debug đã redaction; không lưu event log UI chi tiết kiểu "đang gen prompt 3/8" vào database.
- Observability: log từng bước auto-run với `request_id`/run id, lỗi đã redaction, số shot/prompt/voice đã xử lý và reason khi dừng cần duyệt.
- Tests: thêm backend tests cho state machine, resume idempotent, hai chế độ duyệt, voice polling, subtitle/package readiness và frontend type/UI behavior.
