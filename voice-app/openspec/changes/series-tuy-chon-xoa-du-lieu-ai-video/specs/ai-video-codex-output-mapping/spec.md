## ADDED Requirements

### Requirement: Mapping output Codex phải deterministic và validate trước khi ghi
Hệ thống SHALL chuẩn hoá và validate output Codex bằng mapping deterministic trước khi ghi story, shots, prompt pack hoặc Series Bible vào database.

#### Scenario: Output đúng schema canonical
- **WHEN** Codex trả JSON đúng schema canonical cho story, shots, prompt pack hoặc Series Bible
- **THEN** hệ thống SHALL map dữ liệu vào model nội bộ và ghi DB như luồng hợp lệ

#### Scenario: Output dùng alias được hỗ trợ
- **WHEN** Codex trả key alias đã được định nghĩa rõ như `shots`, `segments`, `video_prompts` hoặc alias tương đương đã whitelist
- **THEN** hệ thống SHALL normalize về field canonical trước khi validate và SHALL log alias mapping summary an toàn

#### Scenario: Output dùng alias mơ hồ hoặc xung đột
- **WHEN** Codex trả nhiều key alias xung đột cho cùng một field hoặc mapping không xác định được nguồn dữ liệu chính xác
- **THEN** hệ thống SHALL reject output, log lỗi mapping và MUST NOT ghi dữ liệu partial vào DB

### Requirement: Validate order, id và count của structured planning output
Hệ thống SHALL kiểm tra order, id và count của output Codex khớp với input project trước khi ghi artifact.

#### Scenario: Prompt pack thiếu shot hoặc segment
- **WHEN** project yêu cầu prompt cho N shots hoặc segments nhưng Codex trả ít hơn N item
- **THEN** hệ thống SHALL reject prompt pack, log expected count và actual count, và MUST NOT xoá prompt cũ hoặc ghi prompt mới partial

#### Scenario: Prompt pack thừa shot hoặc sai order
- **WHEN** Codex trả prompt thừa, trùng `shot_order`, sai `segment_number` hoặc không khớp shot/segment input
- **THEN** hệ thống SHALL reject output và ghi lỗi tiếng Việt rõ ràng cho user/developer

#### Scenario: Shot breakdown sai scene/project context
- **WHEN** Codex trả shot có `scene_order` không tồn tại, `shot_order` trùng hoặc thứ tự không liên tục
- **THEN** hệ thống SHALL reject shot breakdown hoặc normalize chỉ khi mapping là deterministic và đầy đủ, sau đó validate lại trước khi ghi DB

### Requirement: Validate type và required creative fields
Hệ thống SHALL validate kiểu dữ liệu và required creative fields trước khi ghi story, shots, prompt pack hoặc Series Bible.

#### Scenario: Field sai type
- **WHEN** Codex trả field dạng object/list cho field bắt buộc là string, hoặc string cho field bắt buộc là array/object
- **THEN** hệ thống SHALL normalize nếu có rule an toàn; nếu không thì SHALL reject output với validation error cụ thể

#### Scenario: Prompt video thiếu continuity fields
- **WHEN** video prompt thiếu duration, aspect ratio, subject/action, camera, start/end frame, continuity notes, retention notes, transition notes hoặc sound design notes
- **THEN** hệ thống SHALL reject hoặc repair bằng fallback chỉ khi fallback không làm mất ý nghĩa và SHALL log field nào đã fallback

#### Scenario: Series Bible thiếu nhân vật hoặc bối cảnh cốt lõi
- **WHEN** Codex tạo/cập nhật Series Bible nhưng thiếu character bible hoặc world/style bible cốt lõi
- **THEN** hệ thống SHALL yêu cầu bổ sung hoặc reject update, không ghi bible rỗng làm ảnh hưởng các tập sau

### Requirement: Không ghi partial data khi validation fail
Hệ thống SHALL dùng transaction hoặc trình tự ghi an toàn để validation fail không làm mất dữ liệu hợp lệ cũ.

#### Scenario: Prompt pack mới invalid khi prompt cũ đang tồn tại
- **WHEN** project đã có prompt cũ và Codex trả prompt pack mới invalid
- **THEN** hệ thống SHALL giữ prompt cũ, giữ prompt_status hiện tại hoặc đánh dấu failure rõ ràng, và MUST NOT xoá file prompt cũ

#### Scenario: Shot breakdown invalid sau story đã approve
- **WHEN** story đã approve nhưng shot breakdown mới invalid
- **THEN** hệ thống SHALL giữ story và existing shots nếu có, log validation failure, và không tạo shot partial

### Requirement: Strict mapping phải áp dụng cho cả project lẻ và project trong series
Hệ thống SHALL áp dụng cùng lớp mapping/validation cho project lẻ và episode project trong series.

#### Scenario: Project lẻ generate prompt
- **WHEN** project lẻ gọi generate prompt pack
- **THEN** hệ thống SHALL validate count/order/type/required fields như project thuộc series

#### Scenario: Episode project generate prompt
- **WHEN** project thuộc series gọi generate prompt pack
- **THEN** hệ thống SHALL validate thêm rằng prompt không mâu thuẫn với Series Bible về nhân vật, bối cảnh và style nếu có dữ liệu đủ để kiểm tra

### Requirement: Mapping errors phải dễ debug và không leak nội dung dài
Hệ thống SHALL ghi debug event cho mapping/validation error với thông tin đủ fix nhưng không lưu full prompt/source/narration dài hoặc secret.

#### Scenario: Mapping fail
- **WHEN** output Codex không map được vào model canonical
- **THEN** hệ thống SHALL log step name, project id, series id nếu có, expected keys, received keys, expected count, actual count, error code và request id

#### Scenario: Technical details redaction
- **WHEN** hệ thống ghi technical details cho lỗi mapping/validation
- **THEN** technical details MUST NOT chứa full source block, full prompt video, narration dài hoặc secret; chỉ lưu count, ids, key names, type summary và preview đã truncate

### Requirement: Codex retry không được làm dữ liệu mất đồng bộ
Hệ thống SHALL giữ retry behavior hiện có nhưng chỉ ghi output sau khi attempt cuối cùng hoặc attempt thành công đã pass mapping/validation đầy đủ.

#### Scenario: Attempt đầu invalid, attempt sau valid
- **WHEN** Codex attempt đầu trả JSON invalid hoặc mapping fail và retry sau trả output valid
- **THEN** hệ thống SHALL chỉ ghi output của attempt valid và log attempt invalid là warning

#### Scenario: Tất cả attempts invalid
- **WHEN** tất cả Codex attempts đều invalid hoặc mapping fail
- **THEN** hệ thống SHALL trả lỗi validation rõ ràng, giữ dữ liệu cũ và ghi debug event failure
