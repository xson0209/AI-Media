## MODIFIED Requirements

### Requirement: Danh sách chọn tiếng Việt cho nguồn tiếng gốc

Bảng dựng nhanh MP4 SHALL trình bày lựa chọn nguồn âm thanh bằng một danh sách chọn với nhãn tiếng Việt, thay cho công tắc bật/tắt.

Nhãn của danh sách SHALL là "Âm thanh", vì danh sách quyết định cả giọng đọc lẫn tiếng gốc chứ không chỉ tiếng gốc.

Danh sách SHALL có ba lựa chọn: kết hợp giọng đọc với tiếng gốc làm nền, chỉ dùng giọng đọc, hoặc chỉ dùng tiếng gốc.

Lựa chọn mặc định SHALL là chỉ dùng giọng đọc, giữ đúng hành vi mặc định hiện tại.

Nhãn của mỗi lựa chọn SHALL nói trực tiếp kết quả người dùng nhận được, không diễn đạt theo nghĩa đảo của field API.

Phần diễn giải bên dưới danh sách SHALL đổi theo mức đang chọn để nói rõ mức đó làm gì với giọng đọc và với tiếng gốc.

Cấu hình trên API SHALL nhận thêm một field mức âm thanh ba giá trị. Field boolean tiếng gốc cũ SHALL được giữ lại để cấu hình do bản trước ghi ra vẫn đọc được, và SHALL NOT bị bỏ.

#### Scenario: Danh sách chọn hiện ba lựa chọn tiếng Việt

- **WHEN** người dùng mở bảng dựng nhanh MP4
- **THEN** lựa chọn nguồn âm thanh hiện dưới dạng danh sách chọn nhãn "Âm thanh" với ba lựa chọn tiếng Việt

#### Scenario: Mặc định giữ nguyên hành vi cũ

- **WHEN** người dùng mở bảng dựng nhanh MP4 lần đầu và không đổi gì
- **THEN** lựa chọn đang ở mức chỉ dùng giọng đọc
- **AND** MP4 dựng ra giống kết quả trước khi có danh sách chọn

#### Scenario: Chọn giữ tiếng gốc làm nền có tác dụng thật

- **WHEN** người dùng chọn kết hợp giọng đọc với tiếng gốc làm nền rồi dựng MP4
- **THEN** MP4 dựng ra có tiếng gốc của clip làm nền

#### Scenario: Chọn chỉ dùng tiếng gốc có tác dụng thật

- **WHEN** người dùng chọn chỉ dùng tiếng gốc rồi dựng MP4
- **THEN** MP4 dựng ra có tiếng gốc của clip ở mức nguyên bản và không có giọng đọc

#### Scenario: Diễn giải đổi theo mức đang chọn

- **WHEN** người dùng đổi mức âm thanh trong danh sách
- **THEN** phần diễn giải bên dưới đổi theo và nói đúng mức đang chọn làm gì với giọng đọc và tiếng gốc

#### Scenario: Cấu hình của bản cũ vẫn dùng được

- **WHEN** một client gửi cấu hình dựng MP4 chỉ có field boolean tiếng gốc cũ, không có mức âm thanh
- **THEN** hệ thống suy mức âm thanh từ field boolean cũ và không báo lỗi cấu hình
