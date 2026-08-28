## ADDED Requirements

### Requirement: Story Episode hỗ trợ nguồn truyện tranh có cấu trúc
Hệ thống PHẢI (MUST) cho phép Story Episode liên kết một `StoryEpisodeSourceDocument` được tạo từ Comic Series Analysis và coi document/revision đó là nguồn chuẩn của nội dung tập.

#### Scenario: Mở Episode vừa handoff
- **WHEN** người dùng mở Story Studio từ một comic handoff thành công
- **THEN** Story Studio PHẢI chọn đúng Series và Story Episode
- **AND** PHẢI hiển thị nguồn truyện, revision, coverage, limitation và liên kết xem evidence

#### Scenario: Client cũ chỉ hiểu source_input
- **WHEN** API hoặc UI cũ đọc `source_input` và `source_digest`
- **THEN** hệ thống CÓ THỂ trả projection tương thích từ Source Document
- **AND** mọi thao tác sửa nguồn chuẩn PHẢI tạo revision của Source Document thay vì chỉ thay chuỗi projection

#### Scenario: Story Episode nhập tay không có Source Document
- **WHEN** một Episode cũ hoặc Episode nhập tay chỉ có `source_input`
- **THEN** Story Studio PHẢI tiếp tục hoạt động theo contract hiện có
- **AND** Source Document mới KHÔNG ĐƯỢC trở thành bắt buộc đối với dữ liệu legacy

#### Scenario: Chọn nguồn hiện hành của Episode
- **WHEN** Episode có nhiều Source Document revision
- **THEN** `current_source_document_id` PHẢI trỏ tới đúng một revision approved hiện hành
- **AND** compiler KHÔNG ĐƯỢC tự chọn revision mới nhất chưa approved thay pointer đó

### Requirement: Story Studio phát triển kịch bản từ nguồn truyện tranh đã duyệt
Hệ thống PHẢI (MUST) dùng source revision đã approved, nội dung chương, plot beats, character/location mappings và Series Canon khi tạo đúng ba candidate.

#### Scenario: Tạo ba candidate từ Comic Source
- **WHEN** người dùng yêu cầu phát triển kịch bản cho Episode có Comic Source hợp lệ
- **THEN** context PHẢI bao gồm synopsis, plot structure, các source chunks liên quan, nhân vật, bối cảnh, canon, limitation và định hướng người dùng
- **AND** hệ thống PHẢI tạo đúng ba candidate theo contract Story Studio hiện có

#### Scenario: Nguồn quá dài cho một prompt
- **WHEN** Source Document vượt context budget
- **THEN** compiler PHẢI dùng tóm tắt toàn chương cộng plot beats và truy xuất chunk liên quan theo nhiệm vụ
- **AND** PHẢI ghi phần đã dùng, phần bị rút gọn và source revision

#### Scenario: Nguồn partial
- **WHEN** revision được duyệt có text, OCR hoặc vision coverage không đầy đủ
- **THEN** Story Studio PHẢI truyền limitation vào context và output review
- **AND** AI KHÔNG ĐƯỢC bịa phần nguồn bị thiếu như đã quan sát

#### Scenario: Ba candidate dùng cùng nguồn
- **WHEN** Story Studio tạo ba candidate cho một Episode nhập từ Comic Analysis
- **THEN** cả ba candidate PHẢI dùng cùng Source Document revision và cùng context snapshot
- **AND** retry một candidate KHÔNG ĐƯỢC tự chuyển sang revision nguồn mới hơn

### Requirement: Chế độ phát triển từ nguồn truyện phải thể hiện quyền và mức độ bám nguồn
Hệ thống PHẢI (MUST) lưu `development_mode` cho Story Episode nhập từ truyện tranh và dùng mode đó khi tạo candidate.

