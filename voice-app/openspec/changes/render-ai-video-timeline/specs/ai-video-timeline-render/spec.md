## ADDED Requirements

### Requirement: Quản lý video clip theo từng shot
Hệ thống SHALL cho phép người dùng gắn video clip vào từng shot của AI Video project phase 2 để dùng làm nguyên liệu render timeline.

#### Scenario: Upload clip cho một shot
- **WHEN** người dùng upload file video cho một shot phase 2 hợp lệ
- **THEN** hệ thống lưu clip vào artifact storage của project, liên kết clip với shot đó, đánh dấu clip là active và trả về metadata cơ bản của clip

#### Scenario: Chặn upload cho shot không tồn tại
- **WHEN** người dùng upload clip cho `shot_id` không thuộc project hiện tại
- **THEN** hệ thống từ chối request và hiển thị lỗi tiếng Việt rằng không tìm thấy shot video

#### Scenario: Thay thế clip active
- **WHEN** người dùng upload clip mới cho shot đã có clip active
- **THEN** hệ thống đánh dấu clip cũ là không active, lưu clip mới là active và đánh dấu render output cũ của project là không còn mới nhất

#### Scenario: Xóa clip active
- **WHEN** người dùng xóa clip active của một shot
- **THEN** hệ thống bỏ liên kết clip active khỏi shot đó, xóa hoặc đánh dấu artifact tương ứng để cleanup an toàn, và readiness render báo thiếu clip cho shot đó

#### Scenario: Lưu clip từ provider trong tương lai
- **WHEN** một tích hợp provider video bên ngoài trả về clip cho shot trong phase sau
- **THEN** hệ thống có thể lưu clip đó bằng cùng model clip với `source = provider` và metadata provider mà không thay đổi contract render timeline

### Requirement: Probe và validate metadata clip bằng FFprobe
Hệ thống SHALL đọc và validate metadata video clip trước khi coi clip đó là sẵn sàng render.

#### Scenario: Clip đọc được metadata
- **WHEN** FFprobe đọc thành công duration, width, height, fps và codec của clip upload
- **THEN** hệ thống lưu metadata đó vào clip record và đặt trạng thái clip là sẵn sàng

#### Scenario: Clip không đọc được metadata
- **WHEN** FFprobe không đọc được file upload hoặc file không phải video hợp lệ
- **THEN** hệ thống đặt trạng thái clip là lỗi, lưu lý do lỗi tiếng Việt và không dùng clip đó trong readiness render

#### Scenario: Clip quá lớn hoặc định dạng không được hỗ trợ
- **WHEN** người dùng upload file vượt giới hạn size/duration hoặc có định dạng mà FFmpeg không thể xử lý
- **THEN** hệ thống từ chối hoặc đánh dấu clip lỗi với thông báo tiếng Việt chỉ rõ vấn đề

#### Scenario: FFprobe chưa sẵn sàng
- **WHEN** hệ thống không tìm thấy FFprobe trong runtime
- **THEN** hệ thống không crash, readiness clip/render báo lỗi tiếng Việt yêu cầu cài hoặc cấu hình FFmpeg/FFprobe

### Requirement: Kiểm tra readiness trước khi render MP4
Hệ thống SHALL cung cấp checklist readiness riêng cho render MP4 để chỉ rõ project đã đủ clip, voice, subtitle và runtime hay chưa.

#### Scenario: Project đủ điều kiện render
- **WHEN** project phase 2 có shot hợp lệ, mỗi shot có clip active sẵn sàng, mọi shot có narration đã có voice completed, subtitle đã completed nếu người dùng bật phụ đề, và FFmpeg/FFprobe sẵn sàng
- **THEN** render readiness trả về `ready = true` cùng danh sách reason rỗng

#### Scenario: Thiếu clip theo shot
- **WHEN** một hoặc nhiều shot chưa có clip active sẵn sàng
- **THEN** render readiness trả về `ready = false`, liệt kê `shot_id` còn thiếu và hiển thị reason tiếng Việt theo từng shot hoặc nhóm shot

