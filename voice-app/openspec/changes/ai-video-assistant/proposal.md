## Vì sao

Voicebox đã hoàn thành phần Voice/TTS và voice clone, nhưng người dùng không rành kỹ thuật vẫn phải tự nghĩ kịch bản, chia cảnh, viết prompt ảnh và tạo giọng đọc từng đoạn trước khi mang vào phần mềm dựng phim. Thay đổi này thêm một **AI Video Assistant** dạng wizard để người dùng nhập một ý tưởng ngắn và nhận lại một bộ nguyên liệu sẵn sàng dựng video: prompt ảnh dễ copy, giọng đọc từng cảnh và phụ đề `.srt` khớp timing. Người dùng tự dựng video cuối trong Premiere (hoặc phần mềm tương đương), nên MVP không cần render MP4 trong app.

## Thay đổi

- Thêm workflow AI Video Assistant hướng dẫn người dùng qua các bước: nhập ý tưởng, duyệt kịch bản, chia scene, tạo prompt ảnh, (tùy chọn) upload ảnh để xem trước, tạo giọng đọc, tạo phụ đề và tải gói nguyên liệu.
- Dùng **Codex CLI có sẵn trong máy** (qua cấu hình setting) để tạo creative brief, kịch bản, scene breakdown, style bible, character consistency note và prompt ảnh dễ copy. Không cần OpenAI API key riêng; setting được thiết kế để sau này có thể đổi sang provider khác mà không sửa code.
- Giữ bước tạo ảnh ở dạng thủ công: Voicebox tạo prompt, người dùng render ảnh bằng tool ngoài. Người dùng có thể upload ảnh vào từng scene **chỉ để xem trước cho khớp prompt**, không dùng để render trong app.
- Lưu trạng thái video project gồm scene, prompt pack, ảnh preview đã upload, voice generation và subtitle.
- Tái sử dụng flow TTS hiện có của Voicebox để tạo narration theo từng scene, không thêm voice engine mới.
- Tạo phụ đề `.srt` theo thứ tự scene và duration thật của audio để khớp khi kéo vào timeline Premiere.
- Cho phép lấy nguyên liệu theo hai cách: copy/tải lẻ từng phần (prompt từng cảnh, voice từng cảnh, file `.srt`) và một nút "Tải tất cả" đóng gói `.zip` đặt tên theo thứ tự cảnh.
- Dùng tiếng Việt cho giao diện workflow mặc định và các tên file người dùng tải về.
- Thêm log lỗi chi tiết cho API, AI planning (Codex CLI), upload ảnh và voice generation để dễ bắt lỗi khi người dùng báo sự cố.

## Capabilities

### New Capabilities
- `ai-video-assistant`: Workflow từ ý tưởng đến **bộ nguyên liệu dựng video**, gồm tạo project, Codex CLI hỗ trợ viết script/scene/prompt, người dùng upload ảnh preview từng scene, Voicebox tạo narration, tạo phụ đề `.srt` và đóng gói tải về (copy/lẻ và `.zip`).

### Modified Capabilities
- Không có.

## Ảnh hưởng

- Backend: thêm API video project, scene, asset preview, voice status, subtitle và download/đóng gói; thêm storage dưới data dir; tích hợp với flow `/generate` hiện có; thêm service gọi Codex CLI (`codex exec`).
- Frontend: thêm wizard tiếng Việt cho người không rành kỹ thuật: nhập ý tưởng, duyệt kịch bản, copy prompt, upload ảnh preview, theo dõi voice và tải gói nguyên liệu.
- Data: thêm bảng SQLite cho video project/scene/asset preview và subtitle (theo đúng pattern migration sẵn có của Voicebox, không thêm Alembic); file storage cho prompt, ảnh preview, audio reference và subtitle.
- Dependencies: cần **Codex CLI** có trong máy và đã đăng nhập để chạy bước planning/prompt. Không cần FFmpeg vì MVP không render MP4.
- Logging/Debug: thêm mã lỗi, correlation ID/request ID, log theo từng project/scene và thông báo lỗi thân thiện cho người dùng.
- Hệ thống hiện có: voice profile, generation history, audio serving và story audio timeline vẫn tương thích, được tái sử dụng thay vì thay thế.
