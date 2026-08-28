## ADDED Requirements

### Requirement: Ảnh nhập từ truyện tranh giữ quan hệ giữa bản gốc và các derivative
Hệ thống PHẢI (MUST) quản lý original, analysis image, preview, tile và export như các artifact liên quan của cùng source asset/revision.

#### Scenario: Tạo derivative từ ảnh nguồn
- **WHEN** ảnh gốc được convert, rasterize hoặc chia tile
- **THEN** mỗi derivative PHẢI lưu source asset ID, source checksum, codec/transform version, kích thước và mục đích sử dụng
- **AND** artifact gốc PHẢI bất biến

#### Scenario: Tạo lại derivative bằng codec mới
- **WHEN** codec hoặc transform pipeline thay đổi
- **THEN** hệ thống PHẢI tạo derivative revision mới
- **AND** derivative cũ PHẢI còn truy xuất được cho analysis/handoff đã dùng nó

#### Scenario: Dedupe cùng blob nhưng khác provenance
- **WHEN** hai nguồn có ảnh cùng checksum
- **THEN** hệ thống CÓ THỂ dùng chung blob vật lý
- **AND** PHẢI giữ occurrence, URL, source revision và handoff mapping riêng cho từng nguồn

### Requirement: Ảnh được chọn từ Comic Analysis phải qua gate Reference Asset của Series
Hệ thống PHẢI (MUST) ánh xạ ảnh nguồn đã chọn thành Reference Asset đúng nhân vật, địa điểm và vai trò; approval phân tích không tự động kích hoạt ảnh trong prompt.

#### Scenario: Handoff ảnh nhân vật hoặc địa điểm
- **WHEN** người dùng chọn ảnh trong handoff preview
- **THEN** target asset PHẢI lưu provenance, checksum, crop/tile nếu có và entity/role đích
- **AND** PHẢI ở trạng thái `pending_approval` và `active=false` trước khi dùng trong prompt

#### Scenario: Provider không hỗ trợ attachment tham chiếu
- **WHEN** prompt sau này dùng asset nhưng provider không thể nhận ảnh
- **THEN** hệ thống PHẢI báo fallback text rõ ràng
- **AND** KHÔNG ĐƯỢC tuyên bố ảnh nguồn đã được gửi cho provider

#### Scenario: Người dùng không chọn ảnh
- **WHEN** source asset có trong analysis nhưng không được chọn ở preview
- **THEN** hệ thống KHÔNG ĐƯỢC tạo Series Reference Asset từ ảnh đó

### Requirement: Artifact phụ thuộc Comic Source phải lưu revision và evidence đã dùng
Hệ thống PHẢI (MUST) mở rộng dependency snapshot để ghi analysis revision, source document revision, source chunks và source/reference assets thực sự ảnh hưởng artifact.

#### Scenario: Tạo Master Story từ Comic Source
- **WHEN** Story Studio tạo candidate hoặc Master Story
- **THEN** dependency snapshot PHẢI ghi source document revision, các chunk/plot/canon/character revision đã dùng và limitation tại thời điểm tạo

#### Scenario: Tạo prompt ảnh dùng reference nhập từ truyện
- **WHEN** một panel prompt dùng visual identity hoặc location asset từ Comic handoff
- **THEN** dependency snapshot PHẢI ghi đúng Reference Asset revision và source checksum

#### Scenario: Xem provenance của artifact
- **WHEN** người dùng mở artifact phụ thuộc nguồn truyện tranh
- **THEN** UI/API PHẢI cho biết analysis ID, handoff ID, source revision và evidence liên quan bằng tiếng Việt

### Requirement: Stale từ Comic Source chỉ lan tới artifact bị ảnh hưởng
Hệ thống PHẢI (MUST) đánh dấu stale theo dependency và chỉ sau khi revision mới được áp dụng vào Series/Story Episode.

#### Scenario: Sửa OCR hoặc lời thoại đã handoff
- **WHEN** Source Document revision mới thay đổi nội dung lời thoại/narration được candidate hoặc Master Story dùng
- **THEN** các artifact nội dung phụ thuộc đoạn đó PHẢI stale
- **AND** Reference Asset không phụ thuộc text đó KHÔNG ĐƯỢC stale

#### Scenario: Thay ảnh visual identity của một nhân vật
- **WHEN** Reference Asset revision mới được duyệt cho nhân vật
- **THEN** panel/prompt/render phụ thuộc visual identity cũ PHẢI stale
- **AND** Episode không dùng nhân vật đó KHÔNG ĐƯỢC stale

#### Scenario: Re-analysis chưa commit
- **WHEN** Comic Analysis có revision mới nhưng target vẫn dùng handoff revision cũ
- **THEN** hệ thống chỉ PHẢI hiển thị `Có phiên bản nguồn mới`
- **AND** KHÔNG ĐƯỢC lan stale cho artifact đích trước commit update handoff

#### Scenario: Thay derivative nhưng pixel-equivalent
- **WHEN** preview hoặc derivative kỹ thuật được tạo lại nhưng source checksum và nội dung pixel dùng bởi artifact không đổi
- **THEN** hệ thống KHÔNG ĐƯỢC mặc định stale artifact nội dung
- **AND** pixel-equivalent chỉ được xác nhận bằng `decoded_pixel_hash` sau orientation/colorspace normalization cùng algorithm/transform version; nếu dùng perceptual hash phải lưu algorithm, version và threshold

### Requirement: Xóa nguồn hoặc job không được làm mất artifact Series đang tham chiếu
Hệ thống PHẢI (MUST) giữ reference count hoặc quan hệ retention để bảo vệ source asset, Source Document và derivative đang được Episode/Reference sử dụng.

#### Scenario: Xóa analysis chưa handoff
- **WHEN** job không có target artifact tham chiếu
- **THEN** hệ thống CÓ THỂ xóa rows và files theo retention policy
- **AND** PHẢI cleanup staging và derivative orphan

#### Scenario: Xóa analysis đã handoff
- **WHEN** source document hoặc asset đang được Series/Story Episode tham chiếu
- **THEN** hệ thống PHẢI chặn xóa vật lý hoặc giữ artifact bất biến theo retention
- **AND** PHẢI giải thích dữ liệu nào đang phụ thuộc nguồn đó
