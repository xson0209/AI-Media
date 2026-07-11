## ADDED Requirements

### Requirement: Route riêng cho workflow lấy cảm hứng từ video
Hệ thống SHALL cung cấp một route frontend và API backend riêng cho workflow lấy cảm hứng từ video, tách khỏi route AI Video hiện tại.

#### Scenario: Mở màn lấy cảm hứng từ video
- **WHEN** người dùng mở route `/video-inspiration`
- **THEN** hệ thống hiển thị workspace `Lấy cảm hứng từ video` bằng tiếng Việt
- **AND** workspace này không nằm trong component AI Video Assistant hiện tại

#### Scenario: Backend dùng API prefix riêng
- **WHEN** frontend tạo job, upload video, gửi link, chạy phân tích hoặc viết lại kịch bản
- **THEN** frontend gọi endpoint dưới `/video-inspiration`
- **AND** hệ thống MUST NOT thêm endpoint ingestion mới dưới `/ai-video`

#### Scenario: Đưa kịch bản sang form AI Video
- **WHEN** người dùng có kịch bản mới và bấm `Đưa vào form AI Video`
- **THEN** hệ thống mở `/ai-video?draft=video-inspiration`
- **AND** hệ thống điền sẵn form tạo dự án AI Video bằng kết quả đã duyệt và dữ liệu phân tích
- **AND** hệ thống chưa tạo project hoặc bắt đầu auto-run cho tới khi người dùng tự cấu hình và bấm tạo trong AI Video

### Requirement: Nhập video bằng upload MP4 hoặc link công khai
Hệ thống SHALL cho phép người dùng đưa nguồn video vào bằng upload `.mp4` hoặc link công khai theo kiểu best-effort.

#### Scenario: Upload MP4 hợp lệ
- **WHEN** người dùng upload file `.mp4` hợp lệ trong giới hạn dung lượng/thời lượng
- **THEN** hệ thống tạo một video inspiration job và lưu source video vào storage của job

#### Scenario: Upload file không hợp lệ
- **WHEN** người dùng upload file không phải video hợp lệ hoặc vượt giới hạn
- **THEN** hệ thống từ chối bằng thông báo tiếng Việt dễ hiểu
- **AND** không tạo artifact mồ côi trong storage

#### Scenario: Nhập link công khai
- **WHEN** người dùng dán link công khai từ YouTube, TikTok, Facebook hoặc Instagram
- **THEN** hệ thống thử lấy video bằng downloader adapter
- **AND** nếu lấy được thì tạo job giống luồng upload

#### Scenario: Máy chưa cài FFmpeg global
- **WHEN** máy người dùng chưa có `ffmpeg` hoặc `ffprobe` trong PATH
- **THEN** workflow link import SHALL dùng FFmpeg đóng gói trong backend venv của project khi có
- **AND** hệ thống SHALL không yêu cầu người dùng cài FFmpeg global chỉ để nhận link video công khai

#### Scenario: Nền tảng trả video và audio tách riêng
- **WHEN** downloader lấy được một stream video và một stream audio riêng từ link công khai
- **THEN** hệ thống SHALL ghép hai stream thành một file MP4 nguồn có cả hình và tiếng
- **AND** job SHALL lưu file đã ghép làm `source_path` để bước tách lời nói dùng đúng audio

#### Scenario: Link bị nền tảng chặn
- **WHEN** link cần đăng nhập, private, DRM, CAPTCHA, livestream hoặc downloader không lấy được media
- **THEN** hệ thống báo rõ bằng tiếng Việt rằng link này chưa tải được
- **AND** UI đề nghị người dùng upload file `.mp4` thay thế

#### Scenario: Link công khai cần phiên đăng nhập trình duyệt
- **WHEN** nền tảng yêu cầu xác minh đăng nhập cho một link người dùng có quyền xem
- **THEN** UI SHALL cho người dùng tự bật tùy chọn dùng phiên đăng nhập trình duyệt
- **AND** hệ thống SHALL chỉ dùng cookie trình duyệt trong lần tải đó khi người dùng bật rõ ràng
- **AND** hệ thống MUST NOT lưu cookie hoặc token đăng nhập vào database

