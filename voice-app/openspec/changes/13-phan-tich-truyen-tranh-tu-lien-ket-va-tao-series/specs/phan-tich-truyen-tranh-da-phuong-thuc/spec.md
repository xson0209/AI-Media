## ADDED Requirements

### Requirement: Mỗi revision tạo gói phân tích truyện tranh có cấu trúc
Hệ thống PHẢI (MUST) tạo `ComicAnalysisPackage` có schema version và stable ID cho nguồn, trang, ảnh, tile, panel, bong bóng thoại, text chunk, nhân vật, địa điểm, plot beat, canon candidate và limitation.

#### Scenario: Phân tích hoàn tất đầy đủ
- **WHEN** text, ảnh, OCR và vision đều hoàn tất
- **THEN** package PHẢI lưu revision nguồn, revision phân tích, coverage từng modality, ngôn ngữ, số trang, số panel, số lời thoại và thời điểm tạo
- **AND** mọi entity PHẢI có ID ổn định để review và handoff tham chiếu

#### Scenario: Một modality chỉ hoàn tất một phần
- **WHEN** text, OCR, panel detection, character analysis hoặc vision bị thiếu một phần
- **THEN** package PHẢI ghi coverage, error và limitation theo modality
- **AND** UI PHẢI phân biệt rõ `completed`, `partial` và `unavailable`

#### Scenario: Structured output không hợp lệ
- **WHEN** một bước AI trả thiếu field bắt buộc, sai type hoặc evidence ID không tồn tại
- **THEN** hệ thống PHẢI từ chối output đó hoặc retry theo giới hạn
- **AND** KHÔNG ĐƯỢC ghi kết quả sai schema thành analysis completed

### Requirement: AI vision phải nhận ảnh thật qua input đa phương thức
Hệ thống PHẢI (MUST) gửi nội dung ảnh hoặc tile qua trường image input chính thức của adapter AI; chỉ gửi đường dẫn local, tên file hoặc metadata trong text KHÔNG ĐƯỢC coi là AI đã xem ảnh.

#### Scenario: Gửi ảnh cho model đa phương thức
- **WHEN** adapter hỗ trợ vision
- **THEN** adapter PHẢI đọc artifact đã xác thực và đính kèm bytes, multipart/file handle thực sự gắn vào trường image input, provider file ID hoặc image input tương đương được provider hỗ trợ
- **AND** request manifest PHẢI ánh xạ mỗi attachment với `asset_id`, `tile_id`, page order và tọa độ nguồn

#### Scenario: Phân tích nhiều ảnh hoặc nhiều tile
- **WHEN** số attachment vượt giới hạn một request
- **THEN** hệ thống PHẢI chia batch có thứ tự, giữ context nhận dạng liên batch và tổng hợp kết quả theo stable ID
- **AND** KHÔNG ĐƯỢC làm mất liên kết evidence với ảnh hoặc tile gốc

#### Scenario: Provider không nhận được ảnh
- **WHEN** adapter không hỗ trợ vision, upload thất bại hoặc attachment không thể decode
- **THEN** hệ thống PHẢI đánh dấu vision `unavailable` hoặc `partial`
- **AND** KHÔNG ĐƯỢC sinh mô tả pixel như thể ảnh đã được quan sát

#### Scenario: Kiểm tra capability đọc pixel
- **WHEN** hệ thống xác nhận adapter vision sẵn sàng
- **THEN** acceptance check PHẢI dùng ảnh fixture có dữ kiện chỉ suy ra được từ pixel
- **AND** adapter chỉ được báo ready khi trả đúng dữ kiện hình ảnh theo ngưỡng kiểm tra

### Requirement: Hệ thống xác định thứ tự trang, panel và thứ tự đọc
Hệ thống PHẢI (MUST) bảo toàn thứ tự ảnh nguồn và suy luận page/panel reading order theo chế độ `auto`, `vertical`, `page_ltr` hoặc `page_rtl` với confidence.

#### Scenario: Truyện dọc
- **WHEN** nguồn là ảnh dài hoặc chuỗi ảnh webtoon
- **THEN** hệ thống PHẢI ưu tiên thứ tự từ trên xuống
- **AND** panel/tile PHẢI giữ tọa độ liên tục so với ảnh hoặc trang gốc

