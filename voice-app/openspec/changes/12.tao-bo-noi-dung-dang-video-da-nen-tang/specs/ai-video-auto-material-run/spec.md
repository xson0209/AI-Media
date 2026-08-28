## ADDED Requirements

### Requirement: Auto-run tạo bộ nội dung đăng sau prompt và trước voice
Hệ thống SHALL chèn bước generate_publishing_metadata sau generate_prompts và trước review_prompts, voice hoặc subtitle đối với các material target yêu cầu bộ nội dung đăng.

#### Scenario: Luồng full materials
- **WHEN** auto-run có material_target = "full_materials"
- **THEN** thứ tự chính SHALL là generate_prompts, generate_publishing_metadata, review_prompts, generate_voice, waiting_voice, generate_subtitle
- **AND** hệ thống MUST NOT enqueue voice trước khi bộ nội dung đăng đã completed và không stale

#### Scenario: Luồng video clips
- **WHEN** auto-run có material_target = "video_clips"
- **THEN** hệ thống SHALL tạo bộ nội dung đăng sau prompt và trước khi tiếp tục các bước clip, voice, subtitle và render hiện có
- **AND** readiness render hiện có SHALL tiếp tục được áp dụng ngoài readiness của bộ nội dung đăng

#### Scenario: Bộ nội dung đăng đã hợp lệ
- **WHEN** project đã có bộ nội dung đăng completed, không stale và fingerprint khớp input hiện tại
- **THEN** auto-run SHALL skip generate_publishing_metadata
- **AND** hệ thống MUST NOT tạo revision metadata mới không cần thiết

#### Scenario: Bộ nội dung đăng thiếu hoặc stale
- **WHEN** prompt video đã hợp lệ nhưng bộ nội dung đăng đang missing, stale hoặc failed retryable
- **THEN** auto-run SHALL chạy generate_publishing_metadata mà không force regenerate prompt hợp lệ

#### Scenario: Tạo bộ nội dung đăng thất bại
- **WHEN** Codex, mapping hoặc validation thất bại ở generate_publishing_metadata
- **THEN** auto-run SHALL dừng với current_step = "generate_publishing_metadata" và trạng thái lỗi phù hợp
- **AND** auto-run MUST NOT tạo voice, subtitle, clip hoặc render từ run đó cho tới khi lỗi được xử lý

#### Scenario: Retry từ bước bộ nội dung đăng
- **WHEN** người dùng retry auto-run đã fail ở generate_publishing_metadata
- **THEN** hệ thống SHALL resume từ artifact thiếu hoặc stale gần nhất
- **AND** hệ thống MUST NOT tạo lại story, shot hoặc prompt đang hợp lệ

#### Scenario: Dùng planning pool chung
- **WHEN** auto-run gọi Codex để tạo bộ nội dung đăng
- **THEN** request SHALL đi qua planning pool và cơ chế giới hạn concurrency hiện có
- **AND** hệ thống MUST NOT tạo một đường gọi Codex riêng bỏ qua giới hạn tài nguyên chung

### Requirement: Gate duyệt prompt đồng thời duyệt bộ nội dung đăng
Hệ thống SHALL dùng review gate review_stage = "prompts" hiện có để người dùng duyệt đồng thời prompt video và bộ nội dung đăng, thay vì thêm một gate thứ ba.

#### Scenario: Review-gated dừng sau khi có đủ dữ liệu
- **WHEN** auto-run review_gated đã tạo xong prompt video và bộ nội dung đăng cho target yêu cầu metadata
- **THEN** auto-run SHALL chuyển status = "needs_review" với review_stage = "prompts"
- **AND** UI SHALL diễn giải gate này là duyệt prompt video và nội dung đăng
- **AND** hệ thống MUST NOT tạo voice hoặc subtitle trước khi người dùng tiếp tục

#### Scenario: Metadata chưa hợp lệ thì chưa mở gate
- **WHEN** prompt video đã hoàn tất nhưng bộ nội dung đăng còn missing, stale hoặc invalid
- **THEN** auto-run MUST NOT coi gate prompt là sẵn sàng để duyệt
- **AND** hệ thống SHALL hoàn thành hoặc báo lỗi bước metadata trước

#### Scenario: Full-auto tự duyệt prompt và nội dung đăng
- **WHEN** auto-run full_auto tạo thành công prompt và bộ nội dung đăng
- **THEN** hệ thống SHALL ghi nhận gate prompts là auto-approved
- **AND** hệ thống SHALL tiếp tục sang voice/subtitle mà không chuyển needs_review

