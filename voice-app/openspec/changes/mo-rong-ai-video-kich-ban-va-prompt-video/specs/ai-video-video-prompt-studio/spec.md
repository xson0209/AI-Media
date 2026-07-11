## ADDED Requirements

### Requirement: Nhập nhiều nguồn nội dung cho video project
Hệ thống SHALL cho phép người dùng tạo hoặc cập nhật AI video project bằng nhiều nguồn nội dung có cấu trúc, không chỉ một chủ đề ngắn.

#### Scenario: Người dùng nhập nhiều loại nội dung
- **WHEN** người dùng nhập ý tưởng chính, ý tưởng phụ, kịch bản thô, dàn ý, ghi chú nhân vật, phong cách video, đối tượng xem, điều bắt buộc hoặc điều cần tránh
- **THEN** hệ thống lưu từng nguồn nội dung với loại, thứ tự và nội dung tương ứng để AI planning sử dụng khi phát triển kịch bản

#### Scenario: Người dùng chỉ nhập ý tưởng chính
- **WHEN** người dùng chỉ nhập một ý tưởng chính
- **THEN** hệ thống vẫn tạo project hợp lệ và dùng các giá trị mặc định an toàn cho những nguồn nội dung còn thiếu

#### Scenario: Người dùng sửa nguồn nội dung sau khi đã có kịch bản
- **WHEN** người dùng sửa, thêm, xóa hoặc sắp xếp lại nguồn nội dung sau khi project đã có script, shot hoặc prompt video
- **THEN** hệ thống đánh dấu script, shot, prompt video, voice/subtitle liên quan và package là cần kiểm tra hoặc tạo lại

### Requirement: AI phát triển nội dung thành kịch bản hấp dẫn
Hệ thống SHALL dùng AI planning để tổng hợp nguồn input và phát triển thành nội dung video có cấu trúc câu chuyện hấp dẫn hơn, thay vì chỉ chia cảnh cơ học.

#### Scenario: AI tổng hợp input thành story strategy
- **WHEN** người dùng yêu cầu AI phát triển nội dung từ các nguồn input
- **THEN** hệ thống tạo story strategy gồm hook, xung đột hoặc vấn đề chính, emotional arc, các điểm thú vị, cao trào nhỏ, payoff/kết thúc và mục tiêu giữ chân người xem

#### Scenario: AI viết lại kịch bản chi tiết
- **WHEN** story strategy được tạo thành công
- **THEN** hệ thống tạo kịch bản chi tiết phù hợp mục tiêu video, có lời thoại hoặc narration tiếng Anh nếu project dùng video tiếng Anh, đồng thời có mô tả tiếng Việt để người dùng hiểu nội dung

#### Scenario: AI không được làm mất ý chính của người dùng
- **WHEN** AI phát triển nội dung từ input thô
- **THEN** hệ thống giữ lại các ý chính, điều bắt buộc và điều cần tránh do người dùng cung cấp trong script và story strategy

### Requirement: Review và approve kịch bản trước khi tạo shot
Hệ thống SHALL yêu cầu người dùng review và approve story strategy, continuity bible và detailed script trước khi AI tạo shot breakdown.

#### Scenario: Hiển thị màn hình review kịch bản
- **WHEN** AI hoàn thành story strategy, continuity bible và detailed script
- **THEN** hệ thống hiển thị màn hình review với nội dung đầy đủ để người dùng đọc và kiểm tra

#### Scenario: Người dùng duyệt kịch bản
- **WHEN** người dùng nhấn nút "Duyệt kịch bản"
- **THEN** hệ thống lưu trạng thái story_approved = true và cho phép tạo shot breakdown

#### Scenario: Người dùng từ chối kịch bản
- **WHEN** người dùng nhấn nút "Viết lại"
- **THEN** hệ thống giữ nguyên source blocks, gọi lại AI để tạo story mới, và reset story_approved = false

