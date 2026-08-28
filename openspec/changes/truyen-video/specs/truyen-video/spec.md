# Capability: Truyện ảnh sang video

## ADDED Requirements

### Requirement: Handoff video thủ công từ tập truyện ảnh

Hệ thống MUST cho phép người dùng tạo video handoff thủ công từ một Story Episode có `output_intent = "truyen_anh"` khi tập đó đã có dữ liệu truyện đủ rõ để AI Video phát triển lại thành video.

#### Scenario: Tập truyện ảnh có panel prompt được handoff sang AI Video

- **GIVEN** một Story Episode có `output_intent = "truyen_anh"`
- **AND** Master Story đã được duyệt hoặc image adaptation có panel prompt hợp lệ
- **AND** người dùng chọn handoff video từ truyện ảnh
- **WHEN** backend tạo video adaptation
- **THEN** backend tạo hoặc mở AI Video project được liên kết với Story Episode
- **AND** backend không chặn chỉ vì episode là `truyen_anh`
- **AND** video adaptation trả về `linked_video_project_id`

#### Scenario: Tập truyện ảnh chưa có prompt truyện

- **GIVEN** một Story Episode có `output_intent = "truyen_anh"`
- **AND** chưa có image adaptation panels hoặc các panels không có nội dung prompt/visual đủ dùng
- **WHEN** người dùng yêu cầu handoff video từ truyện ảnh
- **THEN** backend từ chối bằng lỗi có thể đọc được
- **AND** lỗi hướng dẫn người dùng tạo prompt truyện trước

### Requirement: Dữ liệu truyện ảnh được truyền rõ sang AI Video

Khi handoff từ truyện ảnh, hệ thống MUST truyền dữ liệu truyện sang AI Video bằng source blocks có cấu trúc, đủ để AI Video phát triển lại thành kịch bản/prompt video mà không chỉ dựa vào một logline ngắn.

#### Scenario: Source blocks chứa storyboard và prompt ảnh

- **GIVEN** image adaptation có nhiều panel prompt theo thứ tự
- **WHEN** backend tạo AI Video project từ truyện ảnh
- **THEN** source blocks của project bao gồm dữ liệu Master Story nếu có
- **AND** source blocks bao gồm storyboard panel theo thứ tự
- **AND** mỗi panel giữ các trường có sẵn như caption/dialogue, scene_context, camera_angle, composition_notes, dialogue_note, visual_description, prompt, negative_prompt
- **AND** source blocks bao gồm character/style/must_have/avoid/canon context khi có

#### Scenario: Dữ liệu panel dài cần chia block

- **GIVEN** truyện ảnh có nhiều panel hoặc prompt dài
- **WHEN** backend format source blocks cho AI Video
- **THEN** backend có thể chia storyboard/prompt thành nhiều block có thứ tự
- **AND** thứ tự panel không bị đảo
- **AND** các trường quan trọng không bị loại bỏ im lặng

### Requirement: Metadata handoff phải nêu rõ nguồn

Video adaptation payload MUST ghi rõ nguồn dữ liệu handoff để người dùng và hệ thống phân biệt handoff từ Master Story với handoff từ prompt truyện.

#### Scenario: Payload ghi nguồn image_story_prompts

- **GIVEN** người dùng handoff video từ truyện ảnh
- **WHEN** backend lưu video adaptation
- **THEN** `payload_json.handoff_source` bằng `"image_story_prompts"`
- **AND** payload có `source_mode_requested`
- **AND** payload có `source_mode_resolved`
- **AND** payload có `source_panel_count`
- **AND** payload có `source_prompt_count`
- **AND** payload có `source_image_adaptation_id` nếu dùng image adaptation
- **AND** payload có `source_image_adaptation_revision` nếu dùng image adaptation

### Requirement: Có thể tự chạy đến bước prompt video

Hệ thống MUST hỗ trợ tùy chọn sau handoff để tự chạy AI Video đến bước prompt video và dừng lại, không tạo các vật liệu/render sau đó.

#### Scenario: Start auto-run prompts_only sau handoff

- **GIVEN** video handoff từ truyện ảnh tạo được AI Video project
- **AND** request yêu cầu `start_auto_run = true`
- **WHEN** backend start auto-run
- **THEN** auto-run dùng `material_target = "prompts_only"`
- **AND** hệ thống dừng sau khi tạo prompt video
- **AND** hệ thống không gọi Veo/video clips
- **AND** hệ thống không tạo voice
- **AND** hệ thống không tạo subtitle
- **AND** hệ thống không render MP4

### Requirement: UI phân biệt handoff video từ truyện

Story Studio UI MUST có hành động rõ ràng để handoff video từ prompt truyện, không lẫn với render ảnh hoặc handoff video mặc định.

#### Scenario: Người dùng thấy hành động sau khi có prompt truyện

- **GIVEN** Story Episode đã có panel prompt
- **WHEN** người dùng mở phần Video truyện trong Story Studio
- **THEN** UI hiển thị hành động handoff video từ truyện hoặc tạo prompt video
- **AND** UI giải thích luồng này không render ảnh/video
- **AND** sau khi thành công UI hiển thị link mở AI Video project
