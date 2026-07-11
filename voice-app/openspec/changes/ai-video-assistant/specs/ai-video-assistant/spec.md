## ADDED Requirements

### Requirement: Tạo video project từ một ý tưởng ngắn
Hệ thống SHALL cho phép người dùng non-tech tạo AI video project bằng cách nhập một chủ đề hoặc ý tưởng ngắn và các tùy chọn cơ bản cho bộ nguyên liệu dựng video.

#### Scenario: Người dùng bắt đầu một video project
- **WHEN** người dùng nhập chủ đề và chọn các tùy chọn như ngôn ngữ, thời lượng mục tiêu, tỷ lệ khung hình, phong cách hình ảnh và voice profile
- **THEN** hệ thống tạo video project và lưu chủ đề, tùy chọn và trạng thái draft ban đầu

#### Scenario: Người dùng chỉ nhập thông tin tối thiểu
- **WHEN** người dùng chỉ nhập chủ đề
- **THEN** hệ thống dùng giá trị mặc định an toàn cho ngôn ngữ, thời lượng mục tiêu, tỷ lệ khung hình, phong cách hình ảnh và voice settings

### Requirement: Dùng tiếng Việt làm ngôn ngữ mặc định của workflow
Hệ thống SHALL hiển thị workflow AI Video Assistant bằng tiếng Việt mặc định cho người dùng, đồng thời vẫn cho phép mở rộng i18n sau này.

#### Scenario: Người dùng mở AI Video Assistant
- **WHEN** người dùng mở trang AI Video Assistant
- **THEN** hệ thống hiển thị các bước, nút bấm, thông báo lỗi và hướng dẫn chính bằng tiếng Việt dễ hiểu

#### Scenario: Nội dung kỹ thuật tồn tại trong hệ thống
- **WHEN** hệ thống lưu JSON, generation ID, file path nội bộ hoặc metadata package
- **THEN** giao diện mặc định không bắt người dùng đọc các nội dung kỹ thuật đó

### Requirement: Cấu hình và kiểm tra Codex CLI cho AI planning
Hệ thống SHALL dùng Codex CLI trong máy làm provider mặc định cho bước sinh kịch bản và prompt, thông qua setting có thể kiểm tra được từ UI/backend.

#### Scenario: Codex CLI khả dụng
- **WHEN** backend kiểm tra setting `provider=codex-cli` với `codex_path` hợp lệ và Codex CLI đã đăng nhập
- **THEN** hệ thống đánh dấu planning provider sẵn sàng và cho phép người dùng sinh kịch bản/prompt

#### Scenario: Codex CLI không khả dụng
- **WHEN** `codex_path` không tồn tại, lệnh `codex exec` lỗi, timeout hoặc Codex CLI chưa đăng nhập
- **THEN** hệ thống không chạy planning, ghi log chi tiết an toàn và trả thông báo tiếng Việt kèm request ID để người dùng biết cần kiểm tra Codex CLI

#### Scenario: Lỗi Codex CLI hiển thị ngay trong wizard
- **WHEN** Codex CLI chưa sẵn sàng tại bước người dùng đang thao tác trong wizard
- **THEN** hệ thống hiển thị thông báo và nút kiểm tra/thử lại ngay tại bước đó, không bắt người dùng tự tìm vào trang Settings

#### Scenario: Planning provider được đổi trong tương lai
- **WHEN** setting provider không phải `codex-cli`
- **THEN** hệ thống chỉ dùng provider đó nếu backend đã implement rõ ràng, nếu không phải trả lỗi cấu hình thân thiện

### Requirement: Sinh kịch bản và scene có cấu trúc
Hệ thống SHALL dùng Codex CLI-assisted generation để chuyển ý tưởng video thành kịch bản có cấu trúc và chia thành các scene.

#### Scenario: Sinh kịch bản thành công
- **WHEN** người dùng yêu cầu sinh kịch bản cho project
- **THEN** hệ thống lưu creative brief, kịch bản hoàn chỉnh và danh sách scene theo thứ tự với lời thoại, mô tả hình ảnh và thời lượng dự kiến