#### Scenario: Chặn tạo shot khi chưa duyệt kịch bản
- **WHEN** người dùng cố gắng tạo shot breakdown khi story_approved = false
- **THEN** hệ thống hiển thị thông báo tiếng Việt yêu cầu duyệt kịch bản trước

### Requirement: Giữ continuity từ đầu đến cuối video
Hệ thống SHALL tạo và sử dụng continuity bible để giữ nhất quán nội dung, nhân vật, phong cách và chi tiết hình ảnh xuyên suốt video.

#### Scenario: Tạo continuity bible
- **WHEN** AI phát triển kịch bản chi tiết
- **THEN** hệ thống tạo continuity bible gồm nhân vật chính, đặc điểm gương mặt, tuổi, trang phục, đạo cụ lặp lại, bối cảnh, tone màu, mood, phong cách camera và các chi tiết không được thay đổi giữa các shot

#### Scenario: Prompt video tham chiếu continuity
- **WHEN** hệ thống tạo prompt video cho một shot
- **THEN** prompt video của shot đó bao gồm các continuity notes cần thiết để giữ nhân vật, đạo cụ, bối cảnh, ánh sáng và phong cách nhất quán với toàn project

#### Scenario: Người dùng sửa continuity bible
- **WHEN** người dùng chỉnh continuity bible sau khi đã có shot hoặc prompt video
- **THEN** hệ thống đánh dấu các prompt video liên quan là cần tạo lại và đánh dấu package là cũ

### Requirement: Chia scene thành shot rất ngắn để render video
Hệ thống SHALL chia kịch bản thành scene lớn và các shot rất ngắn có thể copy prompt sang công cụ tạo video bên ngoài, nhằm tạo nhịp xem nhanh hơn và nhiều chuyển cảnh hơn.

#### Scenario: Chia scene thành nhiều shot
- **WHEN** AI tạo scene breakdown cho một scene dài hơn thời lượng shot mục tiêu
- **THEN** hệ thống chia scene đó thành nhiều shot theo thứ tự, mỗi shot có thời lượng dự kiến, mô tả tiếng Việt, narration tiếng Anh nếu có, mục đích shot và liên kết scene cha

#### Scenario: Mỗi shot chỉ có một hành động hoặc một góc quay chính
- **WHEN** hệ thống tạo shot breakdown từ một scene
- **THEN** mỗi shot chỉ thể hiện một hành động chính hoặc một góc quay chính, tránh gom nhiều hành động hoặc nhiều góc máy phức tạp vào cùng một shot 1-5 giây

#### Scenario: Shot có thời lượng phù hợp video AI
- **WHEN** hệ thống tạo shot từ một scene có narration hoặc visual action
- **THEN** mỗi shot mặc định nằm trong khoảng 1-5 giây, trừ khi người dùng cấu hình thời lượng khác hoặc nội dung yêu cầu shot không lời ngắn hơn

#### Scenario: Scene dài được chia thành nhiều chuyển cảnh
- **WHEN** một scene dài hơn 5 giây hoặc có nhiều ý hình ảnh
- **THEN** hệ thống chia scene thành nhiều shot ngắn với chuyển cảnh rõ ràng để video không bị một cảnh đứng yên quá lâu

#### Scenario: Không để một scene chỉ có một góc quay
- **WHEN** một scene có nhiều hơn một shot
- **THEN** hệ thống tạo các shot với góc máy, cỡ cảnh, bố cục hoặc chuyển động camera khác nhau để scene không bị một góc quay hoặc một bố cục lặp lại gây nhàm chán

#### Scenario: Narration không bị nhồi vào một shot ngắn
- **WHEN** lời thoại hoặc narration của một scene dài hơn thời lượng shot mục tiêu
- **THEN** hệ thống chia narration thành các cụm ngắn theo shot hoặc giữ narration ở cấp scene, nhưng không ép một câu dài vào một shot 1-5 giây gây khó nghe

#### Scenario: Scene không lời vẫn có shot
- **WHEN** một scene được đánh dấu không narration
- **THEN** hệ thống vẫn có thể tạo shot visual-only với prompt video, nhưng không yêu cầu voice cho shot đó khi kiểm tra readiness

