## ADDED Requirements

### Requirement: Popup tạo và chọn series phải hiển thị thông tin rõ ràng
Hệ thống SHALL cung cấp popup tạo/chọn series bằng tiếng Việt cho các luồng cần chọn series, thay vì chỉ dựa vào select inline khi người dùng cần xem nhiều thông tin trước khi quyết định.

#### Scenario: Mở popup chọn series trong AI Video
- **WHEN** người dùng cần chọn series để tạo tập AI Video trực tiếp
- **THEN** UI SHALL mở popup chọn series
- **AND** popup SHALL hiển thị danh sách series dạng card có tên, loại series, số tập, số tập video, số tập truyện, số hồ sơ nhân vật, trạng thái provider binding nếu có và ngày cập nhật
- **AND** popup SHALL ưu tiên hoặc chỉ cho chọn series `video_story_only` theo quy tắc tạo AI Video trực tiếp hiện có

#### Scenario: Series không phù hợp với ngữ cảnh
- **WHEN** một series không được phép dùng trong ngữ cảnh hiện tại
- **THEN** UI SHALL không cho chọn series đó hoặc hiển thị series đó ở trạng thái disabled
- **AND** UI SHALL giải thích bằng tiếng Việt vì sao series không phù hợp

#### Scenario: Xem chi tiết series trước khi chọn
- **WHEN** người dùng xem một series trong popup
- **THEN** UI SHALL hiển thị preview rút gọn của nhân vật cố định, bối cảnh/world, style hình ảnh, quy tắc nhất quán, điều cần tránh và tóm tắt tập trước nếu có
- **AND** UI SHALL hiển thị số lượng `character_profiles` để người dùng biết series đã có dàn nhân vật hay chưa

#### Scenario: Tìm kiếm và lọc series
- **WHEN** danh sách series có nhiều mục
- **THEN** popup SHALL cho tìm kiếm theo tên series
- **AND** popup SHALL cho lọc theo loại series nếu ngữ cảnh cho phép xem nhiều loại

### Requirement: Popup tạo series mới phải giải thích mode và preview trước khi lưu
Hệ thống SHALL cung cấp popup tạo series mới bằng tiếng Việt, có cấu trúc rõ ràng cho tên series, loại series và các trường Series Bible chính.

#### Scenario: Tạo series mới từ AI Video
- **WHEN** người dùng bấm tạo series mới trong AI Video
- **THEN** UI SHALL mở popup tạo series mới
- **AND** popup SHALL cho nhập tên series, chọn `series_mode`, nhân vật cố định, bối cảnh/world, style hình ảnh, quy tắc nhất quán, điều cần tránh và tóm tắt tập trước
- **AND** popup SHALL giải thích tác động của từng `series_mode` bằng tiếng Việt

#### Scenario: Preview trước khi lưu series
- **WHEN** người dùng đã nhập thông tin series mới
- **THEN** popup SHALL hiển thị preview tóm tắt series sẽ được tạo
- **AND** preview SHALL chỉ rõ series này dùng được trong AI Video, Story Studio hoặc cả hai tùy `series_mode`

#### Scenario: Sau khi tạo series thành công
- **WHEN** hệ thống tạo series mới thành công
- **THEN** UI SHALL chọn series vừa tạo trong ngữ cảnh hiện tại
- **AND** UI SHALL cung cấp hành động tiếp theo phù hợp như mở quản lý nhân vật hoặc tạo tập mới

### Requirement: Luồng AI Video cơ bản không series phải giữ nguyên
Hệ thống MUST NOT bắt buộc project không có `series_id` đi qua luồng dàn nhân vật series, popup duyệt nhân vật mới hoặc canon gate của series.

#### Scenario: Tạo AI Video cơ bản
- **WHEN** người dùng tạo AI Video project không chọn series
- **THEN** hệ thống SHALL tiếp tục dùng workflow hiện có
- **AND** hệ thống MUST NOT yêu cầu `episode_cast`, `SeriesCharacterProfile` hoặc duyệt nhân vật mới

#### Scenario: Auto-run video cơ bản
- **WHEN** auto-run chạy trên project không có `series_id`
- **THEN** auto-run SHALL giữ các review gate hiện có
- **AND** auto-run MUST NOT dừng ở `review_stage = "character_proposals"`

