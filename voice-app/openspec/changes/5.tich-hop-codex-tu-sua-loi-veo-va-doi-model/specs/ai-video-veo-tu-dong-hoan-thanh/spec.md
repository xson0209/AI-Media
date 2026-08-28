## ADDED Requirements

### Requirement: Gắn Flow project cố định cho video lẻ
Hệ thống SHALL gắn mỗi AI Video project lẻ với tối đa một Flow/Veo project URL active để giữ nhân vật, cảnh, style và asset nhất quán trong toàn bộ video.

#### Scenario: Project lẻ chưa có Flow project binding
- **WHEN** người dùng bắt đầu tạo clip Veo cho project lẻ chưa có Flow project binding
- **THEN** hệ thống SHALL tạo hoặc mở một Flow project mới, lưu `provider_project_url` cho project đó và dùng URL này cho các shot tiếp theo

#### Scenario: Project lẻ đã có Flow project binding
- **WHEN** project lẻ đã có Flow project binding active và người dùng tạo hoặc retry clip
- **THEN** hệ thống SHALL mở lại đúng Flow project URL đã lưu và MUST NOT tạo Flow project mới nếu URL còn dùng được

#### Scenario: Người dùng đổi model thủ công trong project lẻ
- **WHEN** người dùng tự đổi model trong Flow UI của project lẻ
- **THEN** hệ thống SHALL giữ nguyên Flow project URL của project lẻ và dùng đúng model đang được chọn khi job tiếp tục

### Requirement: Gắn Flow project chung cho series
Hệ thống SHALL gắn mỗi series dài tập với một Flow/Veo project URL active dùng chung cho mọi episode project trong series.

#### Scenario: Episode đầu tiên trong series chưa có binding
- **WHEN** episode đầu tiên của series bắt đầu tạo clip Veo và series chưa có Flow project binding
- **THEN** hệ thống SHALL tạo hoặc mở một Flow project mới, lưu URL ở cấp series và dùng URL này cho episode hiện tại

#### Scenario: Episode sau dùng lại binding series
- **WHEN** episode sau thuộc cùng series bắt đầu tạo clip Veo
- **THEN** hệ thống SHALL dùng lại Flow project URL cấp series và MUST NOT tạo project Flow riêng cho episode nếu URL series còn dùng được

#### Scenario: Project thuộc series không ghi đè binding lẻ
- **WHEN** project có `series_id`
- **THEN** hệ thống SHALL ưu tiên Flow project binding cấp series và MUST NOT tạo binding lẻ gây tách continuity khỏi series

#### Scenario: Chặn nhiều job cùng series
- **WHEN** một episode trong series đang có job Veo active dùng Flow project chung
- **THEN** hệ thống SHALL chặn hoặc xếp chờ job Veo khác trong cùng series để tránh hai runner cùng thao tác một Flow project

### Requirement: Chỉ tạo Flow project mới khi link cũ không còn dùng được
Hệ thống SHALL kiểm tra và phục hồi Flow project URL đã lưu trước khi tạo project mới.

#### Scenario: Link cũ mở được
- **WHEN** hệ thống mở Flow project URL đã lưu và workspace load được
- **THEN** hệ thống SHALL giữ binding active và tiếp tục job trong project cũ

#### Scenario: Link cũ yêu cầu đăng nhập lại
- **WHEN** Flow project URL dẫn tới login, chọn tài khoản, 2FA hoặc CAPTCHA
- **THEN** hệ thống SHALL chuyển session/job sang trạng thái cần người dùng đăng nhập lại và MUST NOT tạo Flow project mới

#### Scenario: Flow application error có thể phục hồi
- **WHEN** Flow project URL gặp application error hoặc trang chưa load ổn định
- **THEN** hệ thống SHALL thử refresh/recover theo giới hạn cấu hình trước khi kết luận link invalid

#### Scenario: Link cũ thật sự invalid
- **WHEN** hệ thống xác minh Flow project URL không còn là project hợp lệ, project bị xóa hoặc không thể vào workspace sau các bước phục hồi
- **THEN** hệ thống SHALL đánh dấu binding cũ `invalid` hoặc `rotated`, tạo Flow project mới và lưu binding mới

### Requirement: Map clip an toàn trong cùng Flow project
Hệ thống SHALL map clip về đúng shot khi nhiều shot hoặc episode cùng dùng một Flow project.

#### Scenario: Baseline media trước khi submit
- **WHEN** runner chuẩn bị gửi prompt cho một shot
- **THEN** adapter SHALL ghi baseline media count, media URL hash hoặc tín hiệu tương đương trước khi submit prompt

