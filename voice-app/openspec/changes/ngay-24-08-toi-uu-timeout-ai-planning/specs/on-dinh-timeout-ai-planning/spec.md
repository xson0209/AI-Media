## ADDED Requirements

### Requirement: Timeout không được leo thang fallback model

Khi một lời gọi Codex CLI thất bại vì timeout, hệ thống SHALL dừng ngay và trả lỗi, KHÔNG được đổi sang profile model khác rồi chạy lại cùng request đó. Timeout là dấu hiệu request quá lớn, không phải dấu hiệu cấu hình model sai.

#### Scenario: Lần thử đầu timeout

- **WHEN** lời gọi Codex CLI đầu tiên (profile `preferred`) hết thời gian chờ
- **THEN** hệ thống SHALL raise `AIPlanningError` với `error_code = "CODEX_EXEC_TIMEOUT"` mà không chạy thêm subprocess nào
- **AND** tổng thời gian chờ của lời gọi logic đó SHALL không vượt quá một lần ngân sách timeout

#### Scenario: Lỗi cấu hình model thật vẫn được fallback

- **WHEN** lời gọi thất bại với thông báo provider chứa dấu hiệu model/config không hợp lệ (ví dụ `unknown model`, `model_reasoning_effort`)
- **THEN** hệ thống SHALL vẫn thử lại bằng profile `user_connected_fallback`

#### Scenario: Lỗi tạm thời của provider vẫn được fallback

- **WHEN** lời gọi thất bại với HTTP 429/503 hoặc dấu hiệu quá tải tạm thời, và không phải timeout
- **THEN** hệ thống SHALL vẫn thử lại theo thang fallback hiện có

### Requirement: Thông báo timeout phải nêu hành động khả thi

Thông báo lỗi timeout SHALL không hướng người dùng tới việc tăng timeout, vì trần 600 giây là cứng và UI không có control để sửa. Thông báo SHALL hướng tới việc giảm khối lượng của một lần yêu cầu.

#### Scenario: Người dùng nhận lỗi timeout

- **WHEN** một bước planning thất bại vì `CODEX_EXEC_TIMEOUT`
- **THEN** thông báo trả về UI SHALL nêu cách giảm khối lượng (giảm thời lượng mục tiêu, giảm số segment, rút ngắn nguồn nội dung)
- **AND** thông báo SHALL không chứa hướng dẫn tăng timeout trong Settings

### Requirement: Reasoning effort theo bước là mức trần

Mỗi bước planning SHALL khai báo được một **mức trần** reasoning effort. Effort thực thi SHALL là giá trị thấp hơn giữa effort người dùng chọn và trần của bước, theo thang bậc `low < medium < high < xhigh < max < ultra`. Trần SHALL không bao giờ nâng effort lên cao hơn mức người dùng đã chọn.

#### Scenario: Người dùng chọn effort cao, bước cơ học có trần thấp hơn

- **WHEN** settings đặt `model_reasoning_effort = "xhigh"` và bước `video_prompt_generation` khai báo trần `medium`
- **THEN** lệnh Codex cho bước đó SHALL mang `model_reasoning_effort="medium"`

#### Scenario: Bước sáng tạo không có trần

- **WHEN** settings đặt `model_reasoning_effort = "xhigh"` và bước `shot_breakdown` không khai báo trần
- **THEN** lệnh Codex SHALL mang `model_reasoning_effort="xhigh"`

#### Scenario: Người dùng chọn effort thấp hơn cả trần

- **WHEN** settings đặt `model_reasoning_effort = "low"` và bước khai báo trần `medium`
- **THEN** lệnh Codex SHALL mang `model_reasoning_effort="low"`
- **AND** trần SHALL không nâng giá trị lên `medium`

#### Scenario: Không có override nào từ người dùng

- **WHEN** settings và env đều không đặt effort, và bước khai báo trần `medium`
- **THEN** effort thực thi SHALL là `medium`, không phải `DEFAULT_CODEX_REASONING_EFFORT`

#### Scenario: Trần không hợp lệ

- **WHEN** một bước khai báo trần không thuộc `CODEX_REASONING_EFFORTS`
- **THEN** hệ thống SHALL coi như bước đó không có trần, và SHALL không làm lệnh Codex thất bại

### Requirement: Output bị cắt không được che giấu thành thành công

Khi một lời gọi đã truyền JSON schema, hệ thống SHALL không được bọc output không parse được thành `{"text": <raw>}` rồi trả về như kết quả hợp lệ. Output bị cắt là dạng thất bại phổ biến nhất khi request quá lớn và phải nhìn thấy được.

#### Scenario: Có schema nhưng output không parse được

- **WHEN** lời gọi truyền `output_schema` và output trả về không phải JSON object hợp lệ
- **THEN** hệ thống SHALL raise lỗi với error code phân biệt được (ví dụ `CODEX_OUTPUT_TRUNCATED`)
- **AND** SHALL ghi `output_chars` để chẩn đoán được là bị cắt hay hỏng cấu trúc

#### Scenario: Không truyền schema thì giữ nguyên hành vi

- **WHEN** lời gọi không truyền `output_schema` (ví dụ các bước research chờ text thuần)
- **THEN** hệ thống SHALL giữ nguyên hành vi bọc `{"text": <raw>}` như trước

### Requirement: Metrics đủ để đo được trước và sau

Mỗi lời gọi Codex SHALL ghi lại số liệu định lượng đủ để so sánh hiệu năng trước và sau khi tối ưu, thay vì chỉ ghi thành công hay thất bại.

#### Scenario: Lời gọi kết thúc

- **WHEN** một lời gọi Codex kết thúc, dù thành công hay thất bại
- **THEN** hệ thống SHALL ghi `prompt_chars`, `output_chars`, `elapsed_ms`, `effective_reasoning_effort` và `attempt` vào observability
- **AND** khi lời gọi thuộc một lô, SHALL ghi thêm `batch_index` và `batch_total`

#### Scenario: Truy vấn hiệu năng theo bước

- **WHEN** cần đánh giá bước nào đang tiến gần trần timeout
- **THEN** các số liệu trên SHALL truy được theo `step_name` và `project_id`

### Requirement: Trần timeout giữ nguyên

Change này SHALL không nâng trần timeout 600 giây ở bất kỳ tầng nào. Cách xử lý request quá lớn là làm nó nhỏ lại.

#### Scenario: Caller yêu cầu ngân sách lớn hơn trần

- **WHEN** một caller truyền `timeout_seconds` lớn hơn 600
- **THEN** hệ thống SHALL vẫn clamp về 600 như hành vi hiện tại