### Requirement: AI Video series phải tạo episode cast từ hồ sơ nhân vật
Hệ thống SHALL tạo một `episode_cast` cho mỗi AI Video project thuộc series bằng cách đọc `SeriesCharacterProfile`, Series Bible và Series Memory.

#### Scenario: Series có hồ sơ nhân vật
- **WHEN** AI Video phát triển story cho project có `series_id` và series có `SeriesCharacterProfile`
- **THEN** AI SHALL chọn nhân vật phù hợp cho tập hiện tại thành `episode_cast`
- **AND** mỗi nhân vật trong cast SHALL có vai trò trong tập, mức độ quan trọng và lý do chọn bằng tiếng Việt

#### Scenario: Series chưa có hồ sơ nhân vật
- **WHEN** AI Video series chưa có `SeriesCharacterProfile` nhưng có `character_bible`
- **THEN** AI MAY dùng `character_bible` làm fallback để phát triển story
- **AND** hệ thống SHOULD gợi ý người dùng chuyển nhân vật quan trọng thành hồ sơ có cấu trúc
- **AND** hệ thống MUST NOT tự tạo `SeriesCharacterProfile` nếu chưa được người dùng duyệt

### Requirement: Scene, shot và prompt video series phải biết nhân vật nào xuất hiện
Hệ thống SHALL lưu hoặc trả metadata đủ rõ để scene, shot và prompt video biết nhân vật nào xuất hiện trong từng đoạn.

#### Scenario: Chia scene cho series nhiều nhân vật
- **WHEN** hệ thống chia story series thành scene
- **THEN** mỗi scene SHOULD có danh sách nhân vật liên quan và mục đích tương tác của họ trong scene

#### Scenario: Chia shot cho series nhiều nhân vật
- **WHEN** hệ thống chia scene thành shot
- **THEN** mỗi shot SHALL xác định nhân vật nhìn thấy, vị trí tương đối, hành động và biểu cảm chính nếu có nhân vật foreground

#### Scenario: Tạo prompt từ shot nhiều nhân vật
- **WHEN** hệ thống tạo prompt video cho shot có nhiều nhân vật
- **THEN** prompt SHALL mô tả từng nhân vật riêng biệt
- **AND** prompt SHALL tránh mô tả mơ hồ khiến video model đổi mặt, đổi tóc, đổi trang phục hoặc nhân bản nhân vật

### Requirement: AI được đề xuất nhân vật mới nhưng không được tự ghi canon
Hệ thống SHALL cho phép AI đề xuất nhân vật mới khi story cần, nhưng MUST NOT ghi nhân vật mới vào `SeriesCharacterProfile` hoặc Series Memory canon nếu chưa có quyết định duyệt rõ của người dùng.

#### Scenario: AI đề xuất nhân vật mới ảnh hưởng canon
- **WHEN** AI tạo nhân vật mới có tên, foreground, thoại, vai trò plot, quan hệ canon hoặc khả năng tái xuất
- **THEN** hệ thống SHALL lưu proposal ở trạng thái chờ duyệt
- **AND** hệ thống SHALL dừng auto-run ở `status = "needs_review"` với `review_stage = "character_proposals"`
- **AND** hệ thống MUST NOT dùng proposal đó như canon approved cho artifact downstream

#### Scenario: AI chỉ thêm người nền vô danh
- **WHEN** AI chỉ mô tả người nền vô danh, đám đông, silhouette hoặc extra không có thoại và không ảnh hưởng canon
- **THEN** hệ thống MAY tiếp tục auto-run mà không dừng duyệt nhân vật
- **AND** prompt SHALL ghi rõ đây là background extras không phải nhân vật canon

### Requirement: Người dùng phải có ba quyết định cho nhân vật mới
Hệ thống SHALL cho phép người dùng quyết định từng proposal nhân vật mới bằng ba hành động: thêm vào Series, chỉ dùng trong tập này hoặc từ chối.

#### Scenario: Thêm nhân vật mới vào Series
- **WHEN** người dùng chọn thêm proposal vào Series
- **THEN** hệ thống SHALL tạo `SeriesCharacterProfile` từ proposal đã duyệt
- **AND** hệ thống SHALL cập nhật revision/memory/dependency liên quan
- **AND** auto-run SHALL resume bằng context series mới nhất

