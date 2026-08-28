## ADDED Requirements

### Requirement: Series xác định phạm vi tạo truyện ảnh, video hoặc cả hai
Hệ thống SHALL cho phép mỗi series có `series_mode` là `image_story_only`, `video_story_only` hoặc `hybrid` và SHALL dùng mode này để quyết định workspace và đầu ra được phép.

#### Scenario: Tạo series truyện ảnh
- **WHEN** người dùng chọn “Series truyện ảnh”
- **THEN** hệ thống SHALL lưu `series_mode = image_story_only`
- **AND** series SHALL khả dụng trong Story Studio
- **AND** hệ thống SHALL không bắt buộc tạo AI Video project

#### Scenario: Tạo series video
- **WHEN** người dùng chọn “Series video”
- **THEN** hệ thống SHALL lưu `series_mode = video_story_only`
- **AND** series SHALL tiếp tục dùng luồng AI Video hiện có
- **AND** hệ thống SHALL không bắt buộc tạo Story Episode

#### Scenario: Tạo series dùng chung
- **WHEN** người dùng chọn “Series truyện + video”
- **THEN** hệ thống SHALL lưu `series_mode = hybrid`
- **AND** Story Studio và AI Video SHALL dùng chung `series_id`, Series Bible, Hồ sơ nhân vật và Series Memory

#### Scenario: Series video cũ chưa có mode
- **WHEN** migration hoặc client cũ gặp một VideoSeries chưa có `series_mode`
- **THEN** hệ thống SHALL coi series đó là `video_story_only`
- **AND** project và episode video cũ SHALL tiếp tục hoạt động như trước

#### Scenario: Story Studio lọc series
- **WHEN** người dùng mở danh sách series trong Story Studio
- **THEN** hệ thống SHALL hiển thị series `image_story_only` và `hybrid`
- **AND** hệ thống SHALL không cho tạo Story Episode trong series `video_story_only`

#### Scenario: AI Video lọc series
- **WHEN** người dùng tạo episode trực tiếp trong AI Video
- **THEN** hệ thống SHALL chỉ cho chọn series `video_story_only`
- **AND** hệ thống SHALL không cho tạo VideoProject trực tiếp trong series `image_story_only`
- **AND** video của series `hybrid` SHALL được tạo bằng handoff từ Story Studio

#### Scenario: Thống kê series hybrid
- **WHEN** series có cả Story Episodes và Video Projects
- **THEN** response quản lý series SHALL phân biệt số tập truyện và số tập video
- **AND** handoff của cùng một tập SHALL giữ cùng episode number

### Requirement: Hồ sơ nhân vật có cấu trúc dùng chung cho series
Hệ thống SHALL cho phép một series lưu nhiều Hồ sơ nhân vật có cấu trúc và SHALL dùng cùng các hồ sơ đó cho Story Studio và AI Video.

#### Scenario: Tạo Hồ sơ nhân vật
- **WHEN** người dùng tạo một nhân vật trong series
- **THEN** profile SHALL yêu cầu tên nhân vật
- **AND** profile SHALL cho phép lưu vai trò, khuôn mặt, tóc, vóc dáng, trang phục đặc trưng, tính cách, cách nói chuyện, những điều không được thay đổi và ghi chú

#### Scenario: Story Studio dùng Hồ sơ nhân vật
- **WHEN** AI phát triển truyện hoặc prompt ảnh cho series có character profiles
- **THEN** AI SHALL dùng các profile đó làm nguồn nhân vật ưu tiên
- **AND** prompt SHALL giữ các fixed traits liên quan

#### Scenario: AI Video dùng cùng Hồ sơ nhân vật
- **WHEN** AI Video phát triển story, scene, shot hoặc prompt video cho series có character profiles
- **THEN** AI Video SHALL đọc cùng các profile theo `series_id`
- **AND** hệ thống MUST NOT tạo một bản Hồ sơ nhân vật độc lập chỉ dành cho AI Video

#### Scenario: Ghi chú riêng của một tập
- **WHEN** một tập thay đổi trang phục, cảm xúc, vết thương hoặc trạng thái tạm thời của nhân vật
- **THEN** hệ thống SHALL lưu thay đổi đó trong context của tập
- **AND** hệ thống MUST NOT tự ghi đè fixed traits cấp series

