## ADDED Requirements

### Requirement: Quản lý phiên Chrome riêng cho Veo
Hệ thống SHALL cho phép người dùng cấu hình một Chrome profile riêng của Voicebox để đăng nhập Google/Veo thủ công và dùng lại session đó cho các lần tạo clip sau.

#### Scenario: Mở Chrome để đăng nhập lần đầu
- **WHEN** người dùng bấm "Mở Chrome đăng nhập Veo" khi chưa có phiên hợp lệ
- **THEN** hệ thống SHALL mở Chrome thật bằng profile riêng của Voicebox và điều hướng tới trang Veo hoặc trang cấu hình provider

#### Scenario: Dùng lại session đã đăng nhập
- **WHEN** Chrome profile riêng đã có session Google/Veo còn hiệu lực
- **THEN** hệ thống SHALL dùng lại profile đó cho job tạo clip mà không yêu cầu người dùng đăng nhập lại

#### Scenario: Không dùng profile Chrome cá nhân mặc định
- **WHEN** hệ thống mở Chrome cho provider automation
- **THEN** hệ thống MUST dùng profile riêng đã cấu hình hoặc profile riêng do Voicebox tạo, và MUST NOT tự động attach vào profile Chrome cá nhân mặc định

#### Scenario: Không lưu credential vào database
- **WHEN** người dùng đăng nhập Google/Veo trong Chrome profile riêng
- **THEN** hệ thống MUST NOT lưu mật khẩu, token, cookie hoặc local storage vào database hoặc debug log

### Requirement: Kiểm tra trạng thái phiên Veo
Hệ thống SHALL kiểm tra được phiên Chrome/Veo để biết provider đã sẵn sàng, cần đăng nhập lại hay gặp lỗi cấu hình.

#### Scenario: Phiên đã sẵn sàng
- **WHEN** người dùng bấm "Kiểm tra phiên" và Chrome profile vào được trang tạo video Veo
- **THEN** hệ thống SHALL đánh dấu session `ready`, lưu `last_checked_at` và có thể lưu account hint đã mask nếu đọc được an toàn từ UI

#### Scenario: Provider yêu cầu đăng nhập lại
- **WHEN** kiểm tra session thấy trang Google login, chọn tài khoản, 2FA hoặc CAPTCHA
- **THEN** hệ thống SHALL đánh dấu session `needs_login` và hiển thị hành động mở Chrome để người dùng xác minh thủ công

#### Scenario: Chrome không mở được
- **WHEN** hệ thống không tìm thấy Chrome executable hoặc profile bị lock
- **THEN** hệ thống SHALL trả lỗi tiếng Việt rõ nguyên nhân và MUST NOT bắt đầu job tạo clip

### Requirement: Khởi chạy job tạo clip Veo theo project
Hệ thống SHALL cho phép người dùng khởi chạy job tạo clip bằng Veo cho AI Video project phase 2 đã có prompt video theo shot.

#### Scenario: Bắt đầu job hợp lệ
- **WHEN** project phase 2 có shot và prompt video completed hoặc passed, và session Veo đang `ready`
- **THEN** hệ thống SHALL tạo clip generation job với `project_id`, `provider = "veo"`, `status`, `current_step`, `progress` và danh sách item theo shot cần tạo clip

#### Scenario: Chặn job khi project chưa có prompt
- **WHEN** project chưa có prompt video hợp lệ cho một hoặc nhiều shot bắt buộc
- **THEN** hệ thống SHALL không gửi prompt sang Veo và SHALL hiển thị lỗi tiếng Việt yêu cầu tạo prompt video trước

#### Scenario: Không chạy song song trên cùng project
- **WHEN** project đang có clip generation job ở trạng thái active
- **THEN** request start mới SHALL trả về job active hoặc từ chối bằng lỗi tiếng Việt, và MUST NOT tạo job song song gây trùng prompt/download/clip

#### Scenario: Bỏ qua shot đã có clip provider hợp lệ
- **WHEN** shot đã có clip active từ provider Veo, file còn tồn tại và không bật force
- **THEN** job SHALL skip shot đó và không tạo lại clip không cần thiết

### Requirement: Gửi prompt Veo và chờ clip theo từng shot
Hệ thống SHALL điều phối từng shot bằng cách mở provider, đưa prompt video vào Veo, chờ generation và chuyển trạng thái item rõ ràng.