### Requirement: Tạo shot variation và transition plan hấp dẫn
Hệ thống SHALL tạo nhiều kiểu shot và chuyển cảnh để video có nhịp dựng thú vị, không lặp lại một loại cảnh đơn giản.

#### Scenario: AI tạo shot variation
- **WHEN** hệ thống tạo shot breakdown cho một project
- **THEN** danh sách shot sử dụng nhiều shot type, góc máy, cỡ cảnh, bố cục và camera movement phù hợp như establishing shot, close-up, detail shot, over-the-shoulder, tracking shot, slow push-in, time-lapse ngắn hoặc cinematic ending shot

#### Scenario: Shot có thông tin góc máy và bố cục
- **WHEN** hệ thống tạo một shot
- **THEN** shot đó có thông tin đủ rõ về shot type, camera angle, framing, composition và camera movement để tạo nhịp dựng điện ảnh

#### Scenario: AI tạo transition giữa các shot
- **WHEN** một shot có shot tiếp theo trong cùng scene hoặc sang scene kế tiếp
- **THEN** hệ thống tạo transition note như match cut, camera movement continuation, light transition, object transition hoặc cut theo cảm xúc để hướng dẫn dựng nội dung liền mạch

#### Scenario: Transition không làm mất continuity
- **WHEN** hệ thống tạo transition note cho các shot liên tiếp
- **THEN** transition note phải phù hợp continuity bible và không tự ý thay đổi nhân vật, bối cảnh hoặc phong cách đã khóa

### Requirement: Thay prompt ảnh bằng prompt tạo video
Hệ thống SHALL sử dụng prompt tạo video làm output chính của phase 2, thay cho prompt ảnh trong luồng AI Video Assistant phase 2.

#### Scenario: Tạo prompt video cho shot
- **WHEN** một shot đã sẵn sàng để tạo prompt
- **THEN** hệ thống tạo prompt video tiếng Anh cho shot đó, gồm duration, aspect ratio, subject, primary action, shot type, camera angle, framing, composition, camera movement, subject motion, environment motion, lighting, mood, start frame, end frame, continuity notes và negative prompt

#### Scenario: Prompt không phụ thuộc provider cụ thể
- **WHEN** hệ thống tạo prompt video mặc định
- **THEN** prompt không nhắc tên công cụ cụ thể như Runway, Kling, Veo, Pika hoặc Luma, và phải dùng được như prompt dạng chung cho nhiều công cụ tạo video

#### Scenario: Prompt tối ưu chi tiết theo nội dung shot
- **WHEN** shot có nhân vật, hành động, bối cảnh hoặc cảm xúc cụ thể
- **THEN** prompt video mô tả chi tiết các yếu tố đó thay vì dùng prompt chung chung như "create a video about this scene"

#### Scenario: Negative prompt được tạo kèm
- **WHEN** hệ thống tạo prompt video
- **THEN** hệ thống tạo negative prompt tiếng Anh để tránh text overlay, subtitle, watermark, logo, mặt méo, tay lỗi, flicker, camera shake bất thường hoặc người thừa nếu không phù hợp nội dung

### Requirement: Hỗ trợ song ngữ đúng mục đích
Hệ thống SHALL giúp người dùng không biết tiếng Anh vẫn tạo được video tiếng Anh bằng cách tách ngôn ngữ hiển thị, kịch bản và prompt theo mục đích sử dụng.

#### Scenario: UI hiển thị tiếng Việt
- **WHEN** người dùng thao tác trong AI Video Assistant phase 2
- **THEN** hệ thống hiển thị form, hướng dẫn, trạng thái, lỗi, mô tả shot và giải thích nội dung bằng tiếng Việt dễ hiểu

#### Scenario: Narration tiếng Anh cho video tiếng Anh
- **WHEN** project được cấu hình làm video tiếng Anh
- **THEN** hệ thống tạo script hoặc narration tiếng Anh cho các scene/shot có lời thoại

