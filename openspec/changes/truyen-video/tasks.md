# Công việc

## 1. Backend contract

- [x] Mở rộng `StoryVideoHandoffRequest` với `source_mode`, `start_auto_run`, `material_target`.
- [x] Cho phép `truyen_anh` handoff thủ công khi resolved source là `image_story_prompts`.
- [x] Thêm helper đọc image adaptation panels và format thành source blocks có cấu trúc.
- [x] Thêm metadata audit cho `handoff_source`, panel count, prompt count, image adaptation id/revision.
- [x] Đảm bảo flow không gọi render ảnh, Veo, voice, subtitle hoặc MP4.

## 2. AI Video integration

- [x] Tạo AI Video project với source blocks từ truyện ảnh khi `source_mode = image_story_prompts`.
- [x] Nếu `start_auto_run = true`, start auto-run với `material_target = prompts_only`.
- [x] Lưu `auto_run_id`/trạng thái liên quan vào payload video adaptation.
- [x] Xử lý `open_existing` an toàn với project đã link.

## 3. UI Story Studio

- [x] Thêm nút `Handoff video từ truyện` hoặc `Tạo prompt video` sau khi có panel prompt.
- [x] Hiển thị trạng thái nguồn handoff: Master Story hay prompt truyện.
- [x] Hiển thị link mở AI Video project.
- [x] Cảnh báo rõ nếu chưa có prompt truyện để handoff.

## 4. Kiểm thử

- [x] Test backend: tập `truyen_anh` có image prompts tạo được video adaptation.
- [x] Test backend: payload ghi `handoff_source = image_story_prompts`.
- [x] Test backend: AI Video source blocks chứa storyboard/prompt/canon/style/character data.
- [x] Test backend: `start_auto_run = true` chỉ chạy đến `prompts_only`.
- [x] Test backend: không có image prompts thì trả lỗi hướng dẫn tạo prompt truyện trước.
- [x] Typecheck frontend sau khi thêm UI.