#### Scenario: Không bypass nền tảng
- **WHEN** link không thể truy cập công khai
- **THEN** hệ thống MUST NOT cố bypass paywall, login, quyền riêng tư hoặc CAPTCHA

### Requirement: Tách lời nói trong video thành transcript
Hệ thống SHALL tách audio từ video và chuyển lời nói thành chữ để người dùng xem và sửa.

#### Scenario: Video có lời nói
- **WHEN** job có source video hợp lệ và audio track có lời nói
- **THEN** hệ thống trích audio bằng FFmpeg
- **AND** hệ thống dùng Whisper backend hiện có để tạo transcript
- **AND** transcript được lưu trên job để người dùng xem lại

#### Scenario: Người dùng sửa transcript
- **WHEN** người dùng sửa transcript trong UI
- **THEN** hệ thống lưu transcript mới
- **AND** lần phân tích hoặc rewrite sau đó dùng transcript đã sửa làm nguồn

#### Scenario: Video không có lời nói rõ ràng
- **WHEN** Whisper không phát hiện lời nói rõ ràng hoặc transcript rỗng
- **THEN** hệ thống hiển thị trạng thái tiếng Việt rằng video không có lời nói rõ ràng
- **AND** hệ thống không bịa transcript

### Requirement: Phân tích hình ảnh trong video
Hệ thống SHALL phân tích hình ảnh của video bằng frame đại diện và vision analyzer khi provider sẵn sàng.

#### Scenario: Trích frame đại diện
- **WHEN** job chạy visual analysis
- **THEN** hệ thống dùng FFmpeg/FFprobe lấy metadata và frame đại diện theo thời gian hoặc scene-change
- **AND** hệ thống giới hạn số frame để tránh quá tải

#### Scenario: Vision provider sẵn sàng
- **WHEN** vision analyzer đã được cấu hình và frame đại diện đã có
- **THEN** hệ thống phân tích từng frame thành mô tả tiếng Việt
- **AND** hệ thống tạo visual summary gồm bối cảnh, nhân vật/chủ thể, mood, ánh sáng, camera/framing và khoảnh khắc đáng chú ý

#### Scenario: Vision provider chưa sẵn sàng
- **WHEN** người dùng yêu cầu phân tích hình ảnh nhưng vision analyzer chưa sẵn sàng
- **THEN** hệ thống báo rõ cần cấu hình công cụ phân tích hình ảnh
- **AND** hệ thống MUST NOT tạo phân tích hình ảnh giả từ transcript

### Requirement: Phân tích nội dung video gốc trước khi viết lại
Hệ thống SHALL tổng hợp transcript và visual summary thành bản phân tích tiếng Việt trước khi viết kịch bản mới.

#### Scenario: Phân tích đầy đủ
- **WHEN** transcript và visual summary có sẵn
- **THEN** hệ thống tạo analysis gồm ý chính, hook, cấu trúc, nhân vật/bối cảnh, nhịp dựng, điểm mạnh, điểm yếu và cơ hội viết mới

#### Scenario: Thiếu visual analysis
- **WHEN** chỉ có transcript và người dùng chọn tiếp tục audio-only
- **THEN** analysis phải ghi rõ phần hình ảnh chưa được phân tích
- **AND** hệ thống không nói như thể đã xem hình ảnh

### Requirement: Viết mới mạnh tay từ cảm hứng video gốc
Hệ thống SHALL tạo kịch bản mới theo chế độ `bold_remix`, lấy cảm hứng từ video gốc nhưng không sao chép sát.

#### Scenario: Rewrite mặc định là viết mới mạnh tay
- **WHEN** người dùng bấm viết kịch bản mới
- **THEN** hệ thống dùng rewrite mode `bold_remix`
- **AND** kịch bản mới có thể thay hook, cấu trúc, ví dụ, cách kể, nhịp dựng và payoff