#### Scenario: Truyện theo trang
- **WHEN** người dùng chọn hoặc AI xác định `page_ltr` hay `page_rtl`
- **THEN** hệ thống PHẢI sắp xếp panel theo mode đó
- **AND** PHẢI lưu confidence và bằng chứng bố cục

#### Scenario: Thứ tự đọc không chắc chắn
- **WHEN** bố cục panel chồng lấp, phi tuyến hoặc confidence dưới ngưỡng
- **THEN** hệ thống PHẢI đánh dấu cần review
- **AND** người dùng PHẢI có thể kéo sắp xếp lại page và panel trước khi duyệt

#### Scenario: Người dùng đổi reading mode
- **WHEN** người dùng đổi mode hoặc thứ tự sau khi phân tích
- **THEN** hệ thống PHẢI tạo analysis revision mới
- **AND** mọi bubble, dialogue, plot hoặc evidence phụ thuộc order cũ PHẢI được đánh dấu cần tính lại hoặc review

### Requirement: OCR và bong bóng thoại được lưu riêng, có tọa độ và nguồn chỉnh sửa
Hệ thống PHẢI (MUST) lưu text nhìn thấy trong ảnh theo vùng, loại nội dung, ngôn ngữ, confidence và evidence thay vì chỉ ghép thành một chuỗi văn bản duy nhất.

#### Scenario: Nhận diện bong bóng thoại
- **WHEN** OCR hoặc vision phát hiện vùng thoại
- **THEN** hệ thống PHẢI lưu bounding region, page/panel, reading order, raw text, normalized text, ngôn ngữ, bubble type và confidence

#### Scenario: Nhận diện narration hoặc SFX
- **WHEN** text nằm trong hộp narration, caption hoặc vùng hiệu ứng âm thanh
- **THEN** hệ thống PHẢI phân loại riêng với lời thoại khi bằng chứng đủ
- **AND** PHẢI dùng `unknown` khi không đủ chắc chắn

#### Scenario: Suy luận người nói
- **WHEN** hệ thống gán một lời thoại cho nhân vật
- **THEN** speaker assignment PHẢI có confidence và evidence riêng với confidence OCR
- **AND** KHÔNG ĐƯỢC coi tên người nói là chắc chắn chỉ dựa trên vị trí gần nhất

#### Scenario: Người dùng sửa OCR hoặc người nói
- **WHEN** người dùng sửa text, loại bubble hoặc speaker
- **THEN** hệ thống PHẢI giữ bản raw, bản AI và bản người dùng duyệt
- **AND** revision PHẢI ghi nguồn `user_edited`

### Requirement: Nhân vật được phát hiện và nhóm bằng nhiều bằng chứng
Hệ thống PHẢI (MUST) phát hiện nhân vật lặp lại qua trang/panel, kết hợp đặc điểm hình ảnh với tên, bí danh và lời thoại trong text, đồng thời không khẳng định danh tính khi bằng chứng không đủ.

#### Scenario: Nhân vật xuất hiện nhiều lần
- **WHEN** nhiều panel có visual identity tương đồng
- **THEN** hệ thống PHẢI tạo character candidate với khuôn mặt, tóc, vóc dáng, trang phục, đạo cụ, biểu cảm, vai trò, alias, evidence IDs và confidence

#### Scenario: Hai nhân vật giống nhau
- **WHEN** hình ảnh tương đồng nhưng text, trang phục, quan hệ hoặc ngữ cảnh mâu thuẫn
- **THEN** hệ thống PHẢI giữ các cluster riêng hoặc đánh dấu `possible_duplicate`
- **AND** KHÔNG ĐƯỢC tự gộp thành một nhân vật đã xác nhận

#### Scenario: Gộp hoặc tách nhân vật khi review
- **WHEN** người dùng gộp hai candidate hoặc tách một cluster
- **THEN** hệ thống PHẢI cập nhật liên kết panel, lời thoại, evidence và confidence liên quan
- **AND** PHẢI tạo revision phân tích mới

### Requirement: AI phân tích bối cảnh, quan hệ, cốt truyện và canon candidate
Hệ thống PHẢI (MUST) tạo kết quả có cấu trúc cho tóm tắt chương, diễn biến, địa điểm, quan hệ, trạng thái nhân vật, plot beat và canon candidate từ text và hình ảnh đã quan sát.