#### Scenario: AI đề xuất thay đổi nhân vật
- **WHEN** AI đề xuất thêm hoặc sửa Hồ sơ nhân vật hay continuity
- **THEN** hệ thống SHALL hiển thị đề xuất để người dùng duyệt
- **AND** hệ thống MUST NOT cập nhật dữ liệu series trước khi người dùng chấp thuận

#### Scenario: Series cũ chỉ có Character Bible
- **WHEN** series chưa có character profiles nhưng có `character_bible` dạng văn bản
- **THEN** hệ thống SHALL tiếp tục dùng Character Bible làm fallback
- **AND** việc chuyển thành profile có cấu trúc SHALL chỉ tạo đề xuất và MUST NOT xoá hoặc ghi đè nội dung cũ

### Requirement: Series Memory là bản dựng từ nguồn dữ liệu chính
Hệ thống SHALL coi database là nguồn dữ liệu chính và SHALL dựng `series-memory.md` bằng một service chung từ Series Bible, Hồ sơ nhân vật, Story Episodes đã duyệt và Video Projects.

#### Scenario: Series chưa có memory file
- **WHEN** series chưa có `series-memory.md`
- **THEN** hệ thống SHALL dựng file từ dữ liệu series hiện có trước khi AI phát triển nội dung

#### Scenario: Sync memory cho series hybrid
- **WHEN** series hybrid có Story Episodes và Video Projects
- **THEN** memory SHALL chứa Hồ sơ nhân vật và index/summary của cả hai luồng
- **AND** sync lại file MUST NOT làm mất Story Episode đã duyệt hoặc Video Project hiện có

#### Scenario: Một service chịu trách nhiệm ghi memory
- **WHEN** Story Studio hoặc AI Video cần cập nhật memory
- **THEN** chúng SHALL gọi service sync chung
- **AND** chúng MUST NOT tự append hoặc tự ghi một phần độc lập vào `series-memory.md`

### Requirement: Chọn mục tiêu đầu ra phù hợp với series trước khi AI viết
Hệ thống SHALL yêu cầu Story Episode có `output_intent` phù hợp với `series_mode` trước khi AI tạo kịch bản.

#### Scenario: Series truyện ảnh
- **WHEN** series mode là `image_story_only`
- **THEN** Story Episode SHALL dùng `output_intent = truyen_anh`

#### Scenario: Series dùng chung chọn truyện ảnh
- **WHEN** series mode là `hybrid` và người dùng chọn `truyen_anh`
- **THEN** AI SHALL tối ưu kịch bản cho panel rõ, khoảnh khắc hình ảnh mạnh, caption ngắn và prompt ảnh dễ render

#### Scenario: Series dùng chung chọn video
- **WHEN** series mode là `hybrid` và người dùng chọn `video_truyen`
- **THEN** AI SHALL tối ưu kịch bản cho hook, motion beat, scene/shot pacing, narration, retention, SFX và transition

#### Scenario: Series dùng chung chọn cả hai
- **WHEN** series mode là `hybrid` và người dùng chọn `ca_hai`
- **THEN** AI SHALL cân bằng visual anchor cho truyện ảnh và motion beat cho video
- **AND** Master Story cuối MUST dùng được làm nguồn chung cho cả hai adaptation

#### Scenario: Intent không phù hợp mode
- **WHEN** người dùng yêu cầu output intent không được series mode hỗ trợ
- **THEN** hệ thống SHALL chặn bước generate
- **AND** UI SHALL giải thích bằng tiếng Việt đầu ra nào được series hỗ trợ

### Requirement: AI tạo đúng ba hướng kịch bản
Hệ thống SHALL tạo đúng 3 scenario candidates khác hướng từ Series Memory, Hồ sơ nhân vật, nguồn nhập mới, market profile, language profile và output intent.

#### Scenario: Tạo ba candidate
- **WHEN** người dùng yêu cầu phát triển kịch bản cho Story Episode hợp lệ
- **THEN** hệ thống SHALL tạo đúng 3 candidate
- **AND** mỗi candidate SHALL có strategy type, hook, logline, nội dung chính, key beats, visual moments, motion beats, strengths và risks

#### Scenario: Candidate giữ continuity
- **WHEN** series có Series Bible, character profiles hoặc memory
- **THEN** candidate MUST giữ nhân vật, thế giới, style, fixed traits và continuity rules trừ khi người dùng yêu cầu thay đổi rõ ràng

