# Handoff Video Inspiration và Bộ nhớ Dự án AI Video

Tài liệu này mô tả luồng chuyển một video đã phân tích trong Video Inspiration sang AI Video theo change `10.chuan-hoa-handoff-va-bo-nho-du-an-ai-video`.

## Mục tiêu

Video Inspiration không chỉ đẩy một nhóm source block văn bản sang AI Video. Backend tạo một handoff bền vững, có mã, revision, trạng thái, gói phân tích nguồn và script đích đã duyệt. AI Video dùng handoff này để tạo Project Memory, timeline đích và các context snapshot theo từng nhiệm vụ.

Luồng mặc định vẫn giữ quyền quyết định của người dùng. Tạo project từ handoff không tự chạy auto-run, không gọi Veo, không render MP4 và không tự chọn cấu hình sản xuất ngoài các giá trị người dùng đã xác nhận hoặc mặc định thủ công của project.

## Handoff bền vững

Bảng `video_inspiration_handoffs` lưu:

- `job_id`: job Video Inspiration nguồn.
- `analysis_package_path` và `analysis_package_revision`: dấu vết gói phân tích timeline.
- `schema_version`: phiên bản schema handoff.
- `status`: `draft`, `ready_for_review`, `approved`, `consumed`, `stale` hoặc `failed`.
- `approved_script_revision`: revision script đích đã duyệt.
- `payload_json`: payload có cấu trúc.
- `source_blocks_json`: projection tương thích cho workflow source block cũ.
- `created_project_id`: project AI Video đã được tạo từ handoff nếu có.
- `revision`, `created_at`, `updated_at`, `approved_at`.

Endpoint chính:

- `POST /video-inspiration/jobs/{job_id}/handoffs`: tạo hoặc refresh handoff ở trạng thái review.
- `GET /video-inspiration/jobs/{job_id}/handoffs`: đọc danh sách handoff của job.
- `POST /video-inspiration/jobs/{job_id}/create-ai-video-project`: tạo project thủ công từ handoff đã được backend approve/consume. Mặc định không auto-run.

Nếu thiếu `VideoAnalysisPackage` hoặc script đích đã duyệt, backend chặn tạo handoff/project và trả lỗi tiếng Việt với error code rõ ràng.

## Payload có cấu trúc

`payload_json` tách dữ liệu thành các lớp:

- `source_analysis_ref`: job, schema, analysis package path, completeness và nguồn retention.
- `source_observations`: shot, transcript segment, audio event, OCR/text event, coverage metrics và limitations.
- `learnable_lessons`: content spine, retention map, visual grammar, audio grammar, strengths và rewrite opportunities.
- `target_content`: target audience, video goal, content spine, hook contract, approved script, character/setting state, visual/audio direction, voice/language, must-have và avoid.
- `originality_boundaries`: điều được học và điều không được copy.
- `evidence_refs`: liên kết bằng chứng từ beat, text event hoặc source event.
- `limitations`: hạn chế phân tích.

Transcript nguồn chỉ là bằng chứng hoặc dữ liệu đối chiếu. Voice và subtitle phải dùng narration/script đích đã duyệt.

## Source blocks tương thích

AI Video cũ vẫn có thể đọc source blocks. Backend dựng các block tương thích từ payload có cấu trúc:

- `idea`
- `rough_script`
- `character_notes`
- `style_notes`
- `must_have`
- `avoid`
- `analysis`
- `transcript`

Payload có cấu trúc vẫn là nguồn chuẩn. Source blocks chỉ là projection để giữ tương thích và giúp UI cũ hiển thị được dữ liệu.

## Bộ nhớ Dự án

Khi project AI Video được tạo từ handoff, backend tạo các thẻ trong `video_project_memory_cards` với `memory_scope = "project"` và `status = "approved"`.

Các loại thẻ chính:

- `project_identity`
- `target_audience`
- `video_goal`
- `content_spine`
- `hook_and_payoff`
- `retention_map`
- `character_state`
- `visual_direction`
- `audio_direction`
- `voice_and_language`
- `approved_decision`
- `must_have`
- `avoid`
- `source_evidence`

