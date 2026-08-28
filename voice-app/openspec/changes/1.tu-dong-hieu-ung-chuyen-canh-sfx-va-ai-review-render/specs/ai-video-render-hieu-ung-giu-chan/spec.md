## ADDED Requirements

### Requirement: Tạo enhanced render plan từ creative direction
Hệ thống SHALL tạo enhanced render plan có cấu trúc từ timeline manifest, retention metadata, transition pack và sound design metadata để render hiệu ứng thật khi người dùng bật chế độ dựng nâng cao.

#### Scenario: Tạo plan từ project có creative direction
- **WHEN** project phase 2 có timeline render hợp lệ và các shot có `retention_json`, `transition_json` hoặc `sound_design_json`
- **THEN** hệ thống tạo enhanced render plan gồm transition actions, SFX actions, BGM action nếu có, retention actions và fallback notes

#### Scenario: Project thiếu creative direction
- **WHEN** project có timeline render hợp lệ nhưng thiếu retention/transition/sound metadata
- **THEN** hệ thống vẫn cho render cơ bản và enhanced render plan SHALL ghi rõ không đủ dữ liệu để tự thêm hiệu ứng giữ chân nâng cao

#### Scenario: Plan timing hợp lệ
- **WHEN** hệ thống validate enhanced render plan
- **THEN** mọi transition, SFX và BGM timing MUST nằm trong tổng duration timeline hoặc được clamp/fail rõ bằng lỗi tiếng Việt

#### Scenario: Không lưu plan bán hỏng
- **WHEN** AI hoặc normalizer trả plan thiếu field bắt buộc, timing sai hoặc asset bắt buộc không tồn tại
- **THEN** hệ thống MUST không commit enhanced plan mới và MUST giữ render cơ bản/render output cũ không bị xóa

### Requirement: Render hiệu ứng chuyển cảnh thật
Hệ thống SHALL biến transition action hợp lệ thành hiệu ứng video thật trong MP4 cuối khi FFmpeg/runtime hỗ trợ.

#### Scenario: Render crossfade hoặc dip transition
- **WHEN** transition action yêu cầu crossfade, dip to black hoặc dip to white với duration hợp lệ
- **THEN** hệ thống render hiệu ứng đó giữa hai clip bằng FFmpeg và giữ tổng timeline khớp voice/subtitle

#### Scenario: Render punch zoom hoặc flash nhẹ
- **WHEN** transition action yêu cầu punch zoom, flash hoặc glitch nhẹ để tạo pattern interrupt
- **THEN** hệ thống áp dụng effect trong ngưỡng an toàn, không làm mất nội dung chính của shot và ghi effect vào manifest/report

#### Scenario: Transition continuity risk cao
- **WHEN** `transition_json.continuity_risk` cho thấy rủi ro phá continuity cao
- **THEN** hệ thống SHALL ưu tiên hard cut, match cut nhẹ hoặc fallback an toàn thay vì effect mạnh như glitch/flash dài

#### Scenario: FFmpeg thiếu filter cần thiết
- **WHEN** runtime FFmpeg không hỗ trợ filter cần dùng cho transition action
- **THEN** hệ thống fallback về transition an toàn, ghi warning tiếng Việt và không làm render job crash nếu render cơ bản vẫn khả thi

### Requirement: Mix SFX và BGM thật vào MP4
Hệ thống SHALL mix SFX/BGM asset thật vào audio track cuối khi cue có asset hợp lệ và người dùng bật enhanced audio.

#### Scenario: Cue tiếng kính vỡ có asset hợp lệ
- **WHEN** sound cue được map thành `glass_break` và project có asset âm thanh kính vỡ hợp lệ
- **THEN** hệ thống mix asset đó vào đúng thời điểm cue với volume/fade an toàn và ghi rõ trong enhanced render report

#### Scenario: Cue thiếu asset thật
- **WHEN** sound cue yêu cầu SFX như tiếng kính vỡ nhưng không có asset hợp lệ
- **THEN** hệ thống MUST không báo sai rằng MP4 đã có SFX đó; report SHALL ghi fallback hoặc yêu cầu người dùng upload/chọn asset

#### Scenario: Shot có narration
- **WHEN** shot có voice narration và SFX/BGM chồng lên đoạn đó
- **THEN** hệ thống MUST áp dụng volume policy hoặc ducking để voice rõ hơn SFX/BGM

#### Scenario: Silence drop
- **WHEN** plan yêu cầu silence drop
- **THEN** hệ thống chỉ áp dụng silence drop ở khoảng không lời hoặc vùng transition hợp lệ, không cắt mất lời thoại/narration quan trọng

#### Scenario: Mix nhiều cue cùng lúc
- **WHEN** nhiều SFX/BGM cue trùng thời gian
- **THEN** hệ thống SHALL giới hạn volume tổng hoặc cảnh báo audio clutter risk để tránh âm thanh quá dày

### Requirement: AI review sau render và auto-fix giới hạn
Hệ thống SHALL có thể phân tích output render nâng cao và tự sửa các lỗi render-plan trong giới hạn an toàn trước khi trả kết quả cuối.

#### Scenario: Review render pass
- **WHEN** AI review nhận thấy output đủ tốt theo manifest, plan, metadata và frame/audio summary hiện có
- **THEN** render job đánh dấu review passed và cho phép người dùng tải MP4 kèm báo cáo tiếng Việt

