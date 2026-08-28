## ADDED Requirements

### Requirement: Handoff Video Inspiration được lưu bền vững và có phiên bản
Hệ thống BẮT BUỘC (MUST) lưu handoff phía backend với mã, analysis package, phiên bản, trạng thái duyệt, script revision và project đích.

#### Scenario: Người dùng tạo handoff
- **WHEN** video đã có analysis package và kịch bản mới hợp lệ
- **THEN** hệ thống PHẢI tạo handoff ở trạng thái chờ duyệt hoặc sẵn sàng duyệt
- **AND** reload trình duyệt KHÔNG ĐƯỢC làm mất handoff

#### Scenario: Handoff thiếu dữ liệu bắt buộc
- **WHEN** analysis package hoặc script đã duyệt bị thiếu
- **THEN** hệ thống PHẢI chặn tạo AI Video project
- **AND** PHẢI giải thích mục dữ liệu còn thiếu bằng tiếng Việt

### Requirement: Handoff giữ dữ liệu có cấu trúc
Hệ thống BẮT BUỘC (MUST) truyền target audience, mục tiêu, content spine, hook, retention map, script, visual grammar, audio grammar, originality boundaries và evidence refs dưới dạng có cấu trúc.

#### Scenario: Tạo source blocks tương thích
- **WHEN** client hoặc workflow cũ cần source blocks
- **THEN** hệ thống PHẢI dựng source blocks từ payload cấu trúc
- **AND** payload cấu trúc vẫn PHẢI là nguồn chuẩn

#### Scenario: Dữ liệu dài vượt giới hạn
- **WHEN** transcript, evidence hoặc analysis dài
- **THEN** hệ thống PHẢI rút gọn theo nhóm và mức quan trọng
- **AND** KHÔNG ĐƯỢC làm mất hook, payoff, content spine, narration đích hoặc canon chỉ vì chúng nằm sau dữ liệu nguồn dài

### Requirement: Dữ liệu nguồn và nội dung đích được tách riêng
Hệ thống BẮT BUỘC (MUST) phân biệt nguồn quan sát, bài học được phép học và nội dung đích đã duyệt.

#### Scenario: Transcript nguồn và narration đích khác nhau
- **WHEN** bản rewrite tạo narration mới
- **THEN** voice và subtitle PHẢI dùng narration đích đã duyệt
- **AND** transcript nguồn chỉ được dùng làm bằng chứng hoặc đối chiếu

#### Scenario: Học nhịp nhưng không copy cảnh
- **WHEN** timeline đích học cơ chế hook, nhịp hoặc sound design từ video nguồn
- **THEN** hệ thống PHẢI lưu liên kết bài học
- **AND** KHÔNG ĐƯỢC bắt buộc tái tạo cùng chuỗi shot, nhân vật hoặc câu thoại nguồn

### Requirement: Dự án đơn lẻ có Bộ nhớ Dự án
Hệ thống BẮT BUỘC (MUST) cung cấp Bộ nhớ Dự án cho project không thuộc series để giữ mục tiêu, nội dung, retention, continuity và quyết định đã duyệt.

#### Scenario: Tạo project đơn lẻ
- **WHEN** AI Video project không có `series_id`
- **THEN** Project Memory PHẢI là nguồn chuẩn cho khách hàng mục tiêu, mục tiêu video, content spine, hook-payoff, retention, nhân vật, visual, audio, voice, must-have và avoid

#### Scenario: Candidate bị loại
- **WHEN** một candidate không được chọn hoặc prompt bị lỗi
- **THEN** hệ thống CÓ THỂ giữ artifact trong lịch sử
- **AND** KHÔNG ĐƯỢC tự đưa nội dung đó vào Project Memory đã duyệt

### Requirement: Dự án series kết hợp Project Memory với Series Canon
Hệ thống BẮT BUỘC (MUST) áp dụng Series Canon trước các quyết định cấp dự án khi chúng mâu thuẫn với đặc điểm cố định.

