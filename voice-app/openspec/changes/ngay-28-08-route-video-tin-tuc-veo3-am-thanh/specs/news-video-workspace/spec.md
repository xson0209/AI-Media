## ADDED Requirements

### Requirement: Có workspace Video tin tức và route riêng

Hệ thống SHALL cung cấp workspace frontend tại `/news-video` với tên hiển thị **Video tin tức**, API namespace `/news-video` và UI/artifact nghiệp vụ bằng tiếng Việt. Route SHALL đăng ký theo pattern hiện có của repo và SHALL được thêm vào danh sách `isWideWorkspace`. Provider prompt cũng SHALL mặc định tiếng Việt; technical token tiếng Anh chỉ là tùy chọn tương thích provider. Workspace SHALL không nhúng nguyên `AIVideoAssistant` và SHALL không yêu cầu client gọi trực tiếp endpoint nội bộ của `/ai-video`.

#### Scenario: Mở route Video tin tức

- **WHEN** người dùng truy cập `/news-video`
- **THEN** ứng dụng SHALL mở workspace riêng, hiển thị fallback/trạng thái bằng tiếng Việt và không làm thay đổi route `/ai-video`

#### Scenario: API facade tồn tại

- **WHEN** client gọi `/news-video/projects`
- **THEN** backend SHALL trả schema News Video ổn định, lỗi tiếng Việt và ẩn chi tiết credential/provider session

#### Scenario: Route cũ giữ nguyên

- **WHEN** người dùng sử dụng `/ai-video`, `/video-inspiration` hoặc `/product-video`
- **THEN** contract và hành vi hiện tại SHALL được giữ nguyên, bao gồm fallback speech legacy khi không có cấu hình News Video

### Requirement: Tạo project News Video bằng tiếng Việt

Hệ thống SHALL cho phép tạo, xem, sửa và liệt kê project News Video với chủ đề, input bài viết/transcript, `target_language=vi`, `aspect_ratio=9:16`, tổng thời lượng, thời lượng shot Veo, `visual_format` và nguồn lời mặc định. MVP SHALL lưu cấu hình News trong bảng liên kết một-dòng/project tới `video_projects`, tái sử dụng shot/prompt/clip hiện có và không tạo render project/kho clip song song. Sự tồn tại của row liên kết SHALL là discriminator duy nhất của News project.

#### Scenario: Tạo bản tin dọc

- **WHEN** người dùng gửi chủ đề, nội dung và cấu hình 9:16 hợp lệ
- **THEN** hệ thống SHALL tạo project trạng thái `draft`, đặt `target_language=vi`, đặt `language` tường minh, mặc định shot duration 8 giây và trả effective settings

#### Scenario: Cấu hình không hợp lệ

- **WHEN** tổng thời lượng, aspect ratio hoặc shot duration nằm ngoài giới hạn cấu hình
- **THEN** API SHALL từ chối bằng mã validation và thông báo tiếng Việt, SHALL NOT tạo project một phần

#### Scenario: Chọn visual format

- **WHEN** người dùng chọn `tech_explainer`, `newsroom_presenter`, `cinematic_broll`, `data_motion_graphics` hoặc `hyperframes_hybrid`
- **THEN** prompt SHALL dùng preset đặc tính hình ảnh tương ứng và SHALL NOT sao chép timeline/phong cách độc quyền từ nguồn tham khảo

### Requirement: Luồng hoạt động giống `/ai-video`

News Video SHALL dùng lại đúng máy móc luồng của `/ai-video`, SHALL NOT phát minh chuỗi bước riêng. Auto-run SHALL dùng nguyên `STEP_ORDER` và tập `material_target` hiện có, gồm cả các bước voice, subtitle, render và các tập bước bị skip theo từng target. UI SHALL có đủ năng lực như `/ai-video`, gồm **dựng MP4 tại chỗ**.

#### Scenario: Auto-run dùng chung chuỗi bước