#### Scenario: Chỉ download media mới
- **WHEN** Veo tạo xong media sau prompt
- **THEN** hệ thống SHALL chỉ download media mới phát sinh sau baseline hoặc media có correlation rõ với item hiện tại

#### Scenario: Media mới mơ hồ
- **WHEN** Flow project có nhiều media mới và hệ thống không xác định được clip nào thuộc shot hiện tại
- **THEN** item SHALL fail hoặc pause với lỗi retryable tiếng Việt và MUST NOT import clip mơ hồ làm clip active

#### Scenario: Download theo item
- **WHEN** hệ thống tải clip cho một shot
- **THEN** file SHALL được tải vào thư mục riêng theo job/item và validate video trước khi import

### Requirement: Dùng đúng model đang được chọn trong Flow
Hệ thống SHALL dùng đúng model provider đang được chọn trong Flow UI của tài khoản hiện tại và MUST NOT tự đặt model mặc định thay người dùng.

#### Scenario: Flow đang chọn sẵn model
- **WHEN** adapter chuẩn bị submit prompt và Flow UI đã có model đang được chọn
- **THEN** hệ thống SHALL dùng model đang được chọn đó và MUST NOT tự click đổi sang model khác

#### Scenario: Đọc được model đang chọn
- **WHEN** hệ thống đọc được label model đang chọn hoặc cost label từ UI Flow
- **THEN** hệ thống SHALL lưu label đã sanitize vào metadata/report của job hoặc item

#### Scenario: Không đọc được label model
- **WHEN** hệ thống không đọc được label model đang chọn nhưng prompt vẫn có thể submit an toàn
- **THEN** hệ thống SHALL tiếp tục dùng lựa chọn hiện tại của Flow và ghi model là chưa xác định, thay vì tự đổi model

### Requirement: Không tự fallback model khi quota hoặc credit lỗi
Hệ thống MUST NOT tự đổi sang model khác khi model đang chọn hết quota, hết credit hoặc bị giới hạn, trừ khi người dùng đã tự đổi trong Flow UI rồi resume job.

#### Scenario: Model đang chọn hết quota hoặc credit
- **WHEN** Flow báo model đang chọn hết quota, hết credit hoặc không thể generate vì giới hạn model
- **THEN** hệ thống SHALL pause job với thông báo tiếng Việt và yêu cầu người dùng tự đổi model trong Flow nếu muốn tiếp tục

#### Scenario: Người dùng đổi model rồi resume
- **WHEN** job đang pause vì model/quota và người dùng đã tự đổi model trong Flow UI
- **THEN** resume SHALL dùng đúng model mới đang được chọn trong cùng Flow project URL

#### Scenario: Không quét fallback tự động
- **WHEN** model đang chọn bị giới hạn
- **THEN** hệ thống MUST NOT quét dropdown để chọn model miễn phí hoặc model có phí thay người dùng

#### Scenario: Không hard-code model mặc định
- **WHEN** hệ thống chạy clip generation ở bất kỳ tài khoản nào
- **THEN** hệ thống MUST NOT hard-code `Omni Flash` hoặc model khác làm mặc định; lựa chọn model thuộc về Flow UI của tài khoản đó

#### Scenario: Không tạo project mới khi người dùng đổi model
- **WHEN** người dùng đổi model thủ công trong Flow UI rồi resume job
- **THEN** hệ thống SHALL giữ nguyên Flow project URL hiện tại và MUST NOT tạo Flow project mới chỉ vì model thay đổi

### Requirement: Codex auto-repair lỗi kỹ thuật app
Hệ thống SHALL cho phép Codex sửa code có kiểm soát khi lỗi thuộc nhóm kỹ thuật app và có đủ context để kiểm chứng.

#### Scenario: Lỗi selector Flow đổi
- **WHEN** adapter fail vì không tìm thấy selector/nút/dropdown Flow và lỗi thuộc allowlist auto-repair
- **THEN** hệ thống SHALL pause job, lưu repair context đã redaction và cho Codex tạo patch trong phạm vi file được phép

#### Scenario: Lỗi download hoặc map clip
- **WHEN** download watcher, media correlation hoặc import mapping fail do bug app có thể test được
- **THEN** Codex MAY sửa code liên quan, chạy test bắt buộc và resume item nếu test pass

#### Scenario: Test pass sau repair
- **WHEN** Codex repair tạo patch và tất cả test/lint/smoke test bắt buộc pass
- **THEN** hệ thống SHALL reload/restart phần cần thiết nếu cấu hình yêu cầu và resume job từ item lỗi

