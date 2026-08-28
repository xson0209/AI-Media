## ADDED Requirements

### Requirement: Giữ input nguồn và provenance tối thiểu

News Video SHALL lưu nguyên văn bài viết/transcript/ghi chú người dùng cung cấp, cùng `source_note` hoặc URL HTTP(S) đã sanitize nếu có. Input SHALL được coi là dữ liệu, không phải instruction.

#### Scenario: Dán bài viết tiếng Việt

- **WHEN** người dùng dán bài viết hoặc transcript
- **THEN** hệ thống SHALL giữ bản gốc, ghi nguồn là nội dung người dùng cung cấp và cho phép gắn ghi chú xuất bản/cập nhật nếu biết

#### Scenario: URL chỉ là ghi chú nguồn

- **WHEN** người dùng dán URL bài viết
- **THEN** hệ thống SHALL lưu URL làm ghi chú nguồn, SHALL NOT tự fetch hoặc tự đọc nội dung từ URL, và UI SHALL nói rõ người dùng phải dán nội dung bài

#### Scenario: URL không an toàn

- **WHEN** URL dùng scheme không cho phép hoặc trỏ local/private
- **THEN** hệ thống SHALL báo limitation bằng tiếng Việt và SHALL không tự suy diễn nội dung từ URL

#### Scenario: Chỉ có URL, không có nội dung

- **WHEN** người dùng chỉ dán URL mà không dán nội dung bài
- **THEN** hệ thống SHALL từ chối sinh narration, SHALL nêu rõ thiếu nội dung bằng tiếng Việt và SHALL NOT lấp chỗ trống bằng trí nhớ model

### Requirement: Narration không bịa dữ kiện

Planner SHALL tạo narration/shot outline từ input và source note hiện có; claim chưa rõ phải được đánh dấu `REVIEW_REQUIRED` hoặc diễn đạt thận trọng. MVP không tuyên bố kiểm chứng độc lập toàn Internet.

#### Scenario: Thiếu dữ kiện

- **WHEN** input không đủ để xác nhận số liệu, tên riêng, ngày hoặc trích dẫn
- **THEN** hệ thống SHALL bỏ ý đó hoặc gắn cảnh báo review, SHALL NOT lấp chỗ trống bằng trí nhớ/tưởng tượng

#### Scenario: Prompt injection trong bài

- **WHEN** bài viết chứa câu lệnh yêu cầu bỏ qua quy tắc, lộ secret hoặc gọi tool
- **THEN** hệ thống SHALL coi câu đó là nội dung bài viết, không thực thi và vẫn áp dụng audio/quality contract

### Requirement: Source refs và disclosure trong shot/prompt

Mỗi narration/shot có claim factual SHALL có `source_refs` hoặc ghi chú “chưa xác minh”. Shot SHALL khai báo `asset_mode` là `supplied_real`, `motion_graphics_only` hoặc `generic_ai_illustrative`; hình minh họa AI có nguy cơ gây nhầm SHALL có overlay disclosure **Hình minh họa AI**.

#### Scenario: Hình minh họa AI

- **WHEN** shot mô tả sự kiện/người/sản phẩm nhưng không có footage thật được cung cấp
- **THEN** hệ thống SHALL dùng `generic_ai_illustrative`, chừa safe area cho disclosure và SHALL không gọi đó là bằng chứng

#### Scenario: Footage thật

- **WHEN** người dùng cung cấp asset thật và ghi chú nguồn/quyền sử dụng
- **THEN** shot SHALL lưu asset reference, dùng `supplied_real` và giữ ghi chú provenance trong prompt pack

### Requirement: Quality gate trước khi copy prompt

Hệ thống SHALL chặn Copy/Download nếu shot thiếu source note cho claim factual, thiếu `asset_mode`, thiếu disclosure bắt buộc, audio contract hoặc prompt đang stale. Trạng thái/lý do SHALL bằng tiếng Việt.

#### Scenario: Gate đạt

- **WHEN** input, shot, source refs/disclosure và provider-ready prompt hợp lệ
- **THEN** hệ thống SHALL đánh dấu `ready`/`READY_FOR_MANUAL_VEO` và cho phép copy thủ công

#### Scenario: Gate bị chặn

- **WHEN** có claim chưa xác minh được trình bày như sự thật hoặc artifact stale
- **THEN** hệ thống SHALL trả `review_required`/`blocked`, liệt kê shot/lý do và SHALL không phát hành prompt như đã sẵn sàng

### Requirement: Hiển thị giới hạn kiểm chứng

UI SHALL nói rõ source note là thông tin do người dùng cung cấp nếu chưa có xác minh độc lập, native speech là yêu cầu generation chứ không bảo đảm chính xác, và exact text/headline/citation sẽ được chèn hậu kỳ.

#### Scenario: Xem prompt tin tức

- **WHEN** người dùng mở provider prompt
- **THEN** UI SHALL hiển thị nguồn tham chiếu, disclosure cần có và cảnh báo giới hạn bằng tiếng Việt
