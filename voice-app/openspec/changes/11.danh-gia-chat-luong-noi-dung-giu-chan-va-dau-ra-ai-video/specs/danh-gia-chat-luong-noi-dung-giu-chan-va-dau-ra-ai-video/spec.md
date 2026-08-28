## ADDED Requirements

### Requirement: Hệ thống tạo báo cáo chất lượng xuyên suốt
Hệ thống BẮT BUỘC (MUST) đánh giá analysis package, handoff, Project Memory, candidate, nội dung, story, shot, prompt, voice, subtitle và tính nhất quán giữa các bước.

#### Scenario: Một tầng chưa được kiểm tra
- **WHEN** một artifact đầu vào thay đổi sau lần kiểm tra gần nhất
- **THEN** báo cáo liên quan PHẢI chuyển stale hoặc not_checked
- **AND** KHÔNG ĐƯỢC tiếp tục hiển thị kết quả cũ như còn hợp lệ

#### Scenario: Tổng điểm cao nhưng có lỗi chặn
- **WHEN** báo cáo có điểm tổng cao nhưng còn canon, hook-payoff, originality, narration hoặc subtitle lỗi nghiêm trọng
- **THEN** overall status PHẢI là blocked hoặc needs_review theo quy tắc
- **AND** KHÔNG ĐƯỢC coi tổng điểm là đủ để vượt lỗi chặn

### Requirement: Điểm giữ chân ưu tiên nội dung
Hệ thống BẮT BUỘC (MUST) dùng rubric mặc định 75% nội dung và 25% cách thể hiện cho retention quality.

#### Scenario: Chấm một content beat
- **WHEN** hệ thống đánh giá một beat
- **THEN** PHẢI kiểm tra vai trò, thông tin mới, thay đổi cảm xúc/mức độ quan trọng, câu hỏi được trả lời, vòng mở mới và lý do xem tiếp

#### Scenario: Beat không đóng góp
- **WHEN** một beat có thể xóa mà không làm mất thông tin, cảm xúc, logic hoặc payoff
- **THEN** hệ thống PHẢI ghi `content_stagnation_risk` hoặc cảnh báo tiếng Việt tương đương
- **AND** KHÔNG ĐƯỢC bù điểm chỉ vì beat có nhiều chuyển cảnh hoặc hiệu ứng

#### Scenario: Rubric tùy loại video
- **WHEN** mục đích là kể chuyện, bán hàng, giáo dục hoặc truyền cảm hứng
- **THEN** hệ thống PHẢI dùng trọng số nội dung phù hợp
- **AND** trọng số nội dung KHÔNG ĐƯỢC thấp hơn 60% nếu người dùng chưa xác nhận cấu hình đặc biệt

### Requirement: Hook được chấm đa lớp và đối chiếu payoff
Hệ thống BẮT BUỘC (MUST) đánh giá hook theo nội dung, lời nói, hình ảnh, chữ, âm thanh, tâm lý, khách hàng mục tiêu và lời hứa.

#### Scenario: Hook mạnh nhưng payoff sai
- **WHEN** hook tạo lời hứa hoặc câu hỏi không được nội dung cuối trả đúng
- **THEN** hệ thống PHẢI tạo lỗi hook-payoff nghiêm trọng
- **AND** bản nội dung KHÔNG ĐƯỢC tự động đạt chất lượng

#### Scenario: Hook không phù hợp khách hàng
- **WHEN** hook gây tò mò nhưng không liên quan nhu cầu hoặc mức hiểu biết của khách hàng mục tiêu
- **THEN** hệ thống PHẢI hạ điểm audience fit và giải thích lý do

### Requirement: Video Inspiration và AI Video dùng ba candidate có đánh giá độc lập
Hệ thống BẮT BUỘC (MUST) dùng ba candidate khác hướng, cùng context snapshot và một critic tách biệt để chấm điểm.

#### Scenario: Ba candidate chỉ đổi câu chữ
- **WHEN** các candidate không khác đáng kể về hook, cấu trúc, cảm xúc, hình ảnh hoặc cách giải quyết
- **THEN** hệ thống PHẢI coi bộ candidate chưa hợp lệ
- **AND** PHẢI tạo lại phần bị trùng trong giới hạn cấu hình

#### Scenario: Tổng hợp candidate
- **WHEN** người dùng yêu cầu tổng hợp
- **THEN** hệ thống PHẢI lưu phần lấy từ candidate nào và lý do
- **AND** bản tổng hợp PHẢI được kiểm tra lại nội dung, canon, hook-payoff và originality

### Requirement: Nội dung đích được kiểm tra originality
Hệ thống BẮT BUỘC (MUST) so sánh nguồn và đích ở narration, thứ tự beat, nhân vật, bối cảnh, chuỗi shot, hook, payoff, chữ và visual motif.

#### Scenario: Bản đích copy sát nguồn
- **WHEN** nội dung mới giữ quá nhiều câu thoại, thứ tự beat hoặc chuỗi cảnh đặc trưng vượt chính sách
- **THEN** hệ thống PHẢI báo phần giống và bằng chứng
- **AND** PHẢI chặn hoặc yêu cầu sửa theo mức rủi ro

