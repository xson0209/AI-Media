## ADDED Requirements

### Requirement: Chọn mode nghiên cứu
Hệ thống SHALL cung cấp ba mode: `research`, `creative` và `both`; UI SHALL giải thích vai trò của mỗi mode bằng tiếng Việt trước khi chạy.

#### Scenario: Chạy mode nghiên cứu
- **WHEN** người dùng chọn mode nghiên cứu và bấm chạy
- **THEN** hệ thống tạo một run lưu evidence, docs insight, comparison, risks và trạng thái/token metadata đã redaction

#### Scenario: Chạy mode sáng tạo
- **WHEN** người dùng chọn mode phát triển content và bấm chạy
- **THEN** hệ thống tạo concept, hook, beat, script seed và production notes dựa trên context đã compile

#### Scenario: Chạy cả hai
- **WHEN** người dùng chọn mode `both`
- **THEN** hệ thống chạy hai attempt độc lập, lưu riêng kết quả, sau đó tạo merge result có contribution, bất đồng và các option để người dùng review

### Requirement: Hợp nhất có giới hạn context
Hệ thống SHALL compile accepted memory và source evidence theo budget trước khi gọi AI; SHALL ưu tiên accepted content, quyết định quan trọng và limitations hơn raw run.

#### Scenario: Nhiều project vượt budget
- **WHEN** người dùng chọn nhiều project khiến context vượt giới hạn
- **THEN** hệ thống rút gọn theo thứ tự ưu tiên, hiển thị số project/char đã rút gọn và vẫn giữ project id/provenance

#### Scenario: Hai kết quả mâu thuẫn
- **WHEN** hai attempt đưa ra hướng khác nhau về premise, nhân vật hoặc constraint
- **THEN** merge result hiển thị mâu thuẫn và tạo lựa chọn giải quyết, không tự ghi một bên thành canon

### Requirement: Ghi nhận chi phí và bảo mật run
Hệ thống SHALL lưu thời lượng, trạng thái, model/profile source, token/cost metadata nếu runtime cung cấp; SHALL redaction secret, path nhạy cảm, raw binary và output dài trong log.

#### Scenario: Run thành công
- **WHEN** AI trả kết quả hợp lệ
- **THEN** run lưu metadata tối thiểu để kiểm tra tiêu thụ token và liên kết tới output file mà không log toàn bộ nội dung

#### Scenario: Run timeout hoặc lỗi
- **WHEN** một attempt timeout hoặc trả schema không hợp lệ
- **THEN** hệ thống đánh dấu attempt lỗi, giữ attempt còn lại nếu có, hiển thị retry action và không đưa kết quả lỗi vào accepted memory
