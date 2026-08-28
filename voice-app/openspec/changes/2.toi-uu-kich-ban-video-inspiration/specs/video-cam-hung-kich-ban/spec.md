## ADDED Requirements

### Requirement: Tối ưu kịch bản nhiều bước cho Video Inspiration
Hệ thống SHALL hỗ trợ chế độ viết kịch bản tối ưu nhiều bước cho Video Inspiration, tạo nhiều bản nháp, tự đánh giá và tổng hợp thành một bản cuối tốt nhất.

#### Scenario: Tạo nhiều bản nháp trước khi chọn bản cuối
- **WHEN** người dùng bấm `Viết kịch bản tối ưu`
- **THEN** hệ thống SHALL tạo ít nhất 2 bản nháp kịch bản khác hướng
- **AND** mỗi bản nháp SHALL có hook 3-5 giây, script chính, gợi ý hình ảnh, retention plan và sound design plan

#### Scenario: Chấm điểm bản nháp
- **WHEN** hệ thống đã tạo các bản nháp
- **THEN** hệ thống SHALL chấm điểm từng bản theo hook 3-5 giây, độ rõ ý, độ khác biệt với video gốc, retention, khả năng dựng video, sound design và mức bám định hướng người dùng

#### Scenario: Tổng hợp bản cuối tốt nhất
- **WHEN** hệ thống đã có bản nháp và điểm đánh giá
- **THEN** hệ thống SHALL tổng hợp một bản cuối tốt nhất
- **AND** bản cuối MAY lấy điểm mạnh từ nhiều bản nháp khác nhau
- **AND** bản cuối MUST nhất quán về ý tưởng, ngôn ngữ, nhân vật, retention, âm thanh và gợi ý hình ảnh

### Requirement: Hook giữ chân người xem trong 3-5 giây đầu
Hệ thống SHALL tạo hook 3-5 giây đầu như một trường bắt buộc của kịch bản tối ưu, nhằm giữ chân người xem trước khi họ lướt qua.

#### Scenario: Hook có đủ nội dung dựng
- **WHEN** hệ thống tạo bản kịch bản tối ưu
- **THEN** output SHALL có `hook_3_5s`
- **AND** hook này SHALL mô tả câu mở hoặc hành động mở, hình ảnh mở, câu hỏi tò mò hoặc xung đột chính, và âm thanh mở đầu nếu phù hợp

#### Scenario: Hook không chỉ là tiêu đề
- **WHEN** AI trả về hook
- **THEN** hook MUST NOT chỉ là một tiêu đề ngắn
- **AND** hook SHALL đủ rõ để người dùng hoặc AI Video hiểu 3-5 giây đầu cần thấy gì, nghe gì và khiến người xem muốn xem tiếp vì sao

### Requirement: Kịch bản tối ưu có đủ trường AI Video cần dùng
Hệ thống SHALL xuất bản kịch bản tối ưu thành gói dữ liệu có đủ trường để đưa sang form AI Video mà không cần người dùng tự chia lại nội dung.

#### Scenario: Output có source blocks cho AI Video
- **WHEN** bản kịch bản tối ưu được tạo xong
- **THEN** output SHALL có dữ liệu tương ứng cho các ô AI Video: ý tưởng chính, kịch bản thô, nhân vật và bối cảnh, phong cách video, bắt buộc phải có, cần tránh và phong cách hình ảnh
- **AND** dữ liệu này SHALL bao gồm hook 3-5 giây, big idea, script, segment outline, visual suggestion, retention plan, sound design plan và audio direction

#### Scenario: Đưa sang AI Video không làm mất retention và âm thanh
- **WHEN** người dùng bấm `Đưa vào form AI Video`
- **THEN** draft SHALL đưa retention, sound design và audio direction vào source blocks phù hợp
- **AND** `visualStyle` chỉ chứa bản tóm tắt ngắn dưới giới hạn backend
- **AND** dữ liệu chi tiết dài SHALL nằm trong source blocks

### Requirement: Retention plan trong kịch bản Video Inspiration
Hệ thống SHALL tạo retention plan ở cấp kịch bản để AI Video có thể phát triển tiếp thành story, shot và prompt có nhịp giữ chân tốt.

#### Scenario: Retention plan có cấu trúc
- **WHEN** hệ thống tạo bản kịch bản tối ưu
- **THEN** output SHALL có retention plan gồm câu hỏi người xem, curiosity gap, beat curve, pattern interrupt, payoff và rủi ro người xem rời video

#### Scenario: Retention gắn với từng đoạn
- **WHEN** output có danh sách segments
- **THEN** mỗi segment SHOULD có mục đích retention hoặc vai trò trong nhịp giữ chân người xem

### Requirement: Sound design và hướng âm thanh trong kịch bản Video Inspiration
Hệ thống SHALL tạo sound design plan và audio direction trong kịch bản tối ưu để hướng dẫn dựng video, dù chưa tạo file âm thanh thật.

#### Scenario: Sound design plan toàn kịch bản
- **WHEN** hệ thống tạo bản kịch bản tối ưu
- **THEN** output SHALL có sound design plan gồm mood nhạc nền, ambience, SFX chính, silence drop, impact hoặc riser nếu phù hợp, và mixing notes

#### Scenario: Âm thanh theo từng đoạn
- **WHEN** output có segment outline
- **THEN** segment SHOULD có audio cue phù hợp như whoosh, tap, hit, crumble, ambience change, silence drop hoặc nhạc nâng năng lượng
- **AND** cue SHALL ghi mục đích, ví dụ nhấn hook, giữ nhịp, chuyển cảnh, tạo căng thẳng hoặc payoff

#### Scenario: Âm thanh không che lời thoại
- **WHEN** kịch bản có narration hoặc dialogue quan trọng
- **THEN** sound design plan SHALL có mixing notes yêu cầu voice rõ hơn nhạc và SFX
- **AND** hệ thống MUST NOT mô tả như thể MP4 đã có nhạc/SFX thật nếu chỉ mới là chỉ dẫn dựng
