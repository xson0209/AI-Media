## ADDED Requirements

### Requirement: Mỗi video có Narrative Contract được version hóa và duyệt
Hệ thống BẮT BUỘC (MUST) quản lý một Narrative Contract có revision, trạng thái duyệt, audience, goal, central promise, central question, content spine, hook, payoff, CTA và provenance cho từng project AI Video.

#### Scenario: Tạo nội dung downstream từ contract chưa duyệt
- **WHEN** Narrative Contract chưa ở trạng thái approved
- **THEN** hệ thống KHÔNG ĐƯỢC coi shot, prompt, voice, subtitle hoặc release snapshot cuối là sẵn sàng
- **AND** PHẢI yêu cầu duyệt contract hoặc hiển thị trạng thái review tương ứng

#### Scenario: Contract được sửa sau khi đã tạo artifact
- **WHEN** một revision mới thay đổi hook, content spine, payoff, CTA hoặc beat bắt buộc
- **THEN** artifact phụ thuộc revision cũ PHẢI chuyển stale theo dependency
- **AND** revision cũ PHẢI được giữ để truy vết

### Requirement: AI Video dùng đúng ba candidate độc lập và critic tách biệt
Hệ thống BẮT BUỘC (MUST) tạo đúng ba candidate khác chiến lược từ cùng một context snapshot và dùng critic tách biệt để đánh giá trước khi chọn hoặc synthesis.

#### Scenario: Ba candidate chỉ đổi câu chữ
- **WHEN** candidate không khác đáng kể về hook, cấu trúc, cảm xúc, hình ảnh hoặc cách giải quyết
- **THEN** bộ candidate PHẢI bị coi là chưa hợp lệ
- **AND** hệ thống PHẢI tạo lại candidate bị trùng trong giới hạn retry

#### Scenario: Synthesis từ nhiều candidate
- **WHEN** người dùng yêu cầu tổng hợp
- **THEN** hệ thống PHẢI lưu phần được lấy từ candidate nào và lý do
- **AND** synthesis PHẢI qua canon, originality, hook-payoff và coherence check
- **AND** KHÔNG ĐƯỢC tự duyệt synthesis thay người dùng

### Requirement: Context được biên dịch đúng theo từng nhiệm vụ
Hệ thống BẮT BUỘC (MUST) biên dịch và lưu context snapshot riêng cho story, shot, prompt, voice và subtitle, đồng thời áp dụng đúng thứ tự ưu tiên giữa Series Canon, Project Memory và working draft.

#### Scenario: Tạo prompt video cho một beat
- **WHEN** hệ thống tạo prompt cho một production segment
- **THEN** context PHẢI ghim beat, state in/out, action, continuity, duration, reference và negative rules liên quan
- **AND** KHÔNG ĐƯỢC gửi toàn bộ nguồn dài hoặc context không liên quan chỉ để lấp đầy prompt

#### Scenario: Tạo voice hoặc subtitle
- **WHEN** hệ thống tạo voice hoặc subtitle
- **THEN** context PHẢI dùng narration revision cuối đã duyệt, speaker, language, emotion và timing
- **AND** transcript nguồn PHẢI chỉ được coi là evidence, không phải lời đọc cuối

### Requirement: Mỗi artifact downstream ánh xạ tới beat và narrative revision
Hệ thống BẮT BUỘC (MUST) lưu `narrative_contract_id`, `narrative_revision`, `beat_id` và context/dependency revision trên scene, shot, prompt, voice và subtitle hoặc artifact mapping tương đương.

#### Scenario: Artifact thiếu beat mapping
- **WHEN** một scene, shot, prompt, voice hoặc subtitle không xác định được beat mà nó phục vụ
- **THEN** artifact PHẢI chuyển needs_review hoặc blocked
- **AND** KHÔNG ĐƯỢC coi artifact là sẵn sàng cho release

#### Scenario: Nhiều production segment cùng một beat
- **WHEN** một beat cần nhiều segment để thể hiện
- **THEN** các segment CÓ THỂ dùng cùng `beat_id`
- **AND** mỗi segment PHẢI có production purpose riêng mà không giả tạo thông tin mới hoặc lặp narration máy móc

### Requirement: Mỗi beat phải tạo tiến triển nội dung
Hệ thống BẮT BUỘC (MUST) kiểm tra vai trò, thông tin mới, thay đổi cảm xúc hoặc stakes, câu hỏi được trả lời, open loop tiếp theo và micro-payoff của từng beat.

