## ADDED Requirements

### Requirement: Khởi chạy auto tạo nguyên liệu cho AI Video phase 2
Hệ thống SHALL cho phép người dùng khởi chạy một auto-run cho AI Video project phase 2 để tự điều phối các bước tạo story, segment, prompt video, voice và phụ đề.

#### Scenario: Bắt đầu auto-run hợp lệ
- **WHEN** người dùng bấm Auto tạo nguyên liệu trên một project phase 2 có source content hợp lệ
- **THEN** hệ thống tạo auto-run với `project_id`, `mode`, `status`, `current_step`, `progress` và trả về run id để frontend poll trạng thái

#### Scenario: Chặn auto-run cho project không tồn tại
- **WHEN** client yêu cầu auto-run cho `project_id` không tồn tại
- **THEN** hệ thống từ chối request bằng lỗi tiếng Việt rằng không tìm thấy dự án video

#### Scenario: Chặn auto-run khi project thiếu source bắt buộc
- **WHEN** project chưa có topic hoặc source block có nội dung hợp lệ để AI phát triển story
- **THEN** hệ thống không bắt đầu planning và trả trạng thái `needs_input` hoặc lỗi tiếng Việt chỉ rõ cần bổ sung yêu cầu đầu vào

#### Scenario: Không chạy song song nhiều auto-run trên cùng project
- **WHEN** project đã có một auto-run ở trạng thái `queued`, `running`, `waiting_voice` hoặc `needs_review`
- **THEN** request start mới SHALL trả về run đang active hoặc từ chối bằng lỗi tiếng Việt, và MUST NOT tạo run song song gây trùng voice hoặc package

### Requirement: Chế độ duyệt từng chặng dừng ở story và prompt
Hệ thống SHALL hỗ trợ chế độ `review_gated` để tự chạy đến các điểm cần người dùng duyệt rồi dừng trước khi tạo artifact tốn thời gian.

#### Scenario: Dừng sau khi tạo story
- **WHEN** auto-run ở mode `review_gated` tạo xong story strategy, continuity bible và detailed script
- **THEN** auto-run chuyển sang `status = "needs_review"` với `review_stage = "story"` và MUST NOT tạo voice hoặc phụ đề trước khi người dùng tiếp tục

#### Scenario: Tiếp tục sau khi duyệt story
- **WHEN** người dùng bấm tiếp tục cho auto-run đang `needs_review` ở `review_stage = "story"`
- **THEN** hệ thống ghi nhận story đã được duyệt trong run, approve story nếu cần và resume từ bước tạo segment/shot

#### Scenario: Dừng sau khi tạo prompt video
- **WHEN** auto-run ở mode `review_gated` đã tạo segment/shot và prompt video cho các shot cần thiết
- **THEN** auto-run chuyển sang `status = "needs_review"` với `review_stage = "prompts"` và MUST NOT tạo voice, subtitle hoặc package trước khi người dùng tiếp tục

#### Scenario: Tiếp tục sau khi duyệt prompt
- **WHEN** người dùng bấm tiếp tục cho auto-run đang `needs_review` ở `review_stage = "prompts"`
- **THEN** hệ thống đọc lại project, shot và prompt mới nhất rồi resume từ bước tạo voice cho các shot còn thiếu hoặc stale

#### Scenario: Người dùng sửa thủ công trước khi tiếp tục
- **WHEN** người dùng chỉnh story, shot, prompt segment config hoặc voice profile trong lúc auto-run đang dừng `needs_review`
- **THEN** auto-run khi tiếp tục SHALL dùng trạng thái project mới nhất và SHALL không dùng snapshot cũ làm nguồn sự thật cho artifact tiếp theo

### Requirement: Chế độ tự chạy hết tự approve nhưng vẫn validate
Hệ thống SHALL hỗ trợ mode `full_auto` để tự approve các bước trung gian và chạy đến khi nguyên liệu lõi sẵn sàng, nhưng MUST không bỏ qua validation bắt buộc.

#### Scenario: Full auto chạy qua các điểm duyệt
- **WHEN** auto-run ở mode `full_auto` tạo xong story, segment và prompt video
- **THEN** hệ thống tự ghi nhận các bước trung gian là được duyệt trong phạm vi auto-run và tiếp tục sang voice/subtitle mà không chuyển `needs_review`

#### Scenario: Full auto thiếu voice profile
- **WHEN** auto-run ở mode `full_auto` cần tạo voice nhưng project chưa có voice profile hợp lệ
- **THEN** hệ thống dừng với `status = "needs_input"` hoặc `failed`, hiển thị lỗi tiếng Việt yêu cầu chọn voice profile, và MUST NOT tạo subtitle giả

#### Scenario: Full auto tôn trọng ngôn ngữ video
- **WHEN** project có `target_language = "en"` hoặc `target_language = "vi"`
- **THEN** auto-run SHALL tạo voice và subtitle bằng ngôn ngữ video đã chọn thông qua logic AI Video hiện có và MUST NOT tự fallback sang ngôn ngữ khác