#### Scenario: Nguồn bên ngoài mặc định
- **WHEN** người dùng nhập nguồn công khai nhưng không xác nhận quyền phát triển tiếp canon
- **THEN** mode mặc định PHẢI là `lay_cam_hung_va_viet_moi`
- **AND** AI PHẢI tránh sao chép nguyên văn đoạn dài, lời thoại dài hoặc trình tự cảnh đặc thù không cần thiết

#### Scenario: Bám canon và phát triển tiếp
- **WHEN** người dùng xác nhận có quyền với tác phẩm và chọn `bam_canon_va_phat_trien_tiep`
- **THEN** Story Studio CÓ THỂ dùng canon, nhân vật và unresolved threads đã duyệt để phát triển tập tiếp
- **AND** handoff/source provenance vẫn PHẢI được giữ

#### Scenario: Đổi chế độ phát triển
- **WHEN** development mode thay đổi sau khi đã tạo candidate hoặc Master Story
- **THEN** các artifact sáng tạo phụ thuộc mode cũ PHẢI stale
- **AND** hệ thống PHẢI yêu cầu tạo lại trước khi dùng làm đầu ra hiện hành

### Requirement: Chế độ viết mới phải có kiểm tra tính nguyên bản có bằng chứng
Hệ thống PHẢI (MUST) tạo artifact kiểm tra tính nguyên bản cho candidate và Master Story khi `development_mode = lay_cam_hung_va_viet_moi`.

#### Scenario: Kiểm tra overlap với nguồn
- **WHEN** candidate hoặc Master Story được tạo
- **THEN** originality check PHẢI lưu longest verbatim span, overlap theo source chunk và semantic similarity theo algorithm/threshold version
- **AND** tên riêng, thuật ngữ canon và trích dẫn ngắn được phép PHẢI dùng allowlist có dấu vết

#### Scenario: Vượt ngưỡng sao chép
- **WHEN** verbatim hoặc semantic overlap vượt ngưỡng cấu hình
- **THEN** hệ thống PHẢI chặn approval hoặc yêu cầu người dùng override có lý do
- **AND** override PHẢI được lưu cùng artifact/revision

### Requirement: Thay đổi Comic Source làm stale đúng artifact Story Studio phụ thuộc nguồn
Hệ thống PHẢI (MUST) lưu dependency từ candidate, Master Story và adaptation tới source document/chunk revision thực sự đã dùng.

#### Scenario: Nguồn approved có revision mới
- **WHEN** Episode chuyển sang Comic Source revision mới
- **THEN** candidate và Master Story phụ thuộc revision cũ PHẢI bị đánh dấu stale
- **AND** adaptation phụ thuộc Master Story cũ PHẢI stale theo dependency

#### Scenario: Biểu diễn artifact stale
- **WHEN** source hoặc development mode làm artifact sáng tạo không còn hiện hành
- **THEN** candidate PHẢI chuyển generation/evaluation status tương đương `stale` và không còn selected
- **AND** Master Story PHẢI giữ payload nhưng chuyển approval status `stale`, xóa thời điểm duyệt; UI/API PHẢI chặn dùng artifact stale để tạo adaptation

#### Scenario: Revision mới chưa được áp dụng
- **WHEN** Comic Analysis có revision mới nhưng người dùng chưa commit update handoff
- **THEN** Story Episode và các artifact hiện có PHẢI tiếp tục tham chiếu revision cũ
- **AND** KHÔNG ĐƯỢC tự stale hoặc thay đổi dữ liệu đích chỉ vì nguồn web đã thay đổi

#### Scenario: Chỉ một chunk không liên quan thay đổi
- **WHEN** source revision mới thay đổi một chunk không được artifact hiện tại sử dụng và dependency resolver chứng minh không ảnh hưởng
- **THEN** hệ thống KHÔNG ĐƯỢC mặc định stale artifact không phụ thuộc chunk đó
- **AND** phải lưu lý do nếu vẫn cần stale vì synopsis hoặc plot structure toàn chương thay đổi
