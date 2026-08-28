## ADDED Requirements

### Requirement: Chỉ handoff nội dung đã duyệt
Hệ thống SHALL chỉ cho tạo Research Handoff từ accepted idea/script, approved memory, user brief và score/recommendation còn hiệu lực; raw run, draft và item rejected SHALL bị loại.

#### Scenario: Handoff hợp lệ
- **WHEN** người dùng chọn accepted idea/script và bấm đóng gói
- **THEN** hệ thống tạo handoff revision có provenance, evidence, score, must-have/avoid, limitations và danh sách nguồn/project đã chọn

#### Scenario: Handoff thiếu approval
- **WHEN** người dùng chọn item candidate hoặc score stale
- **THEN** hệ thống chặn handoff, nêu item cần duyệt/chấm lại và không tạo AI Video project dở dang

### Requirement: Tạo AI Video project và deep-link
Hệ thống SHALL chuyển Research Handoff thành source blocks/Project Memory tương thích với AI Video, tạo project mới qua service hiện tại, trả project id và mở được route `/ai-video?projectId=<id>`.

#### Scenario: Tạo project thành công
- **WHEN** handoff commit thành công
- **THEN** hệ thống lưu mapping Research Project → Handoff → AI Video Project, tạo source blocks và điều hướng người dùng thẳng tới AI Video project vừa tạo

#### Scenario: Handoff bấm lặp
- **WHEN** client gửi lại cùng idempotency key và dependency fingerprint
- **THEN** hệ thống trả kết quả project/handoff đã tạo thay vì tạo project trùng

### Requirement: Không tự chạy generation sau handoff
Handoff SHALL tạo project và source context nhưng SHALL không tự chạy story planning, shot, prompt, voice, subtitle, render hoặc publishing nếu người dùng chưa bấm hành động trong AI Video.

#### Scenario: Project mới sau handoff
- **WHEN** người dùng vừa hoàn tất handoff
- **THEN** AI Video hiển thị project với source/memory đã nạp và action rõ để người dùng tự chạy planning

### Requirement: Handoff stale có phạm vi
Hệ thống SHALL đánh stale handoff/project dependency khi accepted research content thay đổi, nhưng SHALL không xóa hoặc sửa ngược artifact đã publish/locked; chỉ artifact phụ thuộc mới cần regenerate.

#### Scenario: Đổi hook sau handoff
- **WHEN** người dùng approve hook mới trong Research Project
- **THEN** handoff liên quan chuyển stale, story/script/shot/prompt phụ thuộc được đánh dấu cần cập nhật theo dependency graph và bản cũ vẫn xem được

### Requirement: Handoff provenance và bảo mật
Handoff SHALL truy xuất được accepted item về source/run/revision/evidence, SHALL lưu path tương đối, và SHALL không chứa secret, raw binary, tool log hoặc config nhạy cảm.

#### Scenario: Xem trace sau handoff
- **WHEN** người dùng mở thông tin nguồn trong AI Video project
- **THEN** hệ thống hiển thị Research Project, handoff revision, accepted idea/script và evidence refs tương ứng mà không lộ dữ liệu nhạy cảm