#### Scenario: Output Codex CLI không hợp lệ
- **WHEN** Codex CLI trả output không đúng schema hoặc thiếu scene bắt buộc
- **THEN** hệ thống không lưu artifact hỏng, ghi log validation error và cho phép người dùng retry

#### Scenario: Người dùng duyệt kịch bản đã sinh
- **WHEN** sinh kịch bản hoàn tất
- **THEN** hệ thống hiển thị kịch bản và danh sách scene ở màn hình duyệt dễ đọc trước khi tiếp tục tạo prompt hoặc voice

#### Scenario: Người dùng sinh lại kịch bản của một scene
- **WHEN** người dùng yêu cầu sinh lại một scene
- **THEN** hệ thống chỉ cập nhật lời thoại, mô tả hình ảnh và thời lượng dự kiến của scene đó mà không xóa các scene đã duyệt khác

#### Scenario: Người dùng duyệt và làm việc theo từng scene
- **WHEN** người dùng duyệt một scene riêng lẻ trong khi các scene khác chưa duyệt
- **THEN** hệ thống cho phép tạo prompt và tạo giọng đọc cho riêng scene đã duyệt đó mà không bắt phải duyệt toàn bộ kịch bản trước

#### Scenario: Người dùng sửa scene đã có prompt hoặc voice
- **WHEN** người dùng sửa lời thoại hoặc mô tả hình ảnh của một scene đã có prompt ảnh, giọng đọc hoặc subtitle
- **THEN** hệ thống đánh dấu prompt ảnh, giọng đọc và subtitle của scene đó là cần làm lại, đồng thời đánh dấu package liên quan là cũ

### Requirement: Sinh prompt ảnh dễ copy cho từng scene
Hệ thống SHALL sinh prompt ảnh để người dùng copy sang công cụ tạo ảnh bên ngoài cho từng scene.

#### Scenario: Sinh prompt pack thành công
- **WHEN** project có các scene đã được duyệt
- **THEN** hệ thống tạo prompt pack cho từng scene gồm main prompt, negative prompt, tỷ lệ khung hình, ghi chú phong cách và ghi chú giữ nhất quán nhân vật/phong cách

#### Scenario: Người dùng copy prompt của một scene
- **WHEN** người dùng bấm Copy Prompt cho một scene
- **THEN** hệ thống copy nội dung prompt hoàn chỉnh của scene đó mà không yêu cầu người dùng đọc JSON hoặc metadata nội bộ

#### Scenario: Scene có nhân vật lặp lại
- **WHEN** nhiều scene cùng dùng một nhân vật
- **THEN** hệ thống đưa ghi chú nhận diện nhân vật nhất quán vào mỗi prompt scene liên quan

### Requirement: Nhận ảnh preview cho từng scene
Hệ thống SHALL cho phép người dùng upload ảnh đã tạo từ công cụ bên ngoài và gắn ảnh đó với từng scene để xem trước, nhưng không bắt buộc ảnh preview để tải package MVP.

#### Scenario: Người dùng upload ảnh preview cho scene
- **WHEN** người dùng upload file ảnh được hỗ trợ cho một scene
- **THEN** hệ thống lưu file, đánh dấu scene đã có ảnh preview và hiển thị preview trong wizard

#### Scenario: Người dùng thay ảnh preview của scene
- **WHEN** người dùng upload ảnh mới cho scene đã có ảnh preview
- **THEN** hệ thống giữ liên kết scene và cập nhật active preview image sang file mới upload

#### Scenario: Người dùng tải package khi chưa có ảnh preview
- **WHEN** người dùng tải bộ nguyên liệu trong khi một số scene chưa có ảnh preview
- **THEN** hệ thống vẫn cho phép tải nếu prompt, voice bắt buộc và subtitle đã sẵn sàng, đồng thời ghi rõ ảnh preview là tùy chọn

