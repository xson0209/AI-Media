## ADDED Requirements

### Requirement: Copy và download provider-ready prompt

Hệ thống SHALL cho phép copy prompt của một shot hoặc tải prompt pack UTF-8. Nội dung copy/download SHALL là provider-ready prompt đã resolve audio contract, không phải raw visual prompt thiếu lời/cấm lời.

#### Scenario: Copy prompt native

- **WHEN** shot `veo_narration` hoặc `veo_dialogue` đạt quality gate
- **THEN** clipboard SHALL có visual contract, exact Vietnamese speech, voice/delivery/timing/lip-sync, negative prompt và source/disclosure note cần thiết

#### Scenario: Copy prompt Voicebox

- **WHEN** shot `voicebox_co_context` hoặc `voicebox_khong_context` đạt quality gate
- **THEN** clipboard SHALL có visual prompt và lệnh cấm spoken words/lip-sync, ghi rõ Voicebox sẽ đọc hậu kỳ; mode có ngữ cảnh SHALL kèm lời để canh nhịp, mode không ngữ cảnh SHALL NOT chứa lời

#### Scenario: Download prompt pack

- **WHEN** người dùng tải toàn bộ project
- **THEN** file SHALL có thứ tự shot, shot id, duration, aspect ratio, provider content, negative prompt, nguồn lời hiệu lực, source refs tối thiểu, disclosure và tên file gợi ý

#### Scenario: Shot chưa đạt gate

- **WHEN** prompt thiếu audio contract, source note, visual field hoặc đang `stale/review_required/blocked`
- **THEN** Copy/Download SHALL bị vô hiệu hóa hoặc trả lỗi tiếng Việt và SHALL không phát hành prompt thiếu trường bắt buộc

### Requirement: Mapping tên file với shot explicit

Hệ thống SHALL đề xuất tên file ổn định gồm slug an toàn, số shot zero-padding và revision; mapping cuối cùng SHALL dựa trên `shot_id` người dùng xác nhận, không dựa vào file mới nhất trong Downloads.

#### Scenario: Tên file chuẩn

- **WHEN** project slug là `ai-chip-moi`, shot thứ nhất revision một
- **THEN** UI SHALL đề xuất `news_ai-chip-moi_s01_v1.mp4` và liên kết với shot id tương ứng

#### Scenario: Filename không khớp

- **WHEN** người dùng chọn file tên khác hoặc revision cũ
- **THEN** UI SHALL cho chọn shot đích explicit, hiển thị cảnh báo mismatch và SHALL không tự đoán shot

### Requirement: Upload clip thủ công có probe

Hệ thống SHALL cho phép upload MP4 vào shot cụ thể, kiểm tra MIME/codec, duration, width/height, aspect ratio và audio stream, rồi delegate storage/probe cho service hiện có. Upload SHALL không ghi đè shot khác do filename trùng.

#### Scenario: Upload hợp lệ

- **WHEN** người dùng chọn clip hợp lệ cho shot đích
- **THEN** hệ thống SHALL lưu clip active vào render projection hiện có và hiển thị metadata bằng tiếng Việt cùng nguồn lời hiệu lực

#### Scenario: Probe không phải bằng chứng có lời

- **WHEN** probe trả `has_audio` true và mức âm bình thường
- **THEN** hệ thống SHALL NOT kết luận clip có lời thoại, vì nhạc/ambience/SFX làm mức âm không phân biệt được clip thiếu lời

#### Scenario: File lỗi hoặc sai tỷ lệ

- **WHEN** probe thất bại, codec không hỗ trợ hoặc duration/aspect lệch giới hạn
- **THEN** hệ thống SHALL giữ clip cũ, trả lý do tiếng Việt và yêu cầu retry/xác nhận; SHALL không crop/trim im lặng

#### Scenario: Thay clip active

- **WHEN** người dùng upload clip mới cho shot đã có clip
- **THEN** hệ thống SHALL giữ lịch sử metadata tối thiểu, deactive clip cũ, đánh dấu subtitle/render stale và không làm đổi shot khác

### Requirement: Review native speech trước readiness

Hệ thống SHALL có action `approved`, `rejected` hoặc `needs_review` cho clip `veo_narration`/`veo_dialogue`, kèm ghi chú tùy chọn. Chỉ `approved` mới qua native audio gate.

#### Scenario: Duyệt native

- **WHEN** người dùng nghe và xác nhận câu, phát âm, speaker, timing và lip-sync
- **THEN** hệ thống SHALL lưu trạng thái approved và cập nhật readiness; SHALL không tạo TTS

#### Scenario: Từ chối native

- **WHEN** clip đọc sai, thêm lời, sai speaker hoặc lip-sync lỗi
- **THEN** hệ thống SHALL giữ clip để tham khảo, chặn render và hướng dẫn tạo lại/đổi mode

### Requirement: Hướng dẫn thủ công bằng tiếng Việt

UI SHALL hiển thị các trạng thái `Chưa copy`, `Đã copy`, `Chờ tải Veo`, `Chờ upload`, `Đã upload`, `Cần nghe duyệt`, `Stale` và `Hoàn tất`; lỗi clipboard/upload SHALL không làm mất mapping đã có.

#### Scenario: Sau khi copy

- **WHEN** clipboard copy thành công
- **THEN** UI SHALL hiển thị shot/file đích và bước tiếp theo “Dán vào Veo 3 và tải MP4 về”, không tự mở provider

#### Scenario: Sau khi upload

- **WHEN** probe/import thành công
- **THEN** UI SHALL hiển thị duration/aspect/audio và action tiếp theo là nghe duyệt native hoặc tạo TTS Voicebox
