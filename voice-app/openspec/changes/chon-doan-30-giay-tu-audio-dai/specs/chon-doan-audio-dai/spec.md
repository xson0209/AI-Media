## ADDED Requirements

### Requirement: Phát hiện file audio dài khi upload mẫu giọng
Hệ thống MUST cho phép người dùng chọn file audio dài hơn giới hạn mẫu 30 giây và chuyển sang bước chọn đoạn thay vì báo lỗi thời lượng ngay lập tức.

#### Scenario: File ngắn không cần chọn đoạn
- **WHEN** người dùng chọn file audio có thời lượng nhỏ hơn hoặc bằng 30 giây
- **THEN** hệ thống MUST cho phép dùng file đó như luồng upload mẫu hiện tại mà không yêu cầu chọn đoạn

#### Scenario: File dài mở bước chọn đoạn
- **WHEN** người dùng chọn file audio có thời lượng lớn hơn 30 giây
- **THEN** hệ thống MUST hiển thị giao diện chọn đoạn tối đa 30 giây từ file đó
- **AND** hệ thống MUST NOT hiển thị lỗi "âm thanh quá dài" trước khi người dùng có cơ hội chọn đoạn

### Requirement: Người dùng chọn và xác nhận đoạn mẫu 30 giây
Hệ thống MUST cung cấp giao diện để người dùng chọn vị trí bắt đầu của đoạn mẫu và xác nhận một đoạn audio tối đa 30 giây.

#### Scenario: Chọn đoạn hợp lệ trong file dài
- **WHEN** người dùng điều chỉnh vị trí bắt đầu trong file audio dài
- **THEN** hệ thống MUST hiển thị khoảng thời gian được chọn với thời lượng không vượt quá 30 giây
- **AND** hệ thống MUST giới hạn vị trí bắt đầu để đoạn chọn không vượt quá cuối file

#### Scenario: Nghe thử đoạn đã chọn
- **WHEN** người dùng bấm nghe thử trong giao diện chọn đoạn
- **THEN** hệ thống MUST phát audio bắt đầu từ vị trí đã chọn
- **AND** hệ thống MUST dừng hoặc giới hạn phát khi hết đoạn đã chọn

#### Scenario: Chưa xác nhận đoạn thì không được gửi sample dài
- **WHEN** file audio dài hơn 30 giây đã được chọn nhưng người dùng chưa xác nhận đoạn
- **THEN** hệ thống MUST không cho submit sample hoặc chép lời sample đó

### Requirement: Backend chỉ lưu đoạn đã cắt làm sample tham chiếu
Backend MUST cắt file upload theo đoạn người dùng chọn trước khi validate và lưu mẫu giọng tham chiếu.

#### Scenario: Upload file dài với đoạn hợp lệ
- **WHEN** client gửi file audio dài kèm `trim_start_seconds` và `trim_duration_seconds` không vượt quá 30 giây tới endpoint thêm sample
- **THEN** backend MUST load/cắt đúng đoạn được chỉ định trước khi validate audio
- **AND** backend MUST lưu đoạn đã cắt dưới dạng sample audio, không lưu toàn bộ file dài làm sample

#### Scenario: Đoạn đã cắt vượt giới hạn sample
- **WHEN** client gửi `trim_duration_seconds` lớn hơn 30 giây hoặc đoạn sau khi cắt vẫn vượt giới hạn 30 giây
- **THEN** backend MUST từ chối request với lỗi validation rõ ràng

#### Scenario: Tham số trim không hợp lệ
- **WHEN** client gửi `trim_start_seconds` âm, `trim_duration_seconds` không dương, hoặc đoạn chọn không thể đọc từ file
- **THEN** backend MUST từ chối request với lỗi 400 và không tạo sample mới

### Requirement: Chép lời dùng đúng đoạn đã chọn
Hệ thống MUST chép lời trên cùng đoạn audio mà người dùng đã chọn để làm sample, không chép lời toàn bộ file dài.

#### Scenario: Chép lời file dài đã chọn đoạn
- **WHEN** người dùng bấm chép lời sau khi xác nhận đoạn trong file audio dài
- **THEN** client MUST gửi thông tin đoạn đã chọn tới endpoint chép lời
- **AND** backend MUST transcribe chỉ đoạn đã chọn

#### Scenario: Kết quả chép lời khớp đoạn sample
- **WHEN** backend trả về kết quả chép lời cho file dài đã chọn đoạn
- **THEN** nội dung reference text được điền vào form MUST tương ứng với đoạn audio sẽ được lưu làm sample

### Requirement: Thông báo UI phân biệt file dài và sample 30 giây
Giao diện MUST giải thích rõ người dùng có thể chọn file dài, nhưng đoạn sample cuối cùng dùng cho clone giọng vẫn tối đa 30 giây.

#### Scenario: Hiển thị hướng dẫn upload mới
- **WHEN** người dùng xem vùng upload mẫu audio
- **THEN** hệ thống MUST hiển thị hướng dẫn rằng file dài có thể được chọn đoạn 30 giây để làm mẫu

#### Scenario: Hiển thị lỗi đúng loại
- **WHEN** file bị từ chối vì kích thước, format hoặc đoạn chọn không hợp lệ
- **THEN** hệ thống MUST hiển thị lỗi tương ứng với nguyên nhân thực tế thay vì chỉ dùng lỗi "âm thanh quá dài"

### Requirement: Luồng ghi âm hiện tại không bị thay đổi
Hệ thống MUST giữ hành vi ghi âm trực tiếp và ghi âm hệ thống trong giới hạn khoảng 30 giây như hiện tại, trừ khi có thay đổi riêng cho recording trong tương lai.

#### Scenario: Ghi âm trực tiếp vẫn tự giới hạn
- **WHEN** người dùng dùng tab ghi âm trực tiếp hoặc ghi âm hệ thống để tạo mẫu
- **THEN** hệ thống MUST tiếp tục tự giới hạn thời lượng ghi âm theo giới hạn sample hiện tại
- **AND** hệ thống MUST không yêu cầu người dùng chọn đoạn sau khi ghi âm thành công
