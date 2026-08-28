## MODIFIED Requirements

### Requirement: Chọn nguồn tiếng nền theo speech source của project

Khi tiếng gốc được dùng làm nền, hệ thống MUST quyết định có thêm tiếng nền cho từng phân đoạn dựa trên speech source hiệu lực của project và việc phân đoạn có narration hay không. Phân đoạn mà giọng đọc đã được trích từ chính clip đó MUST NOT được thêm tiếng nền, vì cộng trùng cùng một nguồn gây vọng tiếng và méo giọng.

Quy tắc trên MUST chỉ áp dụng cho mức kết hợp. Ở mức chỉ dùng tiếng gốc, hệ thống MUST NOT bỏ tiếng gốc của phân đoạn vì lý do giọng đọc trích từ clip, vì ở mức đó không có timeline giọng đọc nào để cộng trùng.

#### Scenario: Project dùng speech source từ clip, phân đoạn có narration

- **WHEN** project dùng speech source trích từ clip provider, phân đoạn có narration, và người dùng đang ở mức kết hợp
- **THEN** hệ thống không thêm tiếng nền cho phân đoạn đó và audio của phân đoạn giữ nguyên như trước change này

#### Scenario: Project dùng speech source từ clip, mức chỉ dùng tiếng gốc

- **WHEN** project dùng speech source trích từ clip provider, phân đoạn có narration, và người dùng đang ở mức chỉ dùng tiếng gốc
- **THEN** hệ thống phát tiếng gốc của clip cho phân đoạn đó ở mức nguyên bản, không đưa phân đoạn về im lặng

#### Scenario: Project dùng speech source từ clip, phân đoạn không narration

- **WHEN** project dùng speech source trích từ clip provider, phân đoạn không có narration, và clip có audio
- **THEN** hệ thống phát tiếng gốc của clip cho phân đoạn đó thay vì im lặng

#### Scenario: Project dùng giọng đọc tổng hợp, phân đoạn có narration

- **WHEN** project dùng giọng đọc tổng hợp, phân đoạn có narration, clip có audio, và người dùng đang ở mức kết hợp
- **THEN** hệ thống thêm tiếng nền từ clip gốc và hạ tiếng nền xuống khi có giọng đọc

#### Scenario: Project dùng giọng đọc tổng hợp, phân đoạn không narration

- **WHEN** project dùng giọng đọc tổng hợp, phân đoạn không có narration, và clip có audio
- **THEN** hệ thống phát tiếng gốc của clip cho phân đoạn đó mà không hạ mức

#### Scenario: Clip không có audio

- **WHEN** clip của phân đoạn không có audio stream
- **THEN** hệ thống dùng nguồn im lặng cho tiếng nền của phân đoạn đó và audio của phân đoạn giữ nguyên như trước change này

#### Scenario: Tiếng gốc bị bỏ

- **WHEN** người dùng chọn mức chỉ dùng giọng đọc trong cấu hình dựng MP4
- **THEN** hệ thống không dựng timeline tiếng nền và audio đầu ra giữ nguyên như trước change này

### Requirement: Người dùng bật tắt tiếng gốc từ bảng dựng MP4

Bảng dựng nhanh MP4 MUST có danh sách chọn ba mức âm thanh để người dùng quyết định dùng giọng đọc, dùng tiếng gốc làm nền, hay chỉ dùng tiếng gốc; và mức đang chọn MUST có tác dụng thật lên MP4 đầu ra. Giá trị mặc định MUST giữ nguyên hành vi trước change này.

#### Scenario: Mặc định giữ hành vi cũ

- **WHEN** người dùng mở bảng dựng MP4 mà chưa đổi cấu hình
- **THEN** mức âm thanh ở mức chỉ dùng giọng đọc và MP4 đầu ra giống hành vi trước change này

#### Scenario: Chọn mức kết hợp

- **WHEN** người dùng chọn mức kết hợp rồi dựng MP4
- **THEN** MP4 đầu ra chứa tiếng nền theo quy tắc chọn nguồn của từng phân đoạn

#### Scenario: Chọn mức chỉ dùng tiếng gốc

- **WHEN** người dùng chọn mức chỉ dùng tiếng gốc rồi dựng MP4
- **THEN** MP4 đầu ra chứa tiếng gốc ở mức nguyên bản và không chứa giọng đọc

#### Scenario: Cấu hình cũ vẫn dùng được

- **WHEN** một client gửi cấu hình dựng MP4 không có thông tin mức âm thanh
- **THEN** hệ thống suy mức từ field boolean tiếng gốc cũ nếu có, ngược lại dùng giá trị mặc định, và không báo lỗi cấu hình