#### Scenario: Không paraphrase sát video gốc
- **WHEN** hệ thống tạo rewritten script
- **THEN** output MUST NOT chỉ đổi câu chữ từ transcript gốc
- **AND** output phải có phần nhắc rằng đây là bản phát triển mới từ cảm hứng, không phải bản chép lại

#### Scenario: Có cấu trúc dễ dùng cho AI Video
- **WHEN** rewrite hoàn tất
- **THEN** kết quả gồm tên ý tưởng mới, big idea, hook, script/narration chính, outline cảnh/segment và gợi ý hình ảnh

### Requirement: Cho chọn tiếng Việt hoặc tiếng Anh cho kịch bản mới
Hệ thống SHALL cho phép người dùng chọn ngôn ngữ của kịch bản mới là tiếng Việt hoặc tiếng Anh, trong khi UI vẫn hiển thị tiếng Việt.

#### Scenario: Viết kịch bản mới tiếng Việt
- **WHEN** người dùng chọn output language `Tiếng Việt`
- **THEN** rewritten script được viết bằng tiếng Việt
- **AND** UI, helper text, progress, lỗi và analysis vẫn là tiếng Việt

#### Scenario: Viết kịch bản mới tiếng Anh
- **WHEN** người dùng chọn output language `Tiếng Anh`
- **THEN** rewritten script/narration chính được viết bằng tiếng Anh
- **AND** phần giải thích trong UI vẫn là tiếng Việt để người dùng hiểu

#### Scenario: Đổi ngôn ngữ và viết lại
- **WHEN** người dùng đổi output language sau khi đã có script
- **THEN** hệ thống cho chạy rewrite lại theo ngôn ngữ mới
- **AND** không làm mất transcript gốc hoặc visual analysis đã lưu

### Requirement: Đưa kịch bản mới vào form AI Video để người dùng cấu hình trước
Hệ thống SHALL cho phép người dùng đưa rewritten script và toàn bộ ngữ cảnh phân tích sang form tạo dự án AI Video, nhưng SHALL NOT tạo project hoặc chạy auto-run cho tới khi người dùng tự cấu hình và bấm tạo trong AI Video.

#### Scenario: Đưa script tiếng Việt vào form AI Video
- **WHEN** rewritten script có output language `vi` và người dùng bấm đưa vào form AI Video
- **THEN** frontend mở `/ai-video?draft=video-inspiration`
- **AND** draft ghi chú ngôn ngữ của bản rewrite trong ô nội dung phù hợp
- **AND** hệ thống SHALL NOT tự ghi đè lựa chọn ngôn ngữ cuối cùng của form AI Video
- **AND** hệ thống chưa tạo AI Video project mới

#### Scenario: Đưa script tiếng Anh vào form AI Video
- **WHEN** rewritten script có output language `en` và người dùng bấm đưa vào form AI Video
- **THEN** frontend mở `/ai-video?draft=video-inspiration`
- **AND** draft ghi chú ngôn ngữ của bản rewrite trong ô nội dung phù hợp
- **AND** hệ thống SHALL NOT tự ghi đè lựa chọn ngôn ngữ cuối cùng của form AI Video
- **AND** UI route mới chưa ghi `created_video_project_id` chỉ vì mở form draft

#### Scenario: Điền đủ các ô nguồn của AI Video
- **WHEN** draft được đưa sang AI Video
- **THEN** form SHALL điền `Tên dự án`, `Ý tưởng chính`, `Kịch bản thô`, `Nhân vật và bối cảnh`, `Phong cách video`, `Bắt buộc phải có`, `Cần tránh` và `Phong cách hình ảnh`
- **AND** dữ liệu điền vào SHALL bao gồm rewritten script, big idea, hook, segment outline, transcript gốc, visual summary, mô tả frame đại diện, nhịp hình ảnh, điểm mạnh, điểm yếu, cơ hội viết mới, ghi chú phân tích và định hướng người dùng khi có