#### Scenario: Full auto gặp planning provider chưa sẵn sàng
- **WHEN** AI planning provider chưa được cấu hình hoặc không thể chạy
- **THEN** auto-run dừng trước bước story/prompt với lỗi tiếng Việt rõ ràng và lưu error code để debug

### Requirement: Auto-run chạy idempotent và resume từ artifact đã có
Hệ thống SHALL đọc trạng thái artifact hiện tại trước mỗi bước để chỉ tạo artifact thiếu, stale hoặc failed retryable.

#### Scenario: Project đã có story hợp lệ
- **WHEN** auto-run bắt đầu trên project đã có story/detailed script còn mới và không bật force
- **THEN** hệ thống skip bước develop story và chuyển sang bước tiếp theo phù hợp với mode duyệt

#### Scenario: Project đã có prompt completed
- **WHEN** các shot của project đã có prompt video `completed` và không stale
- **THEN** hệ thống skip bước tạo prompt cho các shot đó và không tạo version prompt mới không cần thiết

#### Scenario: Project đã có một số voice completed
- **WHEN** một số shot narration đã có voice `completed` với audio path và duration hợp lệ
- **THEN** auto-run chỉ tạo voice cho các shot còn thiếu, stale hoặc failed retryable

#### Scenario: Retry sau lỗi không chạy lại toàn bộ
- **WHEN** auto-run failed ở bước voice hoặc subtitle rồi người dùng bấm retry sau khi sửa cấu hình
- **THEN** hệ thống resume từ bước lỗi gần nhất hoặc bước phụ thuộc còn thiếu, và MUST NOT force regenerate story/prompt đã hợp lệ

### Requirement: Điều phối voice và chờ hoàn tất trước khi tạo subtitle
Hệ thống SHALL tạo voice cho mọi shot có narration cần voice, chờ trạng thái voice terminal, rồi mới tạo phụ đề `.srt`.

#### Scenario: Enqueue voice cho shot cần narration
- **WHEN** auto-run đến bước tạo voice và shot có narration nhưng voice đang `missing`, `stale` hoặc retryable `failed`
- **THEN** hệ thống gọi luồng tạo voice AI Video hiện có cho shot đó với voice profile và language đúng

#### Scenario: Chờ voice hoàn tất
- **WHEN** một hoặc nhiều voice generation đã được enqueue và chưa terminal
- **THEN** auto-run chuyển hoặc giữ `current_step = "waiting_voice"`, poll/sync trạng thái voice từ database và chưa tạo subtitle

#### Scenario: Tạo subtitle sau khi mọi voice bắt buộc hoàn tất
- **WHEN** mọi shot có narration đã có `voice_status = "completed"`, audio path và audio duration hợp lệ
- **THEN** hệ thống tạo file subtitle `.srt` bằng luồng subtitle AI Video hiện có

#### Scenario: Một shot voice thất bại
- **WHEN** một hoặc nhiều shot voice chuyển sang `failed`
- **THEN** auto-run chuyển `failed`, lưu danh sách shot lỗi và failure reason, và MUST NOT tạo subtitle từ tập voice chưa đầy đủ

### Requirement: Hoàn tất khi prompt, voice và SRT sẵn sàng
Hệ thống SHALL coi auto-run hoàn tất khi nguyên liệu lõi prompt video, voice và subtitle `.srt` đã sẵn sàng cho project.

#### Scenario: Hoàn tất nguyên liệu lõi
- **WHEN** mọi shot cần prompt đã có prompt video completed, mọi shot có narration đã có voice completed, và project có subtitle `.srt` completed
- **THEN** auto-run chuyển `completed` và trả summary gồm số shot, số prompt, số voice, trạng thái subtitle và link hoặc action tải các artifact liên quan

#### Scenario: Không tự tạo ZIP trong auto-run
- **WHEN** auto-run hoàn tất prompt, voice và subtitle, kể cả khi client cũ gửi flag tạo package
- **THEN** hệ thống chuyển auto-run sang `completed` mà không gọi luồng tạo ZIP package; người dùng vẫn có thể tạo ZIP thủ công bằng workflow package riêng

### Requirement: Quản lý cancel, continue và retry
Hệ thống SHALL cung cấp API để người dùng tiếp tục sau duyệt, hủy run đang chạy và retry run lỗi mà không tạo trạng thái mâu thuẫn.

#### Scenario: Cancel auto-run đang chờ duyệt
- **WHEN** người dùng cancel auto-run ở trạng thái `needs_review`
- **THEN** auto-run chuyển `cancelled` và các artifact đã tạo trước đó vẫn được giữ trong project

#### Scenario: Cancel auto-run đang chờ voice
- **WHEN** người dùng cancel auto-run ở bước tạo hoặc chờ voice
- **THEN** hệ thống ngừng điều phối các bước tiếp theo, đánh dấu run `cancelled`, và không tự tạo subtitle/package sau đó

