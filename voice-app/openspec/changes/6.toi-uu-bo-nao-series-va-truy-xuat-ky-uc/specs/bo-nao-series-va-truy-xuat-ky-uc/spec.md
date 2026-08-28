## ADDED Requirements

### Requirement: Thẻ nhớ series có cấu trúc và được duyệt
Hệ thống BẮT BUỘC (MUST) lưu ký ức series thành các thẻ có cấu trúc, có loại, liên kết thực thể, nguồn, mức quan trọng, phạm vi hiệu lực, phiên bản và trạng thái duyệt.

#### Scenario: Tạo thẻ nhớ nháp
- **WHEN** người dùng hoặc AI đề xuất một địa điểm, đạo cụ, quan hệ, mạch truyện hoặc quy tắc canon mới
- **THEN** hệ thống PHẢI lưu đề xuất ở trạng thái nháp hoặc chờ duyệt
- **AND** thẻ chưa duyệt KHÔNG ĐƯỢC trở thành quy tắc canon bắt buộc cho lần tạo tiếp theo

#### Scenario: Duyệt thẻ nhớ
- **WHEN** người dùng duyệt một thẻ nhớ hợp lệ
- **THEN** hệ thống PHẢI lưu thời điểm duyệt, phiên bản và nguồn của thẻ
- **AND** bộ chọn ký ức PHẢI có thể sử dụng thẻ trong đúng phạm vi hiệu lực

#### Scenario: Hồ sơ nhân vật không bị nhân đôi
- **WHEN** bộ chọn cần dữ liệu nhân vật
- **THEN** hệ thống PHẢI dùng Hồ sơ nhân vật có cấu trúc hiện có làm nguồn chuẩn
- **AND** hệ thống KHÔNG ĐƯỢC tạo một bản nhân vật độc lập có thể mâu thuẫn với Hồ sơ nhân vật

### Requirement: Trạng thái hiện tại của series được lưu và duyệt riêng
Hệ thống BẮT BUỘC (MUST) duy trì trạng thái hiện tại của nhân vật, quan hệ, địa điểm, đạo cụ và mạch truyện sau tập đã duyệt.

#### Scenario: AI đề xuất trạng thái sau tập
- **WHEN** Master Story hoặc nội dung video của một tập đã được duyệt
- **THEN** hệ thống PHẢI có thể tạo bản đề xuất thay đổi trạng thái
- **AND** bản đề xuất PHẢI chỉ rõ giá trị cũ, giá trị mới và nguồn thay đổi

#### Scenario: Chưa duyệt trạng thái mới
- **WHEN** người dùng chưa duyệt bản trạng thái đề xuất
- **THEN** hệ thống PHẢI tiếp tục dùng trạng thái đã duyệt gần nhất
- **AND** hệ thống KHÔNG ĐƯỢC âm thầm ghi đè trạng thái hiện tại

#### Scenario: Duyệt trạng thái mới
- **WHEN** người dùng duyệt thay đổi trạng thái
- **THEN** hệ thống PHẢI tạo phiên bản trạng thái mới dựa trên số tập tương ứng
- **AND** phiên bản trước PHẢI còn truy xuất được

### Requirement: Lịch sử series được lưu đầy đủ theo nhiều tầng
Hệ thống BẮT BUỘC (MUST) giữ tóm tắt riêng từng tập, tóm tắt chặng, tóm tắt toàn series, trạng thái hiện tại và mạch truyện đang mở.

#### Scenario: Series có nhiều tập
- **WHEN** series có số lượng tập vượt quá dung lượng một gói ngữ cảnh
- **THEN** hệ thống PHẢI giữ lịch sử chi tiết trong cơ sở dữ liệu
- **AND** hệ thống PHẢI dùng tóm tắt chặng và mục lục để tìm đúng tập cũ liên quan
- **AND** hệ thống KHÔNG ĐƯỢC xóa lịch sử cũ chỉ vì không đưa toàn bộ vào yêu cầu AI hiện tại

#### Scenario: Cần nhắc lại sự kiện cũ
- **WHEN** nội dung tập mới liên quan tới một nhân vật, đạo cụ hoặc mạch truyện từ tập cũ
- **THEN** bộ chọn PHẢI lấy tóm tắt tập hoặc chặng chứa sự kiện đó dù tập không nằm trong nhóm tập gần nhất

### Requirement: Gói ngữ cảnh được biên dịch theo nhiệm vụ
Hệ thống BẮT BUỘC (MUST) tạo gói ngữ cảnh khác nhau cho từng loại nhiệm vụ và chỉ lấy dữ liệu cần thiết hoặc bắt buộc.

#### Scenario: Tạo Master Story
- **WHEN** hệ thống chuẩn bị ngữ cảnh để tạo Master Story
- **THEN** gói ngữ cảnh PHẢI ưu tiên danh tính series, nhân vật, quan hệ, mạch truyện mở, trạng thái hiện tại, tập gần nhất và yêu cầu mới

