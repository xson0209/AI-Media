## ADDED Requirements

### Requirement: Codex AI planning mặc định dùng gpt-5.6-sol với reasoning ultra
Hệ thống SHALL ưu tiên chạy mọi tác vụ Codex AI planning bằng model `gpt-5.6-sol` và reasoning effort `ultra` khi người dùng chưa cấu hình override rõ ràng trong app.

#### Scenario: Settings chưa có model override
- **WHEN** AI planning settings không có model override thủ công
- **THEN** command `codex exec` SHALL include `--model gpt-5.6-sol`
- **AND** command SHALL include `--config model_reasoning_effort="ultra"`

#### Scenario: Settings chưa có reasoning effort override
- **WHEN** AI planning settings không có reasoning effort override thủ công
- **THEN** hệ thống SHALL resolve reasoning effort thành `ultra`
- **AND** readiness response SHALL báo requested reasoning effort là `ultra`

#### Scenario: User đã cấu hình override hợp lệ
- **WHEN** user đã lưu model hoặc reasoning effort override hợp lệ trong AI planning settings
- **THEN** hệ thống MAY dùng override đó làm đường ưu tiên
- **AND** UI/log SHALL hiển thị nguồn model là override của app thay vì default

#### Scenario: Không ghi đè global Codex config
- **WHEN** hệ thống áp dụng default `gpt-5.6-sol` và `ultra`
- **THEN** hệ thống MUST NOT sửa global Codex config của user
- **AND** default SHALL được truyền bằng command args hoặc resolver runtime của app

### Requirement: Fallback về cấu hình Codex hiện tại của user khi đường ưu tiên lỗi
Hệ thống SHALL retry bằng cấu hình Codex hiện tại của user đang chạy app/backend khi đường ưu tiên `gpt-5.6-sol + ultra` hoặc override tương ứng không chạy được vì lỗi model/config/reasoning/provider.

#### Scenario: Preferred model không khả dụng
- **WHEN** command ưu tiên fail vì model không tồn tại, không có quyền, bị provider từ chối hoặc endpoint không hỗ trợ
- **THEN** hệ thống SHALL retry bằng fallback profile `user_connected_codex_config`
- **AND** fallback command MUST NOT include forced preferred `--model gpt-5.6-sol`
- **AND** fallback command MUST NOT include forced preferred `--config model_reasoning_effort="ultra"`

#### Scenario: Preferred reasoning effort không khả dụng
- **WHEN** Codex CLI hoặc provider từ chối `model_reasoning_effort="ultra"`
- **THEN** hệ thống SHALL retry bằng cấu hình Codex hiện tại của user
- **AND** response/log SHALL ghi `fallback_reason` liên quan reasoning effort hoặc config

#### Scenario: Fallback thành công
- **WHEN** command ưu tiên fail nhưng fallback command tạo output hợp lệ
- **THEN** hệ thống SHALL trả output của fallback cho workflow gọi
- **AND** metadata SHALL set `fallback_used=true`
- **AND** `effective_model` SHALL phản ánh model fallback nếu đọc được, hoặc label `Cấu hình Codex hiện tại của người dùng` nếu không đọc được

#### Scenario: Cả preferred và fallback đều fail
- **WHEN** command ưu tiên và fallback command đều thất bại
- **THEN** hệ thống SHALL trả lỗi có request ID
- **AND** lỗi SHALL gồm thông tin đã redaction của cả preferred failure và fallback failure đủ để debug
- **AND** hệ thống MUST NOT tự chọn model thứ ba

#### Scenario: Lỗi không thể giải bằng fallback
- **WHEN** Codex CLI không tồn tại, process không khởi động được, auth/login rõ ràng không hợp lệ hoặc request bị hủy chủ động
- **THEN** hệ thống SHALL báo lỗi trực tiếp
- **AND** hệ thống MUST NOT chạy fallback model/config vô nghĩa

### Requirement: Structured-output fallback không bị mất khi thêm model fallback
Hệ thống SHALL giữ fallback inline JSON schema hiện có trong mỗi command profile và SHALL phân biệt schema fallback với model/config fallback trong log.