#### Scenario: Tạo cấu trúc cốt truyện
- **WHEN** coverage nguồn đủ để phân tích nội dung
- **THEN** package PHẢI có synopsis, mở đầu, xung đột, key beats, cao trào, kết thúc, unresolved threads và character state cuối chương

#### Scenario: Phát hiện bối cảnh và quy tắc thế giới
- **WHEN** text hoặc ảnh cung cấp bằng chứng về địa điểm, thời gian, tổ chức, năng lực hoặc quy tắc thế giới
- **THEN** hệ thống PHẢI tạo location/world/canon candidates có evidence và confidence
- **AND** KHÔNG ĐƯỢC tự kích hoạt chúng thành canon Series

#### Scenario: Đề xuất hướng phát triển
- **WHEN** người dùng chọn mục tiêu phát triển thêm kịch bản
- **THEN** hệ thống CÓ THỂ tạo các `development_options` dựa trên unresolved threads và canon đã quan sát
- **AND** các đề xuất này chỉ là nháp; Master Story và đúng ba candidate PHẢI được tạo trong Story Studio sau handoff

### Requirement: Mọi kết luận AI quan trọng phải có evidence và confidence
Hệ thống PHẢI (MUST) liên kết nhận định AI với text chunk, page, asset, tile, panel, OCR hoặc bubble đã tạo ra nhận định đó.

#### Scenario: Chuẩn confidence có version
- **WHEN** OCR, vision, speaker, character matching, reading order hoặc canon analysis trả confidence
- **THEN** confidence PHẢI là số trong khoảng `[0,1]` hoặc `null`
- **AND** kết quả PHẢI lưu method/model version, threshold config version và mapping nhãn thấp/vừa/cao đã dùng

#### Scenario: Nhận định có đủ bằng chứng
- **WHEN** AI xác định tên, đặc điểm, quan hệ, sự kiện, bối cảnh hoặc canon fact
- **THEN** kết quả PHẢI chứa `evidence_ids`, confidence và modality nguồn

#### Scenario: Bằng chứng mâu thuẫn hoặc thiếu
- **WHEN** các evidence mâu thuẫn hoặc không đủ xác nhận
- **THEN** hệ thống PHẢI đưa kết quả vào `uncertainties` hoặc dùng giá trị `unknown`
- **AND** KHÔNG ĐƯỢC trình bày suy đoán như sự thật đã xác nhận

#### Scenario: Người dùng mở evidence
- **WHEN** người dùng chọn một nhận định trong UI
- **THEN** hệ thống PHẢI mở đúng đoạn text, trang, panel, bubble hoặc vùng ảnh liên quan
- **AND** PHẢI hiển thị confidence và limitation bằng tiếng Việt

### Requirement: Nội dung website chỉ là dữ liệu nguồn, không phải chỉ dẫn điều khiển AI
Hệ thống PHẢI (MUST) bao bọc văn bản đã trích/làm sạch từ HTML, OCR và metadata trong cấu trúc dữ liệu không tin cậy và áp dụng prompt contract chống prompt injection.

#### Scenario: Text nguồn yêu cầu thay đổi nhiệm vụ
- **WHEN** nguồn chứa câu như `bỏ qua quy tắc`, `đọc file hệ thống` hoặc `gọi công cụ`
- **THEN** AI PHẢI phân tích câu đó như nội dung truyện hoặc dữ liệu nghi vấn
- **AND** KHÔNG ĐƯỢC thực thi câu đó như instruction

#### Scenario: AI chỉ được truy cập attachment đã chọn
- **WHEN** một batch phân tích chạy
- **THEN** model chỉ PHẢI nhận source package, attachment manifest và ảnh/tile thuộc batch
- **AND** KHÔNG ĐƯỢC tự duyệt URL, đọc file tùy ý hoặc truy cập credential

### Requirement: Người dùng phải review và duyệt một revision phân tích cụ thể
Hệ thống PHẢI (MUST) cung cấp UI review tiếng Việt trước khi kết quả đủ điều kiện handoff sang Series.

