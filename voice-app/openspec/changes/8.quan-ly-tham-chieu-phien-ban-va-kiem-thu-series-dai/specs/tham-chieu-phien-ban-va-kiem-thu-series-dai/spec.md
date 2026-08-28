## ADDED Requirements

### Requirement: Nhân vật và địa điểm có ảnh tham chiếu được duyệt
Hệ thống BẮT BUỘC (MUST) cho phép quản lý nhiều ảnh tham chiếu theo vai trò cho nhân vật và địa điểm.

#### Scenario: Tải ảnh tham chiếu nhân vật
- **WHEN** người dùng tải ảnh khuôn mặt, góc nghiêng, toàn thân, trang phục hoặc biểu cảm cho một nhân vật
- **THEN** hệ thống PHẢI lưu ảnh như artifact tham chiếu của đúng nhân vật và đúng vai trò
- **AND** ảnh PHẢI ở trạng thái chờ duyệt trước khi được dùng trong prompt

#### Scenario: Tải ảnh tham chiếu địa điểm
- **WHEN** người dùng tải ảnh toàn cảnh, lối vào, nội thất, chi tiết nhận diện hoặc ánh sáng cho một địa điểm
- **THEN** hệ thống PHẢI gắn ảnh với đúng địa điểm và vai trò
- **AND** không được tự gắn ảnh đó cho địa điểm khác

#### Scenario: Provider không hỗ trợ ảnh tham chiếu
- **WHEN** adapter provider không thể gửi ảnh tham chiếu
- **THEN** hệ thống PHẢI giữ mô tả văn bản và báo rõ dùng phương án dự phòng
- **AND** KHÔNG ĐƯỢC hiển thị rằng provider đã nhận ảnh nếu ảnh chưa được gửi

### Requirement: Ảnh tham chiếu được quản lý an toàn
Hệ thống BẮT BUỘC (MUST) kiểm tra loại tệp, dung lượng, kích thước, tên tệp và vị trí lưu trữ của ảnh tham chiếu.

#### Scenario: Tệp ảnh không hợp lệ
- **WHEN** người dùng tải tệp không thuộc loại hoặc dung lượng được phép
- **THEN** hệ thống PHẢI từ chối bằng lỗi tiếng Việt
- **AND** KHÔNG ĐƯỢC lưu tệp như ảnh tham chiếu hợp lệ

#### Scenario: Xuất package hoặc debug
- **WHEN** hệ thống xuất package hoặc dữ liệu chẩn đoán
- **THEN** hệ thống KHÔNG ĐƯỢC đưa cookie, token, credential hoặc đường dẫn hồ sơ trình duyệt vào kết quả
- **AND** chỉ được đưa ảnh hoặc metadata ảnh theo chính sách xuất đã cấu hình

### Requirement: Dữ liệu canon và artifact có phiên bản
Hệ thống BẮT BUỘC (MUST) theo dõi phiên bản của dữ liệu canon, ảnh tham chiếu, Master Story, panel, shot, narration và prompt.

#### Scenario: Sửa dữ liệu đã duyệt
- **WHEN** người dùng sửa một dữ liệu canon đã duyệt
- **THEN** hệ thống PHẢI tạo revision mới hoặc bản phiên bản mới
- **AND** phiên bản cũ PHẢI còn truy xuất được cho artifact đã dùng nó

#### Scenario: Xem lịch sử phiên bản
- **WHEN** người dùng mở lịch sử một nhân vật, địa điểm, thẻ nhớ, trạng thái hoặc ảnh tham chiếu
- **THEN** UI PHẢI hiển thị các phiên bản, thời điểm, người hoặc nguồn thay đổi và phần khác nhau bằng tiếng Việt

### Requirement: Artifact lưu đúng quan hệ phụ thuộc
Hệ thống BẮT BUỘC (MUST) lưu artifact đã phụ thuộc vào dữ liệu nào, revision nào và phạm vi ảnh hưởng nào tại thời điểm tạo.

#### Scenario: Tạo prompt có nhân vật và địa điểm
- **WHEN** hệ thống tạo prompt cho một shot có nhân vật Lan tại quán cà phê
- **THEN** dependency snapshot PHẢI lưu revision Hồ sơ Lan, địa điểm quán cà phê, style, trạng thái, Master Story và ảnh tham chiếu thực sự đã dùng