#### Scenario: Output schema bị từ chối trên preferred profile
- **WHEN** preferred profile fail vì provider không hỗ trợ `--output-schema`
- **THEN** hệ thống SHALL retry preferred profile bằng inline JSON schema nếu lỗi thuộc nhóm schema fallback
- **AND** retry này MUST giữ nguyên model/effort của preferred profile

#### Scenario: Preferred profile vẫn fail sau schema fallback
- **WHEN** preferred profile vẫn fail vì model/config sau các bước schema fallback hợp lệ
- **THEN** hệ thống SHALL thử fallback profile
- **AND** fallback profile MAY tiếp tục dùng schema fallback nếu chính fallback cũng gặp lỗi schema

#### Scenario: Log phân biệt hai loại fallback
- **WHEN** schema fallback hoặc model fallback xảy ra
- **THEN** log SHALL dùng step name hoặc metadata khác nhau cho `schema_fallback` và `model_fallback`
- **AND** UI SHALL chỉ báo fallback model khi fallback thật sự chuyển sang cấu hình Codex hiện tại của user

### Requirement: Readiness response và UI hiển thị model thực tế hoặc cấu hình sẽ dùng
Hệ thống SHALL trả metadata model/reasoning trong readiness response và frontend SHALL hiển thị rõ model/effort đang dùng hoặc sẽ dùng bằng tiếng Việt.

#### Scenario: Readiness không chạy exec thật
- **WHEN** frontend gọi readiness check không yêu cầu chạy `codex exec`
- **THEN** response SHALL include requested model và requested reasoning effort
- **AND** response SHALL set `model_verified=false`
- **AND** UI SHALL hiển thị `Cấu hình sẽ dùng: gpt-5.6-sol · ultra`

#### Scenario: Readiness hoặc execution đã verify đường chính
- **WHEN** `codex exec` đã chạy thành công với preferred profile
- **THEN** response hoặc execution metadata SHALL set `effective_model=gpt-5.6-sol`
- **AND** `effective_reasoning_effort=ultra`
- **AND** UI SHALL có thể hiển thị `Đang dùng: gpt-5.6-sol · ultra`

#### Scenario: Execution dùng fallback
- **WHEN** execution thành công bằng fallback profile
- **THEN** UI SHALL hiển thị fallback bằng tiếng Việt
- **AND** UI SHALL hiển thị model fallback nếu biết, hoặc `Cấu hình Codex hiện tại của người dùng` nếu không biết
- **AND** UI SHALL hiển thị request ID liên quan để debug

#### Scenario: Text model dài
- **WHEN** model label, source hoặc fallback reason dài
- **THEN** frontend SHALL wrap/break text trong panel readiness
- **AND** text MUST NOT tràn hoặc che nút tạo dự án

### Requirement: Log model thực tế đã dùng có redaction
Hệ thống SHALL ghi log đủ rõ để xác định model/reasoning profile thực tế đã dùng cho mỗi Codex planning request mà không lộ dữ liệu nhạy cảm.

#### Scenario: Bắt đầu command ưu tiên
- **WHEN** hệ thống bắt đầu chạy Codex command ưu tiên
- **THEN** log SHALL include request ID, provider, requested model, requested reasoning effort, model source, timeout và step name
- **AND** log MUST NOT include full prompt hoặc full source content

#### Scenario: Command thành công
- **WHEN** Codex command tạo output thành công
- **THEN** log SHALL include effective model, effective reasoning effort, fallback flag, elapsed time và output length
- **AND** nếu fallback được dùng thì log SHALL include fallback reason đã redaction

#### Scenario: Không đọc được fallback model cụ thể
- **WHEN** fallback dùng cấu hình Codex hiện tại nhưng app không xác định được model cụ thể
- **THEN** log SHALL ghi model source là `user_connected_codex_config`
- **AND** log SHALL ghi label rõ ràng thay vì để trống hoặc báo nhầm `gpt-5.6-sol`

#### Scenario: Provider trả secret hoặc nội dung dài
- **WHEN** stderr/stdout/provider detail có token, secret, bearer hoặc nội dung dài
- **THEN** log SHALL redact secret và truncate theo giới hạn an toàn hiện có
