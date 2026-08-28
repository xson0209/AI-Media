## ADDED Requirements

### Requirement: Danh sách chọn tiếng Việt cho nguồn tiếng gốc

Bảng dựng nhanh MP4 SHALL trình bày lựa chọn nguồn tiếng gốc bằng một danh sách chọn với nhãn tiếng Việt, thay cho công tắc bật/tắt.

Danh sách SHALL có hai lựa chọn: bỏ tiếng gốc và chỉ dùng giọng đọc, hoặc giữ tiếng gốc làm nền.

Lựa chọn mặc định SHALL là bỏ tiếng gốc, giữ đúng hành vi mặc định hiện tại.

Nhãn của mỗi lựa chọn SHALL nói trực tiếp kết quả người dùng nhận được, không diễn đạt theo nghĩa đảo của field API.

Kiểu dữ liệu của field trên API SHALL không đổi.

#### Scenario: Danh sách chọn hiện hai lựa chọn tiếng Việt

- **WHEN** người dùng mở bảng dựng nhanh MP4
- **THEN** lựa chọn nguồn tiếng gốc hiện dưới dạng danh sách chọn với hai lựa chọn tiếng Việt

#### Scenario: Mặc định giữ nguyên hành vi cũ

- **WHEN** người dùng mở bảng dựng nhanh MP4 lần đầu và không đổi gì
- **THEN** lựa chọn đang ở mức bỏ tiếng gốc
- **AND** MP4 dựng ra giống kết quả trước khi có danh sách chọn

#### Scenario: Chọn giữ tiếng gốc có tác dụng thật

- **WHEN** người dùng chọn giữ tiếng gốc làm nền rồi dựng MP4
- **THEN** MP4 dựng ra có tiếng gốc của clip làm nền

### Requirement: Lưu lại thiết lập dựng giữa các lần mở

Thiết lập dựng của một project SHALL được lưu lại và SHALL được nạp lại khi người dùng mở lại bảng dựng nhanh MP4.

Thiết lập đã lưu SHALL sống qua việc tải lại ứng dụng và việc chuyển sang phần khác rồi quay lại.

Khi chưa có thiết lập đã lưu, hệ thống SHALL dùng giá trị mặc định.

Khi thiết lập đã lưu không đọc được hoặc chứa giá trị không hợp lệ, hệ thống SHALL dùng giá trị mặc định thay vì báo lỗi cho người dùng.

#### Scenario: Tải lại trang không mất lựa chọn

- **WHEN** người dùng chọn giữ tiếng gốc rồi tải lại ứng dụng
- **THEN** lựa chọn giữ tiếng gốc vẫn còn

#### Scenario: Chuyển phần khác rồi quay lại

- **WHEN** người dùng đổi thiết lập, chuyển sang phần khác, rồi quay lại bảng dựng
- **THEN** thiết lập vẫn giữ nguyên giá trị đã chọn

#### Scenario: Thiết lập đã lưu bị hỏng

- **WHEN** thiết lập đã lưu không đọc được
- **THEN** bảng dựng dùng giá trị mặc định và vẫn hoạt động bình thường

### Requirement: Luồng tự động dùng thiết lập người dùng đã chọn

Luồng chạy tự động và luồng tự dựng MP4 sau khi sinh clip SHALL dùng thiết lập dựng mà người dùng đã chọn cho project đó, thay vì dựng bằng thiết lập mặc định.

Khi project chưa có thiết lập đã lưu, luồng tự động SHALL dùng thiết lập mặc định.

#### Scenario: Chạy tự động tôn trọng lựa chọn tiếng gốc

- **WHEN** người dùng chọn giữ tiếng gốc rồi khởi động luồng chạy tự động
- **THEN** MP4 dựng ra từ luồng tự động có tiếng gốc làm nền

#### Scenario: Tự dựng sau khi sinh clip tôn trọng lựa chọn

- **WHEN** người dùng chọn giữ tiếng gốc và luồng sinh clip tự dựng MP4 sau khi xong
- **THEN** MP4 dựng ra có tiếng gốc làm nền

#### Scenario: Project chưa có thiết lập đã lưu

- **WHEN** luồng tự động chạy trên project chưa từng đổi thiết lập dựng
- **THEN** MP4 được dựng bằng thiết lập mặc định
