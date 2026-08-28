## ADDED Requirements

### Requirement: Tạo bộ nội dung đăng video cho YouTube, TikTok và Facebook
Hệ thống SHALL tạo một bộ nội dung đăng video cấp project sau khi prompt video đã hoàn tất, gồm biến thể riêng cho YouTube, TikTok và Facebook.

#### Scenario: Tạo đủ nội dung cho ba nền tảng
- **WHEN** project có story, narration và prompt video hợp lệ, không stale
- **THEN** hệ thống SHALL tạo đúng ba biến thể youtube, tiktok và facebook
- **AND** mỗi biến thể SHALL có đủ title, description, hashtags và thumbnail_prompt

#### Scenario: Không dùng chung một bản cho mọi nền tảng
- **WHEN** hệ thống tạo bộ nội dung đăng video
- **THEN** tiêu đề, mô tả, hashtag và prompt thumbnail SHALL được điều chỉnh theo đặc điểm của từng nền tảng
- **AND** hệ thống MUST NOT chỉ sao chép nguyên văn một biến thể cho cả ba nền tảng nếu không có lý do nội dung hợp lệ

#### Scenario: Bộ nền tảng không bao gồm Messenger
- **WHEN** hệ thống tạo bộ nội dung đăng video trong phạm vi change này
- **THEN** nền tảng thứ ba SHALL là Facebook
- **AND** hệ thống MUST NOT thay Facebook bằng Messenger hoặc tạo thêm trường Messenger ngầm định

#### Scenario: Prompt thumbnail là đầu ra văn bản
- **WHEN** hệ thống tạo thumbnail_prompt
- **THEN** đầu ra SHALL là prompt văn bản để người dùng đưa vào công cụ tạo ảnh AI
- **AND** hệ thống MUST NOT báo rằng ảnh thumbnail đã được render nếu chưa có capability tạo ảnh riêng thực sự chạy thành công

### Requirement: Nội dung đăng được tối ưu theo hồ sơ từng nền tảng
Hệ thống SHALL áp dụng hồ sơ ràng buộc riêng của YouTube, TikTok và Facebook để tối ưu khả năng khám phá, tính phù hợp nền tảng và khả năng thu hút lượt nhấp, nhưng MUST NOT cam kết thứ hạng hoặc lượt xem.

#### Scenario: Tiêu đề phù hợp nền tảng
- **WHEN** Codex tạo tiêu đề cho một nền tảng
- **THEN** tiêu đề SHALL có hook rõ, phản ánh đúng nội dung video và tuân thủ giới hạn độ dài đang được cấu hình cho nền tảng đó
- **AND** tiêu đề MUST NOT chứa tuyên bố sai lệch không được hỗ trợ bởi story hoặc narration

#### Scenario: Mô tả phù hợp nền tảng
- **WHEN** Codex tạo mô tả
- **THEN** mô tả SHALL chứa ngữ cảnh chính, từ khóa liên quan và CTA phù hợp với mục đích video nếu project có CTA
- **AND** mô tả MUST NOT tự bịa đường dẫn, tài khoản, sản phẩm, số liệu hoặc lời cam kết không có trong input project

#### Scenario: Hashtag có cấu trúc
- **WHEN** Codex tạo hashtag
- **THEN** hệ thống SHALL lưu hashtag dưới dạng danh sách chuỗi có cấu trúc
- **AND** từng hashtag MUST NOT rỗng, MUST bắt đầu bằng dấu # sau normalize và MUST NOT trùng nhau trong cùng nền tảng

#### Scenario: Prompt thumbnail đủ thông tin để tạo ảnh
- **WHEN** Codex tạo prompt thumbnail
- **THEN** prompt SHALL mô tả chủ thể, hook hình ảnh, cảm xúc, bố cục, độ tương phản, ánh sáng, tỷ lệ khung hình, safe area và continuity liên quan
- **AND** prompt SHALL chỉ dẫn tránh watermark, logo không được cung cấp, chữ ngẫu nhiên, khuôn mặt hoặc bàn tay lỗi và chi tiết không liên quan
- **AND** prompt SHALL dành vùng bố cục phù hợp nếu thumbnail cần thêm chữ bằng công cụ hậu kỳ

#### Scenario: Không tuyên bố bảo đảm SEO
- **WHEN** UI hoặc API trả bộ nội dung đăng video
- **THEN** hệ thống SHALL mô tả đầu ra là nội dung được tối ưu theo hồ sơ nền tảng
- **AND** hệ thống MUST NOT tuyên bố rằng nội dung chắc chắn lên top, viral, đạt một mức CTR hoặc đạt một số lượt xem cụ thể

### Requirement: Bộ nội dung đăng tôn trọng ngôn ngữ video
Hệ thống SHALL dùng project.target_language làm nguồn sự thật cho ngôn ngữ hướng tới người xem trong tiêu đề, mô tả, hashtag và nội dung chữ được yêu cầu trong prompt thumbnail.

#### Scenario: Project video tiếng Việt
- **WHEN** project có target_language = "vi"
- **THEN** tiêu đề, mô tả và hashtag SHALL phù hợp với người xem tiếng Việt
- **AND** chữ hiển thị được đề xuất trong prompt thumbnail, nếu có, SHALL là tiếng Việt

#### Scenario: Project video tiếng Anh
- **WHEN** project có target_language = "en"
- **THEN** tiêu đề, mô tả và hashtag SHALL phù hợp với người xem tiếng Anh
- **AND** chữ hiển thị được đề xuất trong prompt thumbnail, nếu có, SHALL là tiếng Anh

