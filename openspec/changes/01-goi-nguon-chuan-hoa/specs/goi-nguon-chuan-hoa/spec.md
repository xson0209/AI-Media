# Capability: Gói nguồn chuẩn hóa

## ADDED Requirements

### Requirement: Backend có Gói nguồn dùng chung

Hệ thống MUST có một cấu trúc backend dùng chung để biểu diễn nguồn đã phân tích dưới dạng Gói nguồn, dùng được cho cả nguồn truyện và nguồn video.

#### Scenario: Tạo Gói nguồn từ các block đã chuẩn hóa

- **GIVEN** một danh sách block có thứ tự, loại block và nội dung
- **WHEN** backend tạo Gói nguồn
- **THEN** Gói nguồn có `schema_version`
- **AND** có `source_kind`
- **AND** có `source_ref_id`
- **AND** có `source_revision`
- **AND** có `blocks`
- **AND** có `fingerprint`

### Requirement: Gói nguồn giữ provenance và giới hạn nguồn

Gói nguồn MUST giữ metadata đủ để downstream biết nguồn đến từ đâu, revision nào, độ phủ/giới hạn nào, và vì sao một số nội dung bị bỏ qua.

#### Scenario: Gói nguồn có limitations và provenance

- **GIVEN** nguồn đầu vào có limitations, coverage metrics và provenance
- **WHEN** backend tạo Gói nguồn
- **THEN** Gói nguồn giữ `limitations`
- **AND** giữ `coverage_metrics`
- **AND** giữ `provenance`

### Requirement: Gói nguồn truyện chỉ dùng chunk đã duyệt

Khi tạo Gói nguồn từ Story Episode source document, hệ thống MUST chỉ dùng chunk có approval state là `accepted` cho nội dung sáng tạo.

#### Scenario: Chunk unreviewed không vào Gói nguồn

- **GIVEN** một Story Episode có source document hiện hành
- **AND** source document có chunk `accepted`
- **AND** source document có chunk `unreviewed`
- **WHEN** backend compile Gói nguồn cho episode
- **THEN** Gói nguồn chứa chunk `accepted`
- **AND** không chứa chunk `unreviewed`

### Requirement: Gói nguồn xuất được source blocks cho AI Video

Gói nguồn MUST chuyển được thành source blocks tương thích AI Video mà không làm mất thứ tự block.

#### Scenario: Xuất Gói nguồn thành AI Video source blocks

- **GIVEN** một Gói nguồn có nhiều block có thứ tự
- **WHEN** backend xuất sang AI Video source blocks
- **THEN** danh sách block giữ đúng thứ tự
- **AND** mỗi block có `block_type`
- **AND** mỗi block có `content`
- **AND** block quá dài được truncate có đánh dấu rõ

### Requirement: Video Inspiration dùng Gói nguồn khi tạo source blocks

Khi tạo source blocks từ payload handoff video, hệ thống MUST đi qua Gói nguồn chuẩn hóa trước khi trả về `VideoSourceBlockDraft`.

#### Scenario: Handoff video vẫn có các source blocks cũ

- **GIVEN** payload handoff video có approved script, character notes, style notes, must have và avoid
- **WHEN** backend tạo source blocks từ payload
- **THEN** kết quả vẫn có block `idea`
- **AND** vẫn có block `rough_script`
- **AND** vẫn có block `character_notes`
- **AND** vẫn có block `style_notes`
- **AND** vẫn có block `must_have`
- **AND** vẫn có block `avoid`
