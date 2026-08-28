## ADDED Requirements

### Requirement: Chấm điểm ý tưởng và kịch bản
Hệ thống SHALL chấm điểm mỗi idea/script theo rubric có version với thang 0-10 cho từng tiêu chí: hook 20%, cấu trúc 15%, xung đột/cảm xúc 15%, retention/open loop/payoff 15%, độ mới và khoảng cách nguồn 15%, khả năng phát triển nhân vật/series 10%, khả năng sản xuất AI Video 10%.

#### Scenario: Tính điểm tổng
- **WHEN** một idea/script có đủ các điểm thành phần hợp lệ
- **THEN** hệ thống lưu điểm tổng 0-100, từng điểm thành phần, trọng số, rubric version và thời điểm chấm

#### Scenario: Thiếu tiêu chí
- **WHEN** một tiêu chí chưa có bằng chứng hoặc không thể đánh giá
- **THEN** hệ thống đánh dấu `incomplete`, nêu lý do và không hiển thị như recommendation chắc chắn

### Requirement: Giải thích điểm và evidence
Mỗi điểm SHALL có explanation, evidence refs hoặc limitation; UI SHALL hiển thị điểm mạnh, điểm yếu, rủi ro và hành động cải thiện bằng tiếng Việt.

#### Scenario: Người dùng mở chi tiết score
- **WHEN** người dùng mở bảng chấm điểm của một phương án
- **THEN** hệ thống hiển thị tổng điểm, biểu đồ/bảng thành phần, lý do, evidence, cảnh báo và đề xuất sửa cụ thể

#### Scenario: Điểm độ mới thấp
- **WHEN** originality score dưới ngưỡng an toàn hoặc có cảnh báo giống nguồn
- **THEN** hệ thống hiển thị cảnh báo nổi bật và không gắn nhãn khuyên chọn tự động dù tổng điểm cao

### Requirement: Phương án khuyên chọn có safety gate
Hệ thống SHALL xếp hạng các phương án nhưng chỉ gắn `recommended` khi đạt ngưỡng tổng điểm, có hook/structure tối thiểu, không vi phạm must-have/avoid và đạt ngưỡng originality/feasibility; recommendation SHALL có lý do và confidence.

#### Scenario: Có một phương án đủ điều kiện
- **WHEN** một phương án có điểm tổng cao nhất và vượt mọi safety gate
- **THEN** hệ thống hiển thị "Khuyên chọn" cùng lý do, trade-off, confidence và action duyệt

#### Scenario: Có nhiều phương án gần điểm
- **WHEN** hai hoặc nhiều phương án chênh lệch không quá 3 điểm
- **THEN** hệ thống hiển thị nhóm phương án đồng hạng, nêu khác biệt và không che phương án còn lại

#### Scenario: Người dùng ghi đè recommendation
- **WHEN** người dùng chọn phương án khác hoặc bỏ recommendation
- **THEN** hệ thống lưu quyết định người dùng riêng với AI score, ghi revision/provenance và dùng lựa chọn đó cho handoff nếu được approve

### Requirement: Score stale theo dependency
Score SHALL ghi dependency fingerprint của idea/script, source package và rubric; khi dependency thay đổi, score liên quan SHALL chuyển `stale` và không được dùng làm recommendation hiện hành.

#### Scenario: Source hoặc script thay đổi
- **WHEN** accepted source, script seed hoặc rubric revision thay đổi
- **THEN** hệ thống đánh stale các score phụ thuộc và yêu cầu chấm lại trước khi handoff
