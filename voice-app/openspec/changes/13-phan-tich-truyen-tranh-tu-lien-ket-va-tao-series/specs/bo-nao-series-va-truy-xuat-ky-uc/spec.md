## ADDED Requirements

### Requirement: Nội dung đầy đủ của chương phải ở Episode Source, không phải Series Memory
Hệ thống PHẢI (MUST) giữ full text, OCR, page/panel sequence, dialogue, narration và evidence trong Story Episode Source; Series Memory chỉ giữ kiến thức dài hạn đã được chọn và duyệt.

#### Scenario: Handoff một chương dài
- **WHEN** Comic handoff tạo Source Document có nhiều trang, panel và text
- **THEN** hệ thống KHÔNG ĐƯỢC sao chép toàn bộ document vào Series Memory hoặc `series-memory.md`
- **AND** memory chỉ PHẢI chứa index/summary và liên kết tới Episode Source khi cần

#### Scenario: Đề xuất sự kiện và trạng thái dài hạn
- **WHEN** analysis phát hiện quan hệ, sự kiện, canon hoặc trạng thái cuối chương có thể cần cho tập sau
- **THEN** hệ thống PHẢI tạo memory/current-state proposals có evidence
- **AND** chỉ item được duyệt theo policy Series mới được compiler dùng như ký ức chuẩn

#### Scenario: Xóa hoặc ẩn một memory proposal
- **WHEN** người dùng bỏ một đề xuất memory nhưng giữ Episode Source
- **THEN** full source PHẢI vẫn còn trong Story Episode
- **AND** compiler KHÔNG ĐƯỢC coi đề xuất đã bỏ là Series Memory approved

### Requirement: Context compiler truy xuất Comic Source theo nhiệm vụ và giữ provenance
Hệ thống PHẢI (MUST) truy xuất source chunks liên quan đến nhiệm vụ thay vì luôn nhét toàn bộ chương vào mọi prompt.

#### Scenario: Tạo candidate hoặc Master Story
- **WHEN** compiler chuẩn bị context cho ba candidate hoặc Master Story
- **THEN** context PHẢI ưu tiên synopsis, plot beats, nhân vật, canon và source chunks liên quan tới hướng phát triển
- **AND** mỗi chunk PHẢI giữ source document revision và evidence IDs

#### Scenario: Tạo prompt panel hoặc kiểm tra continuity
- **WHEN** nhiệm vụ cần chi tiết hình ảnh, lời thoại hoặc một sự kiện cụ thể
- **THEN** compiler PHẢI có thể truy xuất panel, OCR, dialogue, visual description và character/location evidence tương ứng

#### Scenario: Vượt ngân sách ngữ cảnh
- **WHEN** các chunk liên quan vẫn vượt budget
- **THEN** compiler PHẢI phân bổ dung lượng theo nhóm, rút gọn có kiểm soát và báo phần bị bỏ
- **AND** KHÔNG ĐƯỢC âm thầm thay full source bằng một digest không truy vết được

#### Scenario: Xem dấu vết nguồn đã dùng
- **WHEN** người dùng mở context trace của candidate, Master Story hoặc prompt
- **THEN** UI/API PHẢI liệt kê Source Document revision, chunk, page, panel và evidence đã dùng
- **AND** PHẢI phân biệt dữ liệu Series Memory với dữ liệu Episode Source

### Requirement: Context compiler tôn trọng limitation và trạng thái duyệt của nguồn
Hệ thống PHẢI (MUST) chỉ dùng nội dung approved làm nguồn sáng tạo mặc định và phải truyền limitation có ảnh hưởng vào tác vụ AI.

#### Scenario: Chunk chỉ có raw hoặc AI text chưa duyệt
- **WHEN** một chunk chưa có approved text
- **THEN** compiler KHÔNG ĐƯỢC coi nó là nguồn chuẩn đã duyệt
- **AND** mặc định PHẢI loại chunk `unreviewed` khỏi context sáng tạo và handoff approved

#### Scenario: Vision hoặc OCR thiếu coverage
- **WHEN** Source Document ghi modality partial/unavailable
- **THEN** compiler PHẢI đưa limitation tương ứng vào context
- **AND** output AI KHÔNG ĐƯỢC mô tả phần thiếu như dữ kiện đã quan sát

### Requirement: Source revision tham gia context fingerprint và cache
Hệ thống PHẢI (MUST) đưa source document revision, development mode và các chunk revision đã chọn vào fingerprint của context.

#### Scenario: Cùng source revision và cùng nhiệm vụ
- **WHEN** dữ liệu, selection và budget không đổi
- **THEN** compiler CÓ THỂ tái sử dụng context snapshot/cache tương ứng

#### Scenario: Source revision hoặc development mode đổi
- **WHEN** một trong các dependency đó thay đổi
- **THEN** context fingerprint PHẢI đổi
- **AND** hệ thống KHÔNG ĐƯỢC tái sử dụng snapshot cũ như dữ liệu hiện hành
