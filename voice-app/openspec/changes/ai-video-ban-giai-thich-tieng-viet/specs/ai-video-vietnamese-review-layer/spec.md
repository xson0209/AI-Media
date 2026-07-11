## ADDED Requirements

### Requirement: Lớp review tiếng Việt độc lập với ngôn ngữ video cuối
Hệ thống SHALL cung cấp bản tiếng Việt để người dùng đọc hiểu và duyệt nội dung AI Video phase 2, và bản review tiếng Việt đó MUST NOT tự động thay đổi ngôn ngữ video cuối.

#### Scenario: Project video tiếng Anh vẫn có bản review tiếng Việt
- **WHEN** người dùng làm AI Video project có `target_language = "en"`
- **THEN** hệ thống vẫn hiển thị bản tiếng Việt để người dùng hiểu story, segment và prompt video
- **AND** voice, narration sản xuất, phụ đề video cuối và metadata video vẫn dùng tiếng Anh theo `target_language`

#### Scenario: Project video tiếng Việt vẫn có bản review tiếng Việt
- **WHEN** người dùng làm AI Video project có `target_language = "vi"`
- **THEN** hệ thống hiển thị bản tiếng Việt để người dùng hiểu story, segment và prompt video
- **AND** hệ thống không tạo thêm bản tiếng Anh chỉ để người dùng duyệt, trừ khi prompt gốc cần tiếng Anh kỹ thuật cho công cụ tạo video

#### Scenario: Đổi ngôn ngữ video không đổi mục đích của bản review
- **WHEN** người dùng đổi `target_language` của project từ tiếng Anh sang tiếng Việt hoặc ngược lại
- **THEN** các artifact sản xuất phụ thuộc ngôn ngữ video được đánh stale theo logic hiện có
- **AND** bản review tiếng Việt vẫn được coi là lớp hỗ trợ người dùng, không phải nguồn sự thật cho voice hoặc subtitle video cuối

### Requirement: Story, continuity và kịch bản có bản tiếng Việt để duyệt
Hệ thống SHALL tạo và hiển thị bản tiếng Việt dễ đọc cho story strategy, continuity bible và detailed script trong AI Video phase 2.

#### Scenario: AI phát triển story cho video tiếng Anh
- **WHEN** AI phát triển story cho project có `target_language = "en"`
- **THEN** hệ thống tạo bản tiếng Việt cho story strategy, continuity bible và detailed script để người dùng Việt đọc duyệt
- **AND** hệ thống vẫn giữ bản sản xuất tiếng Anh cho nội dung người xem nghe hoặc đọc trong video cuối

#### Scenario: AI phát triển story cho video tiếng Việt
- **WHEN** AI phát triển story cho project có `target_language = "vi"`
- **THEN** hệ thống tạo bản tiếng Việt cho story strategy, continuity bible và detailed script
- **AND** bản sản xuất dùng cho video cuối cũng không được mâu thuẫn với tiếng Việt

#### Scenario: UI hiển thị rõ bản review và bản sản xuất
- **WHEN** người dùng mở phần `Story, continuity và kịch bản`
- **THEN** UI hiển thị bản tiếng Việt để duyệt bằng nhãn rõ ràng
- **AND** nếu có bản sản xuất khác ngôn ngữ, UI hiển thị bản đó như nội dung dùng cho video cuối, không lẫn với bản review

### Requirement: Prompt segment 10 giây có mô tả tiếng Việt đủ hiểu
Hệ thống SHALL cung cấp mô tả tiếng Việt cho từng prompt segment 10 giây để người dùng hiểu timeline, micro-scene, hành động, camera, chuyển cảnh và nội dung narration.

#### Scenario: Tạo segment breakdown cho video tiếng Anh
- **WHEN** AI tạo segment breakdown cho project có `target_language = "en"`
- **THEN** mỗi segment có mô tả tiếng Việt với timeline hoặc mốc thời gian trong segment
- **AND** mô tả tiếng Việt giải thích hành động chính, camera/chuyển cảnh và nội dung narration tiếng Anh theo cách người dùng Việt hiểu được

#### Scenario: Tạo segment breakdown cho video tiếng Việt
- **WHEN** AI tạo segment breakdown cho project có `target_language = "vi"`
- **THEN** mỗi segment có mô tả tiếng Việt với timeline hoặc mốc thời gian trong segment
- **AND** narration/video language tiếng Việt được thể hiện nhất quán với mô tả review tiếng Việt