#### Scenario: Review phát hiện lỗi có thể sửa
- **WHEN** AI review phát hiện SFX lệch timing, volume quá lớn, transition quá dài hoặc effect nên fallback nhưng không cần tạo lại clip/voice/subtitle
- **THEN** hệ thống có thể cập nhật enhanced render plan và re-render trong giới hạn attempt đã cấu hình

#### Scenario: Review yêu cầu user action
- **WHEN** AI review phát hiện lỗi cần tạo lại clip, tạo lại voice, upload asset hoặc sửa nội dung shot
- **THEN** hệ thống dừng auto-fix, giữ output hiện có nếu có và hiển thị báo cáo tiếng Việt với action người dùng cần làm

#### Scenario: Hết số lần auto-fix
- **WHEN** số lần fix/re-render đạt giới hạn
- **THEN** hệ thống MUST dừng lặp, lưu báo cáo attempt cuối và không tiếp tục render vô hạn

#### Scenario: Review không được nói quá nguồn dữ liệu
- **WHEN** AI review chỉ có manifest/metadata mà không có frame hoặc audio summary đầy đủ
- **THEN** báo cáo review MUST nói rõ phạm vi phân tích và không khẳng định đã nghe/xem chi tiết mà hệ thống chưa cung cấp

### Requirement: Export artifact tiếng Việt có số thứ tự
Hệ thống SHALL xuất các file đọc được bởi người dùng bằng tiếng Việt và bắt đầu bằng số thứ tự để sắp xếp ổn định trong thư mục/package.

#### Scenario: Export đủ file tiếng Việt
- **WHEN** enhanced render hoàn tất hoặc package enhanced render được tạo
- **THEN** hệ thống SHALL tạo các artifact có tên `1. Kịch bản và nhịp giữ chân.md`, `2. Shot list và chuyển cảnh.csv`, `3. Prompt video và chỉ dẫn hiệu ứng.md`, `4. Âm thanh SFX và mixing notes.md`, `5. Báo cáo AI review sau render.md` và `6. Timeline manifest dựng MP4.json`

#### Scenario: Filename an toàn trên hệ điều hành
- **WHEN** hệ thống ghi hoặc zip các artifact tiếng Việt
- **THEN** filename SHALL được sanitize để hợp lệ trên Windows/macOS nhưng vẫn giữ tiếng Việt khi có thể

#### Scenario: File review chưa có vì chưa chạy AI review
- **WHEN** người dùng tắt AI review hoặc review chưa chạy
- **THEN** file `5. Báo cáo AI review sau render.md` SHALL ghi rõ trạng thái chưa review thay vì giả lập kết quả đánh giá

#### Scenario: Thứ tự file không phụ thuộc locale
- **WHEN** người dùng mở thư mục/package trên hệ điều hành khác nhau
- **THEN** số thứ tự ở đầu filename SHALL giúp file sắp xếp theo đúng thứ tự đọc mong muốn

### Requirement: Enhanced render không phá render cơ bản
Hệ thống SHALL giữ workflow render MP4 cơ bản hoạt động khi enhanced render bị tắt, thiếu asset hoặc gặp lỗi có thể fallback.

#### Scenario: Người dùng tắt enhanced render
- **WHEN** enhanced render setting bị tắt
- **THEN** hệ thống dùng render pipeline cơ bản hiện có và không yêu cầu SFX/BGM asset hoặc AI review

#### Scenario: Enhanced render lỗi nhưng render cơ bản khả thi
- **WHEN** enhanced render plan hoặc FFmpeg enhanced graph fail trước khi ghi output cuối
- **THEN** hệ thống SHALL trả lỗi tiếng Việt có fallback rõ hoặc cho phép render cơ bản, không làm mất clip/voice/subtitle/package hiện có

#### Scenario: Output cũ trở thành stale
- **WHEN** transition action, SFX asset, BGM asset, review fix action, clip, voice hoặc subtitle thay đổi sau render completed
- **THEN** hệ thống SHALL đánh dấu output enhanced cũ là stale để người dùng biết cần render lại

### Requirement: UI tiếng Việt cho enhanced render
Hệ thống SHALL hiển thị enhanced render bằng tiếng Việt trong AI Video Assistant mà không biến màn hình thành timeline editor phức tạp.

#### Scenario: Bật/tắt enhanced render
- **WHEN** người dùng mở panel dựng MP4 cho project phase 2
- **THEN** UI cung cấp setting rõ ràng để bật/tắt hiệu ứng chuyển cảnh, SFX/BGM và AI review trước khi render

#### Scenario: Hiển thị mapping SFX/transition
- **WHEN** project có enhanced render plan
- **THEN** UI hiển thị tóm tắt tiếng Việt về transition, SFX, BGM, fallback và warning theo shot hoặc theo nhóm cue

#### Scenario: Hiển thị báo cáo sau render
- **WHEN** render job có AI review report
- **THEN** UI hiển thị trạng thái pass/fail, các lỗi đã sửa, lỗi cần người dùng xử lý và link tải báo cáo tiếng Việt

#### Scenario: Không làm timeline editor kéo-thả
- **WHEN** enhanced render UI được implement
- **THEN** UI SHALL giữ dạng panel vận hành/checklist/report, không yêu cầu timeline kéo-thả nhiều track trong change này
