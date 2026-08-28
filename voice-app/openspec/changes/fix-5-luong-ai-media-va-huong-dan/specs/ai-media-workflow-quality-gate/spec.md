## ADDED Requirements

### Requirement: Năm workspace phải mở và hiển thị dữ liệu nghiệp vụ thật
Hệ thống SHALL mở được `/story-studio`, `/comic-series-analysis`, `/ai-video`, `/research` và `/video-inspiration`, đồng thời hiển thị nội dung nghiệp vụ tương ứng từ backend thật mà không có lỗi console nghiêm trọng hoặc request bắt buộc thất bại.

#### Scenario: Mở đủ năm workspace
- **WHEN** người kiểm thử lần lượt truy cập năm route trên Vite đang kết nối FastAPI thật
- **THEN** mỗi route hiển thị heading/workspace đúng, dữ liệu hoặc empty state hợp lệ và các request bắt buộc trả kết quả thành công

### Requirement: Research phải dùng nội dung Người Que thật
Quy trình Research MUST dùng project **“Nghiên cứu Series: Người Que”**, source/memory, lần chạy, ý tưởng và lựa chọn thật đã có. Hệ thống và tài liệu MUST hạn chế dữ liệu ví dụ, MUST NOT tạo tên kiểu `codex_test`, và mọi nội dung phụ mới SHALL tiếp nối chủ đề Người Que với giá trị sử dụng thực tế.

#### Scenario: Mở project Research chuẩn
- **WHEN** người dùng mở `/research`
- **THEN** project “Nghiên cứu Series: Người Que” được chọn hoặc có thể chọn, các nguồn/lần chạy/phương án/memory thật hiển thị và không bị thay bằng dữ liệu mẫu

#### Scenario: Cần tạo dữ liệu Research phụ
- **WHEN** một thao tác ghi là bắt buộc để xác minh chấm điểm, phát triển nội dung hoặc handoff
- **THEN** dữ liệu mới dùng tiêu đề/nội dung Người Que có ý nghĩa, không chứa `codex_test`, không xóa hay ghi đè dữ liệu gốc và ID đầu ra được ghi lại

### Requirement: Story Studio phải xác minh chuỗi truyện đến đầu ra sản xuất
Quy trình Story Studio SHALL mở được series và tập thật, hiển thị canon/nhân vật/tham chiếu/prompt, thực hiện được hành động xuất hoặc handoff phù hợp và giữ liên kết series/tập trong đầu ra.

#### Scenario: Kiểm tra series truyện thật
- **WHEN** người dùng chọn một series có tập và dữ liệu canon hiện có
- **THEN** UI hiển thị tập, hồ sơ nhân vật, trạng thái canon, prompt hình/video và các hành động hợp lệ theo trạng thái

#### Scenario: Handoff Story sang AI Video
- **WHEN** người dùng handoff một tập hoặc bản master đã đủ điều kiện
- **THEN** dự án AI Video đích mở được và giữ title, series/episode liên quan, nội dung nguồn và cấu hình đầu ra được duyệt

### Requirement: Comic Series Analysis phải xác minh nguồn đến gói phân tích
Quy trình Comic Series Analysis SHALL mở được job thật, hiển thị trạng thái nguồn/panel/phân tích/rewrite/review, cho phép hành động hợp lệ theo state machine và tạo hoặc mở handoff mà không làm mất provenance.

#### Scenario: Mở job truyện tranh đã phân tích
- **WHEN** người dùng chọn job thật có kết quả hoàn chỉnh hoặc một phần
- **THEN** UI hiển thị source, panel, analysis package, trạng thái review và lỗi/cảnh báo có thể hành động nếu tồn tại

#### Scenario: Chuyển kết quả truyện tranh sang series
- **WHEN** người dùng handoff một analysis package đủ điều kiện
- **THEN** series/tập đích giữ title nguồn, revision, nhân vật/canon và liên kết provenance về job truyện tranh

### Requirement: AI Video phải xác minh chuỗi lập kế hoạch và đầu ra
Quy trình AI Video SHALL mở dự án thật, xác minh provider lập kế hoạch, tải đầy đủ story/scene/shot/prompt khi có, và thực hiện các bước hợp lệ từ phát triển nội dung đến package/render readiness theo cấu hình hiện hành.

#### Scenario: Mở dự án AI Video thật
- **WHEN** người dùng chọn một dự án hiện có hoặc dự án Người Que được handoff
- **THEN** UI hiển thị trạng thái dự án, story/scene/shot/prompt, provider/resource readiness và chỉ bật hành động phù hợp với trạng thái

