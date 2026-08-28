## ADDED Requirements

### Requirement: Ba mức âm thanh cho bản dựng MP4

Cấu hình dựng MP4 SHALL có một mức âm thanh nhận đúng ba giá trị: chỉ dùng giọng đọc, kết hợp giọng đọc với tiếng gốc làm nền, và chỉ dùng tiếng gốc.

Ở mức chỉ dùng giọng đọc, hệ thống SHALL bỏ hoàn toàn tiếng gốc của clip.

Ở mức kết hợp, hệ thống SHALL đưa tiếng gốc xuống làm nền và SHALL hạ mức nền khi có giọng đọc.

Ở mức chỉ dùng tiếng gốc, hệ thống SHALL dùng tiếng gốc ở mức nguyên bản, SHALL NOT hạ mức, và SHALL NOT dùng giọng đọc kể cả khi project đã có giọng đọc hoàn tất.

Giá trị mặc định SHALL là mức chỉ dùng giọng đọc, giữ đúng hành vi trước change này.

#### Scenario: Mức chỉ dùng giọng đọc

- **WHEN** người dùng dựng MP4 ở mức chỉ dùng giọng đọc
- **THEN** MP4 đầu ra không chứa tiếng gốc của clip

#### Scenario: Mức kết hợp

- **WHEN** người dùng dựng MP4 ở mức kết hợp trên project có giọng đọc
- **THEN** MP4 đầu ra chứa cả giọng đọc và tiếng gốc làm nền, và nền được hạ mức trong lúc có giọng đọc

#### Scenario: Mức chỉ dùng tiếng gốc

- **WHEN** người dùng dựng MP4 ở mức chỉ dùng tiếng gốc
- **THEN** MP4 đầu ra chỉ chứa tiếng gốc của clip ở mức nguyên bản và không chứa giọng đọc

#### Scenario: Mức chỉ dùng tiếng gốc trên project đã có giọng đọc

- **WHEN** project đã có giọng đọc hoàn tất cho mọi shot và người dùng chọn mức chỉ dùng tiếng gốc
- **THEN** MP4 đầu ra vẫn không chứa giọng đọc

#### Scenario: Mặc định giữ hành vi cũ

- **WHEN** người dùng mở bảng dựng nhanh MP4 lần đầu và không đổi gì
- **THEN** mức âm thanh đang ở mức chỉ dùng giọng đọc và MP4 đầu ra giống hành vi trước change này

### Requirement: Phân giải mức âm thanh từ cấu hình cũ và cấu hình mới

Cấu hình dựng MP4 SHALL giữ lại field boolean tiếng gốc cũ để cấu hình do bản trước ghi ra vẫn đọc được.

Khi cấu hình có mức âm thanh, hệ thống SHALL dùng mức đó.

Khi cấu hình không có mức âm thanh, hệ thống SHALL suy mức từ field boolean cũ: bỏ tiếng gốc thành mức chỉ dùng giọng đọc, giữ tiếng gốc thành mức kết hợp. Hệ thống SHALL NOT rơi về mức mặc định trong trường hợp này.

Khi người dùng chọn một mức, hệ thống SHALL ghi field boolean cũ khớp với mức đã chọn để cấu hình vẫn đọc được bởi phần code chỉ biết field cũ.

#### Scenario: Job cũ đang giữ tiếng gốc

- **WHEN** hệ thống đọc lại một cấu hình dựng đã lưu không có mức âm thanh và field boolean cũ đang ở trạng thái giữ tiếng gốc
- **THEN** mức âm thanh được phân giải thành mức kết hợp, không phải mức chỉ dùng giọng đọc

#### Scenario: Job cũ đang bỏ tiếng gốc

- **WHEN** hệ thống đọc lại một cấu hình dựng đã lưu không có mức âm thanh và field boolean cũ đang ở trạng thái bỏ tiếng gốc
- **THEN** mức âm thanh được phân giải thành mức chỉ dùng giọng đọc

#### Scenario: Cấu hình mới có mức âm thanh

- **WHEN** cấu hình dựng có mức âm thanh và field boolean cũ nói khác
- **THEN** hệ thống dùng mức âm thanh trong cấu hình

#### Scenario: Thiết lập đã lưu ở máy người dùng của bản cũ

- **WHEN** người dùng mở lại bảng dựng nhanh MP4 với thiết lập đã lưu từ bản trước, không có mức âm thanh
- **THEN** danh sách chọn hiện đúng mức tương ứng với lựa chọn tiếng gốc đã lưu

#### Scenario: Client không gửi thông tin âm thanh

