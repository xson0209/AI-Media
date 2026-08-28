## ADDED Requirements

### Requirement: Story Studio tạo đúng ba candidate AI thật
Hệ thống BẮT BUỘC (MUST) tạo đúng ba candidate bằng AI cho ba chiến lược hook/giữ chân, cảm xúc/drama và hình ảnh/hành động.

#### Scenario: Tạo ba candidate từ cùng ngữ cảnh
- **WHEN** người dùng yêu cầu phát triển Story Episode
- **THEN** hệ thống PHẢI đóng băng một gói ngữ cảnh từ Bộ não Series
- **AND** cả ba candidate PHẢI dùng cùng gói ngữ cảnh và cùng phiên bản canon

#### Scenario: Candidate khác nhau thật sự
- **WHEN** ba candidate được tạo thành công
- **THEN** hệ thống PHẢI kiểm tra chúng khác nhau về hook, cấu trúc beat, trọng tâm cảm xúc hoặc hình ảnh
- **AND** hệ thống KHÔNG ĐƯỢC coi ba bản chỉ đổi tiêu đề hoặc vài câu là hợp lệ

#### Scenario: Một candidate bị lỗi
- **WHEN** một trong ba yêu cầu AI lỗi schema hoặc lỗi tạm thời
- **THEN** hệ thống PHẢI thử lại riêng candidate đó trong giới hạn cấu hình
- **AND** KHÔNG ĐƯỢC tạo lại hai candidate hợp lệ nếu ngữ cảnh không đổi

### Requirement: Candidate được đánh giá độc lập và có lý do
Hệ thống BẮT BUỘC (MUST) dùng một bước đánh giá tách khỏi bước tạo để chấm điểm ba candidate theo rubric của mục tiêu đầu ra.

#### Scenario: Chấm candidate truyện ảnh
- **WHEN** output intent là `truyen_anh`
- **THEN** rubric PHẢI ưu tiên khoảnh khắc hình ảnh, bố cục panel, cảm xúc dễ đọc, caption và khả năng chuyển thành prompt ảnh

#### Scenario: Chấm candidate video truyện
- **WHEN** output intent là `video_truyen`
- **THEN** rubric PHẢI ưu tiên hook, nhịp shot, chuyển động, narration, giữ chân, chuyển cảnh và khả năng chuyển thành prompt video

#### Scenario: Hiển thị lý do chấm
- **WHEN** đánh giá hoàn tất
- **THEN** mỗi candidate PHẢI có điểm từng tiêu chí, lý do, bằng chứng, điểm mạnh, điểm yếu và rủi ro bằng tiếng Việt
- **AND** hệ thống KHÔNG ĐƯỢC chỉ trả về một tổng điểm không giải thích

### Requirement: Người dùng có thể chọn hoặc tổng hợp candidate
Hệ thống BẮT BUỘC (MUST) cho phép người dùng lấy nguyên một candidate hoặc tạo Master Story tổng hợp từ phần tốt nhất của nhiều candidate.

#### Scenario: Chọn một candidate
- **WHEN** người dùng chọn một candidate hợp lệ
- **THEN** hệ thống PHẢI tạo Master Story từ nội dung candidate đó
- **AND** Master Story vẫn PHẢI chờ người dùng duyệt

#### Scenario: Tổng hợp phần tốt nhất
- **WHEN** người dùng yêu cầu tổng hợp
- **THEN** AI PHẢI nhận candidate, đánh giá và canon liên quan
- **AND** kết quả PHẢI là một câu chuyện liền mạch, đúng schema và chỉ rõ nguồn phần được chọn

#### Scenario: Tổng hợp vi phạm canon
- **WHEN** Master Story tổng hợp vi phạm lỗi canon chặn
- **THEN** hệ thống PHẢI từ chối chuyển sang chờ duyệt
- **AND** PHẢI trả về lỗi cùng dữ liệu canon liên quan

### Requirement: Prompt được chấm chất lượng ngữ nghĩa
Hệ thống BẮT BUỘC (MUST) chấm prompt ảnh và prompt video theo canon, nhận diện, hành động, thời lượng, continuity, camera, khả năng render, ngôn ngữ, phụ đề, giữ chân, chuyển cảnh và âm thanh.

#### Scenario: Prompt đủ trường nhưng mâu thuẫn
- **WHEN** prompt có đủ tất cả trường bắt buộc nhưng chứa hành động, timeline, camera hoặc trạng thái mâu thuẫn
- **THEN** hệ thống PHẢI đánh prompt chưa đạt
- **AND** PHẢI nêu tiêu chí, bằng chứng và gợi ý sửa

#### Scenario: Prompt đạt ngưỡng
- **WHEN** prompt đạt ngưỡng điểm cấu hình và không còn lỗi chặn
- **THEN** hệ thống PHẢI chuyển prompt sang trạng thái đạt kiểm tra
- **AND** prompt vẫn PHẢI chờ người dùng duyệt trước khi render

#### Scenario: Prompt chưa đạt ngưỡng
- **WHEN** prompt không đạt điểm hoặc còn lỗi chặn
- **THEN** hệ thống PHẢI chuyển prompt sang sửa tự động hoặc cần người dùng xem lại theo cấu hình
- **AND** KHÔNG ĐƯỢC gửi prompt sang provider render

### Requirement: Prompt được tự sửa có giới hạn và có phiên bản
Hệ thống BẮT BUỘC (MUST) có thể tự sửa prompt dựa trên lỗi đã phát hiện, giữ lịch sử phiên bản và dừng sau số lần giới hạn.

#### Scenario: Sửa prompt lần đầu
- **WHEN** prompt chưa đạt và còn lượt sửa
- **THEN** AI PHẢI chỉ sửa các vấn đề được chỉ ra và giữ các phần đã đạt
- **AND** hệ thống PHẢI lưu phiên bản mới cùng danh sách thay đổi

#### Scenario: Prompt đạt sau khi sửa
- **WHEN** phiên bản sửa đạt điểm và không còn lỗi chặn
- **THEN** hệ thống PHẢI dừng vòng sửa
- **AND** PHẢI để người dùng duyệt phiên bản đạt thay vì tự duyệt

#### Scenario: Hết lượt sửa
- **WHEN** prompt vẫn chưa đạt sau số lần sửa tối đa
- **THEN** hệ thống PHẢI chuyển sang `needs_review`
- **AND** PHẢI hiển thị lỗi còn lại và các lựa chọn sửa thủ công, khôi phục hoặc tạo lại

### Requirement: Workflow không gọi provider video thật
Hệ thống BẮT BUỘC (MUST) hoàn thành tạo candidate, đánh giá, tổng hợp, kiểm tra và sửa prompt mà không cần gọi Veo hoặc provider tạo video.

#### Scenario: Chạy kiểm thử chất lượng
- **WHEN** bộ kiểm thử của capability này chạy
- **THEN** hệ thống PHẢI dùng AI giả lập, dữ liệu cố định hoặc adapter kiểm thử
- **AND** KHÔNG ĐƯỢC submit prompt, tạo clip hoặc tiêu credit provider