#### Scenario: Beat có thể xóa mà không mất giá trị
- **WHEN** xóa một beat không làm mất thông tin, logic, cảm xúc, bằng chứng, setup hoặc payoff
- **THEN** hệ thống PHẢI ghi `content_stagnation_risk` hoặc lỗi tương đương
- **AND** beat KHÔNG ĐƯỢC qua quality gate chỉ vì có nhiều hiệu ứng, camera hoặc SFX

#### Scenario: Hook không được payoff trả lời
- **WHEN** central promise hoặc central question trong hook không được payoff giải quyết đúng
- **THEN** hệ thống PHẢI tạo blocking error hook-payoff
- **AND** KHÔNG ĐƯỢC tạo release snapshot sẵn sàng

### Requirement: Continuity được kiểm tra bằng state in và state out
Hệ thống BẮT BUỘC (MUST) theo dõi state in/out của nhân vật, cảm xúc, kiến thức, địa điểm, đạo cụ và open loop giữa các beat hoặc segment liền kề.

#### Scenario: Trạng thái đoạn sau không nối được đoạn trước
- **WHEN** state out của đoạn trước mâu thuẫn với state in của đoạn sau mà không có hành động hoặc transition giải thích
- **THEN** hệ thống PHẢI tạo continuity error kèm hai artifact và bằng chứng liên quan
- **AND** đoạn bị ảnh hưởng PHẢI chuyển needs_review hoặc blocked theo mức nghiêm trọng

#### Scenario: Thay đổi continuity có chủ đích
- **WHEN** người dùng hoặc nội dung yêu cầu time jump, location jump, wardrobe change hoặc thay đổi trạng thái có chủ đích
- **THEN** hệ thống PHẢI lưu transition/reason tương ứng
- **AND** KHÔNG ĐƯỢC báo lỗi chỉ vì state trước và sau khác nhau

### Requirement: Auto-run phải chạy quality gate trước khi đi tiếp
Hệ thống BẮT BUỘC (MUST) chạy story quality gate trước khi duyệt story và prompt quality gate trước khi duyệt prompt trong đường chạy auto-run.

#### Scenario: Full auto gặp lỗi chặn
- **WHEN** full auto gặp canon, originality, hook-payoff, missing beat mapping, stale narration hoặc continuity blocking error
- **THEN** auto-run PHẢI dừng ở trạng thái needs_review hoặc blocked
- **AND** KHÔNG ĐƯỢC tự override hoặc tiếp tục tạo voice, subtitle, clip hay render

#### Scenario: Chỉ có warning được cấu hình cho phép
- **WHEN** quality gate chỉ có warning không chặn và policy cho phép tiếp tục
- **THEN** auto-run CÓ THỂ đi tiếp
- **AND** PHẢI lưu warning, evidence và policy đã dùng

### Requirement: Repair chỉ sửa đúng phạm vi lỗi và có giới hạn
Hệ thống BẮT BUỘC (MUST) giới hạn targeted repair theo artifact/beat bị lỗi, giữ lịch sử phiên bản và dừng sau số lần cấu hình.

#### Scenario: Prompt chỉ lỗi camera hoặc kỹ thuật
- **WHEN** prompt chỉ lỗi framing, camera, duration hoặc renderability
- **THEN** repair PHẢI giữ central promise, payoff, CTA, beat content và narration đã duyệt
- **AND** PHẢI lưu thay đổi trước/sau

#### Scenario: Repair vẫn không đạt sau giới hạn
- **WHEN** artifact vẫn không đạt sau tối đa số lần repair
- **THEN** trạng thái PHẢI chuyển needs_review hoặc blocked
- **AND** KHÔNG ĐƯỢC tiếp tục vòng sửa vô hạn

### Requirement: Social publishing chỉ đọc release snapshot đã duyệt
Hệ thống BẮT BUỘC (MUST) tách content production khỏi social publishing bằng một release snapshot bất biến hoặc có version.

#### Scenario: Luồng publishing nhận một video sẵn sàng
- **WHEN** social publishing chuẩn bị batch đăng
- **THEN** nó PHẢI tham chiếu project, narrative revision, render revision và metadata revision từ release snapshot
- **AND** KHÔNG ĐƯỢC sửa story, beat, shot, prompt, voice, subtitle hoặc render artifact

#### Scenario: Nội dung đổi sau khi đã chuẩn bị đăng
- **WHEN** dependency của release snapshot thay đổi
- **THEN** snapshot và publish batch liên quan PHẢI chuyển stale
- **AND** hệ thống PHẢI tạo snapshot/batch mới thay vì ghi đè lịch sử đã chuẩn bị hoặc đã đăng
