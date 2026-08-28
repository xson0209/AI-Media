## ADDED Requirements

### Requirement: Video được chia thành shot theo dòng thời gian
Hệ thống BẮT BUỘC (MUST) phát hiện ranh giới shot, thời gian bắt đầu, kết thúc, thời lượng và keyframe đại diện cho video nguồn.

#### Scenario: Video có nhiều cảnh cắt
- **WHEN** video nguồn chứa nhiều thay đổi cảnh rõ ràng
- **THEN** hệ thống PHẢI tạo các shot riêng theo timeline
- **AND** KHÔNG ĐƯỢC chỉ dùng một danh sách frame cách đều làm đại diện duy nhất

#### Scenario: Shot dài có nhiều thay đổi
- **WHEN** một shot dài có chuyển động hoặc thay đổi hình ảnh đáng kể
- **THEN** hệ thống PHẢI có thể chọn nhiều keyframe trong giới hạn cấu hình
- **AND** các keyframe PHẢI liên kết với đúng shot và timestamp

### Requirement: Transcript giữ timestamp và nguồn chỉnh sửa
Hệ thống BẮT BUỘC (MUST) lưu transcript thành các segment có thời gian, nội dung, ngôn ngữ, người nói khi có và mức tin cậy.

#### Scenario: STT có timestamp chi tiết
- **WHEN** công cụ STT trả timestamp segment hoặc từ
- **THEN** hệ thống PHẢI giữ timestamp đó trong dữ liệu phân tích
- **AND** PHẢI liên kết segment với shot chồng lấp theo thời gian

#### Scenario: STT chỉ có timestamp cấp chunk
- **WHEN** công cụ STT không có timestamp chi tiết
- **THEN** hệ thống PHẢI lưu cấp chính xác thấp hơn
- **AND** KHÔNG ĐƯỢC bịa timestamp chính xác tới từng từ

#### Scenario: Người dùng sửa transcript
- **WHEN** người dùng chỉnh nội dung transcript
- **THEN** hệ thống PHẢI lưu bản chỉnh sửa và nguồn `user_edited`
- **AND** bản transcript thô PHẢI còn truy xuất được

### Requirement: Hình ảnh, chuyển động và chữ được phân tích theo shot
Hệ thống BẮT BUỘC (MUST) phân tích chủ thể, bối cảnh, camera, chuyển động, chuyển cảnh và chữ trên màn hình theo từng shot.

#### Scenario: Shot có chuyển động camera
- **WHEN** camera pan, tilt, zoom, tiến, lùi hoặc rung có thể quan sát được
- **THEN** hệ thống PHẢI lưu mô tả camera motion và mức tin cậy
- **AND** không được khẳng định loại chuyển động khi frame hoặc dữ liệu không đủ

#### Scenario: Video có chữ trên màn hình
- **WHEN** OCR hoặc vision nhận diện được chữ
- **THEN** hệ thống PHẢI lưu nội dung, thời gian, vùng tương đối, ngôn ngữ và confidence
- **AND** người dùng PHẢI có thể sửa kết quả sai

#### Scenario: Vision không xem được frame
- **WHEN** công cụ phân tích không truy cập hoặc không hiểu được frame
- **THEN** hệ thống PHẢI ghi limitations rõ ràng
- **AND** KHÔNG ĐƯỢC tạo mô tả hình ảnh như đã quan sát thành công

### Requirement: Âm thanh được phân tích độc lập với transcript
Hệ thống BẮT BUỘC (MUST) tạo timeline cho speech, music, ambience, SFX, silence và thay đổi năng lượng.

#### Scenario: Video có lời và nhạc nền
- **WHEN** video có speech cùng music hoặc SFX
- **THEN** hệ thống PHẢI liên kết các sự kiện âm thanh theo thời gian
- **AND** PHẢI báo nguy cơ che lời khi chỉ số phù hợp vượt ngưỡng cấu hình