#### Scenario: Segment không có narration riêng
- **WHEN** một segment không có narration riêng
- **THEN** UI vẫn hiển thị mô tả tiếng Việt giải thích phần hình ảnh, hành động và chuyển cảnh của segment đó

### Requirement: Prompt video có prompt gốc và bản giải thích tiếng Việt
Hệ thống SHALL lưu, trả về và hiển thị prompt video gốc để copy sang công cụ tạo video, đồng thời cung cấp bản giải thích tiếng Việt để người dùng hiểu prompt đó yêu cầu gì.

#### Scenario: Tạo prompt video bằng tiếng Anh kỹ thuật
- **WHEN** AI tạo prompt video bằng tiếng Anh kỹ thuật cho công cụ tạo video
- **THEN** hệ thống lưu prompt gốc để copy nguyên văn
- **AND** hệ thống lưu bản giải thích tiếng Việt mô tả nội dung hình ảnh, hành động, camera, ánh sáng, mood, continuity và yêu cầu ngôn ngữ người xem nếu có

#### Scenario: Xem prompt video trong UI
- **WHEN** người dùng mở phần `Prompt video`
- **THEN** UI hiển thị bản giải thích tiếng Việt để người dùng đọc hiểu
- **AND** UI vẫn cung cấp prompt gốc bằng nhãn rõ ràng để copy hoặc tải xuống

#### Scenario: Copy prompt video không kèm bản giải thích tiếng Việt
- **WHEN** người dùng bấm copy prompt để dùng trong công cụ tạo video bên ngoài
- **THEN** hệ thống copy prompt gốc dùng cho công cụ tạo video
- **AND** hệ thống không tự động trộn bản giải thích tiếng Việt vào prompt gốc, trừ khi người dùng chọn tải hoặc xem bản đầy đủ có chú thích

#### Scenario: Prompt video cũ chưa có bản giải thích tiếng Việt
- **WHEN** project có prompt video cũ chưa lưu bản giải thích tiếng Việt
- **THEN** UI không bị lỗi khi hiển thị prompt
- **AND** UI cho người dùng biết cần tạo lại prompt video để có bản giải thích tiếng Việt nếu cần

### Requirement: Export và package kèm bản tiếng Việt để làm việc bên ngoài
Hệ thống SHALL đưa bản review tiếng Việt vào download/package AI Video để người dùng có thể đọc hiểu khi rời khỏi Voicebox.

#### Scenario: Download prompt video từng segment
- **WHEN** người dùng tải prompt video của một segment
- **THEN** file tải xuống chứa prompt gốc dùng cho công cụ tạo video
- **AND** file chứa phần `Bản giải thích tiếng Việt` hoặc tương đương để người dùng đọc hiểu prompt đó

#### Scenario: Export package phase 2
- **WHEN** người dùng export AI Video package phase 2
- **THEN** package kèm bản tiếng Việt để duyệt cho story, continuity, segment list và prompt video
- **AND** manifest hoặc hướng dẫn package giải thích bản tiếng Việt là nội dung hỗ trợ người dùng, không phải phụ đề video cuối trừ khi video language là tiếng Việt

### Requirement: UI wording phân biệt bản review tiếng Việt với phụ đề video
Hệ thống SHALL dùng nhãn và thông báo tiếng Việt rõ ràng để phân biệt bản review trong app với phụ đề video cuối.

#### Scenario: UI không hardcode narration tiếng Anh
- **WHEN** người dùng xem phần voice, subtitle hoặc segment narration
- **THEN** UI không mô tả chung là `narration tiếng Anh` nếu project có thể là tiếng Việt
- **AND** UI dùng wording như `narration theo ngôn ngữ video` hoặc nhãn ngôn ngữ động tương đương

#### Scenario: UI không gọi bản review là phụ đề video
- **WHEN** người dùng xem bản tiếng Việt giải thích story, segment hoặc prompt video
- **THEN** UI không làm người dùng hiểu nhầm đây là file phụ đề `.srt` hoặc burn-in subtitle của video cuối
- **AND** UI dùng wording như `Bản tiếng Việt để duyệt`, `Bản giải thích tiếng Việt` hoặc tương đương

#### Scenario: Trạng thái và lỗi vẫn bằng tiếng Việt
- **WHEN** hệ thống hiển thị trạng thái, lỗi, helper text hoặc notice trong AI Video workflow
- **THEN** các nội dung UI đó được viết bằng tiếng Việt tự nhiên và không phụ thuộc vào `target_language` của video cuối
