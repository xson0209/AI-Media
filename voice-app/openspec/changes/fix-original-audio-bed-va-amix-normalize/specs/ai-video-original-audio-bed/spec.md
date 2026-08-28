## ADDED Requirements

### Requirement: Chọn nguồn tiếng nền theo speech source của project

Khi tiếng gốc được bật, hệ thống MUST quyết định có thêm tiếng nền cho từng phân đoạn dựa trên speech source hiệu lực của project và việc phân đoạn có narration hay không. Phân đoạn mà giọng đọc đã được trích từ chính clip đó MUST NOT được thêm tiếng nền, vì cộng trùng cùng một nguồn gây vọng tiếng và méo giọng.

#### Scenario: Project dùng speech source từ clip, phân đoạn có narration

- **WHEN** project dùng speech source trích từ clip provider và phân đoạn có narration
- **THEN** hệ thống không thêm tiếng nền cho phân đoạn đó và audio của phân đoạn giữ nguyên như trước change này

#### Scenario: Project dùng speech source từ clip, phân đoạn không narration

- **WHEN** project dùng speech source trích từ clip provider, phân đoạn không có narration, và clip có audio
- **THEN** hệ thống phát tiếng gốc của clip cho phân đoạn đó thay vì im lặng

#### Scenario: Project dùng giọng đọc tổng hợp, phân đoạn có narration

- **WHEN** project dùng giọng đọc tổng hợp, phân đoạn có narration, và clip có audio
- **THEN** hệ thống thêm tiếng nền từ clip gốc và hạ tiếng nền xuống khi có giọng đọc

#### Scenario: Project dùng giọng đọc tổng hợp, phân đoạn không narration

- **WHEN** project dùng giọng đọc tổng hợp, phân đoạn không có narration, và clip có audio
- **THEN** hệ thống phát tiếng gốc của clip cho phân đoạn đó mà không hạ mức

#### Scenario: Clip không có audio

- **WHEN** clip của phân đoạn không có audio stream
- **THEN** hệ thống dùng nguồn im lặng cho tiếng nền của phân đoạn đó và audio của phân đoạn giữ nguyên như trước change này

#### Scenario: Tiếng gốc bị tắt

- **WHEN** người dùng tắt tiếng gốc trong cấu hình dựng MP4
- **THEN** hệ thống không dựng timeline tiếng nền và audio đầu ra giữ nguyên như trước change này

### Requirement: Tiếng nền lấy từ clip gốc

Tiếng nền MUST được rút từ clip gốc của phân đoạn, MUST NOT lấy từ bản clip đã qua làm sạch watermark. Việc rút tiếng nền MUST NOT ghi đè hay sửa đổi clip gốc.

#### Scenario: Làm sạch watermark đang bật

- **WHEN** làm sạch watermark đang bật và hệ thống dựng tiếng nền cho phân đoạn
- **THEN** tiếng nền được rút từ clip gốc, không phải từ bản derivative đã làm sạch

#### Scenario: Clip gốc không bị thay đổi

- **WHEN** hệ thống rút tiếng nền từ clip
- **THEN** file clip gốc giữ nguyên nội dung và không bị ghi đè

### Requirement: Tiếng nền khớp thời lượng từng phân đoạn

Mỗi đoạn tiếng nền MUST có thời lượng đúng bằng thời lượng phân đoạn tương ứng trong timeline. Tiếng nền ngắn hơn MUST được kéo dài bằng khoảng lặng, tiếng nền dài hơn MUST được cắt bớt.

#### Scenario: Tiếng gốc ngắn hơn phân đoạn

- **WHEN** audio của clip ngắn hơn thời lượng phân đoạn
- **THEN** đoạn tiếng nền được kéo dài bằng khoảng lặng cho đủ thời lượng phân đoạn

#### Scenario: Tiếng gốc dài hơn phân đoạn