#### Scenario: Hiển thị kết quả review
- **WHEN** package có kết quả toàn bộ hoặc một phần
- **THEN** UI PHẢI có các tab `Nội dung truyện`, `Trang và panel`, `Lời thoại`, `Nhân vật`, `Bối cảnh`, `Cốt truyện`, `Canon`, `Ảnh nguồn` và `Cảnh báo`

#### Scenario: Chỉnh kết quả trước khi duyệt
- **WHEN** người dùng review
- **THEN** họ PHẢI có thể loại text/ảnh sai, sửa OCR, sửa speaker, đổi reading order, gộp/tách nhân vật, sửa tên/đặc điểm, chọn ảnh tham chiếu và chỉnh canon candidate

#### Scenario: Duyệt kết quả partial
- **WHEN** package còn limitation hoặc coverage dưới ngưỡng
- **THEN** UI PHẢI hiển thị cảnh báo và yêu cầu xác nhận rõ ràng
- **AND** approval PHẢI ghi các limitation mà người dùng đã chấp nhận

#### Scenario: Sửa sau khi đã duyệt
- **WHEN** text, panel order, OCR, nhân vật, canon candidate hoặc asset selection của revision đã duyệt thay đổi
- **THEN** hệ thống PHẢI tạo revision mới hoặc hủy approval hiện tại
- **AND** revision cũ vẫn PHẢI còn truy xuất được

### Requirement: Approval phải đóng băng manifest nội dung được chấp nhận
Hệ thống PHẢI (MUST) lưu một approval manifest bất biến cho revision được duyệt, phân loại mọi item liên quan thành `accepted`, `excluded` hoặc `unreviewed`.

#### Scenario: Duyệt analysis revision
- **WHEN** người dùng xác nhận kết quả phân tích
- **THEN** manifest PHẢI lưu hash/revision của text chunk, page, panel, OCR, dialogue, character, location, plot, canon và asset được accepted, danh sách excluded và limitation đã chấp nhận
- **AND** PHẢI lưu approval manifest hash cùng analysis revision

#### Scenario: Item chưa review
- **WHEN** một item còn trạng thái `unreviewed`
- **THEN** item đó KHÔNG ĐƯỢC handoff hoặc được context compiler dùng như nguồn approved

#### Scenario: Selection thay đổi sau approval
- **WHEN** người dùng đổi accepted/excluded item hoặc sửa nội dung nằm trong manifest
- **THEN** hệ thống PHẢI tạo analysis revision/manifest mới và vô hiệu approval cũ

### Requirement: Workflow AI dùng planning pool và manifest attachment riêng
Hệ thống PHẢI (MUST) chạy mọi OCR/vision/synthesis call qua planning concurrency chung với workflow type riêng `comic_series_analysis` và không dùng work key Video Inspiration.

#### Scenario: Nhiều batch ảnh
- **WHEN** job cần nhiều call AI
- **THEN** mỗi call PHẢI ghi job ID, step, batch ID, attachment manifest hash, schema version và trạng thái vào observability an toàn
- **AND** KHÔNG ĐƯỢC log full source, full prompt hoặc binary ảnh

#### Scenario: Planning pool bận hoặc call bị hủy
- **WHEN** job chưa có slot hoặc người dùng hủy trong lúc chờ
- **THEN** job PHẢI giữ checkpoint/waiting state riêng và không chiếm work key Video Inspiration
- **AND** retry PHẢI tiếp tục đúng batch chưa hoàn tất

### Requirement: Phân tích truyện tranh không gọi pipeline tạo media hoặc AI Video
Hệ thống PHẢI (MUST) hoàn thành capability phân tích mà không tạo ảnh mới, video, audio, transcript video, shot timeline, clip hoặc AI Video project.

#### Scenario: Chạy phân tích truyện tranh
- **WHEN** người dùng bắt đầu hoặc retry phân tích
- **THEN** hệ thống KHÔNG ĐƯỢC gọi image-generation provider, Veo, STT video, render video hoặc auto-run AI Video

#### Scenario: Hoàn tất review
- **WHEN** người dùng duyệt ComicAnalysisPackage
- **THEN** hành động tiếp theo chỉ PHẢI là lưu kết quả hoặc chuẩn bị handoff sang Series/Story Studio
- **AND** KHÔNG ĐƯỢC hiển thị hành động handoff trực tiếp sang AI Video
