# Capability: Tạo truyện từ Gói nguồn

## ADDED Requirements

### Requirement: Story Studio MUST compile candidate source from canonical Source Package

Khi Story Studio tạo candidate cho một Story Episode, hệ thống MUST compile nguồn từ Gói nguồn chuẩn đã tạo từ source document hiện hành, thay vì chỉ dùng một payload nguồn rời do Story Studio tự dựng.

#### Scenario: Candidate generation dùng Gói nguồn chuẩn

- **GIVEN** một Story Episode có source document hiện hành
- **AND** source document đó đã được duyệt
- **WHEN** Story Studio tạo 3 candidate
- **THEN** candidate generation phải dựa trên Gói nguồn chuẩn
- **AND** Gói nguồn đó có `schema_version`
- **AND** có `source_kind`
- **AND** có `source_revision`
- **AND** có `fingerprint`

### Requirement: Candidate structured source MUST expose package metadata

Khi Story Studio nhét structured source vào candidate brief, hệ thống MUST bao gồm metadata chính của Gói nguồn để downstream biết candidate đó bám vào nguồn nào.

#### Scenario: Structured source có package metadata

- **GIVEN** Story Studio đang tạo candidate
- **WHEN** structured source được đưa vào creative brief
- **THEN** structured source phải bao gồm `source_document_id`
- **AND** `source_revision`
- **AND** `schema_version`
- **AND** `source_kind`
- **AND** `fingerprint`
- **AND** `coverage_metrics` nếu có
- **AND** `limitations` nếu có

### Requirement: Candidate dependency fingerprint MUST follow the Source Package fingerprint

Mỗi StoryScenarioCandidate MUST lưu fingerprint của Gói nguồn chuẩn trong trường dependency fingerprint hiện có, để candidate sau này có thể bị stale đúng theo nguồn đã dùng.

#### Scenario: Candidate fingerprint bám vào Gói nguồn

- **GIVEN** Story Studio tạo một candidate
- **WHEN** candidate được lưu
- **THEN** `dependency_fingerprint` phải bằng fingerprint của Gói nguồn chuẩn
- **AND** `source_document_revision` vẫn phản ánh revision nguồn hiện hành

### Requirement: Story Studio output behavior remains stable

Việc chuyển sang Gói nguồn chuẩn MUST không làm thay đổi số lượng candidate, quy trình chọn master hoặc quy trình tổng hợp master.

#### Scenario: Story candidate pipeline vẫn giữ hành vi hiện có

- **GIVEN** một Story Episode hợp lệ
- **WHEN** Story Studio tạo candidate
- **THEN** hệ thống vẫn tạo đúng 3 candidate
- **AND** các candidate vẫn thuộc ba chiến lược bắt buộc
- **AND** hệ thống vẫn cho phép chọn hoặc synthesize master như cũ
- **AND** output trả về cho UI vẫn tương thích với luồng hiện tại

### Requirement: UI language MUST remain separate from generated content language

Hệ thống MUST giữ giao diện người dùng bằng tiếng Việt, đồng thời cho phép ngôn ngữ nội dung truyện/video được chọn riêng qua cấu hình nội dung như `target_language` hoặc `language_profile`.

#### Scenario: UI tiếng Việt nhưng nội dung có thể là ngôn ngữ khác

- **GIVEN** người dùng đang dùng giao diện Story Studio hoặc Video Inspiration
- **AND** giao diện hiển thị label, hint, trạng thái và lỗi bằng tiếng Việt
- **WHEN** người dùng chọn `target_language` là một ngôn ngữ khác tiếng Việt
- **THEN** hệ thống không được đổi label giao diện sang ngôn ngữ đó
- **AND** các prompt tạo nội dung phải yêu cầu title, hook, story/script, narration, thoại, phụ đề và CTA dùng đúng `target_language`
- **AND** các field giải thích cho UI như `reason_vi`, `review_vi` hoặc `*_vi` vẫn phải viết tiếng Việt

### Requirement: Content language selection MUST not be hard-locked to Vietnamese and English

Các luồng tạo truyện/video liên quan MUST cho phép chọn ngôn ngữ nội dung ngoài `vi` và `en` khi ngôn ngữ đó nằm trong danh sách hệ thống hỗ trợ.

#### Scenario: Chọn ngôn ngữ nội dung mở rộng

- **GIVEN** người dùng chọn một ngôn ngữ nội dung hợp lệ như `ja`, `ko`, `zh`, `fr`, `de`, `es`, `pt`, `ru` hoặc `it`
- **WHEN** Story Studio, Comic handoff, AI Video hoặc Video Inspiration lưu cấu hình tạo nội dung
- **THEN** `target_language` phải giữ nguyên mã ngôn ngữ đã chọn
- **AND** hệ thống không được tự ép về `vi` hoặc `en`
- **AND** tên ngôn ngữ trong dropdown UI phải hiển thị bằng tiếng Việt để người dùng đọc được
