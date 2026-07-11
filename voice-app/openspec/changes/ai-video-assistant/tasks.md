## 1. Data Model và Storage

- [x] 1.1 Thêm SQLite models và migrations cho video projects, video scenes, scene prompt artifacts, preview image assets, subtitles và package exports mà không sửa requirement hiện có của voice/story.
- [x] 1.2 Tuân theo pattern migration hiện có trong `backend/database/migrations.py` (`_migrate_*` idempotent); không thêm Alembic.
- [x] 1.3 Thêm Pydantic request/response models cho tạo video project, project detail, scene updates, prompt packs, preview image assets, voice status, subtitles và package exports.
- [x] 1.4 Thêm storage helpers cho `data/video_projects/{project_id}/` với subfolders cho prompts, preview images, subtitles, package manifests và zip exports.
- [x] 1.5 Thêm cleanup an toàn cho video project bị xóa và scene preview image bị thay thế, không xóa nhầm generation audio hiện có.
- [x] 1.6 Thêm helper tạo tên file tải về bằng tiếng Việt đã sanitize, giữ storage nội bộ bằng ID/UUID an toàn.

## 2. Backend Video Project APIs

- [x] 2.1 Thêm routes tạo, list, retrieve, update và delete video projects.
- [x] 2.2 Thêm routes retrieve/update ordered scene data cho project.
- [x] 2.3 Thêm route đánh dấu từng scene đã được duyệt (per-scene approval), cho phép tạo prompt/voice cho scene đã duyệt mà không cần duyệt toàn bộ kịch bản.
- [x] 2.4 Thêm project status calculation: thiếu script, thiếu prompt, thiếu voice (chỉ tính scene có lời và chưa đánh dấu cố ý không lời), thiếu subtitle, package cũ và package readiness.
- [x] 2.5 Thêm backend validation để không tạo package khi còn scene có lời thoại thiếu narration bắt buộc hoặc subtitle chưa sẵn sàng; scene cố ý không lời không bị tính là thiếu.
- [x] 2.6 Chuẩn hóa API error response cho AI Video Assistant gồm message tiếng Việt thân thiện, error code và request ID.
- [x] 2.7 Thêm endpoint kiểm tra cấu hình AI planning provider để UI biết Codex CLI đã sẵn sàng hay chưa, dùng được để hiển thị lỗi inline trong wizard.
- [x] 2.8 Thêm route đánh dấu/bỏ đánh dấu một scene là cố ý không lời (no-narration) để loại scene đó khỏi yêu cầu voice và readiness.

## 3. Logging và Debuggability

- [x] 3.1 Thêm request/correlation ID cho các API AI Video Assistant và đưa ID đó vào log cũng như response lỗi.
- [x] 3.2 Thêm structured logging cho project ID, scene ID, asset ID, generation ID, package export ID, endpoint, step name và elapsed time.
- [x] 3.3 Log lỗi Codex CLI planning/prompt generation với provider/model, command path, timeout, exit code, validation errors, request ID và exception class, nhưng không log token/secret.
- [x] 3.4 Log lỗi upload image preview với project ID, scene ID, sanitized filename, MIME/type, file size và lý do reject.
- [x] 3.5 Log lỗi voice generation theo scene với project ID, scene ID, voice profile ID, generation ID nếu có và failure reason.
- [x] 3.6 Log lỗi subtitle/package export với project ID, package export ID nếu có, artifact còn thiếu, file path nội bộ đã sanitize và exception class.
- [x] 3.7 Thêm advanced debug panel hoặc debug details endpoint an toàn để developer xem request ID/package ID liên quan khi người dùng báo lỗi.

## 4. Codex CLI Planning Services

- [x] 4.1 Thêm settings cho AI planning provider: `provider`, `codex_path`, model mặc định, timeout và output schema path; mặc định dùng `codex-cli`.
- [x] 4.2 Implement provider check chạy lệnh nhẹ để xác minh Codex CLI tồn tại, chạy được và đã đăng nhập; trả lỗi tiếng Việt khi chưa sẵn sàng.
- [x] 4.3 Implement service gọi `codex exec` non-interactive cho creative brief generation từ topic và user preferences cơ bản.
- [x] 4.4 Implement structured script và scene generation với lời thoại, mô tả hình ảnh, target duration và scene order.
- [x] 4.5 Implement regenerate một scene, chỉ update scene đó mà không thay toàn bộ project.
- [x] 4.6 Validate và persist AI output dạng structured artifacts, lỗi invalid output phải trả retry error thân thiện và log chi tiết.
- [x] 4.7 Đảm bảo prompt/system instruction yêu cầu output phù hợp tiếng Việt khi project language là tiếng Việt.
- [x] 4.8 Thiết kế provider interface đủ hẹp để sau này có thể thêm provider khác hoặc local LLM mà không sửa UI wizard.