#### Scenario: Thuật ngữ kỹ thuật trong prompt thumbnail
- **WHEN** công cụ tạo ảnh hiểu các chỉ dẫn camera, lighting hoặc composition bằng tiếng Anh tốt hơn
- **THEN** thumbnail_prompt MAY dùng thuật ngữ kỹ thuật tiếng Anh
- **AND** prompt MUST NOT yêu cầu chữ hướng tới người xem bằng ngôn ngữ khác với target_language

#### Scenario: Không fallback sai ngôn ngữ
- **WHEN** Codex không tạo được bộ nội dung đúng target_language
- **THEN** hệ thống SHALL trả lỗi validation có thể retry
- **AND** hệ thống MUST NOT âm thầm lưu một bộ nội dung bằng ngôn ngữ khác làm đầu ra hoàn tất

### Requirement: Lưu bộ nội dung đăng thành artifact có phiên bản và trạng thái
Hệ thống SHALL persist bộ nội dung đăng video cấp project với trạng thái, revision, dấu stale và fingerprint của input để có thể tải lại, retry và xác định độ mới.

#### Scenario: Ghi artifact thành công
- **WHEN** toàn bộ output yêu cầu đã vượt qua mapping và validation
- **THEN** hệ thống SHALL lưu project_id, target_language, dữ liệu ba nền tảng, status, revision, stale và input_fingerprint
- **AND** API đọc project SHALL có thể trả lại cùng artifact sau khi người dùng refresh ứng dụng

#### Scenario: Tạo lại mà input không đổi
- **WHEN** artifact đang completed, không stale và fingerprint vẫn khớp input hiện tại
- **THEN** request không bật force SHALL trả artifact hiện có
- **AND** hệ thống MUST NOT tạo revision mới không cần thiết

#### Scenario: Input nội dung thay đổi
- **WHEN** topic, source block, story, detailed script, narration, shot, prompt video đang active, continuity, visual style, aspect ratio, mục đích video, audience, CTA hoặc target_language thay đổi
- **THEN** hệ thống SHALL đánh dấu bộ nội dung đăng hiện có là stale
- **AND** artifact stale MUST NOT được báo là sẵn sàng xuất bản

#### Scenario: Cấu hình voice thay đổi nhưng nội dung không đổi
- **WHEN** người dùng chỉ đổi voice profile, TTS engine, seed hoặc tham số tạo audio mà narration text không đổi
- **THEN** hệ thống MUST NOT đánh dấu bộ nội dung đăng video stale chỉ vì thay đổi đó

#### Scenario: Tạo lại metadata không làm stale voice
- **WHEN** người dùng tạo lại toàn bộ hoặc một nền tảng trong bộ nội dung đăng
- **THEN** hệ thống MUST NOT đánh dấu voice hoặc subtitle stale nếu narration và timing không đổi

### Requirement: Cho phép tạo lại từng nền tảng hoặc toàn bộ
Hệ thống SHALL cho phép người dùng tạo lại riêng YouTube, TikTok, Facebook hoặc tạo lại toàn bộ bộ nội dung đăng mà không phá dữ liệu hợp lệ ngoài phạm vi được chọn.

#### Scenario: Tạo lại một nền tảng
- **WHEN** người dùng yêu cầu tạo lại riêng youtube, tiktok hoặc facebook
- **THEN** hệ thống SHALL chỉ thay thế biến thể được yêu cầu sau khi biến thể mới vượt qua validation
- **AND** hai biến thể còn lại MUST được giữ nguyên

#### Scenario: Tạo lại toàn bộ
- **WHEN** người dùng yêu cầu tạo lại tất cả nền tảng
- **THEN** hệ thống SHALL tạo và validate đủ ba biến thể trước khi thay thế artifact hiện có

#### Scenario: Tạo lại một nền tảng thất bại
- **WHEN** output mới của nền tảng được chọn không hợp lệ hoặc Codex thất bại
- **THEN** hệ thống SHALL giữ nguyên biến thể hợp lệ cũ
- **AND** hệ thống SHALL trả trạng thái lỗi có thể retry mà không ghi dữ liệu dở dang

#### Scenario: Retry sau lỗi
- **WHEN** lần tạo bộ nội dung đăng trước đó thất bại và người dùng retry
- **THEN** hệ thống SHALL retry đúng phạm vi bị lỗi hoặc stale
- **AND** hệ thống MUST NOT tạo lại story, shot hoặc prompt video hợp lệ nếu các artifact đó không stale

### Requirement: Xóa và reset xử lý artifact bộ nội dung đăng đúng phạm vi
Hệ thống SHALL đưa bộ nội dung đăng video vào vòng đời xóa/reset của AI Video project.

#### Scenario: Reset generated data
- **WHEN** người dùng reset generated data của project nhưng giữ source và cấu hình project
- **THEN** hệ thống SHALL xóa bộ nội dung đăng video cùng các generated artifact khác thuộc phạm vi reset

#### Scenario: Xóa project
- **WHEN** người dùng xác nhận xóa AI Video project
- **THEN** hệ thống SHALL xóa artifact bộ nội dung đăng của project đó
- **AND** hệ thống MUST NOT xóa artifact của project khác

#### Scenario: Xóa hoặc sửa source block
- **WHEN** source block của project đã có bộ nội dung đăng bị xóa hoặc thay đổi
- **THEN** hệ thống SHALL đánh dấu bộ nội dung đăng stale thay vì tiếp tục báo artifact cũ là sẵn sàng