Project không thuộc series dùng Project Memory làm nguồn chuẩn cấp project. Project thuộc series vẫn giữ `series_id` trong thẻ để các workflow sau có thể kết hợp Project Memory với Series Canon theo thứ tự ưu tiên: canon cố định trước, quyết định project đã duyệt sau.

API tạo project từ handoff có thể nhận `series_id`. Khi có `series_id`, Project Memory không ghi ngược vào Series Canon. Nếu project phát hiện thay đổi có ý nghĩa dài hạn, thay đổi đó phải đi qua luồng đề xuất/cập nhật series riêng thay vì âm thầm sửa canon.

## Timeline đích

Timeline đích được lưu trong `video_project_target_timeline_beats`.

Planner không copy timestamp hoặc chuỗi shot nguồn. Nó dùng retention map, content spine, mục tiêu video và cấu hình project để tạo beat mới theo duration đích. Mỗi beat gồm:

- `beat_order`
- `start_seconds`, `end_seconds`, `duration_seconds`
- `role`
- `content`
- `viewer_question`
- `new_information`
- `micro_payoff`
- `visual_direction`
- `audio_direction`
- `evidence_refs_json`
- `source_lesson_refs_json`
- `revision`

Nếu project chưa có duration, planner dùng duration tối thiểu hợp lý và số beat từ retention map nguồn. Đây là timeline đích để sản xuất video mới, không phải timeline nguồn được co giãn.

## Context snapshot theo nhiệm vụ

Endpoint:

- `POST /ai-video/projects/{project_id}/context/compile`
- `GET /ai-video/projects/{project_id}/context/snapshots`

Các task hỗ trợ:

- `story`
- `shot`
- `prompt_image`
- `prompt_video`
- `voice`
- `subtitle`

Context compiler chọn dữ liệu đúng nhiệm vụ:

- Story nhận target audience, goal, content spine, hook/payoff, retention, avoid và một phần timeline đích.
- Shot/prompt nhận timeline đích, visual/audio direction, retention role, must-have và avoid.
- Voice/subtitle nhận narration đích đã duyệt, voice/language, hook/payoff; không lấy transcript nguồn làm lời đọc mặc định.

Mỗi lần compile lưu `video_project_context_snapshots` với `context_json` và `source_refs_json` để truy xuất dữ liệu đã dùng.

## Revision, dependency và stale

Handoff, Project Memory và timeline đích đều có revision. Với project thuộc series, backend ghi `artifact_dependency_snapshots` từ handoff sang các phạm vi:

- `video_project`
- `video_story`
- `video_shot`
- `video_prompt`
- `scene_voice`
- `subtitle`
- `package`

Khi narration/script đích đổi, handoff chuyển sang `stale`, project được đánh dấu `planning_status = "stale"`, package hiện tại stale và `artifact_stale_events` được tạo cho voice, subtitle và package với lý do tiếng Việt. Prompt/style không bị stale chỉ vì transcript nguồn đổi.

Khi transcript nguồn được sửa để đối chiếu, backend invalidates analysis package của job nguồn nhưng không mặc định stale voice/subtitle của project đã tạo, vì voice/subtitle phụ thuộc narration đích đã duyệt chứ không phụ thuộc toàn bộ transcript nguồn.

## UI

Video Inspiration có tab `Handoff` để tạo/review handoff backend trước khi tạo project. Tab này hiển thị:

- nguồn quan sát;
- bài học được phép học;
- nội dung đích đã duyệt;
- originality/evidence/limitations;
- source blocks tương thích.

AI Video có khu vực `Bộ nhớ dự án` để xem Project Memory, timeline đích và context snapshot gần đây. Các nút Story, Shot, Prompt, Voice và Subtitle chỉ compile context snapshot; chúng không chạy generation.

## Nguyên tắc vận hành

- Không tạo project nếu thiếu analysis package hoặc script đích đã duyệt.
- Không dùng transcript nguồn như narration đích.
- Không copy chuỗi shot nguồn thành timeline đích.
- Không tự chạy auto-run hoặc gọi Veo khi người dùng chưa yêu cầu.
- Chỉ dữ liệu người dùng nhập hoặc kết quả đã duyệt mới trở thành Project Memory chuẩn.
- Source blocks cũ được giữ để tương thích, nhưng payload handoff có cấu trúc là nguồn chuẩn.