#### Scenario: Thiếu voice bắt buộc
- **WHEN** một shot có narration nhưng voice chưa completed hoặc thiếu `audio_path` hoặc thiếu `audio_duration`
- **THEN** render readiness trả về `ready = false` và chỉ rõ shot còn thiếu giọng đọc

#### Scenario: Thiếu subtitle khi bật burn-in subtitle
- **WHEN** người dùng chọn render có phụ đề burn-in nhưng project chưa có subtitle completed
- **THEN** render readiness trả về `ready = false` và yêu cầu tạo phụ đề trước khi render

#### Scenario: Shot không lời dùng duration dự kiến
- **WHEN** một shot không có narration nhưng có `duration_seconds` hợp lệ
- **THEN** render readiness coi shot đó đủ timer và không yêu cầu voice cho shot đó

#### Scenario: Shot thiếu timer
- **WHEN** một shot không có narration và cũng không có `duration_seconds` hợp lệ
- **THEN** render readiness trả về `ready = false` và chỉ rõ shot thiếu thời lượng render

### Requirement: Tạo timeline duration từ voice thật
Hệ thống SHALL dùng thời lượng thật của voice theo shot làm nguồn timer chính cho video timeline.

#### Scenario: Shot có narration
- **WHEN** shot có narration và voice completed
- **THEN** duration render của shot bằng `audio_duration` thật của voice đã tạo

#### Scenario: Shot không có narration
- **WHEN** shot không có narration và có `duration_seconds` hợp lệ
- **THEN** duration render của shot bằng `duration_seconds`

#### Scenario: Tính start/end timeline theo shot_order
- **WHEN** hệ thống tạo timeline manifest để render
- **THEN** mỗi shot có `start_seconds` và `end_seconds` được cộng dồn theo `shot_order` tăng dần, không tạo gap mặc định giữa các shot

#### Scenario: Subtitle khớp cùng timeline
- **WHEN** project có subtitle cue đã tạo từ voice duration thật
- **THEN** render timeline sử dụng cùng trục thời gian với subtitle để phụ đề không lệch voice trong MP4 cuối

### Requirement: Normalize clip theo timer và aspect ratio project
Hệ thống SHALL chuẩn hóa từng clip theo duration mục tiêu, aspect ratio, resolution, fps và codec trước khi concat.

#### Scenario: Clip dài hơn timer
- **WHEN** clip của shot dài hơn duration mục tiêu của shot
- **THEN** hệ thống trim clip về đúng duration mục tiêu theo setting render đã chọn

#### Scenario: Clip ngắn hơn timer
- **WHEN** clip của shot ngắn hơn duration mục tiêu của shot
- **THEN** hệ thống kéo clip đủ duration bằng freeze frame cuối theo mặc định

#### Scenario: Clip lệch duration quá lớn
- **WHEN** clip ngắn hơn hoặc dài hơn timer vượt ngưỡng cảnh báo đã cấu hình
- **THEN** readiness hoặc render manifest hiển thị cảnh báo tiếng Việt để người dùng biết clip có thể bị đứng hình hoặc bị cắt nhiều

#### Scenario: Chuẩn hóa aspect ratio bằng crop
- **WHEN** người dùng chọn `fit_mode = crop`
- **THEN** hệ thống scale và crop center clip để lấp đầy khung theo aspect ratio project

#### Scenario: Chuẩn hóa aspect ratio bằng pad
- **WHEN** người dùng chọn `fit_mode = pad`
- **THEN** hệ thống scale clip vừa khung và thêm nền màu để giữ toàn bộ nội dung gốc

#### Scenario: Chuẩn hóa codec và fps
- **WHEN** hệ thống tạo intermediate clip cho render
- **THEN** clip intermediate có cùng resolution, fps, pixel format và codec để concat ổn định

### Requirement: Render MP4 bằng FFmpeg
Hệ thống SHALL render video MP4 hoàn chỉnh bằng FFmpeg từ các clip đã normalize, voice audio và subtitle theo setting người dùng chọn.