#### Scenario: Candidate theo nguồn nhập mới
- **WHEN** người dùng upload hoặc nhập nội dung mới
- **THEN** AI SHALL dùng nội dung đó làm nguồn chính cho tập hiện tại
- **AND** AI MAY phát triển thêm chi tiết nếu không mâu thuẫn dữ liệu series

### Requirement: Chấm điểm candidate theo mục tiêu đầu ra
Hệ thống SHALL chấm điểm ba candidates bằng rubric thay đổi theo output intent để chọn hoặc tổng hợp bản tốt nhất.

#### Scenario: Rubric truyện ảnh
- **WHEN** output intent là `truyen_anh`
- **THEN** scoring SHALL ưu tiên panel potential, caption/lời thoại, prompt ảnh, consistency nhân vật, bố cục hình ảnh và market fit

#### Scenario: Rubric video
- **WHEN** output intent là `video_truyen`
- **THEN** scoring SHALL ưu tiên hook, motion/action, pacing, narration, retention, SFX/transition và khả năng handoff sang AI Video

#### Scenario: Rubric cả hai
- **WHEN** output intent là `ca_hai`
- **THEN** scoring SHALL cân bằng nội dung, panel potential, video pacing, continuity, visual moments, motion beats và khả năng tái sử dụng

#### Scenario: Chọn hoặc tổng hợp bản thắng
- **WHEN** ba candidates đã có score
- **THEN** hệ thống SHALL cho chọn candidate thắng hoặc tổng hợp bản cuối
- **AND** hệ thống SHALL lưu lý do chọn bằng tiếng Việt

### Requirement: Master Story Episode phải được duyệt trước khi tạo sản phẩm
Hệ thống SHALL lưu bản thắng hoặc bản tổng hợp thành Master Story Episode và SHALL yêu cầu người dùng duyệt trước khi tạo adaptation.

#### Scenario: Master Story có cấu trúc đầy đủ
- **WHEN** hệ thống tạo Master Story Episode
- **THEN** output SHALL có title, logline, hook, full story, key beats, character emotions, visual moments, motion beats, retention plan, market/language profile, must-have, avoid và continuity updates

#### Scenario: Duyệt Master Story
- **WHEN** người dùng duyệt Master Story
- **THEN** hệ thống SHALL lưu trạng thái approved
- **AND** hệ thống SHALL cho phép tạo adaptation được series mode và output intent hỗ trợ

#### Scenario: Chưa duyệt Master Story
- **WHEN** người dùng cố tạo adaptation từ Master Story chưa duyệt
- **THEN** hệ thống SHALL chặn thao tác và hiển thị thông báo tiếng Việt

#### Scenario: Master Story thay đổi
- **WHEN** Master Story đã approved bị thay đổi
- **THEN** hệ thống SHALL huỷ trạng thái approved của Master Story và đưa về chờ duyệt
- **AND** mọi adaptation đã tồn tại liên quan SHALL bị đánh dấu stale
- **AND** hệ thống SHALL chờ người dùng quyết định hành động tiếp theo

### Requirement: Tạo panel và prompt ảnh từ Master Story đã duyệt
Hệ thống SHALL tạo Image Story Adaptation gồm panel, caption/lời thoại, mô tả hình ảnh, prompt và consistency notes từ Master Story đã duyệt.

#### Scenario: Chia thành panel
- **WHEN** người dùng tạo truyện ảnh
- **THEN** hệ thống SHALL chia câu chuyện thành panel theo thứ tự
- **AND** mỗi panel SHALL có mục đích, caption hoặc lời thoại và mô tả hình ảnh

#### Scenario: Tạo prompt ảnh
- **WHEN** panel hợp lệ
- **THEN** mỗi panel SHALL có prompt ảnh, negative prompt, style notes và character consistency notes
- **AND** prompt SHALL dùng các character profiles và fixed traits liên quan

#### Scenario: Prompt ảnh không phá continuity
- **WHEN** prompt mô tả nhân vật, bối cảnh hoặc style
- **THEN** prompt SHALL tham chiếu dữ liệu series và Master Story
- **AND** prompt MUST NOT tự thay đổi fixed traits

### Requirement: Prompt ảnh phải được duyệt trước khi render
Hệ thống SHALL tách trạng thái prompt khỏi trạng thái render và MUST NOT gửi prompt chưa được người dùng duyệt sang image provider.