- **WHEN** audio của clip dài hơn thời lượng phân đoạn
- **THEN** đoạn tiếng nền bị cắt còn đúng thời lượng phân đoạn

#### Scenario: Tổng thời lượng tiếng nền khớp timeline

- **WHEN** hệ thống ghép các đoạn tiếng nền thành một timeline
- **THEN** tổng thời lượng timeline tiếng nền khớp tổng thời lượng timeline giọng đọc

### Requirement: Hạ tiếng nền khi có giọng đọc

Khi trộn tiếng nền với giọng đọc, hệ thống MUST hạ mức tiếng nền theo thời gian thực dựa trên giọng đọc, dùng giọng đọc làm tín hiệu điều khiển. Việc trộn MUST được thực hiện một lần trên toàn timeline, MUST NOT thực hiện riêng cho từng phân đoạn.

#### Scenario: Trộn một lần trên toàn timeline

- **WHEN** hệ thống trộn timeline tiếng nền với timeline giọng đọc
- **THEN** việc hạ mức được áp dụng một lần trên toàn timeline để mức nền đều nhau giữa các phân đoạn

#### Scenario: Tiếng nền hạ xuống khi có giọng

- **WHEN** giọng đọc đang phát tại một thời điểm
- **THEN** tiếng nền tại thời điểm đó bị hạ mức so với khi không có giọng đọc

#### Scenario: Tiếng nền trở lại khi hết giọng

- **WHEN** giọng đọc kết thúc tại một thời điểm
- **THEN** tiếng nền trở lại mức nền bình thường sau khoảng thời gian phục hồi ngắn

#### Scenario: Timeline tiếng nền toàn im lặng

- **WHEN** mọi phân đoạn đều không được thêm tiếng nền
- **THEN** hệ thống bỏ hẳn bước trộn tiếng nền và dùng trực tiếp timeline giọng đọc

### Requirement: Tiếng nền hoạt động độc lập với enhanced render

Tiếng nền MUST hoạt động bất kể enhanced render hay trộn SFX/BGM có được bật hay không. Tổng thời lượng dùng cho tiếng nền MUST được tính từ timeline, MUST NOT phụ thuộc vào enhanced render plan.

#### Scenario: Enhanced render tắt

- **WHEN** người dùng bật tiếng gốc nhưng tắt enhanced render
- **THEN** tiếng nền vẫn được dựng và trộn vào MP4

#### Scenario: Trộn SFX/BGM tắt nhưng tiếng gốc bật

- **WHEN** người dùng bật tiếng gốc nhưng tắt trộn SFX/BGM
- **THEN** tiếng nền vẫn được dựng và trộn vào MP4, không có asset SFX/BGM nào được thêm

#### Scenario: Cả tiếng gốc và SFX/BGM đều bật

- **WHEN** người dùng bật cả tiếng gốc và trộn SFX/BGM
- **THEN** MP4 chứa giọng đọc, tiếng nền đã hạ mức, và các asset SFX/BGM

### Requirement: Lỗi dựng tiếng nền không làm hỏng cả bản dựng

Khi dựng hoặc trộn tiếng nền thất bại, hệ thống MUST tiếp tục dựng MP4 bằng timeline giọng đọc và MUST ghi lại lý do fallback. Lỗi tiếng nền MUST NOT làm cả job render thất bại. Đường ghi fallback MUST hoạt động cả khi enhanced render bị tắt.

#### Scenario: Rút tiếng nền thất bại

- **WHEN** việc rút audio từ clip cho tiếng nền thất bại
- **THEN** hệ thống dựng MP4 bằng timeline giọng đọc và ghi lý do fallback

#### Scenario: Trộn tiếng nền thất bại

- **WHEN** việc trộn tiếng nền với giọng đọc thất bại
- **THEN** hệ thống dựng MP4 bằng timeline giọng đọc và ghi lý do fallback

#### Scenario: Fallback khi enhanced render tắt

