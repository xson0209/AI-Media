## ADDED Requirements

### Requirement: Chạy song song các bước xử lý theo từng clip

Luồng dựng MP4 SHALL xử lý các bước theo từng clip — làm sạch dấu AI và chuẩn hoá clip — song song trên nhiều clip cùng lúc, thay vì tuần tự từng clip một.

Số clip xử lý đồng thời SHALL được suy ra từ số nhân CPU của máy và SHALL có thể ghi đè bằng biến môi trường. Giá trị hiệu lực SHALL luôn ở mức tối thiểu là 1.

Kết quả ghép video SHALL giữ đúng thứ tự timeline bất kể clip nào hoàn thành trước.

#### Scenario: Nhiều clip được xử lý đồng thời

- **WHEN** một job render có nhiều clip và mức song song hiệu lực lớn hơn 1
- **THEN** nhiều clip được làm sạch dấu AI cùng lúc
- **AND** tổng thời gian chờ nhỏ hơn tổng thời gian của từng clip cộng lại

#### Scenario: Thứ tự clip sau khi ghép không phụ thuộc thứ tự hoàn thành

- **WHEN** các clip hoàn thành theo thứ tự khác thứ tự timeline
- **THEN** danh sách file đưa vào bước ghép video vẫn theo đúng thứ tự timeline

#### Scenario: Ghi đè mức song song bằng biến môi trường

- **WHEN** biến môi trường mức song song được đặt một giá trị hợp lệ
- **THEN** luồng render dùng đúng giá trị đó thay cho giá trị suy ra từ số nhân CPU

#### Scenario: Giá trị mức song song không hợp lệ

- **WHEN** biến môi trường mức song song rỗng, không phải số, bằng 0 hoặc âm
- **THEN** luồng render dùng giá trị suy ra từ số nhân CPU và không báo lỗi job

#### Scenario: Một clip lỗi không làm mất thông tin lỗi

- **WHEN** một clip thất bại ở bước làm sạch dấu AI hoặc chuẩn hoá
- **THEN** job render thất bại với đúng thông báo lỗi và mã lỗi của clip đó

### Requirement: Cập nhật trạng thái job an toàn khi chạy song song

Việc ghi trạng thái job xuống cơ sở dữ liệu SHALL chỉ diễn ra ở luồng điều phối, không diễn ra bên trong các tác vụ song song.

Số liệu tổng hợp về cache SHALL phản ánh đúng tổng số lần dùng lại và số lần phải tạo mới, không bị mất mát khi nhiều clip hoàn thành gần nhau.

#### Scenario: Tổng hợp số liệu cache đúng khi chạy song song

- **WHEN** một job render xử lý nhiều clip song song với một phần clip đã có cache
- **THEN** tổng số lần dùng lại cache cộng với tổng số lần tạo mới bằng đúng số clip trong timeline

### Requirement: Truyền đúng hãng của clip vào bước làm sạch dấu AI

Bước làm sạch dấu AI SHALL nhận hãng phát hành cụ thể của clip khi thông tin đó có trong dữ liệu clip, thay vì để bước làm sạch tự dò toàn bộ danh sách hãng được hỗ trợ.

Khi dữ liệu clip không có hãng phát hành, bước làm sạch SHALL giữ hành vi dò tự động như hiện tại.

#### Scenario: Clip có hãng phát hành

- **WHEN** một clip có hãng phát hành nằm trong danh sách được hỗ trợ
- **THEN** bước làm sạch chỉ dò dấu của đúng hãng đó

#### Scenario: Clip không có hãng phát hành

- **WHEN** một clip không lưu hãng phát hành
- **THEN** bước làm sạch dò tự động toàn bộ danh sách hãng được hỗ trợ
- **AND** clip vẫn được làm sạch bình thường

### Requirement: Mặc định backend làm sạch dấu AI là lựa chọn nhanh

Backend làm sạch dấu AI mặc định SHALL là lựa chọn nhanh dựa trên thuật toán ảnh thông thường, không phải lựa chọn dùng mô hình học sâu.

Lựa chọn dùng mô hình học sâu SHALL vẫn còn trong danh sách để người dùng chọn khi cần.

Nhãn hiển thị của mỗi lựa chọn SHALL bằng tiếng Việt và SHALL nêu rõ đặc điểm về tốc độ.

#### Scenario: Bảng dựng mở lần đầu

- **WHEN** người dùng mở bảng dựng nhanh MP4 mà chưa từng đổi lựa chọn
- **THEN** backend làm sạch dấu AI đang chọn là lựa chọn nhanh

#### Scenario: Người dùng chọn backend dùng mô hình học sâu

- **WHEN** người dùng chọn lựa chọn dùng mô hình học sâu và bấm dựng
- **THEN** job render dùng đúng lựa chọn đó

### Requirement: Báo tiến độ theo bước thực tế đang chạy

Trong lúc làm sạch dấu AI, luồng render SHALL cập nhật tiến độ kèm số clip đã hoàn thành trên tổng số clip, với nội dung tiếng Việt nói rõ đang làm sạch dấu AI.

Giai đoạn sau khi trộn audio cho tới khi hoàn tất SHALL có ít nhất một mốc cập nhật tiến độ, để thanh tiến độ không đứng im từ mốc trộn audio tới khi kết thúc.

Nội dung báo tiến độ SHALL không mô tả một bước khác với bước đang thực sự chạy.

#### Scenario: Đang làm sạch dấu AI

- **WHEN** luồng render đang làm sạch dấu AI cho các clip
- **THEN** nội dung tiến độ nói rõ đang làm sạch dấu AI kèm số clip đã xong trên tổng số

#### Scenario: Đang ghép và xuất file cuối

- **WHEN** luồng render đã trộn audio xong và đang ghép/xuất file cuối
- **THEN** có mốc cập nhật tiến độ cho giai đoạn này trước khi job chuyển sang hoàn tất

#### Scenario: Bước làm sạch bị tắt

- **WHEN** người dùng tắt làm sạch dấu AI
- **THEN** luồng render không báo nội dung tiến độ về làm sạch dấu AI