## 5. Image Prompt và Preview Workflow

- [x] 5.1 Implement style bible và character consistency artifact generation cho approved scenes.
- [x] 5.2 Implement prompt pack per scene gồm main prompt, negative prompt, aspect ratio, style notes và character notes.
- [x] 5.3 Thêm API fetch/copy complete plain-text prompt content cho từng scene.
- [x] 5.4 Thêm endpoint tải prompt của từng scene và prompt pack với filename tiếng Việt, ví dụ `Prompt ảnh - Cảnh 01.txt`.
- [x] 5.5 Thêm API upload image preview file được hỗ trợ cho một scene và lưu dưới video project folder.
- [x] 5.6 Thêm API replace active preview image cho một scene, giữ project state cũ khi hữu ích.
- [x] 5.7 Thêm image preview serving endpoint với safe path resolution.
- [x] 5.8 Đảm bảo thiếu ảnh preview không chặn tạo voice, tạo subtitle hoặc tải package.

## 6. Voice và Subtitle Integration

- [x] 6.1 Thêm service logic tạo narration theo scene bằng generation behavior hiện có của Voicebox và voice profile đã chọn.
- [x] 6.2 Lưu scene narration generation ID, status, audio path hoặc audio URL, actual duration và failure reason.
- [x] 6.3 Thêm retry cho scene narration failed mà không tạo lại audio đã completed.
- [x] 6.4 Thêm endpoint tải audio của từng scene với filename tiếng Việt, ví dụ `Giọng đọc - Cảnh 01.wav`.
- [x] 6.5 Thêm subtitle generation từ scene dialogue và actual scene audio duration.
- [x] 6.6 Thêm subtitle splitting rules để caption dễ đọc theo aspect ratio và duration audio.
- [x] 6.7 Mark prompt ảnh, voice, subtitle và package của scene là stale khi scene dialogue/mô tả hình ảnh hoặc project voice profile thay đổi.
- [x] 6.8 Thêm endpoint tải subtitle với filename tiếng Việt, ví dụ `Phụ đề - <Tên dự án>.srt`.

## 7. Package Export cho Premiere

- [x] 7.1 Implement package readiness checklist: prompt đã có, narration bắt buộc completed, subtitle sẵn sàng, preview images optional.
- [x] 7.2 Implement package manifest JSON dễ đọc gồm project title, language, aspect ratio, scene order, prompt filenames, audio filenames, subtitle filename và preview image filenames nếu có.
- [x] 7.3 Implement ZIP creation cho bộ nguyên liệu: prompt từng scene, audio từng scene, subtitle `.srt`, manifest và ảnh preview nếu có.
- [x] 7.4 Thêm file hướng dẫn ngắn trong ZIP, ví dụ `00 - Huong dan.txt`, giải thích thứ tự thư mục và cách mang vào Premiere ở mức non-tech.
- [x] 7.5 Thêm endpoint tạo/tải package ZIP với filename tiếng Việt, ví dụ `Bộ nguyên liệu - <Tên dự án>.zip`.
- [x] 7.6 Persist package export status, created_at, stale flag, manifest path, zip path và failure reason.
- [x] 7.7 Đảm bảo package cũ bị đánh dấu stale khi script, prompt, voice hoặc subtitle thay đổi.
- [x] 7.8 Giới hạn path traversal và sanitize mọi filename trước khi ghi ZIP.

## 8. Frontend AI Video Assistant Wizard