### Requirement: Tạo giọng đọc bằng voice hiện có của Voicebox
Hệ thống SHALL tạo narration audio cho từng scene bằng voice profile và behavior TTS hiện có của Voicebox.

#### Scenario: Người dùng tạo voice cho toàn bộ scene
- **WHEN** người dùng yêu cầu tạo voice cho các scene đã duyệt
- **THEN** hệ thống gửi lời thoại từng scene vào voice profile đã chọn và lưu generation ID, status, audio path hoặc audio URL và duration thật cho từng scene

#### Scenario: Tạo voice lỗi ở một scene
- **WHEN** tạo voice lỗi ở một scene
- **THEN** hệ thống chỉ đánh dấu scene đó là failed và cho phép retry mà không tạo lại audio của các scene đã hoàn tất

#### Scenario: Người dùng đổi voice profile
- **WHEN** người dùng đổi voice profile của video project
- **THEN** hệ thống báo rằng narration hiện tại có thể cần tạo lại trước khi tạo subtitle hoặc tải package

#### Scenario: Scene được đánh dấu cố ý không lời
- **WHEN** người dùng đánh dấu một scene là không cần narration, ví dụ title card, cảnh chuyển hoặc b-roll
- **THEN** hệ thống coi scene đó là hoàn tất về voice, không yêu cầu tạo giọng đọc và không tính scene đó là thiếu narration khi kiểm tra điều kiện tải package

### Requirement: Tạo phụ đề SRT từ lời thoại và timing audio
Hệ thống SHALL tạo subtitle `.srt` cho Premiere từ lời thoại scene và duration thật của audio đã tạo.

#### Scenario: Tạo subtitle sau khi có narration
- **WHEN** toàn bộ narration bắt buộc đã hoàn tất
- **THEN** hệ thống tạo subtitle cues theo thứ tự scene và duration audio thật của từng scene, bỏ qua các scene đã đánh dấu cố ý không lời

#### Scenario: Text phụ đề quá dài
- **WHEN** lời thoại scene quá dài cho một subtitle cue
- **THEN** hệ thống chia lời thoại thành các subtitle cue dễ đọc và phù hợp tỷ lệ video đã chọn

#### Scenario: Người dùng tải file phụ đề
- **WHEN** người dùng tải subtitle file
- **THEN** hệ thống trả file `.srt` với tên tiếng Việt đã sanitize, ví dụ `Phụ đề - <Tên dự án>.srt`

### Requirement: Tải bộ nguyên liệu cho Premiere
Hệ thống SHALL cho phép người dùng lấy nguyên liệu dựng video bằng copy/tải lẻ từng phần và bằng một file `.zip` chứa prompt, voice, subtitle, manifest và ảnh preview nếu có.

#### Scenario: Người dùng tải lẻ prompt của một scene
- **WHEN** người dùng tải prompt của một scene
- **THEN** hệ thống trả file text với tên tiếng Việt đã sanitize, ví dụ `Prompt ảnh - Cảnh 01.txt`

#### Scenario: Người dùng tải lẻ audio của một scene
- **WHEN** người dùng tải voice đã tạo của một scene
- **THEN** hệ thống trả file audio với tên tiếng Việt đã sanitize, ví dụ `Giọng đọc - Cảnh 01.wav`

#### Scenario: Người dùng tải tất cả nguyên liệu
- **WHEN** project có prompt, narration bắt buộc và subtitle đã sẵn sàng
- **THEN** hệ thống tạo file `.zip` gồm prompt từng scene, audio từng scene, subtitle `.srt`, manifest dễ đọc và ảnh preview nếu có

#### Scenario: Project chưa đủ điều kiện tải package
- **WHEN** người dùng bấm Tải tất cả trong khi còn scene có lời thoại nhưng thiếu narration bắt buộc hoặc subtitle chưa tạo
- **THEN** hệ thống chặn tạo package và chỉ rõ scene hoặc bước còn thiếu bằng tiếng Việt, không tính các scene đã đánh dấu cố ý không lời là thiếu