#### Scenario: Tạo voice
- **WHEN** hệ thống tạo voice cho một narration
- **THEN** dependency snapshot PHẢI ưu tiên narration, người nói, voice profile, ngôn ngữ và timing
- **AND** KHÔNG ĐƯỢC tự phụ thuộc vào ảnh địa điểm nếu ảnh không ảnh hưởng voice

### Requirement: Stale chỉ lan truyền tới artifact bị ảnh hưởng
Hệ thống BẮT BUỘC (MUST) đánh dấu stale theo dependency và phạm vi thay đổi thay vì mặc định làm cũ toàn bộ project.

#### Scenario: Đổi ngoại hình một nhân vật
- **WHEN** revision ngoại hình của một nhân vật thay đổi
- **THEN** hệ thống PHẢI stale panel, shot và prompt có phụ thuộc visual identity của nhân vật đó
- **AND** KHÔNG ĐƯỢC stale artifact của tập không dùng nhân vật đó

#### Scenario: Đổi style toàn series
- **WHEN** style hình ảnh đã duyệt thay đổi
- **THEN** hệ thống PHẢI stale prompt ảnh, prompt video và render hình ảnh phụ thuộc style
- **AND** KHÔNG ĐƯỢC stale voice nếu narration, voice profile và ngôn ngữ không đổi

#### Scenario: Đổi narration
- **WHEN** narration hoặc timing đã duyệt thay đổi
- **THEN** hệ thống PHẢI stale voice, subtitle và package liên quan
- **AND** PHẢI giữ prompt hình ảnh nếu prompt không phụ thuộc nội dung narration đã đổi

#### Scenario: Xem lý do stale
- **WHEN** người dùng mở một artifact stale
- **THEN** UI PHẢI hiển thị dữ liệu nguồn thay đổi, phiên bản cũ/mới và lý do ảnh hưởng
- **AND** PHẢI cho phép tạo lại đúng phạm vi

### Requirement: Bộ kiểm thử series dài không gọi Veo
Hệ thống BẮT BUỘC (MUST) có bộ dữ liệu và kiểm thử nhiều tập để xác nhận bộ nhớ, canon, candidate, prompt, voice, subtitle và stale mà không gọi provider video.

#### Scenario: Chạy bộ 30 tập
- **WHEN** bộ kiểm thử thường xuyên chạy
- **THEN** hệ thống PHẢI xử lý ít nhất 30 tập có sự kiện liên kết, nhân vật, địa điểm, đạo cụ và mạch truyện
- **AND** PHẢI kiểm tra chọn ký ức, canon, candidate, tổng hợp, prompt, sửa prompt, voice và subtitle

#### Scenario: Chạy bộ 100 tập
- **WHEN** bộ kiểm thử dài hạn được chọn
- **THEN** hệ thống PHẢI kiểm tra khả năng tìm sự kiện cũ, phân bổ ngữ cảnh và stale có mục tiêu trên tối thiểu 100 tập
- **AND** kết quả PHẢI báo thời gian, dung lượng ngữ cảnh và chỉ số chất lượng

#### Scenario: Không gọi provider video
- **WHEN** bất kỳ bộ kiểm thử capability này chạy
- **THEN** hệ thống KHÔNG ĐƯỢC tạo job Veo, submit prompt, tải clip hoặc tiêu credit provider
- **AND** kiểm thử PHẢI xác nhận không có bản ghi clip hoặc job provider mới

### Requirement: Báo cáo kiểm thử có chỉ số dễ hiểu
Hệ thống BẮT BUỘC (MUST) xuất báo cáo tiếng Việt về chất lượng bộ nhớ, canon, sáng tạo, prompt và stale.

#### Scenario: Hoàn tất kiểm thử
- **WHEN** bộ kiểm thử hoàn tất
- **THEN** báo cáo PHẢI nêu tỷ lệ lấy đúng ký ức, thẻ gây nhiễu, lỗi canon phát hiện, lỗi bị bỏ sót, độ khác biệt candidate, tỷ lệ sửa prompt thành công, stale đúng và stale thừa
- **AND** báo cáo PHẢI nêu rõ có hay không lời gọi provider video
