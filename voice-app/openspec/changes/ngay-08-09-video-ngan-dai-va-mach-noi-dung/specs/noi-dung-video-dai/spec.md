## ADDED Requirements

### Requirement: Chọn độ dài và cách kể
Hệ thống SHALL cho phép chọn video ngắn hoặc dài và cách kể kiến thức/phân tích hoặc truyện/phim, lưu cấu hình và khôi phục khi mở dự án.

#### Scenario: Mở lại dự án dài
- **WHEN** người dùng lưu video dài rồi mở lại
- **THEN** lựa chọn độ dài và cách kể được giữ nguyên

### Requirement: Duyệt dàn ý trước khi viết dài
Hệ thống SHALL tạo dàn ý có trục nội dung, chương và thời lượng; chỉ viết chương sau khi dàn ý được duyệt.

#### Scenario: Tạo nội dung dài lần đầu
- **WHEN** người dùng yêu cầu phát triển video dài chưa có dàn ý
- **THEN** hệ thống trả dàn ý để duyệt và chưa cho duyệt kịch bản sản xuất

### Requirement: Giữ mạch giữa các chương
Hệ thống SHALL viết từng chương với dàn ý tổng và ngữ cảnh trước đó, kiểm tra lặp nội dung và kiểm tra biên tập toàn bài trước khi chuyển sang duyệt kịch bản.

#### Scenario: Có lỗi biên tập nghiêm trọng
- **WHEN** kiểm tra toàn bài báo lỗi chặn
- **THEN** hệ thống không đánh dấu kịch bản sẵn sàng sản xuất và trả lỗi để thử lại

### Requirement: Tiếp tục từ chương hợp lệ
Hệ thống SHALL lưu từng chương hoàn thành và giữ nguyên narration khi ghép kịch bản sản xuất.

#### Scenario: Provider lỗi khi viết chương tiếp theo
- **WHEN** một chương đã lưu hợp lệ và provider lỗi ở chương sau
- **THEN** retry dùng lại các chương đã lưu của đúng revision và chỉ viết tiếp phần thiếu
- **AND** không dùng fallback kịch bản ngắn hoặc thay lời kể đã được biên tập

### Requirement: Duyệt đúng phiên bản và chặn sản xuất sớm
Hệ thống SHALL yêu cầu duyệt dàn ý hiện hành và kiểm tra biên tập đạt trước khi duyệt kịch bản hoặc tạo shot/prompt cho video dài.

#### Scenario: Chạy full auto với dàn ý mới
- **WHEN** full auto tạo xong dàn ý dài
- **THEN** workflow dừng ở review_outline chờ người dùng duyệt

#### Scenario: Người dùng sửa cấu hình khi AI đang chạy
- **WHEN** đầu vào nội dung thay đổi trước khi kết quả AI được lưu
- **THEN** kết quả cũ không ghi đè kế hoạch của đầu vào mới và cần phát triển lại

#### Scenario: Gọi API tạo cảnh trực tiếp trước khi biên tập đạt
- **WHEN** client gọi tạo shot hoặc prompt cho video dài chưa hoàn tất biên tập
- **THEN** API trả lỗi chặn có thể hiểu được và không tạo nội dung sản xuất

### Requirement: Không lặp beat nguồn để kéo dài video
Hệ thống SHALL không quay vòng các beat tham khảo khi timeline đích cần nhiều đoạn hơn.

#### Scenario: Nguồn có ít beat hơn timeline đích
- **WHEN** lập timeline đích dài hơn danh sách beat tham khảo
- **THEN** các đoạn bổ sung không được gán lại thông tin mới hoặc bằng chứng từ beat đầu để giả thành nội dung mới