### Requirement: Tên file tải về bằng tiếng Việt thân thiện
Hệ thống SHALL cung cấp tên file tiếng Việt dễ hiểu cho các file người dùng tải về, trong khi storage nội bộ vẫn dùng tên an toàn.

#### Scenario: Người dùng tải package cuối
- **WHEN** người dùng tải bộ nguyên liệu hoàn tất
- **THEN** hệ thống trả file với tên tiếng Việt đã sanitize, ví dụ `Bộ nguyên liệu - <Tên dự án>.zip`

#### Scenario: Người dùng tải prompt, voice hoặc phụ đề
- **WHEN** người dùng tải prompt pack, scene voice hoặc subtitle file
- **THEN** hệ thống trả file với tên tiếng Việt đã sanitize, ví dụ `Prompt ảnh - Cảnh 01.txt`, `Giọng đọc - Cảnh 01.wav` hoặc `Phụ đề - <Tên dự án>.srt`

#### Scenario: Tên dự án có ký tự không an toàn
- **WHEN** tên dự án chứa ký tự không hợp lệ cho filename
- **THEN** hệ thống loại bỏ hoặc thay thế ký tự đó nhưng vẫn giữ tên file dễ hiểu cho người dùng

### Requirement: Lưu và resume trạng thái video workflow
Hệ thống SHALL lưu trạng thái video project để người dùng có thể rời đi và tiếp tục sau.

#### Scenario: Người dùng mở lại project chưa hoàn tất
- **WHEN** người dùng mở một video project chưa hoàn tất
- **THEN** hệ thống khôi phục topic, scene, prompt, ảnh preview đã upload, trạng thái voice, trạng thái subtitle và trạng thái package

#### Scenario: Người dùng sửa project sau khi đã tải package
- **WHEN** người dùng thay đổi script, prompt, image preview, voice hoặc subtitle sau khi đã tạo package
- **THEN** hệ thống đánh dấu package cũ có thể đã lỗi thời và cho phép tạo package mới

### Requirement: Giao diện wizard cho người không rành kỹ thuật
Hệ thống SHALL hiển thị AI video workflow dưới dạng wizard có hành động rõ ràng, thay vì bắt người dùng hiểu API hoặc khái niệm kỹ thuật.

#### Scenario: Người dùng đi qua các bước tạo nguyên liệu video
- **WHEN** người dùng mở AI Video Assistant
- **THEN** hệ thống hiển thị các bước rõ ràng: nhập ý tưởng, duyệt kịch bản, làm prompt/ảnh preview, tạo voice, tạo phụ đề và tải nguyên liệu

#### Scenario: Có thông tin kỹ thuật nâng cao
- **WHEN** hệ thống lưu metadata kỹ thuật như prompt JSON, generation ID, file path, package manifest hoặc request ID
- **THEN** UI mặc định ẩn các thông tin đó trừ khi người dùng mở advanced/debug view

### Requirement: UI mới đạt chuẩn `design-taste-frontend-v1`
Hệ thống SHALL triển khai các màn hình mới của AI Video Assistant theo chuẩn visual design cao cấp, dễ dùng, không generic và phù hợp người dùng non-tech.

#### Scenario: Màn hình đầu tiên là workflow usable
- **WHEN** người dùng mở AI Video Assistant
- **THEN** màn hình đầu tiên hiển thị trực tiếp form nhập ý tưởng và trạng thái/preview project, không phải landing page marketing hoặc hero căn giữa

#### Scenario: Layout desktop có nhịp bất đối xứng có kiểm soát
- **WHEN** người dùng mở wizard trên desktop
- **THEN** UI dùng bố cục split/asymmetric hoặc grid có trọng tâm rõ ràng, tránh pattern 3 card ngang bằng nhau cho các bước chính