#### Scenario: Chạy bước AI có provider sẵn sàng
- **WHEN** Codex planning provider báo ready và người dùng chạy bước phát triển hoặc tạo prompt trên dữ liệu thật
- **THEN** job hoàn thành hoặc trả lỗi có mã/thông điệp hành động được, dự án lưu đầu ra và UI phản ánh trạng thái mới sau refresh

#### Scenario: Bước phụ thuộc Veo không sẵn sàng
- **WHEN** phiên Veo/Google hoặc project binding chưa sẵn sàng
- **THEN** UI hiển thị readiness/login action rõ ràng, không báo thành công giả và không làm hỏng các đầu ra planning đã có

### Requirement: Video Inspiration phải xác minh nguồn video đến kịch bản và handoff
Quy trình Video Inspiration SHALL mở job video thật, hiển thị transcript/hình/timeline/phân tích/kịch bản, cho phép rewrite hoặc dùng kết quả hiện có và handoff sang AI Video với provenance nguồn.

#### Scenario: Mở job video đã phân tích hoặc viết lại
- **WHEN** người dùng chọn job thật ở trạng thái `analyzed`, `rewritten` hoặc `ai_video_ready`
- **THEN** các tab dữ liệu tương ứng hiển thị nội dung thật, trạng thái job nhất quán và không mất transcript/timeline

#### Scenario: Handoff Video Inspiration sang AI Video
- **WHEN** người dùng đưa kịch bản tối ưu của job đủ điều kiện vào form AI Video
- **THEN** dự án/form đích giữ ý tưởng, kịch bản, định hướng, source job và link/file provenance liên quan

### Requirement: Mỗi lỗi tái hiện phải được sửa và xác minh lại
Mỗi lỗi phát hiện trong năm luồng MUST có bằng chứng tái hiện, patch có phạm vi, kiểm thử phù hợp và một lần chạy lại cùng kịch bản. Không được tuyên bố đạt dựa trên việc không thấy lỗi trong kiểm tra hẹp hơn yêu cầu.

#### Scenario: Phát hiện lỗi UI hoặc API
- **WHEN** snapshot, console, network, backend log hoặc kiểm thử cho thấy một hành vi sai
- **THEN** change ghi nguyên nhân, sửa đúng lớp, chạy kiểm thử liên quan và lặp lại thao tác browser cho đến khi bằng chứng đạt hoặc ghi rõ blocker thật

### Requirement: Phải có HTML hướng dẫn và ma trận chọn công cụ
Hệ thống SHALL cung cấp `docs/huong-dan-5-luong-ai-media.html` bằng tiếng Việt, tự chứa, mở trực tiếp được và mô tả cách dùng năm workspace, handoff, đầu vào/đầu ra, lỗi thường gặp và lựa chọn tối ưu theo chủ đề/mục đích. Phần Research SHALL dùng ví dụ Người Que thật.

#### Scenario: Tra cứu hướng dẫn theo mục đích
- **WHEN** người dùng mở file HTML và chọn một mục tiêu như nghiên cứu ý tưởng, phân tích truyện tranh, chuyển truyện thành series, học từ video hoặc sản xuất video
- **THEN** tài liệu chỉ ra workspace/chuỗi workspace khuyến nghị, lý do, dữ liệu cần chuẩn bị, các bước chính và đầu ra mong đợi

#### Scenario: Kiểm tra tài liệu trên desktop và mobile
- **WHEN** file HTML được mở ở viewport desktop và mobile
- **THEN** mục lục, bảng/ma trận, link năm route và nội dung tiếng Việt đọc được, không tràn ngang nghiêm trọng và không phụ thuộc tài nguyên mạng bắt buộc

### Requirement: Bằng chứng hoàn tất phải bao phủ toàn bộ phạm vi
Change SHALL lưu bằng chứng browser trong `output/playwright/full-flow-2026-08-11/`, kết quả gate code và bảng đối chiếu từng yêu cầu trước khi được đánh dấu hoàn tất.

#### Scenario: Audit hoàn tất
- **WHEN** người thực hiện chuẩn bị kết thúc change
- **THEN** từng route, luồng dữ liệu thật, handoff, lỗi đã sửa, gate tự động và file HTML đều có bằng chứng trực tiếp; mục thiếu bằng chứng vẫn được coi là chưa hoàn tất