#### Scenario: Duyệt prompt
- **WHEN** người dùng duyệt một prompt hoặc duyệt toàn bộ prompt hợp lệ
- **THEN** prompt SHALL chuyển sang trạng thái approved
- **AND** chỉ prompt approved mới đủ điều kiện render

#### Scenario: Prompt chưa duyệt
- **WHEN** người dùng yêu cầu render panel có prompt chưa approved
- **THEN** hệ thống SHALL chặn render và yêu cầu duyệt prompt

#### Scenario: Sửa prompt đã duyệt
- **WHEN** nội dung một prompt approved bị thay đổi
- **THEN** hệ thống SHALL đưa prompt về trạng thái chờ duyệt
- **AND** hệ thống MUST NOT dùng approval của nội dung cũ để render prompt mới

#### Scenario: Chưa cấu hình image provider
- **WHEN** prompt đã được duyệt nhưng chưa có image provider hoặc API key
- **THEN** hệ thống SHALL giữ prompt ở trạng thái chờ provider
- **AND** hệ thống SHALL vẫn cho phép lưu hoặc export prompt
- **AND** hệ thống MUST NOT báo ảnh đã render thành công

#### Scenario: Provider được cấu hình sau
- **WHEN** người dùng cấu hình image provider sau khi đã có prompt approved
- **THEN** hệ thống MUST NOT tự động render
- **AND** UI SHALL chờ người dùng chủ động bấm render

#### Scenario: Người dùng bắt đầu render
- **WHEN** người dùng bấm render và provider đã sẵn sàng
- **THEN** hệ thống SHALL chỉ gửi các prompt approved được chọn
- **AND** hệ thống SHALL hiển thị trạng thái queued, rendering, completed hoặc failed

### Requirement: Video truyện handoff sang AI Video và kết thúc bằng MP4
Hệ thống SHALL tạo Video Story Adaptation bằng cách handoff Master Story đã duyệt sang AI Video project liên kết và SHALL dùng pipeline video hiện có để tạo MP4.

#### Scenario: Tạo AI Video project từ Master Story
- **WHEN** người dùng tạo video từ Master Story đã duyệt
- **THEN** hệ thống SHALL tạo hoặc mở AI Video project cùng `series_id` và episode number
- **AND** project SHALL lưu `story_episode_id`, episode metadata và source blocks từ Master Story

#### Scenario: Handoff Hồ sơ nhân vật
- **WHEN** hệ thống handoff sang AI Video
- **THEN** source context SHALL bao gồm character profiles, fixed traits, visual/motion moments, retention, sound notes, must-have và avoid

#### Scenario: Không duplicate pipeline video
- **WHEN** video cần scene, shot, prompt, voice, subtitle, Veo clip hoặc render
- **THEN** hệ thống SHALL dùng pipeline `/ai-video` hiện có
- **AND** Story Studio MUST NOT tự triển khai lại các bước đó

#### Scenario: MP4 hoàn tất
- **WHEN** render job AI Video liên kết hoàn tất
- **THEN** Story Studio SHALL hiển thị trạng thái hoàn tất
- **AND** Story Studio SHALL cung cấp liên kết mở hoặc tải MP4 từ pipeline hiện có

#### Scenario: Series video tạo tập trực tiếp
- **WHEN** series mode là `video_story_only`
- **THEN** người dùng SHALL tiếp tục tạo episode trực tiếp trong AI Video
- **AND** episode SHALL dùng Hồ sơ nhân vật chung của series

### Requirement: Hỗ trợ market và language profile
Hệ thống SHALL cho phép Story Episode có market profile và language profile để AI phát triển nội dung phù hợp.

#### Scenario: Market Việt Nam
- **WHEN** market profile là Việt Nam
- **THEN** AI SHALL tối ưu hook, caption, nhịp kể, cultural tone và mức giải thích cho người xem Việt Nam

#### Scenario: Market quốc tế
- **WHEN** market profile là quốc tế
- **THEN** AI SHALL tối ưu hook, pacing, wording, visual style và CTA theo thị trường mục tiêu

#### Scenario: Language tiếng Việt
- **WHEN** language profile là tiếng Việt
- **THEN** story, caption và narration copy SHALL dùng tiếng Việt trừ field prompt cần tiếng Anh cho provider