#### Scenario: Layout mobile collapse an toàn
- **WHEN** người dùng mở wizard trên màn hình nhỏ hơn tablet
- **THEN** toàn bộ layout collapse thành một cột, không horizontal scroll, không text overlap và không dùng `h-screen` cho vùng full-height

#### Scenario: Style không dùng dấu hiệu AI generic
- **WHEN** UI mới được hiển thị
- **THEN** hệ thống không dùng emoji, neon glow, gradient text quá đà, palette tím/xanh AI sáo mòn hoặc màu accent quá bão hòa

#### Scenario: Wizard có đầy đủ state cho từng bước
- **WHEN** một bước đang loading, chưa có dữ liệu hoặc gặp lỗi
- **THEN** UI hiển thị skeleton/loading state đúng layout, empty state có hướng dẫn rõ ràng và error state inline bằng tiếng Việt

#### Scenario: Form non-tech dễ đọc
- **WHEN** người dùng nhập topic, chọn voice, chọn tỷ lệ video, upload ảnh preview hoặc chuẩn bị tải package
- **THEN** mỗi field có label phía trên, helper text hoặc error text phía dưới và khoảng cách nhất quán

#### Scenario: Motion không gây nặng UI
- **WHEN** UI dùng animation cho progress, status, copy prompt, upload hoặc package export
- **THEN** animation chỉ dùng transform/opacity hoặc Framer Motion đã được cô lập, không animate top/left/width/height và không gây re-render nặng ở parent wizard

#### Scenario: Dependency icon/motion được kiểm tra
- **WHEN** implementation cần import icon hoặc motion library mới theo chuẩn thiết kế
- **THEN** developer phải xác minh package tồn tại trong `package.json` hoặc thêm dependency rõ ràng trước khi import

### Requirement: Log lỗi chi tiết để dễ debug
Hệ thống SHALL ghi log lỗi chi tiết cho các bước API, Codex CLI planning, upload ảnh preview, voice generation, subtitle generation và package export, đồng thời trả lỗi thân thiện cho UI.

#### Scenario: API request lỗi
- **WHEN** một API của AI Video Assistant trả lỗi
- **THEN** hệ thống ghi log có request ID, project ID nếu có, endpoint, step name, error code, exception class và stack trace server-side

#### Scenario: Codex CLI planning hoặc prompt generation lỗi
- **WHEN** Codex CLI trả lỗi, timeout hoặc output không qua validation
- **THEN** hệ thống ghi log provider/model, project ID, step name, exit code nếu có, validation errors và request ID mà không log secret hoặc token

#### Scenario: Upload image preview lỗi
- **WHEN** người dùng upload file ảnh không hợp lệ hoặc quá lớn
- **THEN** hệ thống ghi log project ID, scene ID, filename đã sanitize, MIME/type, size, lý do reject và request ID

#### Scenario: Package export lỗi
- **WHEN** hệ thống không tạo được file `.zip` hoặc thiếu artifact bắt buộc
- **THEN** hệ thống ghi log project ID, package step, artifact còn thiếu, exception class và request ID

#### Scenario: UI nhận lỗi
- **WHEN** backend trả lỗi cho frontend
- **THEN** UI hiển thị thông báo tiếng Việt dễ hiểu kèm mã lỗi hoặc request ID để người dùng gửi cho người phát triển

### Requirement: Giữ tương thích với workflow voice hiện có
Hệ thống SHALL thêm video workflow mà không làm hỏng voice profile, TTS generation, history, audio import hoặc story timeline hiện có.

#### Scenario: TTS hiện có vẫn hoạt động
- **WHEN** người dùng tạo speech từ editor Voicebox hiện có
- **THEN** hệ thống vẫn tạo và serve audio bằng flow generation hiện tại

#### Scenario: Story audio export hiện có vẫn hoạt động
- **WHEN** người dùng export một Story hiện có thành audio
- **THEN** hệ thống vẫn export mixed audio mà không yêu cầu video project data