#### Scenario: Render thành công
- **WHEN** người dùng bắt đầu render với readiness hợp lệ
- **THEN** hệ thống tạo MP4 output trong artifact storage, lưu đường dẫn output vào render job và cho phép người dùng tải file MP4

#### Scenario: Không tìm thấy FFmpeg
- **WHEN** người dùng bắt đầu render nhưng FFmpeg không sẵn sàng trong runtime
- **THEN** hệ thống không tạo job chạy lỗi sâu bên dưới, mà trả lỗi tiếng Việt yêu cầu cài hoặc cấu hình FFmpeg

#### Scenario: Mute audio gốc của clip
- **WHEN** hệ thống render MP4 mặc định
- **THEN** audio gốc của clip video bị mute và voice Voicebox là audio chính trong MP4

#### Scenario: Shot không lời tạo silence
- **WHEN** timeline có shot không narration
- **THEN** hệ thống thêm silence audio tương ứng duration shot để audio track cuối vẫn khớp video track

#### Scenario: FFmpeg command thất bại
- **WHEN** FFmpeg trả exit code lỗi trong quá trình normalize, concat hoặc mux
- **THEN** render job chuyển sang failed, lưu error code/lý do tiếng Việt và lưu technical details đã rút gọn cho debug panel

### Requirement: Hỗ trợ phụ đề burn-in và sidecar
Hệ thống SHALL hỗ trợ phụ đề theo hai chế độ: burn-in vào video hoặc giữ file SRT rời.

#### Scenario: Burn-in subtitle
- **WHEN** người dùng chọn chế độ phụ đề burn-in
- **THEN** hệ thống chuyển cue subtitle sang ASS hoặc filter tương đương và render phụ đề trực tiếp vào khung hình MP4 cuối

#### Scenario: Sidecar subtitle
- **WHEN** người dùng chọn chế độ phụ đề sidecar
- **THEN** hệ thống không burn phụ đề vào MP4 và vẫn cho phép người dùng tải file SRT hiện có cùng video output

#### Scenario: Subtitle burn-in lỗi font hoặc filter
- **WHEN** FFmpeg không render được subtitle burn-in do lỗi font, file hoặc filter
- **THEN** render job failed với thông báo tiếng Việt rõ ràng và gợi ý thử chế độ sidecar hoặc kiểm tra file subtitle

### Requirement: Quản lý render job bất đồng bộ
Hệ thống SHALL tạo và theo dõi render job bất đồng bộ để người dùng không bị khóa UI trong quá trình render.

#### Scenario: Tạo render job
- **WHEN** người dùng bấm “Dựng MP4” với readiness hợp lệ
- **THEN** hệ thống tạo render job có trạng thái `queued` hoặc `running`, lưu setting snapshot và trả job id cho frontend

#### Scenario: Theo dõi tiến độ render
- **WHEN** frontend poll trạng thái render job
- **THEN** API trả trạng thái hiện tại, progress, bước đang chạy, lỗi nếu có và output URL nếu job completed

#### Scenario: Render job hoàn tất
- **WHEN** FFmpeg tạo MP4 thành công và output tồn tại
- **THEN** render job chuyển sang `completed`, lưu `completed_at`, `output_path` và cho phép tải MP4

#### Scenario: Render job thất bại
- **WHEN** một bước render thất bại
- **THEN** render job chuyển sang `failed`, lưu `failure_reason`, không đánh dấu output là tải được và UI hiển thị lỗi inline

#### Scenario: Ứng dụng đóng khi job đang chạy
- **WHEN** app restart và phát hiện render job còn trạng thái running từ session trước
- **THEN** hệ thống đánh dấu job đó failed với thông báo tiếng Việt rằng render đã bị gián đoạn khi ứng dụng đóng

### Requirement: UI dựng nhanh MP4 theo design-taste-frontend-v1
Hệ thống SHALL triển khai panel “Dựng nhanh MP4” trong AI Video Assistant theo baseline `design-taste-frontend-v1` với DESIGN_VARIANCE 8, MOTION_INTENSITY 6 và VISUAL_DENSITY 4.