- **WHEN** người dùng chạy auto-run ở `/news-video`
- **THEN** hệ thống SHALL đi theo cùng `STEP_ORDER` và cùng quy tắc skip theo `material_target` như `/ai-video`, SHALL NOT dùng stepper riêng của News

#### Scenario: Dựng MP4 tại chỗ

- **WHEN** project News Video có clip hợp lệ và audio theo nguồn lời hiệu lực
- **THEN** workspace SHALL cho dựng MP4 ngay trong route, tái dùng panel render hiện có, và render manifest SHALL nhận `effective_speech_source` theo từng shot

#### Scenario: Xoá logo và tải MP4 về

- **WHEN** người dùng dựng MP4 ở `/news-video`
- **THEN** workspace SHALL có đủ năng lực xoá logo/watermark, chọn backend, xem trạng thái worker và tải MP4 về như `/ai-video`; SHALL NOT viết lại panel render riêng

#### Scenario: Luồng bảy bước đầu-cuối

- **WHEN** người dùng đi hết luồng
- **THEN** workspace SHALL hỗ trợ: nhập nguồn tin → sinh prompt → copy sang Veo 3 → upload clip đã tải → xử lý âm thanh theo mode → dựng MP4 kèm xoá logo → tải MP4 về

#### Scenario: Chưa đủ dữ liệu

- **WHEN** project thiếu input hoặc shot chưa có visual/audio contract
- **THEN** workspace SHALL hiển thị trạng thái `Cần bổ sung`, lý do cụ thể và SHALL khóa action Copy prompt

#### Scenario: Sẵn sàng copy

- **WHEN** shot có provider content, source note và quality gate đạt
- **THEN** workspace SHALL hiển thị số shot sẵn sàng copy và action Copy/Download tương ứng

### Requirement: Tái sử dụng pipeline hiện có

News Video SHALL delegate storage, media probe, clip upload, Voicebox TTS, subtitle và render cho service/facade hiện có. News router SHALL NOT tạo FFmpeg pipeline hoặc bảng `video_shot_clips` thứ hai.

#### Scenario: Tạo TTS

- **WHEN** effective mode là `voicebox_co_context` hoặc `voicebox_khong_context` và voice profile hợp lệ
- **THEN** workspace SHALL gọi Voicebox TTS hiện có với narration tiếng Việt và trả trạng thái bằng tiếng Việt

#### Scenario: Hoàn thiện native

- **WHEN** effective mode là `veo_narration` hoặc `veo_dialogue`
- **THEN** workspace SHALL dùng audio clip Veo sau khi người dùng duyệt, SHALL không tạo TTS tương ứng

### Requirement: MVP chỉ handoff Veo thủ công

News Video SHALL chỉ sinh provider-ready prompt và nhận clip người dùng upload lại. Hệ thống MUST NOT tự submit prompt, tự đăng nhập Google, tự tiêu credit, tự điều khiển Chrome hoặc tự download từ Veo.

#### Scenario: Copy thủ công

- **WHEN** người dùng bấm Copy ở shot đạt gate
- **THEN** clipboard SHALL nhận provider-ready content đầy đủ và UI SHALL hướng dẫn “Dán vào Veo 3 và tải MP4 về”

#### Scenario: Không tự mở provider

- **WHEN** copy/download thành công
- **THEN** ứng dụng SHALL không tự mở Veo/Flow hoặc gọi automation route

### Requirement: Phạm vi project/shot và bảo mật

Mọi API News Video SHALL kiểm tra `project_id`/`shot_id` cùng phạm vi project trước khi đọc/ghi prompt, clip hoặc voice. MVP không giả định user-auth mới; response/log SHALL không chứa token, cookie, Chrome profile, header auth hoặc toàn bộ DOM.

#### Scenario: Shot không thuộc project

- **WHEN** client gửi shot không thuộc project được chọn
- **THEN** API SHALL trả not-found/forbidden bằng tiếng Việt và SHALL không tiết lộ prompt hoặc file