#### Scenario: Submit prompt cho shot
- **WHEN** job xử lý một shot có prompt video hợp lệ
- **THEN** hệ thống SHALL mở đúng phiên Chrome/Veo, đưa prompt vào input provider và submit generation cho shot đó

#### Scenario: Chờ provider tạo clip
- **WHEN** Veo đang tạo clip sau khi prompt được submit
- **THEN** item SHALL ở trạng thái chờ generation và frontend SHALL hiển thị tiếng Việt rằng hệ thống đang chờ Veo tạo clip

#### Scenario: Provider báo quota hoặc lỗi
- **WHEN** Veo báo hết quota, lỗi billing, lỗi policy hoặc lỗi provider khác
- **THEN** hệ thống SHALL dừng item hoặc job với `error_code` phù hợp, lưu failure reason tiếng Việt và MUST NOT retry vô hạn

#### Scenario: Provider yêu cầu thao tác người dùng
- **WHEN** Veo yêu cầu login, xác minh, CAPTCHA hoặc consent mà automation không được tự xử lý
- **THEN** job SHALL chuyển `needs_login` hoặc `needs_user_action`, mở hành động cho người dùng xử lý trong Chrome rồi resume

### Requirement: Theo dõi download và map clip về đúng shot
Hệ thống SHALL tải hoặc bắt file clip provider trả về trong thư mục download tạm riêng theo job/item và map file đó về đúng shot.

#### Scenario: Download clip hoàn tất
- **WHEN** provider tạo xong clip và download file video hoàn tất vào thư mục item
- **THEN** hệ thống SHALL xác nhận file không còn đang tải, size ổn định và extension hoặc MIME thuộc định dạng video hỗ trợ

#### Scenario: Không dùng Downloads mặc định để đoán file
- **WHEN** job chờ file download của một shot
- **THEN** hệ thống MUST dùng download directory riêng theo job/item hoặc cơ chế download event tương đương, và MUST NOT đoán file bằng file mới nhất trong Downloads cá nhân mặc định

#### Scenario: Download timeout
- **WHEN** clip không xuất hiện hoặc file vẫn chưa hoàn tất sau timeout cấu hình
- **THEN** item SHALL chuyển `failed` với lỗi tiếng Việt và job SHALL cho phép retry item đó

#### Scenario: File tải về không phải video hợp lệ
- **WHEN** file tải về không đọc được metadata video hoặc không thuộc định dạng hỗ trợ
- **THEN** hệ thống SHALL đánh dấu item failed, không import file đó làm clip active và hiển thị lỗi tiếng Việt

### Requirement: Import clip provider vào project
Hệ thống SHALL import clip tải từ Veo vào artifact storage của project bằng model `video_shot_clips` hiện có.

#### Scenario: Import clip thành công
- **WHEN** một item có file clip video hợp lệ
- **THEN** hệ thống SHALL lưu file vào artifact storage của project, tạo `video_shot_clips` record với `source = "provider"`, `provider = "veo"`, liên kết đúng `shot_id` và đánh dấu clip là active

#### Scenario: Deactivate clip cũ khi thay thế
- **WHEN** shot đã có clip active và job import clip provider mới cho shot đó
- **THEN** hệ thống SHALL deactivate clip active cũ, lưu clip mới là active và đánh dấu render output cũ là stale

#### Scenario: Lưu metadata provider đã redaction
- **WHEN** hệ thống lưu metadata provider cho clip
- **THEN** metadata SHALL chỉ chứa thông tin an toàn như provider asset id, attempt count, status và filename đã sanitize, và MUST NOT chứa cookie, token, DOM đầy đủ hoặc prompt dài

### Requirement: Resume, retry và cancel job tạo clip
Hệ thống SHALL hỗ trợ resume, retry và cancel job tạo clip mà không tạo trạng thái mâu thuẫn hoặc clip trùng ngoài ý muốn.

#### Scenario: Resume sau khi đăng nhập lại
- **WHEN** job đang `needs_login` và người dùng đã hoàn tất đăng nhập trong Chrome profile riêng
- **THEN** người dùng SHALL có thể resume job từ item chưa hoàn tất, và hệ thống MUST giữ clip đã import trước đó

#### Scenario: Retry item lỗi
- **WHEN** một hoặc nhiều item failed vì download/provider lỗi retryable
- **THEN** retry SHALL chỉ chạy lại item thiếu/lỗi/stale và MUST NOT force tạo lại item đã completed nếu người dùng không bật force

