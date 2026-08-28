# Thiết kế: handoff video từ truyện ảnh

## Hiện trạng

- `StoryVideoHandoffRequest` hiện chỉ có `open_existing`.
- `create_video_adaptation()` đang chặn nếu `episode.output_intent` không thuộc nhóm video.
- Source blocks của AI Video hiện lấy từ Master Story: `idea`, `rough_script`, `character_notes`, `style_notes`, `must_have`, `avoid`.
- Payload video adaptation hiện ghi `handoff_source = "master_story"`.
- AI Video đã có auto-run với `material_target = "prompts_only"` và dừng sau khi tạo prompt video.

## Hướng triển khai

### 1. Mở rộng request handoff

Mở rộng `StoryVideoHandoffRequest` để UI có thể yêu cầu handoff từ truyện ảnh:

- `open_existing: bool = true`
- `source_mode: "auto" | "master_story" | "image_story_prompts" = "auto"`
- `start_auto_run: bool = false`
- `material_target: "prompts_only" | "full_materials" = "prompts_only"` nhưng Story Studio chỉ dùng `prompts_only` trong flow này.

`source_mode = "auto"` chọn `image_story_prompts` nếu image adaptation có panel prompt; nếu không có thì dùng `master_story`.

### 2. Cho phép `truyen_anh` handoff thủ công

Backend chỉ cho phép `truyen_anh` handoff khi request chọn hoặc tự resolve sang `image_story_prompts`.

Điều kiện tối thiểu:

- Episode tồn tại.
- Series tồn tại.
- Master Story đã duyệt, hoặc image adaptation có đủ panel prompt để làm nguồn.
- Nếu dùng image prompts thì image adaptation phải có ít nhất một panel có `prompt` hoặc `visual_description`.

Nếu tập `truyen_anh` không có dữ liệu truyện ảnh đủ rõ, backend trả lỗi có hướng xử lý: tạo prompt truyện trước.

### 3. Tạo source blocks đủ rõ cho AI Video

Khi `handoff_source = "image_story_prompts"`, backend tạo AI Video source blocks theo nhóm:

- `idea`: logline/hook/tên tập từ Master Story.
- `rough_script`: full story từ Master Story, kèm retention plan nếu có.
- `storyboard_panels`: danh sách panel theo thứ tự, gồm order, purpose, caption/dialogue, scene_context, camera_angle, composition_notes, dialogue_note, visual_description.
- `image_prompts`: prompt và negative prompt của từng panel, giữ thứ tự panel.
- `character_notes`: hồ sơ nhân vật + memory/canon quan trọng đang dùng.
- `style_notes`: style bible + anime/manga/webtoon guidance nếu nguồn là truyện.
- `must_have`: must_have từ Master Story + ràng buộc quan trọng từ panel.
- `avoid`: avoid/negative rules + negative_prompt tổng hợp.

Nếu nội dung quá dài, backend chia thành nhiều block có hậu tố theo thứ tự, ví dụ `storyboard_panels_01`, `storyboard_panels_02`, nhưng vẫn giữ thứ tự panel và không làm mất các trường quan trọng.

### 4. Metadata audit rõ ràng

Video adaptation payload phải ghi rõ:

- `handoff_source: "image_story_prompts"`
- `source_mode_requested`
- `source_mode_resolved`
- `source_panel_count`
- `source_prompt_count`
- `source_image_adaptation_id`
- `source_image_adaptation_revision`
- `story_episode_output_intent`
- `settings_source`
- `auto_run_id` nếu đã start auto-run
- `ai_video_url`

Metadata này giúp người dùng biết video được tạo từ prompt truyện, không phải chỉ từ Master Story.

### 5. UI Story Studio

Trong phần `Video truyện`, thêm hành động riêng khi có panel prompt:

- `Handoff video từ truyện`
- hoặc `Tạo prompt video`

Hành động này:

1. Gọi video adaptation với `source_mode = "image_story_prompts"`.
2. Nếu người dùng chọn auto-run, backend hoặc UI start AI Video auto-run `material_target = "prompts_only"`.
3. Hiển thị trạng thái “đã tạo project video / đang tạo prompt video / hoàn tất prompt video”.
4. Hiển thị link mở AI Video project.

### 6. Không render ngoài ý muốn

Flow này không được gọi:

- image render endpoint;
- Veo/video clip generation;
- voice generation;
- subtitle generation;
- MP4 render.

Chỉ dừng ở project video và prompt video.

## Rủi ro và kiểm soát

- Dữ liệu 40 panel có thể dài: cần chunk có thứ tự, không cắt mất prompt quan trọng.
- Prompt ảnh có thể quá cụ thể cho ảnh tĩnh: AI Video cần nhận thêm chỉ dẫn “phát triển lại thành video”, không copy máy móc từng prompt ảnh.
- Nếu đã có AI Video project cùng series/tập: nên mở existing nếu liên kết đã có; nếu trùng không rõ nguồn, backend phải báo lỗi an toàn.