#### Scenario: Continue sai trạng thái
- **WHEN** client gọi continue cho auto-run không ở trạng thái `needs_review` hoặc `needs_input`
- **THEN** hệ thống từ chối bằng lỗi tiếng Việt và MUST NOT thay đổi current step

#### Scenario: Retry sai trạng thái
- **WHEN** client gọi retry cho auto-run chưa ở trạng thái `failed` hoặc `needs_input`
- **THEN** hệ thống từ chối bằng lỗi tiếng Việt và MUST NOT tạo run trùng

### Requirement: UI hiển thị hai chế độ duyệt và tiến độ auto-run
Hệ thống SHALL hiển thị điều khiển auto-run trong AI Video Assistant bằng tiếng Việt, rõ hai chế độ duyệt và tiến độ từng bước.

#### Scenario: Chọn chế độ trước khi chạy
- **WHEN** người dùng mở khu Auto tạo nguyên liệu
- **THEN** UI hiển thị lựa chọn `Duyệt từng chặng` và `Tự chạy hết`, mô tả ngắn tác động của mỗi chế độ, và không hiển thị tùy chọn tạo ZIP trong luồng auto

#### Scenario: Hiển thị progress khi run đang chạy
- **WHEN** auto-run ở trạng thái `queued`, `running` hoặc `waiting_voice`
- **THEN** UI hiển thị bước hiện tại, checklist các bước đã xong/chưa xong, progress nếu có và nút cancel phù hợp

#### Scenario: Diễn giải tiến trình cho người không code
- **WHEN** frontend có auto-run status, current step, summary counts hoặc completed/pending steps
- **THEN** UI SHALL hiển thị mô tả tiếng Việt dễ hiểu về việc hệ thống đang làm, đã xong gì, còn gì tiếp theo và người dùng có cần hành động hay không
- **AND** UI SHALL NOT yêu cầu người dùng hiểu tên kỹ thuật như `generate_prompts`, `waiting_voice` hoặc raw status code để biết chuyện gì đang xảy ra

#### Scenario: Hiển thị trạng thái cần duyệt
- **WHEN** auto-run trả `status = "needs_review"`
- **THEN** UI hiển thị review stage bằng tiếng Việt, giữ người dùng ở phần nội dung cần duyệt và hiển thị action tiếp tục sau khi duyệt

#### Scenario: Restore run sau khi refresh app
- **WHEN** người dùng refresh hoặc rời màn AI Video rồi quay lại project có auto-run active hoặc latest run chưa terminal
- **THEN** UI fetch latest run từ backend và khôi phục progress panel thay vì mất trạng thái đang chạy

#### Scenario: Không lưu diễn giải chi tiết vào database
- **WHEN** UI tạo câu diễn giải chi tiết trong phiên hiện tại, ví dụ "đã có 4/8 prompt" hoặc "đang chờ voice cho các segment còn lại"
- **THEN** hệ thống SHALL giữ phần diễn giải tức thời đó trong session frontend hoặc suy ra trực tiếp từ status response
- **AND** backend SHALL NOT persist event log UI chi tiết mới vào database chỉ để khôi phục các câu diễn giải này sau reload

#### Scenario: Hiển thị lỗi inline
- **WHEN** auto-run failed hoặc needs input
- **THEN** UI hiển thị failure reason bằng tiếng Việt, action retry hoặc hướng dẫn bổ sung input, và không che mất các nút thủ công để người dùng sửa project

### Requirement: Observability và debug cho auto-run
Hệ thống SHALL ghi log và summary đủ để người dùng hoặc developer truy vết auto-run local mà không lộ nội dung nhạy cảm quá mức.

#### Scenario: Log từng bước auto-run
- **WHEN** auto-run chuyển bước hoặc gặp lỗi
- **THEN** hệ thống ghi debug event có run id, project id, step name, status, duration hoặc error code và technical details đã redaction

#### Scenario: Status response có summary dễ hiểu
- **WHEN** frontend poll auto-run status
- **THEN** API trả current step, review stage, progress, completed steps, pending steps, failure reason, counts theo shot/prompt/voice/subtitle và timestamps cần thiết

#### Scenario: Không làm phình database bằng UI progress detail
- **WHEN** auto-run đang chạy và frontend poll trạng thái thường xuyên
- **THEN** backend SHALL keep persisted auto-run data bounded to core state, summary counts, redacted debug details and failure/debug metadata
- **AND** backend SHALL NOT append unbounded per-poll or per-render UI narration entries to `step_results_json` or another database table

#### Scenario: Không trả prompt hoặc narration đầy đủ trong technical details
- **WHEN** hệ thống lưu technical details cho auto-run failure hoặc debug event
- **THEN** technical details MUST không chứa toàn bộ source text, narration dài hoặc prompt đầy đủ; nếu cần thì chỉ lưu id/count/status hoặc preview đã rút gọn