#### Scenario: Prompt video tiếng Anh
- **WHEN** người dùng copy hoặc tải prompt video
- **THEN** nội dung prompt video và negative prompt được xuất bằng tiếng Anh để dùng tốt với các công cụ tạo video quốc tế

### Requirement: UI phase 2 đẹp, thân thiện theo design-taste-frontend-v1
Hệ thống SHALL triển khai UI AI Video Assistant phase 2 theo baseline `design-taste-frontend-v1` để người dùng chạy local vẫn có giao diện tiếng Việt dễ hiểu, đẹp, rõ trạng thái và ít gây nhầm lẫn.

#### Scenario: Màn đầu tiên là workflow sử dụng thật
- **WHEN** người dùng mở AI Video Assistant phase 2
- **THEN** hệ thống hiển thị workflow tạo video có thể thao tác ngay, gồm nhập nguồn nội dung, trạng thái project và bước tiếp theo, thay vì hero/landing marketing hoặc màn giới thiệu không tạo được nội dung

#### Scenario: UI dùng tiếng Việt dễ hiểu cho người không rành kỹ thuật
- **WHEN** người dùng nhập source, duyệt kịch bản, tạo shot, tạo prompt, export hoặc gặp lỗi
- **THEN** form label, helper text, nút bấm, trạng thái, checklist và lỗi được viết bằng tiếng Việt tự nhiên, không dùng technical jargon nếu không mở debug panel

#### Scenario: Form và trạng thái tương tác đầy đủ
- **WHEN** UI có input hoặc action bất đồng bộ
- **THEN** mỗi input có label phía trên, helper text hoặc error text phía dưới, và mỗi bước chính có loading skeleton, empty state, inline error state, retry/copy action phù hợp

#### Scenario: Responsive an toàn trên mobile
- **WHEN** người dùng mở UI ở viewport nhỏ hơn 768px
- **THEN** layout chuyển về một cột, input và button full width khi cần, không horizontal scroll, không text overlap, không sidebar cố định, và không dùng `h-screen` cho vùng full-height mà dùng `min-h-[100dvh]` hoặc ràng buộc tương đương

#### Scenario: Visual style tránh giao diện AI generic
- **WHEN** UI phase 2 được triển khai
- **THEN** giao diện tuân thủ baseline DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4, tránh emoji, tránh neon/glow, tránh palette tím/xanh kiểu AI, dùng tối đa một accent color saturation dưới 80%, và không lạm dụng card lồng card

#### Scenario: Motion và icon không làm lỗi local build
- **WHEN** implementation thêm animation hoặc icon mới
- **THEN** developer kiểm tra `app/package.json` trước khi import thư viện, chỉ dùng dependency đã có hoặc thêm dependency rõ ràng; animation chỉ dùng transform/opacity cho phần chuyển động chính và các animation lặp phải được tách vào component nhỏ để không gây re-render nặng

### Requirement: Regenerate và lock từng shot
Hệ thống SHALL cho phép người dùng khóa shot đã duyệt và tạo lại từng shot hoặc từng nhóm shot mà không phá nội dung đã khóa.

#### Scenario: Người dùng lock một shot
- **WHEN** người dùng khóa một shot đã duyệt
- **THEN** hệ thống lưu trạng thái locked và không tự động thay đổi nội dung, narration, transition hoặc prompt của shot đó trong các lần regenerate batch

#### Scenario: Người dùng regenerate một shot chưa khóa
- **WHEN** người dùng yêu cầu tạo lại một shot chưa khóa
- **THEN** hệ thống chỉ cập nhật shot đó và các artifact phụ thuộc của shot đó, đồng thời đánh dấu package là cũ

#### Scenario: Người dùng regenerate toàn scene
- **WHEN** người dùng yêu cầu tạo lại toàn bộ shot trong một scene
- **THEN** hệ thống chỉ cập nhật các shot chưa khóa trong scene đó và giữ nguyên các shot đã khóa