#### Scenario: Cancel job active
- **WHEN** người dùng cancel job đang chạy hoặc đang chờ user action
- **THEN** job SHALL chuyển `cancelled`, runner SHALL ngừng gửi prompt/download tiếp theo và các clip đã import vẫn được giữ trong project

#### Scenario: App restart khi job đang chạy
- **WHEN** ứng dụng restart trong lúc job đang `running`, `waiting_generation` hoặc `downloading`
- **THEN** hệ thống SHALL sync job về trạng thái cần retry hoặc failed với thông báo tiếng Việt, thay vì để job kẹt active vĩnh viễn

### Requirement: Tự render MP4 sau khi đủ clip
Hệ thống SHALL có tùy chọn tự chuyển sang render MP4 bằng render timeline hiện có sau khi mọi clip bắt buộc đã sẵn sàng.

#### Scenario: Auto-render khi readiness pass
- **WHEN** job tạo clip hoàn tất mọi item và request bật `auto_render`
- **THEN** hệ thống SHALL gọi render readiness hiện có và tạo render job nếu project đủ clip, voice, subtitle và runtime FFmpeg

#### Scenario: Render bị chặn do thiếu input
- **WHEN** clip generation completed nhưng render readiness fail vì thiếu voice, subtitle, FFmpeg hoặc timer
- **THEN** job SHALL không tạo render job, SHALL hiển thị missing reasons tiếng Việt và SHALL giữ clip đã import để người dùng xử lý tiếp

#### Scenario: Không duplicate render logic
- **WHEN** hệ thống cần dựng MP4 sau khi tạo clip
- **THEN** hệ thống MUST dùng render service/job hiện có thay vì tự mux video trong clip generation service

### Requirement: UI tiếng Việt cho phiên Veo và tạo clip
Hệ thống SHALL hiển thị điều khiển phiên Chrome/Veo và job tạo clip trong AI Video Assistant bằng tiếng Việt, rõ trạng thái và hành động cần làm.

#### Scenario: Hiển thị trạng thái phiên
- **WHEN** người dùng mở AI Video Assistant
- **THEN** UI SHALL hiển thị trạng thái phiên Veo/Chrome: chưa cấu hình, cần đăng nhập, đã sẵn sàng hoặc lỗi

#### Scenario: Hiển thị tiến độ theo shot
- **WHEN** clip generation job đang chạy
- **THEN** UI SHALL hiển thị từng shot đang ở bước gửi prompt, chờ Veo, tải clip, import, hoàn tất, lỗi hoặc cần người dùng đăng nhập

#### Scenario: Hành động đăng nhập lại
- **WHEN** job hoặc session ở trạng thái `needs_login`
- **THEN** UI SHALL hiển thị action mở đúng Chrome profile để người dùng đăng nhập lại và action resume sau khi hoàn tất

#### Scenario: Không yêu cầu hiểu raw status
- **WHEN** UI hiển thị tiến độ hoặc lỗi
- **THEN** UI SHALL dùng mô tả tiếng Việt dễ hiểu và MUST NOT bắt người dùng hiểu raw code như `waiting_generation`, `download_timeout` hoặc selector provider

### Requirement: Bảo mật và redaction cho automation provider
Hệ thống SHALL giới hạn dữ liệu nhạy cảm được lưu hoặc log trong quá trình điều khiển Chrome/Veo.

#### Scenario: Redaction debug event
- **WHEN** hệ thống ghi debug event cho session, provider adapter, download hoặc import clip
- **THEN** event SHALL chứa job id, shot id, provider, step, status và error code, nhưng MUST NOT chứa cookie, token, credential, full DOM hoặc full prompt dài

#### Scenario: Không export Chrome profile trong package
- **WHEN** người dùng tạo ZIP nguyên liệu, tải debug hoặc xóa project
- **THEN** hệ thống MUST NOT đưa Chrome profile/session cookies vào package project hoặc debug export

#### Scenario: Cảnh báo profile riêng
- **WHEN** người dùng cấu hình phiên Veo lần đầu
- **THEN** UI SHALL giải thích rằng Voicebox dùng Chrome profile riêng để tránh đụng Chrome cá nhân và để giảm việc đăng nhập lại nhiều lần
