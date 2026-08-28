## ADDED Requirements

### Requirement: Chat phát triển nội dung theo project
Mỗi Research Project SHALL có chat thread dùng research memory hiện tại, accepted source package, accepted related projects và trạng thái series; output chat SHALL là draft mặc định.

#### Scenario: Phát triển Series drama 3 phút
- **WHEN** người dùng yêu cầu phát triển series thành tập tiếp theo
- **THEN** hệ thống trả về continuity cần giữ, các hướng lựa chọn, hook, beat 3 phút, payoff/cliffhanger và script seed có thể review

#### Scenario: Chọn nhiều project cho chat
- **WHEN** người dùng chọn các project liên quan làm context
- **THEN** chat hiển thị rõ project và vai trò context, chỉ dùng phần đã duyệt theo budget và không sửa memory của project liên quan

### Requirement: Nhánh phát triển và approval
Hệ thống SHALL cho phép tạo alternative branch, so sánh draft, lưu candidate, approve thành idea/script/memory card hoặc bỏ qua; draft chưa approve SHALL không thay đổi canon.

#### Scenario: Tạo kết thúc thay thế
- **WHEN** người dùng yêu cầu một ending khác từ kịch bản hiện tại
- **THEN** hệ thống tạo branch mới liên kết revision nguồn, giữ bản cũ nguyên vẹn và cho phép người dùng chọn branch để duyệt

#### Scenario: Duyệt script seed
- **WHEN** người dùng approve script seed
- **THEN** hệ thống lưu script trạng thái `accepted`, compile memory revision mới và cập nhật các score/recommendation phụ thuộc nếu cần

### Requirement: Continuity cho series ngắn
Mỗi script series SHALL có thể ghi hook, mục tiêu nhân vật, xung đột, đảo chiều, payoff, câu hỏi mở, must-have, avoid và trạng thái nhân vật để phát triển tập sau mà không reset context.

#### Scenario: Tạo tập sau
- **WHEN** người dùng nói "viết tiếp tập sau" trong một series đã có accepted episode
- **THEN** hệ thống dùng episode ledger/current state, không lặp beat đã giải quyết và tạo ít nhất một thay đổi trạng thái hoặc câu hỏi mở mới

#### Scenario: Nội dung sau handoff thay đổi
- **WHEN** người dùng approve nội dung mới làm thay đổi script seed hoặc canon đã handoff
- **THEN** hệ thống tạo revision mới và đánh dấu stale đúng artifact AI Video phụ thuộc mà không xóa bản đã tạo

### Requirement: Chat action bằng tiếng Việt
UI SHALL cung cấp action rõ ràng cho giữ ý tưởng, tạo biến thể, tăng drama, sửa logic, phát triển nhân vật, tạo tập sau, lưu memory, chấm điểm và đóng gói handoff.

#### Scenario: Draft có lỗi hoặc không phù hợp
- **WHEN** người dùng không chấp nhận draft chat
- **THEN** người dùng có thể tạo biến thể hoặc bỏ qua mà không tạo accepted memory và không làm đổi project AI Video
