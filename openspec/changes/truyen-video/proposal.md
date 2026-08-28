# Đề xuất: handoff video từ truyện ảnh

## Why

Hiện tại Story Studio có thể tạo prompt truyện ảnh/panel prompt, nhưng luồng `Handoff AI Video` chỉ hoạt động khi tập có `output_intent` thuộc nhóm video và backend đang ghi nguồn handoff là `master_story`. Với tập `truyen_anh`, người dùng đã có đủ chất liệu truyện ảnh nhưng không thể tạo video handoff thủ công để AI Video phát triển lại thành video.

Người dùng cần một luồng rõ ràng: sau khi tạo xong prompt truyện ảnh, có thể bấm handoff video thủ công; backend phải truyền đầy đủ dữ liệu truyện sang AI Video để AI hiểu lại câu chuyện, nhân vật, bối cảnh, panel, hook, thoại/note thoại, prompt ảnh và ràng buộc canon.

## What Changes

- Cho phép tập `truyen_anh` handoff video thủ công khi đã có Master Story đã duyệt và/hoặc image adaptation có panel prompt.
- Khi handoff từ truyện ảnh, backend ghi rõ metadata nguồn, ví dụ `handoff_source = "image_story_prompts"`.
- AI Video project nhận source blocks đủ rõ để phát triển lại thành video, gồm Master Story, storyboard panel, prompt ảnh, bối cảnh, góc máy, note thoại, visual, must-have/avoid, style/canon và hồ sơ nhân vật.
- UI Story Studio có hành động riêng cho “Tạo video handoff” hoặc “Tạo prompt video” từ truyện ảnh, không gây nhầm với render ảnh.
- Tùy chọn tự chạy AI Video đến bước prompt video bằng `material_target = "prompts_only"`, không render ảnh/video, không gọi Veo, không tạo voice/subtitle/MP4.

## Impact

- Backend Story Studio: mở rộng request và logic `create_video_adaptation`.
- AI Video: nhận source blocks mới từ storyboard/prompt truyện ảnh và tùy chọn auto-run `prompts_only`.
- Frontend Story Studio: thêm hành động handoff video từ truyện ảnh và trạng thái/link liên quan.
- Tests: thêm coverage cho `truyen_anh` handoff, metadata nguồn, source blocks và auto-run dừng ở prompt video.

## Non-goals

- Không thay đổi chất lượng sinh Master Story/candidate trong đề xuất này.
- Không tự render ảnh từ prompt truyện.
- Không tự gọi provider video/Veo.
- Không tự tạo voice, phụ đề hoặc MP4.
- Không đổi quy tắc handoff mặc định của các tập đã là `video_truyen` hoặc `ca_hai`, trừ khi người dùng chọn nguồn từ truyện ảnh.

## Tên thay đổi

`truyen-video`

Nội dung OpenSpec viết bằng tiếng Việt. Tên change dùng tiếng Việt không dấu, dưới 15 ký tự và hợp kebab-case để CLI dễ validate.