#### Scenario: Chỉ học cơ chế
- **WHEN** bản mới chỉ học loại hook, nhịp nội dung, camera grammar hoặc sound design nhưng dùng nội dung, nhân vật và cảnh mới
- **THEN** hệ thống KHÔNG ĐƯỢC tự coi đó là sao chép nghiêm trọng

### Requirement: Prompt phải truyền đúng nội dung beat
Hệ thống BẮT BUỘC (MUST) đánh giá prompt theo target content beat trước khi chấm hình thức camera và kỹ thuật.

#### Scenario: Prompt đẹp nhưng không truyền thông tin
- **WHEN** prompt có camera, ánh sáng và chuyển động tốt nhưng không thể hiện thông tin mới, cảm xúc hoặc micro-payoff của beat
- **THEN** hệ thống PHẢI đánh prompt chưa đạt hoặc cảnh báo nghiêm trọng

#### Scenario: Tự sửa prompt kỹ thuật
- **WHEN** prompt chỉ lỗi camera, framing hoặc kỹ thuật
- **THEN** repair PHẢI giữ hook, payoff, narration và nội dung beat đã duyệt
- **AND** KHÔNG ĐƯỢC tự viết lại trục nội dung

### Requirement: Voice được kiểm tra theo narration và beat cuối
Hệ thống BẮT BUỘC (MUST) kiểm tra voice dùng đúng narration revision, ngôn ngữ, người nói, cảm xúc, tốc độ, khoảng ngắt và thời lượng.

#### Scenario: Voice dùng narration cũ
- **WHEN** narration đã đổi nhưng voice vẫn phụ thuộc revision cũ
- **THEN** voice PHẢI bị đánh stale hoặc blocked
- **AND** KHÔNG ĐƯỢC dùng để tạo subtitle cuối

#### Scenario: Voice quá dài cho segment
- **WHEN** thời lượng voice vượt phần usable của segment hoặc làm cắt mất nội dung quan trọng
- **THEN** hệ thống PHẢI báo lỗi và đề xuất rút gọn, đổi nhịp hoặc điều chỉnh segment

### Requirement: Subtitle được kiểm tra với voice cuối
Hệ thống BẮT BUỘC (MUST) kiểm tra subtitle khớp văn bản, timing và revision của voice hoặc narration cuối.

#### Scenario: Subtitle lệch voice
- **WHEN** subtitle thiếu câu, thừa câu, sai thứ tự hoặc timing không khớp voice
- **THEN** subtitle PHẢI bị đánh chưa đạt
- **AND** package cuối KHÔNG ĐƯỢC coi là sẵn sàng

#### Scenario: Subtitle tiết lộ payoff sớm
- **WHEN** chữ phụ đề hiển thị phần payoff trước thời điểm narration và content beat tương ứng
- **THEN** hệ thống PHẢI báo rủi ro giữ chân và yêu cầu sửa timing hoặc chia câu

### Requirement: Retention analytics thực tế được nhập tùy chọn và không cần tài khoản nền tảng
Hệ thống BẮT BUỘC (MUST) cho phép nhập retention data có cấu trúc hoặc nhập tay mà không tự đăng nhập tài khoản nền tảng.

#### Scenario: Nhập dữ liệu retention
- **WHEN** người dùng cung cấp timeline retention và các chỉ số hỗ trợ
- **THEN** hệ thống PHẢI chuẩn hóa theo timestamp và phần trăm thời lượng
- **AND** PHẢI liên kết dữ liệu với content beat và shot tương ứng

#### Scenario: Không có retention thật
- **WHEN** người dùng không cung cấp dữ liệu nền tảng
- **THEN** workflow PHẢI tiếp tục bằng predicted retention
- **AND** UI PHẢI ghi rõ đây là dự đoán

### Requirement: So sánh predicted và actual không khẳng định nhân quả
Hệ thống BẮT BUỘC (MUST) dùng ngôn ngữ tương quan khi đối chiếu retention thật với nội dung video.

#### Scenario: Retention tụt tại một beat
- **WHEN** dữ liệu thật giảm mạnh tại một mốc
- **THEN** hệ thống PHẢI hiển thị nội dung, shot, lời, chữ và âm thanh cùng thời điểm
- **AND** PHẢI dùng cách diễn đạt như “có khả năng liên quan” hoặc “cần kiểm chứng” thay vì khẳng định nguyên nhân chắc chắn

### Requirement: Kiểm thử end-to-end dừng trước Veo
Hệ thống BẮT BUỘC (MUST) kiểm thử từ video nguồn tới analysis, handoff, Project Memory, candidate, story, shot, prompt, voice và subtitle mà không gọi provider tạo clip.

#### Scenario: Chạy bộ kiểm thử toàn luồng
- **WHEN** bộ kiểm thử capability này chạy
- **THEN** hệ thống KHÔNG ĐƯỢC tạo job Veo, submit prompt, tạo clip hoặc tiêu credit provider
- **AND** PHẢI xác nhận không có bản ghi provider clip mới

#### Scenario: Báo cáo cho người không viết mã
- **WHEN** kiểm thử hoàn tất
- **THEN** báo cáo PHẢI nêu lỗi chính, ảnh hưởng, bằng chứng và bước xử lý tiếp theo bằng tiếng Việt
