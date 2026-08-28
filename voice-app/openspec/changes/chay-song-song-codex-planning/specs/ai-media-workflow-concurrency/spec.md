## ADDED Requirements

### Requirement: Tối đa ba workflow AI media được xử lý cùng lúc
Hệ thống SHALL dùng một workflow pool toàn app để xử lý tối đa 3 work items active trong một backend process, bao gồm AI Video auto-run và Video Inspiration analyze/rewrite.

#### Scenario: Ba dự án khác nhau chạy cùng lúc
- **WHEN** ba dự án khác nhau được bắt đầu và chưa có dự án nào trùng work key
- **THEN** hệ thống SHALL cho phép cả ba dự án lấy workflow slot và tiến hành xử lý

#### Scenario: Dự án thứ tư tự chờ
- **WHEN** ba workflow slots đang được dùng và người dùng bắt đầu dự án thứ tư
- **THEN** hệ thống SHALL xếp dự án thứ tư vào hàng chờ, hiển thị trạng thái chờ bằng tiếng Việt và tự tiếp tục khi có slot

#### Scenario: Hai AI Video và một Video Inspiration dùng chung pool
- **WHEN** hai AI Video auto-runs và một Video Inspiration operation cùng active
- **THEN** hệ thống SHALL tính cả ba vào cùng giới hạn workflow toàn app

#### Scenario: Không chạy trùng cùng project hoặc job
- **WHEN** một work key đang chạy hoặc đang chờ và client yêu cầu chạy lại cùng work key
- **THEN** hệ thống MUST NOT tạo operation trùng và SHALL trả trạng thái hoặc thông báo tiếng Việt rõ ràng

#### Scenario: Trả slot trong mọi kết quả
- **WHEN** workflow hoàn tất, lỗi, bị hủy hoặc dừng để chờ người dùng duyệt/nhập thêm
- **THEN** hệ thống SHALL trả workflow slot để công việc tiếp theo có thể chạy

### Requirement: Codex planning dùng pool chung tối đa ba tác vụ
Hệ thống SHALL điều phối các Codex planning operations của AI Video và Video Inspiration qua planning pool chung, mặc định tối đa 3 operation chạy đồng thời và tối đa một operation trên mỗi work key.

#### Scenario: Video Inspiration không bypass planning pool
- **WHEN** Video Inspiration analyze hoặc rewrite cần gọi Codex
- **THEN** operation SHALL acquire planning slot trước khi chạy Codex và release slot sau success, timeout, invalid output, cancel hoặc exception

#### Scenario: AI Video manual và auto-run dùng cùng pool
- **WHEN** AI Video phát triển story, tạo shot hoặc tạo prompt từ manual API hay auto-run
- **THEN** operation SHALL dùng cùng planning pool và MUST NOT tạo Codex subprocess trùng trên cùng project

#### Scenario: Full prompt pack không bị chia nhỏ
- **WHEN** một AI Video project cần prompt cho nhiều shot/segment
- **THEN** hệ thống SHALL gửi toàn bộ phần cần tạo trong một full-pack Codex call của project đó và MUST NOT chia song song theo shot

#### Scenario: Không ghi nội dung nhạy cảm vào debug event
- **WHEN** hệ thống ghi event chờ/lấy/trả planning slot
- **THEN** event MUST NOT chứa full prompt, full source hoặc narration dài; chỉ lưu id, count, length, step và thời lượng an toàn

### Requirement: Video Inspiration analyze và rewrite chạy nền
Hệ thống SHALL xếp lịch Video Inspiration analyze/rewrite thành background operation để HTTP request trả nhanh và ứng dụng tiếp tục phục vụ polling/thao tác khác.

#### Scenario: Analyze endpoint trả sau khi xếp lịch
- **WHEN** người dùng bắt đầu analyze trên job hợp lệ
- **THEN** endpoint SHALL lưu trạng thái queued/active, schedule background runner và trả response mà không đợi toàn bộ STT/Codex pipeline hoàn tất

#### Scenario: Rewrite endpoint trả sau khi xếp lịch
- **WHEN** người dùng bắt đầu rewrite trên job hợp lệ
- **THEN** endpoint SHALL schedule background runner và trả response mà không đợi bốn bước Codex nối tiếp hoàn tất

#### Scenario: Ứng dụng vẫn phản hồi trong lúc Codex chạy
- **WHEN** background runner đang chạy FFmpeg, frame extraction hoặc Codex subprocess dài
- **THEN** health check, polling và thao tác dự án khác SHALL vẫn được phục vụ mà không bị block bởi công việc đồng bộ đó

#### Scenario: Mỗi background runner dùng DB session riêng
- **WHEN** Video Inspiration operation chạy ngoài request đã tạo nó
- **THEN** runner SHALL mở và đóng DB session riêng và MUST NOT dùng đồng thời request session giữa các thread

#### Scenario: Restart không để job treo vô hạn
- **WHEN** backend khởi động và DB còn job active nhưng không còn runtime task tương ứng
- **THEN** hệ thống SHALL đánh dấu job interrupted/failed bằng thông báo tiếng Việt và cho phép retry

### Requirement: Toàn ứng dụng chỉ tạo tối đa hai voice cùng lúc
Hệ thống SHALL áp dụng hard cap 2 voice inferences trong một backend process cho mọi đường generation, bao gồm queue workers và streaming/direct generation.