#### Scenario: Thay đổi narration làm stale voice/subtitle
- **WHEN** regenerate làm thay đổi narration hoặc thời lượng dự kiến của một shot có lời
- **THEN** hệ thống đánh dấu voice, subtitle và package liên quan là cần tạo lại hoặc kiểm tra lại

### Requirement: Kiểm tra chất lượng prompt video
Hệ thống SHALL kiểm tra prompt video trước khi coi prompt đó là sẵn sàng copy hoặc export.

#### Scenario: Prompt thiếu trường quan trọng
- **WHEN** prompt video thiếu duration, aspect ratio, subject, primary action, shot type, camera angle, framing, composition, camera movement, motion details, continuity notes hoặc negative prompt
- **THEN** hệ thống đánh dấu prompt là chưa đạt chất lượng và yêu cầu regenerate hoặc bổ sung trước khi package được coi là sẵn sàng

#### Scenario: Prompt đủ điều kiện copy
- **WHEN** prompt video có đủ các trường bắt buộc và nội dung không rỗng
- **THEN** hệ thống cho phép người dùng copy, tải file prompt và dùng prompt đó trong package export

#### Scenario: UI hiển thị checklist dễ hiểu
- **WHEN** một prompt video chưa đạt chất lượng
- **THEN** UI hiển thị checklist tiếng Việt chỉ rõ thiếu yếu tố nào như camera, chuyển động, continuity hoặc negative prompt

### Requirement: Export gói nguyên liệu prompt video
Hệ thống SHALL xuất gói nguyên liệu phase 2 tập trung vào prompt video, kịch bản, shot list, continuity, voice và subtitle.

#### Scenario: Tải ZIP phase 2 thành công
- **WHEN** project có source/story đã duyệt, shot hợp lệ, prompt video đạt chất lượng, voice bắt buộc và subtitle sẵn sàng
- **THEN** hệ thống tạo ZIP gồm hướng dẫn sử dụng, kịch bản tiếng Anh, mô tả tiếng Việt, continuity bible, shot list, prompt video từng shot, voice, subtitle và manifest

#### Scenario: Tên thư mục prompt video
- **WHEN** hệ thống tạo ZIP phase 2
- **THEN** thư mục prompt chính trong ZIP dùng tên tiếng Việt thân thiện như `Prompt video` thay vì `Prompt ảnh`

#### Scenario: Package thiếu prompt video
- **WHEN** người dùng tải package trong khi một shot bắt buộc chưa có prompt video đạt chất lượng
- **THEN** hệ thống chặn export và chỉ rõ shot còn thiếu prompt video bằng tiếng Việt

#### Scenario: Package không bắt buộc preview image
- **WHEN** project chưa có ảnh preview cho một số shot hoặc scene
- **THEN** hệ thống vẫn cho phép export nếu prompt video, voice bắt buộc và subtitle đã sẵn sàng

### Requirement: Giữ tương thích với voice và subtitle hiện có
Hệ thống SHALL tái sử dụng voice generation và subtitle workflow hiện có khi mở rộng sang scene/shot phase 2.

#### Scenario: Tạo voice từ narration phase 2
- **WHEN** một scene hoặc shot có narration tiếng Anh cần tạo giọng
- **THEN** hệ thống dùng voice profile và TTS flow hiện có để tạo audio, lưu generation ID, audio path, duration thật và trạng thái lỗi nếu có

#### Scenario: Subtitle dùng timing audio thật
- **WHEN** toàn bộ narration bắt buộc đã tạo audio thành công
- **THEN** hệ thống tạo subtitle từ lời thoại và duration thật của audio, không chỉ dựa vào duration dự kiến của shot

#### Scenario: Workflow voice cũ không bị ảnh hưởng
- **WHEN** người dùng tạo speech từ editor Voicebox hiện có hoặc dùng AI Video Assistant phase 1 project cũ
- **THEN** hệ thống vẫn tạo và serve audio bằng flow generation hiện tại mà không yêu cầu dữ liệu shot phase 2

### Requirement: Resume project phase 2
Hệ thống SHALL lưu trạng thái phase 2 để người dùng có thể rời app và quay lại tiếp tục chỉnh nội dung, shot và prompt video.