#### Scenario: Nội dung thay đổi trong lúc chờ duyệt
- **WHEN** người dùng sửa story, narration, shot, prompt, target_language, mục đích video, audience hoặc CTA trong lúc run đang needs_review
- **THEN** hệ thống SHALL đánh dấu bộ nội dung đăng phụ thuộc là stale và vô hiệu quyết định duyệt cũ nếu output đã thay đổi
- **AND** khi continue, auto-run SHALL tạo lại metadata cần thiết và quay lại gate prompts trước khi tạo voice

#### Scenario: Tiếp tục sau khi duyệt
- **WHEN** người dùng approve gate prompts và prompt cùng bộ nội dung đăng vẫn hợp lệ
- **THEN** full_materials SHALL tiếp tục từ generate_voice
- **AND** video_clips SHALL tiếp tục theo bước clip hiện có
- **AND** publishing_kit SHALL hoàn tất mà không tạo voice hoặc subtitle

### Requirement: Giữ tương thích prompts_only và thêm target publishing_kit
Hệ thống SHALL giữ nguyên hành vi của prompts_only và bổ sung publishing_kit làm material target riêng cho trường hợp cần prompt cùng bộ nội dung đăng nhưng không cần voice hoặc subtitle.

#### Scenario: Client cũ dùng prompts_only
- **WHEN** client gửi material_target = "prompts_only"
- **THEN** auto-run SHALL hoàn tất sau prompt và gate prompt hiện có
- **AND** hệ thống MUST NOT âm thầm đổi prompts_only thành target bắt buộc tạo metadata, voice hoặc subtitle

#### Scenario: Chạy publishing kit
- **WHEN** client gửi material_target = "publishing_kit"
- **THEN** auto-run SHALL tạo story, shot, prompt video và bộ nội dung đăng theo artifact cần thiết
- **AND** auto-run MUST NOT yêu cầu voice profile
- **AND** auto-run MUST NOT tạo voice hoặc subtitle

#### Scenario: Publishing kit review-gated
- **WHEN** publishing_kit chạy ở mode review_gated
- **THEN** auto-run SHALL dừng tại review_stage = "prompts" sau khi prompt và bộ nội dung đăng đã sẵn sàng
- **AND** run SHALL chỉ hoàn tất sau khi người dùng approve

#### Scenario: Publishing kit full-auto
- **WHEN** publishing_kit chạy ở mode full_auto
- **THEN** auto-run SHALL tự approve gate prompt và hoàn tất sau khi prompt cùng bộ nội dung đăng hợp lệ

#### Scenario: Client không gửi material target
- **WHEN** client cũ không gửi material_target
- **THEN** hệ thống SHALL tiếp tục dùng default full_materials
- **AND** default này SHALL tạo bộ nội dung đăng trước voice và subtitle theo luồng mới

### Requirement: Auto-run summary phản ánh readiness của bộ nội dung đăng
Hệ thống SHALL trả trạng thái bộ nội dung đăng trong summary và dùng trạng thái đó khi tính readiness cho các target có yêu cầu metadata.

#### Scenario: Poll trạng thái auto-run
- **WHEN** frontend poll auto-run
- **THEN** response SHALL có trạng thái metadata, revision hoặc readiness tương đương, số nền tảng hoàn tất và cờ stale
- **AND** response MUST NOT yêu cầu frontend đọc full title, description hoặc prompt thumbnail từ technical debug details

#### Scenario: Readiness full materials
- **WHEN** material_target = "full_materials"
- **THEN** core_ready SHALL chỉ là true khi prompt video, bộ nội dung đăng, mọi voice bắt buộc và subtitle đều completed, không stale

#### Scenario: Readiness publishing kit
- **WHEN** material_target = "publishing_kit"
- **THEN** core_ready SHALL là true khi prompt video và bộ nội dung đăng completed, không stale
- **AND** voice hoặc subtitle missing MUST NOT làm target này thất bại

#### Scenario: Readiness prompts only
- **WHEN** material_target = "prompts_only"
- **THEN** core_ready SHALL tiếp tục chỉ phụ thuộc prompt readiness
- **AND** metadata, voice hoặc subtitle missing MUST NOT làm target này thất bại

#### Scenario: Readiness video clips
- **WHEN** material_target = "video_clips"
- **THEN** core_ready SHALL yêu cầu thêm bộ nội dung đăng completed, không stale bên cạnh clip/render readiness hiện có

#### Scenario: Resume run được tạo bởi phiên bản cũ
- **WHEN** một run cũ của full_materials hoặc video_clips được resume sau khi triển khai change này và chưa có bộ nội dung đăng
- **THEN** hệ thống SHALL chèn bước metadata còn thiếu trước voice hoặc render
- **AND** hệ thống MUST NOT làm hỏng run cũ chỉ vì step_results_json chưa có field metadata mới