#### Scenario: Ba voice cùng sẵn sàng
- **WHEN** ba voice jobs cùng sẵn sàng chạy
- **THEN** tối đa hai jobs SHALL ở phần inference thật và job còn lại SHALL ở trạng thái queued cho đến khi có slot

#### Scenario: Streaming không bypass giới hạn
- **WHEN** một streaming generation được bắt đầu trong lúc hai queue workers đang inference
- **THEN** streaming generation SHALL chờ voice slot và tổng số inference MUST NOT vượt 2

#### Scenario: Cấu hình không thể nâng quá hai
- **WHEN** env/config yêu cầu generation concurrency lớn hơn 2
- **THEN** hệ thống SHALL clamp giá trị runtime về 2

#### Scenario: Slot được trả sau lỗi hoặc hủy
- **WHEN** voice generation hoàn tất, lỗi, timeout hoặc bị hủy
- **THEN** hệ thống SHALL trả inference slot để voice tiếp theo tự chạy

### Requirement: Trạng thái voice phản ánh đúng hàng đợi
Hệ thống SHALL phân biệt voice đã xếp hàng với voice đang chuẩn bị model và voice đang inference.

#### Scenario: Voice vừa được enqueue
- **WHEN** generation được đưa vào hàng đợi nhưng worker chưa nhận
- **THEN** generation và scene/shot liên quan SHALL có trạng thái `queued`

#### Scenario: Worker bắt đầu xử lý
- **WHEN** worker nhận generation và bắt đầu chuẩn bị model
- **THEN** trạng thái SHALL chuyển sang `loading_model`, sau đó `generating` khi inference bắt đầu

#### Scenario: UI không hiển thị raw status
- **WHEN** frontend nhận các trạng thái nội bộ
- **THEN** frontend SHALL hiển thị câu tiếng Việt dễ hiểu như `Đang chờ tạo giọng`, `Đang tải giọng đọc`, `Đang tạo giọng`

### Requirement: Hủy dự án dọn công việc đang chờ
Hệ thống SHALL truyền yêu cầu hủy xuống các background/voice jobs thuộc dự án mà chưa hoàn tất.

#### Scenario: Hủy AI Video có voice queued
- **WHEN** người dùng hủy auto-run và project có generation đang queued
- **THEN** các queued generations thuộc project SHALL bị hủy và MUST NOT chạy sau đó

#### Scenario: Không xóa voice đã hoàn tất
- **WHEN** người dùng hủy dự án có một số audio đã completed
- **THEN** hệ thống MUST NOT xóa các audio completed chỉ vì hủy phần còn lại

#### Scenario: Hủy Video Inspiration đang chờ workflow slot
- **WHEN** người dùng hủy Video Inspiration operation còn queued
- **THEN** operation SHALL rời hàng chờ và không bắt đầu pipeline

#### Scenario: Hủy operation đang chạy
- **WHEN** operation đang ở bước không thể dừng tức thời
- **THEN** hệ thống SHALL ghi nhận yêu cầu hủy, hiển thị `Đang dừng`, không bắt đầu bước nặng tiếp theo và chuyển terminal ở checkpoint an toàn

### Requirement: STT được bảo vệ bằng giới hạn riêng
Hệ thống SHALL dùng STT gate mặc định tối đa 1 inference cho Video Inspiration trong một backend process.

#### Scenario: Hai video cùng cần nhận dạng lời nói
- **WHEN** một Video Inspiration job đang chạy STT và job khác đến bước STT
- **THEN** job thứ hai SHALL chờ STT slot và tự tiếp tục khi job đầu trả slot

### Requirement: UI hiển thị trạng thái điều phối bằng tiếng Việt
Hệ thống SHALL cung cấp resource snapshots và frontend SHALL hiển thị trạng thái workflow/voice dễ hiểu cho người dùng không biết kỹ thuật.

#### Scenario: Hiển thị tổng quan đang chạy và đang chờ
- **WHEN** có workflow hoặc voice active/queued
- **THEN** UI SHALL hiển thị tối thiểu số dự án đang chạy, số dự án đang chờ, `Tạo giọng: x/2` và số voice đang chờ

#### Scenario: Video Inspiration không khóa toàn trang
- **WHEN** một Video Inspiration job đang analyze/rewrite nền
- **THEN** frontend SHALL chỉ khóa thao tác xung đột của job đó và SHALL cho phép người dùng chọn/tạo/bắt đầu job khác nếu còn workflow slot hoặc chấp nhận xếp hàng

#### Scenario: Chuyển màn hình không dừng dự án
- **WHEN** người dùng chuyển sang project hoặc khu vực khác trong lúc background operation đang chạy
- **THEN** operation SHALL tiếp tục và trạng thái mới nhất SHALL xuất hiện lại khi người dùng quay lại hoặc refresh

### Requirement: Giới hạn được công bố theo phạm vi single-process
Hệ thống SHALL coi các giới hạn workflow/planning/voice/STT là toàn cục trong một backend process local và MUST NOT tuyên bố chúng là giới hạn phân tán giữa nhiều process/replica.

#### Scenario: Runtime local mặc định
- **WHEN** ứng dụng chạy với một backend process như cấu hình desktop/local hiện tại
- **THEN** các giới hạn SHALL lần lượt là workflow 3, planning 3, voice 2 và STT 1 nếu không có cấu hình hạ thấp hợp lệ