- [x] 8.1 Thêm top-level AI Video Assistant page/route mà không ảnh hưởng voice/profile/story screens hiện có.
- [x] 8.2 Xác minh frontend dependencies trước khi implement UI: Tailwind v4, Framer Motion hiện có, icon library hiện có; nếu dùng Phosphor/Radix icons theo `design-taste-frontend-v1` thì thêm dependency rõ ràng trước khi import.
- [x] 8.3 Xác định visual direction cho AI Video Assistant: neutral light base, một accent color saturation thấp, không neon glow, không tím/xanh AI generic, không emoji.
- [x] 8.4 Build shell layout desktop dạng split/asymmetric: cột thao tác chính cho wizard và vùng preview/status phụ, không dùng centered hero hoặc 3-card row cho workflow chính.
- [x] 8.5 Build mobile layout collapse một cột an toàn, không horizontal scroll, không text overlap và không dùng `h-screen` cho section full-height.
- [x] 8.6 Build bước nhập ý tưởng với fields tiếng Việt: chủ đề, ngôn ngữ, thời lượng, tỷ lệ video, phong cách ảnh và voice profile; mọi field có label phía trên, helper/error text phía dưới.
- [x] 8.7 Build kiểm tra Codex CLI hiển thị inline ngay tại bước đang làm trong wizard với thông báo sẵn sàng hoặc lỗi cấu hình dễ hiểu kèm nút thử lại; không bắt người dùng vào Settings.
- [x] 8.8 Build bước duyệt kịch bản với scene rows/cards dễ đọc, approve và regenerate per-scene, đánh dấu scene cố ý không lời, tránh lạm dụng nested cards.
- [x] 8.9 Build bước prompt/ảnh preview với Copy Prompt, tải prompt, upload ảnh preview, preview ảnh và tactile active/pressed states cho nút chính.
- [x] 8.10 Build bước voice/subtitle với generate/retry controls per-scene, trạng thái narration theo scene, đánh dấu scene cố ý không lời, indicator "cần làm lại" cho prompt/voice/subtitle khi scene bị sửa, tải audio từng scene và tạo/tải `.srt`.
- [x] 8.11 Build bước tải nguyên liệu với readiness checklist, tải lẻ từng phần, nút `Tải tất cả (.zip)` và stale-package messaging.
- [x] 8.12 Thêm skeleton loading theo đúng layout, empty state có hướng dẫn rõ ràng và inline error state cho từng bước wizard.
- [x] 8.13 Cô lập animation/micro-interactions trong component nhỏ, chỉ animate transform/opacity và tránh re-render nặng ở parent wizard.
- [x] 8.14 Ẩn technical metadata mặc định; internal JSON, IDs, file paths, package manifests và request IDs nằm trong advanced/debug view.
- [x] 8.15 Viết toàn bộ copy chính của wizard bằng tiếng Việt trước, chuẩn bị key i18n để thêm ngôn ngữ khác sau.
- [x] 8.16 Hiển thị lỗi API/Codex/voice/package bằng tiếng Việt kèm request ID hoặc mã lỗi để người dùng gửi lại cho developer.

## 9. Tests và Verification

- [x] 9.1 Thêm backend unit tests cho tạo, lưu, retrieve và delete video project.
- [x] 9.2 Thêm backend tests cho Codex CLI provider check: path thiếu, command lỗi, timeout và success mocked.
- [x] 9.3 Thêm backend tests cho structured AI artifact validation và retryable failure responses.
- [x] 9.4 Thêm backend tests cho prompt pack generation/storage và scene preview image upload/replacement.
- [x] 9.5 Thêm backend tests cho filename tiếng Việt đã sanitize ở prompt, audio, subtitle và ZIP package download.
- [x] 9.6 Thêm backend tests cho error response có error code/request ID và log context cơ bản.
- [x] 9.7 Thêm backend tests cho scene narration status updates dùng mocked Voicebox generation.
- [x] 9.8 Thêm backend tests cho subtitle generation từ actual audio durations.
- [x] 9.9 Thêm backend tests cho package readiness validation, ZIP content list, manifest content và missing-artifact errors.
- [x] 9.10 Thêm frontend tests hoặc manual verification notes cho wizard tiếng Việt từ topic đến tải ZIP.
- [x] 9.11 Thêm visual QA checklist cho AI Video Assistant: desktop asymmetric layout, mobile one-column layout, no emoji, no neon/purple AI palette, loading/empty/error states, no text overlap.
- [x] 9.12 Chạy frontend typecheck và kiểm tra responsive screenshots/manual QA cho desktop và mobile trước khi đánh dấu UI task hoàn tất.
- [x] 9.13 Chạy targeted backend tests và frontend typecheck trước khi đánh dấu change hoàn tất.