#### Scenario: Không chạy ngay sau khi chuyển form
- **WHEN** AI Video nhận draft từ Video Inspiration
- **THEN** AI Video SHALL đặt cách tạo project về `Thủ công`
- **AND** hệ thống SHALL NOT gọi AI Video auto-run hoặc `material_target = "full_materials"`
- **AND** draft SHALL NOT tự set thị trường/mục đích video, ngôn ngữ cuối cùng, thời lượng, số prompt, tỷ lệ, voice profile hoặc output auto-run
- **AND** người dùng SHALL tự chọn thị trường/mục đích video, ngôn ngữ, thời lượng, tỷ lệ, voice profile và cách chạy trước khi bấm tạo

#### Scenario: API tạo project cũ không tự chạy nếu thiếu yêu cầu rõ
- **WHEN** caller gọi endpoint `/video-inspiration/jobs/{job_id}/create-ai-video-project` mà không đặt `start_full_materials = true`
- **THEN** hệ thống MAY tạo project phase 2 theo API cũ
- **BUT** hệ thống SHALL NOT bắt đầu auto-run

### Requirement: Trạng thái, lỗi và quyền riêng tư dễ hiểu
Hệ thống SHALL hiển thị trạng thái và lỗi bằng tiếng Việt, đồng thời không log dữ liệu nhạy cảm quá mức.

#### Scenario: Progress non-tech
- **WHEN** job đang chạy
- **THEN** UI hiển thị các bước như `Đang lấy video`, `Đang tách lời nói`, `Đang phân tích hình ảnh`, `Đang viết kịch bản mới`
- **AND** UI không yêu cầu người dùng hiểu các thuật ngữ như ASR, frame sampling hoặc provider adapter

#### Scenario: Lỗi có hành động tiếp theo
- **WHEN** job fail do link, FFmpeg, Whisper, vision provider hoặc file không hợp lệ
- **THEN** UI hiển thị lỗi tiếng Việt và gợi ý hành động tiếp theo như upload file, chọn video khác hoặc cấu hình công cụ còn thiếu

#### Scenario: Log không chứa dữ liệu quá dài hoặc nhạy cảm
- **WHEN** hệ thống ghi debug event hoặc technical details
- **THEN** hệ thống MUST NOT log full transcript dài, full rewritten script, binary frame, video binary hoặc URL có token nhạy cảm
- **AND** technical details chỉ lưu metadata, count, ids, trạng thái hoặc preview đã rút gọn

### Requirement: Định hướng thêm ý tưởng của người dùng
Hệ thống SHALL cho phép người dùng nhập một định hướng phát triển thêm không bắt buộc để kịch bản mới và phần chuyển sang AI Video bám sát suy nghĩ của người dùng hơn.

#### Scenario: Nhập định hướng trước khi viết lại
- **WHEN** người dùng nhập định hướng như `làm thành video người que 3D, giữ chủ đề nhân quả`
- **AND** người dùng bấm viết kịch bản mới
- **THEN** rewrite prompt SHALL bao gồm định hướng đó
- **AND** kịch bản mới SHALL dùng định hướng đó cho phong cách, nhân vật, bối cảnh, hình thức thể hiện và visual suggestions khi phù hợp

#### Scenario: Bỏ trống định hướng vẫn chạy bình thường
- **WHEN** người dùng không nhập định hướng thêm
- **THEN** upload/link import, analyze, rewrite và chuyển sang AI Video SHALL vẫn hoạt động như trước
- **AND** hệ thống MUST NOT bắt người dùng nhập ô này

#### Scenario: Sửa định hướng sau khi đã có kịch bản
- **WHEN** người dùng đổi hoặc xóa định hướng đã lưu
- **THEN** hệ thống SHALL lưu định hướng mới
- **AND** hệ thống SHALL xóa kịch bản đã rewrite trước đó để tránh dùng bản cũ không còn đúng ý người dùng

#### Scenario: Chuyển định hướng sang AI Video
- **WHEN** người dùng đưa kịch bản sang form AI Video
- **THEN** draft SHALL bao gồm định hướng của người dùng khi có
- **AND** ô `Phong cách hình ảnh` hoặc các ô nguồn của form SHALL giúp AI Video biết định hướng như `người que 3D`, chủ đề, tone hoặc format người dùng đã nhập