- **WHEN** tiếng nền thất bại trong lúc enhanced render đang tắt
- **THEN** lý do fallback vẫn được ghi lại và job render vẫn hoàn tất

#### Scenario: Clip thiếu file

- **WHEN** file clip của phân đoạn không tồn tại lúc dựng tiếng nền
- **THEN** hệ thống dùng nguồn im lặng cho phân đoạn đó hoặc fallback về timeline giọng đọc, và ghi lý do

#### Scenario: Thời lượng phân đoạn không hợp lệ

- **WHEN** một phân đoạn có thời lượng bằng không hoặc âm
- **THEN** hệ thống không sinh câu lệnh tiếng nền không hợp lệ cho phân đoạn đó và bản dựng vẫn hoàn tất

### Requirement: Giọng đọc không bị chia nhỏ khi trộn nhiều nguồn

Khi trộn nhiều nguồn audio, hệ thống MUST giữ nguyên mức giọng đọc thay vì chia nhỏ theo số lượng nguồn được trộn. Mức của từng asset SFX/BGM MUST tiếp tục do cấu hình của asset quyết định.

#### Scenario: Trộn một asset SFX

- **WHEN** hệ thống trộn giọng đọc với một asset SFX
- **THEN** mức giọng đọc trong bản trộn giữ nguyên như khi chưa trộn

#### Scenario: Trộn nhiều asset SFX

- **WHEN** hệ thống trộn giọng đọc với nhiều asset SFX
- **THEN** mức giọng đọc không giảm thêm theo số lượng asset được trộn

#### Scenario: Mức asset vẫn theo cấu hình

- **WHEN** một asset SFX được cấu hình mức âm lượng riêng
- **THEN** asset đó được trộn theo đúng mức đã cấu hình

### Requirement: Người dùng bật tắt tiếng gốc từ bảng dựng MP4

Bảng dựng nhanh MP4 MUST có công tắc để người dùng bật hoặc tắt tiếng gốc, và trạng thái công tắc MUST có tác dụng thật lên MP4 đầu ra. Giá trị mặc định MUST giữ nguyên hành vi trước change này.

#### Scenario: Mặc định giữ hành vi cũ

- **WHEN** người dùng mở bảng dựng MP4 mà chưa đổi cấu hình
- **THEN** tiếng gốc ở trạng thái tắt và MP4 đầu ra giống hành vi trước change này

#### Scenario: Bật tiếng gốc

- **WHEN** người dùng bật công tắc tiếng gốc rồi dựng MP4
- **THEN** MP4 đầu ra chứa tiếng nền theo quy tắc chọn nguồn của từng phân đoạn

#### Scenario: Cấu hình cũ vẫn dùng được

- **WHEN** một client gửi cấu hình dựng MP4 không có thông tin tiếng gốc
- **THEN** hệ thống dùng giá trị mặc định và không báo lỗi cấu hình

### Requirement: Giữ nguyên kiến trúc tách video và audio

Change này MUST NOT đổi kiến trúc tách nhánh video khỏi nhánh audio rồi mux ở cuối. Nhánh video MUST tiếp tục loại bỏ audio trước khi ghép. Tiếng nền MUST được xử lý trong nhánh audio.

#### Scenario: Nhánh video vẫn loại bỏ audio

- **WHEN** hệ thống chuẩn hoá và ghép các clip cho nhánh video
- **THEN** nhánh video vẫn loại bỏ audio và không mang theo audio của clip

#### Scenario: Tiếng nền nằm trong nhánh audio

- **WHEN** hệ thống dựng tiếng nền
- **THEN** tiếng nền được xử lý trong nhánh audio và chỉ gặp nhánh video ở bước mux cuối

#### Scenario: Phụ đề không bị ảnh hưởng

- **WHEN** người dùng bật hoặc tắt tiếng gốc
- **THEN** hành vi phụ đề nhúng, phụ đề rời và không phụ đề không thay đổi