#### Scenario: Chỉ dùng nhân vật trong tập này
- **WHEN** người dùng chọn chỉ dùng proposal trong tập hiện tại
- **THEN** hệ thống SHALL lưu nhân vật như episode-only guest
- **AND** hệ thống MUST NOT ghi nhân vật đó vào `SeriesCharacterProfile` hoặc Series Memory canon
- **AND** auto-run SHALL tiếp tục với phạm vi sử dụng giới hạn trong project/tập hiện tại

#### Scenario: Từ chối nhân vật mới
- **WHEN** người dùng từ chối proposal
- **THEN** hệ thống SHALL đánh dấu proposal là rejected
- **AND** hệ thống SHALL regenerate story, shot hoặc prompt bị ảnh hưởng từ checkpoint an toàn
- **AND** artifact mới MUST NOT tiếp tục phụ thuộc vào nhân vật đã bị từ chối

### Requirement: Auto-run series phải resume từ checkpoint sau khi duyệt nhân vật
Hệ thống SHALL lưu `resume_step` và artifact bị ảnh hưởng khi dừng ở gate nhân vật mới, để tiếp tục auto-run từ điểm phù hợp sau khi người dùng quyết định.

#### Scenario: Resume sau khi duyệt xong proposal
- **WHEN** mọi proposal bắt buộc trong `review_stage = "character_proposals"` đã có quyết định
- **THEN** auto-run SHALL chuyển khỏi `needs_review`
- **AND** auto-run SHALL chạy tiếp từ `resume_step`
- **AND** auto-run SHALL đọc lại dữ liệu project/series mới nhất trước khi tạo artifact tiếp theo

#### Scenario: Full-auto gặp nhân vật canon mới
- **WHEN** auto-run ở mode full-auto tạo proposal nhân vật mới ảnh hưởng canon
- **THEN** auto-run MUST dừng ở `review_stage = "character_proposals"`
- **AND** full-auto MUST NOT tự approve hoặc tự ghi nhân vật đó vào series canon

### Requirement: Prompt video series phải là phim hoạt hình 3D nhiều nhân vật
Hệ thống SHALL tạo prompt video cho AI Video series theo hướng phim hoạt hình 3D/stylized 3D/cinematic 3D animation và hỗ trợ nhiều nhân vật trong cùng một shot.

#### Scenario: Prompt có nhiều nhân vật đã duyệt
- **WHEN** một shot có từ hai nhân vật foreground trở lên
- **THEN** prompt SHALL mô tả từng nhân vật với identity lock, vị trí, hành động, biểu cảm và tương tác
- **AND** prompt SHALL giữ đúng fixed traits từ `SeriesCharacterProfile` hoặc episode-only guest đã duyệt

#### Scenario: Negative prompt cho nhiều nhân vật
- **WHEN** hệ thống tạo negative prompt cho shot series
- **THEN** negative prompt SHALL chặn duplicate character, identity swap, unintended named character, wrong face, wrong hairstyle, wrong signature outfit và extra foreground character ngoài cast

#### Scenario: Không dùng rule một nhân vật chính duy nhất
- **WHEN** project thuộc series và có episode cast nhiều nhân vật
- **THEN** hệ thống MUST NOT yêu cầu prompt giữ "same main character only"
- **AND** prompt SHALL yêu cầu dùng đúng approved episode cast và episode-only guests của tập hiện tại

### Requirement: UI review nhân vật mới phải rõ ràng bằng tiếng Việt
Hệ thống SHALL hiển thị proposal nhân vật mới trong UI bằng card review rõ ràng, cho phép người dùng hiểu tác động trước khi quyết định.

#### Scenario: Hiển thị card proposal
- **WHEN** auto-run dừng ở `review_stage = "character_proposals"`
- **THEN** UI SHALL hiển thị danh sách proposal cần duyệt
- **AND** mỗi card SHALL có tên, vai trò, lý do AI đề xuất, mức ảnh hưởng canon, khả năng tái xuất, mô tả ngoại hình, tính cách/cách nói và artifact bị ảnh hưởng

#### Scenario: Tiếp tục sau khi xử lý proposal
- **WHEN** người dùng đã quyết định xong mọi proposal bắt buộc
- **THEN** UI SHALL cho phép tiếp tục auto-run
- **AND** UI SHALL hiển thị bằng tiếng Việt auto-run sẽ chạy tiếp từ bước nào
