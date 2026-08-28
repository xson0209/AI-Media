## ADDED Requirements

### Requirement: Chọn nhiều file clip trong một lần

Bảng dựng nhanh MP4 SHALL cho phép chọn nhiều file clip trong một lần thao tác chọn file.

Nút nạp một clip riêng cho từng shot SHALL được giữ nguyên để thay lẻ một segment.

Danh sách định dạng file được nhận SHALL giống danh sách của đường nạp một clip.

#### Scenario: Chọn nhiều file cùng lúc

- **WHEN** người dùng chọn nhiều file clip trong một lần
- **THEN** tất cả file được chọn đều được đưa vào bước khớp tên

#### Scenario: Nạp lẻ một clip vẫn dùng được

- **WHEN** người dùng dùng nút nạp clip của một shot cụ thể
- **THEN** clip đó được nạp cho đúng shot như trước

### Requirement: Khớp tên file dạng số với số thứ tự segment

Hệ thống SHALL khớp mỗi file với một shot bằng cách đọc phần tên file không tính phần mở rộng và hiểu nó như số thứ tự segment.

Phần tên file SHALL được coi là khớp khi nó là một số nguyên dương và tồn tại shot có số thứ tự bằng số đó.

Số có chữ số 0 ở đầu SHALL được hiểu như cùng một số với dạng không có chữ số 0 ở đầu.

Khi nhiều file cùng khớp về một shot, hệ thống SHALL không tự chọn hộ mà SHALL báo xung đột cho người dùng.

#### Scenario: Tên file là số khớp với shot đang có

- **WHEN** file tên `3.mp4` được chọn và project có shot số thứ tự 3
- **THEN** file đó được khớp với shot số thứ tự 3

#### Scenario: Tên file có chữ số 0 ở đầu

- **WHEN** file tên `03.mp4` được chọn và project có shot số thứ tự 3
- **THEN** file đó được khớp với shot số thứ tự 3

#### Scenario: Tên file là số vượt quá số shot

- **WHEN** file tên `19.mp4` được chọn và project chỉ có 18 shot
- **THEN** file đó bị đánh dấu bỏ qua kèm lý do không có segment tương ứng

#### Scenario: Tên file không đọc được thành số

- **WHEN** file tên `intro.mp4` được chọn
- **THEN** file đó bị đánh dấu bỏ qua kèm lý do không đọc được số segment

#### Scenario: Hai file khớp cùng một segment

- **WHEN** cả `3.mp4` và `03.mp4` cùng được chọn
- **THEN** hệ thống báo xung đột cho segment 3 và không nạp file nào cho segment đó

### Requirement: Xem trước và xác nhận trước khi nạp

Sau khi chọn file, hệ thống SHALL hiện bảng khớp và SHALL chờ người dùng xác nhận trước khi nạp bất kỳ file nào.

Bảng khớp SHALL nêu với mỗi file: tên file, segment được khớp hoặc trạng thái bỏ qua, và lý do bỏ qua nếu có.

Người dùng SHALL có thể huỷ mà không có file nào được nạp.

#### Scenario: Bảng khớp hiện trước khi nạp

- **WHEN** người dùng vừa chọn xong nhiều file
- **THEN** bảng khớp được hiện
- **AND** chưa có file nào được nạp lên máy chủ

#### Scenario: Người dùng huỷ ở bảng khớp

- **WHEN** người dùng huỷ ở bảng khớp
- **THEN** không có clip nào được nạp và dữ liệu clip hiện có không đổi

#### Scenario: Không có file nào khớp

- **WHEN** toàn bộ file được chọn đều không khớp segment nào
- **THEN** bảng khớp nêu rõ không có file nào khớp
- **AND** hành động nạp không khả dụng

### Requirement: Nạp theo lô có ghi hãng phát hành

Khi nạp theo lô, mỗi clip SHALL được lưu kèm hãng phát hành, thay vì lưu không có hãng như đường nạp tay hiện tại.

Toàn bộ kiểm tra của đường nạp một clip — dung lượng tối đa, thời lượng tối đa, danh sách định dạng, và việc vô hiệu clip cũ của cùng shot — SHALL vẫn được áp dụng cho từng file trong lô.

#### Scenario: Clip nạp theo lô lưu được hãng phát hành

- **WHEN** người dùng xác nhận nạp một lô clip
- **THEN** mỗi clip được nạp có lưu hãng phát hành

#### Scenario: File vượt giới hạn trong lô

- **WHEN** một file trong lô vượt giới hạn dung lượng hoặc thời lượng
- **THEN** file đó bị từ chối với đúng thông báo lỗi của đường nạp một clip

#### Scenario: Nạp lô cho shot đã có clip

- **WHEN** một shot trong lô đã có clip đang hoạt động
- **THEN** clip cũ bị vô hiệu và clip mới trở thành clip đang hoạt động

### Requirement: Lỗi từng file không làm đổ cả lô

Khi một file trong lô nạp thất bại, các file còn lại SHALL vẫn được nạp.

Sau khi nạp xong, hệ thống SHALL báo số file thành công và danh sách file thất bại kèm lý do của từng file.

#### Scenario: Một file lỗi giữa lô

- **WHEN** một file trong lô thất bại khi nạp
- **THEN** các file còn lại vẫn được nạp thành công
- **AND** kết quả nêu rõ file nào thất bại và vì sao

#### Scenario: Báo kết quả sau khi nạp lô

- **WHEN** một lô nạp kết thúc
- **THEN** người dùng thấy số file đã nạp thành công trên tổng số file được khớp