#### Scenario: UI hiển thị workflow render thật
- **WHEN** người dùng mở project phase 2 có shot
- **THEN** panel render hiển thị danh sách shot, trạng thái clip, readiness checklist, setting render, trạng thái job và action tải MP4 thay vì màn giới thiệu hoặc hero marketing

#### Scenario: UI dùng tiếng Việt tự nhiên
- **WHEN** người dùng upload clip, kiểm tra readiness, render, gặp lỗi hoặc tải MP4
- **THEN** label, helper text, lỗi, checklist, trạng thái và nút bấm trong panel render được viết bằng tiếng Việt dễ hiểu cho người không rành kỹ thuật

#### Scenario: Không dùng emoji hoặc visual AI generic
- **WHEN** panel render được implement
- **THEN** UI không dùng emoji trong text/markup/alt text, không dùng neon/glow, không dùng palette tím/xanh kiểu AI và dùng tối đa một accent color có saturation dưới 80%

#### Scenario: Layout responsive an toàn
- **WHEN** panel render hiển thị trên viewport nhỏ hơn 768px
- **THEN** layout collapse về một cột, input và button full width khi cần, không horizontal scroll, không text overlap và không dùng `h-screen` cho vùng full-height

#### Scenario: Form upload và settings đầy đủ trạng thái
- **WHEN** UI có file upload hoặc setting render
- **THEN** mỗi control có label phía trên, helper text hoặc error text phía dưới, loading skeleton theo layout, empty state, inline error state và tactile active feedback

#### Scenario: Motion không gây re-render nặng
- **WHEN** UI thêm animation cho progress, checklist hoặc trạng thái job
- **THEN** animation chỉ dùng transform/opacity, motion phức tạp được tách vào component nhỏ, không dùng React state cho animation liên tục và không thêm dependency khi chưa kiểm tra `app/package.json`

#### Scenario: Dependency frontend được kiểm tra trước khi import
- **WHEN** implementation muốn import thư viện icon, motion hoặc UI mới cho panel render
- **THEN** developer MUST kiểm tra `app/package.json` trước; nếu dependency chưa có thì phải thêm dependency rõ ràng trong implementation hoặc dùng pattern đã có trong codebase

### Requirement: Tải và quản lý output MP4
Hệ thống SHALL cho phép người dùng tải MP4 cuối và quản lý trạng thái output render mới nhất.

#### Scenario: Tải output MP4 mới nhất
- **WHEN** project có render job completed mới nhất và file output còn tồn tại
- **THEN** người dùng có thể tải MP4 với filename tiếng Việt an toàn dựa trên tên project

#### Scenario: Output cũ sau khi source thay đổi
- **WHEN** clip, voice, subtitle, shot order hoặc render settings liên quan thay đổi sau khi job completed
- **THEN** hệ thống đánh dấu output cũ là stale hoặc readiness báo cần render lại trước khi coi MP4 là bản mới nhất

#### Scenario: File output không còn tồn tại
- **WHEN** API download MP4 được gọi nhưng file output đã bị xóa hoặc không còn truy cập được
- **THEN** hệ thống trả lỗi tiếng Việt rằng file render không còn tồn tại và yêu cầu render lại

### Requirement: Cleanup artifact render an toàn
Hệ thống SHALL cleanup artifact render và clip theo vòng đời project mà không xóa nhầm dữ liệu người dùng cần giữ.

#### Scenario: Xóa project
- **WHEN** người dùng xóa AI Video project
- **THEN** hệ thống xóa shot clips, intermediate render files, subtitle ASS tạm và MP4 output thuộc project đó cùng với artifact AI Video khác

#### Scenario: Render job failed
- **WHEN** render job failed sau khi đã tạo intermediate files
- **THEN** hệ thống có thể cleanup intermediate tạm nhưng vẫn giữ log/debug và trạng thái failed để người dùng hiểu lỗi

#### Scenario: Thay clip active
- **WHEN** người dùng thay clip active của shot
- **THEN** hệ thống không xóa ngay clip cũ nếu còn render job completed tham chiếu tới output cũ, nhưng không dùng clip cũ cho render mới
