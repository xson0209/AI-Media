## Why

Luồng AI Video phase 2 hiện suy ra số prompt segment từ thời lượng video và hardcode mỗi prompt khoảng 10 giây. Người dùng cần kiểm soát trực tiếp cấu trúc video, ví dụ 6 prompt, mỗi prompt 10 giây, mỗi prompt có 3 cảnh nhỏ để tạo video 60 giây với 18 cảnh nhỏ.

## What Changes

- Cho phép người dùng nhập số lượng prompt segment cho project AI Video phase 2.
- Cho phép người dùng nhập thời gian mỗi prompt segment thay vì luôn cố định 10 giây.
- Cho phép người dùng nhập số cảnh nhỏ trong mỗi prompt segment.
- Hệ thống tự tính tổng thời lượng video và tổng số cảnh nhỏ từ ba cấu hình trên.
- AI shot/segment breakdown phải tạo đúng số prompt segment đã chọn, mỗi prompt có đúng số cảnh nhỏ đã chọn và timeline nội bộ khớp thời lượng prompt.
- Backend phải normalize được các biến thể JSON phổ biến khi Codex trả về sai tên field hoặc shape, để không lỗi nếu nội dung vẫn đủ dữ liệu hợp lệ.
- UI hiển thị preview cấu trúc trước khi tạo project, ví dụ `6 prompt x 10s = 60s` và `6 x 3 = 18 cảnh nhỏ`.
- Project cũ vẫn hoạt động bằng fallback từ `target_duration_seconds` và mode prompt 10 giây hiện có.

## Capabilities

### New Capabilities

- `ai-video-configurable-prompt-segments`: Người dùng cấu hình được số prompt segment, thời lượng mỗi prompt và số cảnh nhỏ trong mỗi prompt cho AI Video phase 2; backend tạo/validate/normalize segment breakdown theo cấu hình đó.

### Modified Capabilities

- Không có capability đã archive cần sửa trong `openspec/specs`.

## Impact

- Backend models/API: thêm field cấu hình prompt segment vào request/response project và lưu ở `video_projects`.
- Backend planning: thay hardcode `VIDEO_PROMPT_SEGMENT_SECONDS` bằng cấu hình theo project khi tính số segment, usable duration, timeline, narration length và prompt generation.
- Backend normalization/validation: mở rộng parser để nhận các alias như `segments`, `prompt_segments`, `micro_scenes`, `scenes`, `timeline`, `beats` khi Codex trả output khác shape nhưng vẫn hợp lệ.
- Frontend AI Video Assistant: thêm input cho số prompt, thời gian mỗi prompt, cảnh nhỏ mỗi prompt; đổi thời lượng thành giá trị tự tính/preview để tránh mâu thuẫn.
- Tests: bổ sung test cho API model, migration, UI calculation, exact segment count, exact micro-scene count, timeline theo duration tùy chọn và output Codex lệch format nhưng vẫn được normalize.