#### Scenario: Mở lại project phase 2
- **WHEN** người dùng mở lại một project phase 2 chưa hoàn tất
- **THEN** hệ thống khôi phục source blocks, story strategy, continuity bible, script, scene, shot, lock state, prompt video, voice/subtitle status và package status

#### Scenario: Project có artifact cũ
- **WHEN** người dùng mở project có package đã tạo nhưng source, continuity, shot, prompt, voice hoặc subtitle đã thay đổi sau đó
- **THEN** hệ thống hiển thị package là cũ và yêu cầu tạo package mới trước khi tải bản mới nhất

### Requirement: Xử lý lỗi AI và retry thân thiện
Hệ thống SHALL xử lý lỗi AI planning với retry logic và thông báo tiếng Việt dễ hiểu.

#### Scenario: Codex call thất bại lần đầu
- **WHEN** một Codex call fail do timeout, network error hoặc invalid JSON
- **THEN** hệ thống tự động retry sau 2 giây, tối đa 3 lần

#### Scenario: Codex call thất bại sau 3 lần retry
- **WHEN** Codex call vẫn fail sau 3 lần retry
- **THEN** hệ thống dừng pipeline, hiển thị thông báo lỗi tiếng Việt và log error với request_id

#### Scenario: Thông báo lỗi tiếng Việt
- **WHEN** hệ thống gặp lỗi AI planning
- **THEN** người dùng thấy thông báo tiếng Việt không chứa technical jargon, ví dụ: "AI xử lý quá lâu. Thử lại hoặc rút ngắn nội dung." thay vì "Codex CLI timeout 60s"

#### Scenario: Debug panel hiển thị technical details
- **WHEN** người dùng mở debug panel
- **THEN** hệ thống hiển thị request_id, step_name, error_type và technical details để troubleshooting

### Requirement: Ghi log lỗi local có cấu trúc để dễ sửa
Hệ thống SHALL ghi log local có cấu trúc cho pipeline AI Video phase 2 để người dùng và developer có thể truy lỗi khi chạy trên máy cá nhân mà không cần dịch vụ observability bên ngoài.

#### Scenario: Log từng bước pipeline chính
- **WHEN** hệ thống chạy các bước source synthesis, story development, continuity generation, shot breakdown, video prompt generation, voice generation, subtitle generation hoặc package export
- **THEN** hệ thống ghi log local cho start, success, warning và failure của bước đó với `request_id`, `project_id`, `step_name`, thời điểm, `duration_ms`, `retry_count` và trạng thái kết quả

#### Scenario: Log lỗi có đủ ngữ cảnh kỹ thuật
- **WHEN** một bước pipeline lỗi do timeout, invalid JSON, validation error, provider/CLI error, file IO error hoặc export blocker
- **THEN** log lỗi bao gồm `request_id`, `project_id`, `scene_id` nếu có, `shot_id` nếu có, `step_name`, `provider`, `model`, `error_code`, exception class, message kỹ thuật, validation errors và stack trace ngắn nếu có

#### Scenario: Log không làm lộ dữ liệu nhạy cảm
- **WHEN** hệ thống ghi log request, response hoặc file metadata
- **THEN** log không chứa secret token, API key, bearer token, full uploaded binary, path nhạy cảm không cần thiết hoặc toàn bộ nội dung audio; nội dung người dùng dài phải được truncate hoặc redaction an toàn

#### Scenario: Debug panel giúp copy thông tin lỗi
- **WHEN** người dùng gặp lỗi và mở debug panel trong UI local
- **THEN** hệ thống cho phép copy `request_id`, friendly message, step name, error code và technical details đã redaction để gửi lại cho developer

#### Scenario: Debug/status endpoint đọc được lỗi gần nhất
- **WHEN** developer gọi debug/status endpoint local cho một project phase 2
- **THEN** response trả về trạng thái các artifact chính, lỗi gần nhất theo step, `request_id` tương ứng và đường dẫn log local nếu môi trường cho phép hiển thị