#### Scenario: Tạo prompt panel ảnh
- **WHEN** hệ thống chuẩn bị ngữ cảnh cho một panel ảnh
- **THEN** gói ngữ cảnh PHẢI chứa nhân vật, trang phục, địa điểm, phong cách, trạng thái và panel liền kề liên quan
- **AND** KHÔNG NÊN chứa lịch sử không liên quan chỉ để lấp đầy dung lượng

#### Scenario: Tạo voice hoặc subtitle
- **WHEN** hệ thống chuẩn bị ngữ cảnh cho voice hoặc subtitle
- **THEN** hệ thống PHẢI ưu tiên narration đã duyệt, ngôn ngữ, người nói, cách nói, cảm xúc và thời lượng
- **AND** hệ thống KHÔNG ĐƯỢC bắt buộc gửi toàn bộ dữ liệu hình ảnh của series

### Requirement: Dung lượng ngữ cảnh được phân bổ theo nhóm
Hệ thống BẮT BUỘC (MUST) thay cách lấy 24.000 ký tự đầu bằng cơ chế phân bổ dung lượng theo nhóm và mức quan trọng.

#### Scenario: Một nhóm dữ liệu quá dài
- **WHEN** Series Bible hoặc lịch sử tập vượt dung lượng được phân bổ
- **THEN** hệ thống PHẢI rút gọn trong chính nhóm đó
- **AND** hệ thống KHÔNG ĐƯỢC làm mất toàn bộ nhóm trạng thái hiện tại hoặc quy tắc bất biến nằm phía sau

#### Scenario: Một nhóm dùng không hết dung lượng
- **WHEN** một nhóm dữ liệu ngắn hơn phần được phân bổ
- **THEN** hệ thống PHẢI có thể chuyển phần dư cho nhóm liên quan khác
- **AND** vẫn PHẢI bảo vệ dữ liệu bắt buộc

#### Scenario: Báo phần bị rút gọn
- **WHEN** có dữ liệu bị rút gọn
- **THEN** phản hồi hoặc nhật ký an toàn PHẢI nêu nhóm bị rút gọn và dung lượng đã dùng
- **AND** KHÔNG ĐƯỢC ghi token, cookie hoặc dữ liệu đăng nhập provider

### Requirement: Người dùng xem được nguồn ký ức AI đã dùng
Hệ thống BẮT BUỘC (MUST) lưu và hiển thị dấu vết các thẻ, phiên bản và nhóm dữ liệu đã được dùng cho một tác vụ AI.

#### Scenario: Xem nguồn của prompt
- **WHEN** người dùng mở chi tiết một prompt ảnh hoặc video
- **THEN** UI PHẢI cho biết các nhân vật, địa điểm, mạch truyện, trạng thái và tập cũ đã được dùng
- **AND** người dùng PHẢI có thể mở dữ liệu nguồn bằng giao diện tiếng Việt

### Requirement: Prompt được kiểm tra mâu thuẫn canon
Hệ thống BẮT BUỘC (MUST) kiểm tra prompt ảnh và prompt video đối với canon đã duyệt trước khi cho phép dùng làm đầu ra đạt chất lượng.

#### Scenario: Prompt đổi đặc điểm cố định
- **WHEN** prompt làm thay đổi khuôn mặt, tóc, trang phục cố định hoặc đặc điểm không được thay đổi của nhân vật
- **THEN** hệ thống PHẢI trả về lỗi chặn với bằng chứng Hồ sơ nhân vật liên quan
- **AND** prompt KHÔNG ĐƯỢC chuyển sang trạng thái đạt chất lượng

#### Scenario: Prompt dùng sai trạng thái hoặc mạch truyện
- **WHEN** prompt dùng sai người đang giữ đạo cụ, sai địa điểm, sai quan hệ hoặc tiết lộ bí mật trước thời điểm được phép
- **THEN** hệ thống PHẢI trả về lỗi chặn hoặc cảnh báo theo mức nghiêm trọng
- **AND** kết quả PHẢI chỉ rõ dữ liệu canon bị mâu thuẫn

#### Scenario: Ghi đè lỗi canon
- **WHEN** người dùng có quyền chọn ghi đè một lỗi canon
- **THEN** hệ thống PHẢI yêu cầu lý do
- **AND** hệ thống PHẢI lưu người thực hiện, thời điểm, lỗi được ghi đè và phiên bản prompt

### Requirement: Tệp Markdown chỉ là bản dựng
Hệ thống BẮT BUỘC (MUST) dựng các tệp bộ nhớ từ cơ sở dữ liệu và KHÔNG ĐƯỢC coi tệp Markdown là nguồn chuẩn độc lập.

#### Scenario: Dựng lại tệp bộ nhớ
- **WHEN** tệp bộ nhớ bị thiếu, cũ hoặc sai phiên bản
- **THEN** hệ thống PHẢI có thể dựng lại từ Series Bible, Hồ sơ nhân vật, thẻ nhớ, trạng thái và lịch sử đã duyệt
- **AND** không được mất dữ liệu chuẩn trong cơ sở dữ liệu