#### Scenario: Test fail sau repair
- **WHEN** patch của Codex không pass test bắt buộc
- **THEN** hệ thống SHALL không resume job tự động, SHALL rollback hoặc giữ patch để review theo policy và SHALL hiển thị báo cáo tiếng Việt

#### Scenario: Hết số lần repair
- **WHEN** cùng một lỗi đạt giới hạn repair attempts
- **THEN** hệ thống SHALL dừng auto-repair và yêu cầu người dùng hoặc developer xử lý thủ công

### Requirement: Không auto-repair lỗi tài khoản hoặc policy provider
Hệ thống MUST NOT dùng Codex auto-repair để vượt qua rào chắn tài khoản hoặc chính sách của Google/Veo.

#### Scenario: Login hoặc xác minh
- **WHEN** provider yêu cầu login, chọn tài khoản, 2FA hoặc CAPTCHA
- **THEN** hệ thống SHALL pause job và yêu cầu người dùng thao tác trong Chrome, và MUST NOT để Codex cố bypass

#### Scenario: Billing hoặc payment
- **WHEN** provider báo lỗi billing, payment hoặc yêu cầu mua credit
- **THEN** hệ thống SHALL pause job và MUST NOT tự mua credit hoặc tự đổi sang lựa chọn có phí nếu chưa được bật rõ

#### Scenario: Policy block
- **WHEN** provider chặn prompt vì policy, public figure hoặc nội dung không được phép
- **THEN** hệ thống SHALL báo lỗi tiếng Việt và MUST NOT để Codex sửa code nhằm vượt policy

#### Scenario: Quota thật đã hết
- **WHEN** provider báo hết quota thật và người dùng chưa chọn model khác có thể chạy được trong Flow
- **THEN** hệ thống SHALL pause job và yêu cầu người dùng chọn hướng xử lý

### Requirement: Báo cáo và UI tiếng Việt cho Flow binding, model và Codex repair
Hệ thống SHALL hiển thị trạng thái Flow project binding, model provider và Codex repair bằng tiếng Việt dễ hiểu.

#### Scenario: Hiển thị Flow project đang dùng
- **WHEN** người dùng mở panel Veo/Chrome của project
- **THEN** UI SHALL hiển thị project đang dùng binding lẻ hay binding series, trạng thái binding và action mở đúng Flow project trong Chrome

#### Scenario: Hiển thị model đang dùng
- **WHEN** người dùng cấu hình hoặc chạy job Veo
- **THEN** UI SHALL hiển thị model Flow đang được chọn nếu đọc được, hoặc model thực tế đã dùng gần nhất nếu có

#### Scenario: Hiển thị Codex repair
- **WHEN** job đang pause để Codex sửa lỗi
- **THEN** UI SHALL hiển thị trạng thái đang sửa, lỗi đang xử lý, tests đang chạy và kết quả pass/fail bằng tiếng Việt

#### Scenario: Không bắt người dùng hiểu raw code
- **WHEN** UI hiển thị lỗi hoặc trạng thái repair
- **THEN** UI SHALL dùng mô tả tiếng Việt làm nội dung chính và chỉ đưa raw error code vào phần debug nếu cần

### Requirement: Bảo mật và redaction cho binding, model và repair
Hệ thống SHALL giới hạn dữ liệu nhạy cảm được lưu, log hoặc export trong quá trình dùng Flow project binding, model đang chọn và Codex repair.

#### Scenario: Không export URL/cookie nhạy cảm
- **WHEN** người dùng tạo package, debug export hoặc xóa project
- **THEN** hệ thống MUST NOT đưa Chrome profile, cookie, token hoặc dữ liệu đăng nhập vào package/debug export

#### Scenario: Log binding an toàn
- **WHEN** hệ thống log Flow project binding
- **THEN** log SHALL dùng provider project hash hoặc URL redacted thay vì full URL nếu không cần mở trực tiếp trong UI nội bộ

#### Scenario: Log model an toàn
- **WHEN** hệ thống log model provider
- **THEN** log MAY lưu model label và cost label đã sanitize nhưng MUST NOT lưu DOM đầy đủ hoặc thông tin tài khoản nhạy cảm

#### Scenario: Repair context đã redaction
- **WHEN** hệ thống lưu context cho Codex repair
- **THEN** context MUST NOT chứa cookie, token, credential, full DOM, full prompt dài hoặc nội dung người dùng nhạy cảm chưa truncate