- **WHEN** một client gửi cấu hình dựng MP4 không có mức âm thanh và cũng không có field boolean cũ
- **THEN** hệ thống dùng giá trị mặc định và không báo lỗi cấu hình

### Requirement: Dựng audio ở mức chỉ dùng tiếng gốc

Ở mức chỉ dùng tiếng gốc, timeline tiếng gốc SHALL trở thành nguồn audio chính của bản dựng.

Hệ thống SHALL giữ tiếng gốc ở mức nguyên bản, SHALL NOT áp bộ hạ mức theo giọng đọc, và SHALL NOT trộn timeline tiếng gốc với timeline giọng đọc.

Quy tắc bỏ tiếng nền cho phân đoạn có giọng đọc trích từ chính clip đó SHALL NOT áp dụng ở mức này, vì ở mức này không có timeline giọng đọc nào để cộng trùng.

Phân đoạn có clip không chứa audio stream SHALL im lặng và SHALL sinh cảnh báo tiếng Việt cho phân đoạn đó, và SHALL NOT làm bản dựng thất bại.

Khi mọi phân đoạn đều im lặng, hệ thống SHALL ghi cảnh báo rõ ràng rằng MP4 đầu ra không có tiếng.

#### Scenario: Tiếng gốc thành audio chính

- **WHEN** người dùng dựng MP4 ở mức chỉ dùng tiếng gốc và các clip đều có audio
- **THEN** audio của MP4 đầu ra là tiếng gốc của clip ở mức nguyên bản, không bị hạ mức ở bất kỳ đoạn nào

#### Scenario: Project có giọng đọc trích từ clip

- **WHEN** project dùng speech source trích từ clip provider, phân đoạn có narration, và người dùng chọn mức chỉ dùng tiếng gốc
- **THEN** phân đoạn đó vẫn phát tiếng gốc của clip, không bị đưa về im lặng

#### Scenario: Clip không có audio stream

- **WHEN** clip của một phân đoạn không có audio stream và người dùng dựng ở mức chỉ dùng tiếng gốc
- **THEN** phân đoạn đó im lặng, bản dựng vẫn hoàn tất, và người dùng nhận cảnh báo cho phân đoạn đó

#### Scenario: Mọi clip đều không có tiếng

- **WHEN** không phân đoạn nào có audio dùng được và người dùng dựng ở mức chỉ dùng tiếng gốc
- **THEN** bản dựng vẫn hoàn tất và báo cáo ghi rõ MP4 đầu ra không có tiếng

#### Scenario: Enhanced audio vẫn trộn lên trên

- **WHEN** người dùng bật enhanced audio và dựng ở mức chỉ dùng tiếng gốc
- **THEN** SFX/BGM vẫn được trộn lên trên nền tiếng gốc theo quy tắc enhanced audio hiện có

### Requirement: Tạo phụ đề ở mức chỉ dùng tiếng gốc

Ở mức chỉ dùng tiếng gốc, việc tạo phụ đề SHALL NOT đòi giọng đọc hoàn tất cho shot có narration.

Mốc thời gian cue phụ đề ở mức này SHALL được chia theo thời lượng render của từng shot, cùng trục thời gian với video timeline.

Hệ thống SHALL NOT tự bật hoặc tự tắt chế độ phụ đề khi người dùng đổi mức âm thanh. Chế độ phụ đề SHALL tiếp tục do người dùng chọn.

#### Scenario: Tạo phụ đề khi chưa có giọng đọc

- **WHEN** project có narration nhưng chưa có giọng đọc, người dùng đang ở mức chỉ dùng tiếng gốc và yêu cầu tạo phụ đề
- **THEN** phụ đề được tạo thành công, không báo lỗi thiếu giọng đọc

#### Scenario: Phụ đề khớp trục thời gian video

- **WHEN** phụ đề được tạo ở mức chỉ dùng tiếng gốc
- **THEN** mốc thời gian cue nằm đúng trong khoảng thời gian của shot tương ứng trên video timeline

#### Scenario: Chế độ phụ đề vẫn do người dùng chọn

- **WHEN** người dùng đổi mức âm thanh sang chỉ dùng tiếng gốc
- **THEN** chế độ phụ đề đang chọn không bị hệ thống thay đổi

#### Scenario: Bật phụ đề nhúng ở mức chỉ dùng tiếng gốc

- **WHEN** người dùng chọn phụ đề nhúng cùng mức chỉ dùng tiếng gốc và project đã có phụ đề hoàn tất
- **THEN** MP4 đầu ra có phụ đề nhúng và audio là tiếng gốc của clip