#### Scenario: Video không có lời nói
- **WHEN** transcript trống nhưng video có nhạc, ambience hoặc SFX
- **THEN** hệ thống PHẢI tiếp tục tạo timeline âm thanh
- **AND** KHÔNG ĐƯỢC coi video hoàn toàn không có nội dung âm thanh

### Requirement: Giữ chân toàn video được phân tích chủ yếu bằng nội dung
Hệ thống BẮT BUỘC (MUST) phân tích retention dự đoán với tỷ trọng nội dung lớn hơn cách thể hiện và mặc định dùng tỷ lệ 75% nội dung, 25% trình bày.

#### Scenario: Một beat có thông tin mới
- **WHEN** một đoạn cung cấp bằng chứng, tiết lộ, ví dụ, thay đổi cảm xúc hoặc micro-payoff mới
- **THEN** hệ thống PHẢI ghi rõ giá trị nội dung và lý do người xem có thể tiếp tục

#### Scenario: Một beat lặp hoặc lan man
- **WHEN** một đoạn không thêm thông tin, không thay đổi mức độ quan trọng và có thể xóa mà không ảnh hưởng câu chuyện
- **THEN** hệ thống PHẢI ghi nguy cơ tụt giữ chân
- **AND** PHẢI nêu bằng chứng nội dung thay vì chỉ dựa vào camera ít thay đổi

#### Scenario: Payoff không trả đúng lời hứa
- **WHEN** phần cuối không trả lời câu hỏi hoặc lời hứa đã mở ở hook
- **THEN** hệ thống PHẢI ghi lỗi không nhất quán hook-payoff
- **AND** xem đây là rủi ro nội dung nghiêm trọng

### Requirement: Retention được lưu thành các beat có bằng chứng
Hệ thống BẮT BUỘC (MUST) lưu mỗi beat nội dung với thời gian, vai trò, câu hỏi, thông tin mới, micro-payoff, vòng mở, rủi ro và bằng chứng.

#### Scenario: Xem một beat retention
- **WHEN** người dùng mở beat trên timeline
- **THEN** UI PHẢI hiển thị đoạn video, transcript, frame hoặc âm thanh làm bằng chứng
- **AND** PHẢI giải thích bằng tiếng Việt người xem đang chờ điều gì và nhận được gì

### Requirement: Phân tích retention được ghi rõ là dự đoán
Hệ thống BẮT BUỘC (MUST) phân biệt phân tích dự đoán từ video với dữ liệu retention thực tế của nền tảng.

#### Scenario: Chưa có dữ liệu nền tảng
- **WHEN** người dùng chỉ cung cấp video nguồn
- **THEN** hệ thống PHẢI dùng nhãn `predicted_from_content` hoặc cách diễn đạt tiếng Việt tương đương
- **AND** KHÔNG ĐƯỢC khẳng định chắc chắn người xem đã rời đi tại một timestamp

### Requirement: Gói phân tích có phiên bản, độ phủ và hạn chế
Hệ thống BẮT BUỘC (MUST) tạo `VideoAnalysisPackage` có phiên bản schema, coverage metrics, confidence và limitations.

#### Scenario: Thiếu một modality
- **WHEN** transcript, vision, OCR hoặc audio analysis không hoàn tất
- **THEN** gói phân tích PHẢI nêu rõ phần thiếu và tỷ lệ độ phủ
- **AND** UI PHẢI cho biết kết quả là đầy đủ, một phần hay chỉ dựa trên một modality

### Requirement: Phân tích không cần API tạo ảnh hoặc Veo
Hệ thống BẮT BUỘC (MUST) hoàn thành capability này mà không gọi API sinh ảnh, Veo hoặc provider tạo clip.

#### Scenario: Chạy phân tích và kiểm thử
- **WHEN** người dùng phân tích video hoặc bộ kiểm thử chạy
- **THEN** hệ thống KHÔNG ĐƯỢC tạo ảnh mới, submit prompt video, tạo clip hoặc tiêu credit provider