#### Scenario: Language tiếng Anh
- **WHEN** language profile là tiếng Anh
- **THEN** story, caption và narration output SHALL dùng tiếng Anh
- **AND** UI và lỗi SHALL vẫn dùng tiếng Việt

### Requirement: Provider được tách vai trò và không tự phát sinh chi phí
Hệ thống SHALL tách planning provider, image provider và video provider, đồng thời SHALL yêu cầu hành động rõ ràng của người dùng trước khi render ảnh.

#### Scenario: Planning provider
- **WHEN** hệ thống viết, chấm điểm, tổng hợp hoặc tạo prompt
- **THEN** hệ thống SHALL dùng planning/content provider và validate output trước khi lưu

#### Scenario: Image provider
- **WHEN** người dùng chủ động render prompt approved
- **THEN** hệ thống SHALL dùng image provider adapter đã cấu hình
- **AND** hệ thống SHALL ghi nhận lỗi provider bằng trạng thái tiếng Việt dễ hiểu

#### Scenario: Video provider
- **WHEN** hệ thống cần tạo clip hoặc MP4
- **THEN** hệ thống SHALL handoff sang pipeline AI Video hiện có

#### Scenario: Không trích cookie web
- **WHEN** provider yêu cầu phiên đăng nhập hoặc automation web
- **THEN** hệ thống MUST NOT tự động đọc, copy, giải mã hoặc lưu cookie/token từ browser cá nhân
- **AND** browser automation nếu có SHALL dùng profile/session riêng và user login thủ công

### Requirement: Change kết thúc ở sản phẩm render
Hệ thống SHALL coi prompt/ảnh truyện và MP4 là sản phẩm cuối của Change 4.

#### Scenario: Hoàn tất truyện ảnh khi chưa có renderer
- **WHEN** chưa có image provider
- **THEN** sản phẩm khả dụng SHALL là panel và bộ prompt đã được duyệt

#### Scenario: Hoàn tất truyện ảnh khi có renderer
- **WHEN** các panel được render thành công
- **THEN** sản phẩm khả dụng SHALL gồm ảnh panel và metadata liên quan

#### Scenario: Hoàn tất video
- **WHEN** AI Video render thành công
- **THEN** sản phẩm cuối SHALL là MP4 của render job liên kết

#### Scenario: Không publish trong Change 4
- **WHEN** ảnh hoặc MP4 đã hoàn tất
- **THEN** hệ thống MUST NOT tự động đăng lên TikTok, YouTube hoặc Facebook trong Change 4
- **AND** social publishing SHALL thuộc một OpenSpec riêng

### Requirement: UI tiếng Việt phản ánh đúng mode và trạng thái
Hệ thống SHALL triển khai UI quản lý series, Hồ sơ nhân vật và Story Studio bằng tiếng Việt tự nhiên.

#### Scenario: Chọn loại series
- **WHEN** người dùng tạo series
- **THEN** UI SHALL hiển thị “Series truyện ảnh”, “Series video” và “Series truyện + video”

#### Scenario: Quản lý Hồ sơ nhân vật
- **WHEN** người dùng mở phần nhân vật của series
- **THEN** UI SHALL hiển thị form có các trường đã định nghĩa
- **AND** cùng dữ liệu SHALL khả dụng từ Story Studio và AI Video

#### Scenario: Hiển thị candidates
- **WHEN** AI đã tạo và chấm điểm candidates
- **THEN** UI SHALL hiển thị đúng 3 hướng, điểm, lý do chọn, điểm mạnh, rủi ro và hành động duyệt

#### Scenario: Hiển thị trạng thái ảnh
- **WHEN** Image Story Adaptation đang được xử lý
- **THEN** UI SHALL phân biệt prompt nháp, chờ duyệt, đã duyệt, chờ provider, đang render, hoàn tất, stale và lỗi

#### Scenario: Hiển thị nhánh video
- **WHEN** Video Story Adaptation đã liên kết AI Video project
- **THEN** UI SHALL cho mở đúng project và hiển thị liên kết MP4 khi hoàn tất

#### Scenario: Không dùng raw status làm nội dung chính
- **WHEN** UI hiển thị lỗi hoặc trạng thái nền
- **THEN** UI SHALL dùng mô tả tiếng Việt tự nhiên
- **AND** raw code chỉ xuất hiện trong debug panel nếu cần
