## ADDED Requirements

### Requirement: Series là tuỳ chọn cho AI Video projects
Hệ thống SHALL cho phép AI Video project có hoặc không có series. Project không thuộc series MUST tiếp tục hoạt động như luồng project lẻ hiện tại, không bắt buộc chọn series và không thay đổi dữ liệu bắt buộc khi tạo project.

#### Scenario: Tạo project lẻ không chọn series
- **WHEN** người dùng tạo AI Video project mà không chọn series
- **THEN** hệ thống SHALL tạo project với `series_id` rỗng hoặc tương đương và các bước story, shots, prompt, voice, subtitle, package SHALL hoạt động như trước

#### Scenario: Tạo project trong series
- **WHEN** người dùng tạo tập mới trong một series
- **THEN** hệ thống SHALL tạo AI Video project có liên kết tới series và lưu metadata tập như episode number, episode title hoặc topic hiện tại

### Requirement: Series Bible lưu continuity dài hạn
Hệ thống SHALL lưu Series Bible gồm thông tin nhân vật, bối cảnh, style, continuity rules, negative rules và summary các tập trước để dùng lại giữa các tập.

#### Scenario: Tạo series mới
- **WHEN** người dùng tạo series mới cho AI Video
- **THEN** hệ thống SHALL lưu title series và các trường bible/summary ban đầu, cho phép bỏ trống các trường chưa có nội dung

#### Scenario: Cập nhật Series Bible
- **WHEN** người dùng chỉnh nhân vật, bối cảnh, style hoặc rules của series
- **THEN** hệ thống SHALL lưu phiên bản mới và các tập tạo sau đó SHALL dùng nội dung mới trong planning context

### Requirement: Episode planning kế thừa Series Bible
Hệ thống SHALL đưa Series Bible vào các bước Codex planning của project thuộc series để giữ cùng nhân vật, bối cảnh và style qua nhiều tập.

#### Scenario: Generate story cho tập trong series
- **WHEN** project thuộc series gọi bước develop story bằng Codex
- **THEN** prompt planning SHALL bao gồm character bible, world bible, style bible, continuity rules, negative rules và previous episode summary của series

#### Scenario: Generate shots và prompt pack cho tập trong series
- **WHEN** project thuộc series gọi generate shots hoặc generate video prompt pack
- **THEN** prompt planning SHALL nhắc rõ những thuộc tính nhân vật/bối cảnh/style không được thay đổi và SHALL preserve episode order trong series

#### Scenario: Project lẻ không bị inject Series Bible
- **WHEN** project không thuộc series gọi planning
- **THEN** hệ thống MUST NOT inject Series Bible rỗng hoặc giả vào prompt Codex

### Requirement: Recent projects hỗ trợ nhóm theo series
Giao diện SHALL hiển thị project gần đây theo nhóm series khi project có series, đồng thời vẫn hiển thị project lẻ trong nhóm riêng hoặc dạng phẳng dễ hiểu.

#### Scenario: Recent list có series và project lẻ
- **WHEN** danh sách project gần đây gồm cả episode projects và standalone projects
- **THEN** UI SHALL hiển thị episode projects dưới series tương ứng và SHALL vẫn cho chọn project lẻ trực tiếp

#### Scenario: Chọn một tập trong series
- **WHEN** người dùng chọn một episode project trong nhóm series
- **THEN** UI SHALL mở đúng project đó và giữ context series hiển thị rõ ràng để người dùng biết đang làm tập nào

### Requirement: Tạo tập mới từ series giữ continuity
Hệ thống SHALL hỗ trợ tạo episode project mới từ một series đã có và tự điền context continuity phù hợp cho tập mới.

#### Scenario: Tạo tập tiếp theo
- **WHEN** người dùng bấm tạo tập mới trong series
- **THEN** hệ thống SHALL đề xuất episode number tiếp theo và tạo project mới kế thừa series id, series bible, target language, visual style hoặc cấu hình prompt nếu người dùng chọn reuse

#### Scenario: Tạo tập mới không làm thay đổi tập cũ
- **WHEN** người dùng tạo hoặc generate tập mới trong series
- **THEN** hệ thống MUST NOT sửa story, shots, prompts hoặc artifacts của các tập cũ trừ khi người dùng thao tác rõ ràng trên tập đó

### Requirement: Series summary cập nhật có kiểm soát
Hệ thống SHALL có cách lưu hoặc cập nhật summary các tập đã hoàn thành để tập sau biết trạng thái câu chuyện hiện tại.

#### Scenario: Hoàn tất một tập trong series
- **WHEN** một episode project hoàn tất story hoặc prompt review
- **THEN** hệ thống SHALL cho phép cập nhật previous episode summary hoặc latest series summary bằng dữ liệu đã validate, không ghi summary từ output Codex chưa hợp lệ

#### Scenario: Summary quá dài
- **WHEN** previous episode summary vượt giới hạn prompt an toàn
- **THEN** hệ thống SHALL truncate hoặc summarize theo cách có log rõ ràng và MUST NOT làm mất character/world/style bible cốt lõi