#### Scenario: Project yêu cầu đổi fixed trait
- **WHEN** Project Memory hoặc handoff đề xuất đổi đặc điểm cố định của nhân vật series
- **THEN** hệ thống PHẢI trả lỗi canon hoặc tạo đề xuất thay đổi series riêng
- **AND** KHÔNG ĐƯỢC âm thầm ghi đè Series Canon

### Requirement: Timeline đích được lập theo mục tiêu video mới
Hệ thống BẮT BUỘC (MUST) tạo timeline đích từ content spine, retention map, thời lượng, mục đích, nền tảng và cấu hình segment của project.

#### Scenario: Thời lượng đích khác video nguồn
- **WHEN** người dùng chọn thời lượng đích ngắn hoặc dài hơn nguồn
- **THEN** hệ thống PHẢI tái cấu trúc beat nội dung theo thời lượng mới
- **AND** KHÔNG ĐƯỢC chỉ co giãn timestamp của shot nguồn

#### Scenario: Beat đích hợp lệ
- **WHEN** timeline đích hoàn tất
- **THEN** mỗi beat PHẢI có vai trò, thông tin mới, câu hỏi hoặc vòng mở, micro-payoff, hình ảnh, âm thanh và thời gian
- **AND** tổng thời lượng PHẢI phù hợp cấu hình project

### Requirement: Mỗi nhiệm vụ nhận ngữ cảnh riêng
Hệ thống BẮT BUỘC (MUST) biên dịch ngữ cảnh khác nhau cho story, shot, prompt, voice và subtitle.

#### Scenario: Tạo prompt video
- **WHEN** AI Video tạo prompt cho một segment
- **THEN** ngữ cảnh PHẢI chứa beat đích, trạng thái đầu/cuối, hành động, camera, continuity, retention role và evidence liên quan
- **AND** không nên chứa toàn bộ transcript nguồn không liên quan

#### Scenario: Tạo voice
- **WHEN** AI Video tạo voice
- **THEN** ngữ cảnh PHẢI chứa narration đích, người nói, ngôn ngữ, cảm xúc, tốc độ và thời lượng
- **AND** KHÔNG ĐƯỢC phụ thuộc bắt buộc vào frame hoặc shot nguồn không liên quan

#### Scenario: Tạo subtitle
- **WHEN** hệ thống tạo subtitle
- **THEN** subtitle PHẢI dựa trên voice hoặc narration cuối cùng và timing tương ứng
- **AND** KHÔNG ĐƯỢC lấy transcript nguồn làm phụ đề mặc định

### Requirement: Người dùng kiểm soát cấu hình và thời điểm chạy
Hệ thống BẮT BUỘC (MUST) giữ quyền xác nhận thị trường, ngôn ngữ, thời lượng, tỷ lệ, voice và chế độ chạy cho người dùng.

#### Scenario: Tạo project từ handoff
- **WHEN** người dùng xác nhận handoff nhưng chưa yêu cầu chạy tự động
- **THEN** hệ thống PHẢI tạo project ở chế độ thủ công
- **AND** KHÔNG ĐƯỢC tự bắt đầu auto-run, tạo clip hoặc gọi Veo

### Requirement: Handoff và Project Memory có dấu vết phiên bản
Hệ thống BẮT BUỘC (MUST) lưu revision và dependency của analysis package, handoff, script, Project Memory, target timeline và artifact đầu ra.

#### Scenario: Sửa narration đích
- **WHEN** narration đích đã duyệt thay đổi
- **THEN** voice, subtitle và package liên quan PHẢI được đánh dấu stale
- **AND** UI PHẢI hiển thị lý do

#### Scenario: Sửa transcript nguồn nhưng narration đích không đổi
- **WHEN** người dùng sửa transcript nguồn để đối chiếu nhưng nội dung đích không phụ thuộc phần sửa
- **THEN** hệ thống KHÔNG ĐƯỢC mặc định stale toàn bộ voice và subtitle
