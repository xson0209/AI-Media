## ADDED Requirements

### Requirement: Chỉ revision phân tích đã duyệt mới được handoff sang Series
Hệ thống PHẢI (MUST) yêu cầu một `ComicAnalysisPackage` đã được người dùng duyệt và target hợp lệ trước khi tạo preview hoặc commit handoff.

#### Scenario: Tạo Series mới
- **WHEN** người dùng chọn tạo Series mới từ revision đã duyệt
- **THEN** preview PHẢI cho phép chọn `image_story_only` hoặc `hybrid` và nhập các metadata còn thiếu
- **AND** target PHẢI mặc định `image_story_only` và KHÔNG ĐƯỢC mặc định thành `video_story_only`

#### Scenario: Chọn output intent của Episode mới
- **WHEN** handoff tạo Story Episode trong Series mới hoặc hiện có
- **THEN** output intent PHẢI mặc định `truyen_anh`
- **AND** chỉ Series `hybrid` mới CÓ THỂ cho người dùng chọn `ca_hai`; handoff này KHÔNG ĐƯỢC tự chọn `video_truyen`

#### Scenario: Thêm vào Series hiện có
- **WHEN** người dùng chọn Series hiện có
- **THEN** hệ thống chỉ PHẢI cho chọn series `image_story_only` hoặc `hybrid`
- **AND** PHẢI từ chối series `video_story_only` bằng thông báo tiếng Việt

#### Scenario: Revision chưa duyệt hoặc approval đã cũ
- **WHEN** analysis revision chưa approved hoặc nội dung đã thay đổi sau approval
- **THEN** hệ thống PHẢI chặn preview/commit
- **AND** yêu cầu người dùng review và duyệt revision hiện tại

### Requirement: Handoff preview phải đầy đủ và không gây side effect
Hệ thống PHẢI (MUST) tạo preview deterministic cho target Series mà không ghi hoặc sửa Series, Story Episode, Memory, Canon, Character Profile hay Reference Asset.

#### Scenario: Tính deterministic của preview
- **WHEN** analysis revision, approval manifest hash, target dependency fingerprint, selected items, development mode, rights attestation revision và mapping/schema version không đổi
- **THEN** hệ thống PHẢI tạo cùng preview fingerprint và cùng item classification
- **AND** preview KHÔNG ĐƯỢC gọi một AI matching mới chưa được persist/version hóa làm thay đổi kết quả ngầm

#### Scenario: Xem preview tạo Series mới
- **WHEN** người dùng yêu cầu preview cho Series mới
- **THEN** preview PHẢI liệt kê dữ liệu Series, Story Episode, Source Document, Character Profile, location, canon, memory draft và reference asset sẽ được tạo
- **AND** PHẢI hiển thị số lượng text chunk, trang, panel, OCR, lời thoại, narration và ảnh nguồn

#### Scenario: Xem preview cập nhật Series hiện có
- **WHEN** target là Series hiện có
- **THEN** preview PHẢI phân loại từng item thành `create`, `update`, `merge`, `skip`, `duplicate` hoặc `conflict`
- **AND** PHẢI lưu target dependency fingerprint gồm revision của Series, Episode, Profile, Memory/Current State, Reference và entity đích liên quan đã đọc

#### Scenario: Rời preview không xác nhận
- **WHEN** người dùng đóng hoặc hủy preview
- **THEN** hệ thống KHÔNG ĐƯỢC tạo hoặc sửa bất kỳ artifact đích nào

### Requirement: Handoff ánh xạ đầy đủ dữ liệu cấp Series
Hệ thống PHẢI (MUST) ánh xạ kiến thức dài hạn đã được chọn từ phân tích sang cấu trúc Series thay vì chỉ tạo tên Series và tóm tắt chương.

#### Scenario: Ánh xạ metadata và Bible
- **WHEN** commit tạo Series mới
- **THEN** tên truyện PHẢI ánh xạ thành tên Series, mô tả tổng quan và thể loại thành Series Memory Card loại `series_summary`, phong cách hình ảnh/kể chuyện thành Style Bible, bối cảnh và quy tắc thế giới thành World Bible
- **AND** market/language của chương PHẢI ánh xạ vào Story Episode thay vì giả định VideoSeries hiện có trường tương ứng

#### Scenario: Tóm tắt chương không ghi đè previous episode
- **WHEN** handoff mang synopsis của chương đang phân tích
- **THEN** synopsis PHẢI được lưu trong Episode Source và có thể tạo episode memory proposal
- **AND** KHÔNG ĐƯỢC tự ghi synopsis đó thành `previous_episode_summary` của chính tập nếu workflow Series chưa xác nhận đây là diễn biến trước tập

#### Scenario: Ánh xạ nhân vật, địa điểm và quan hệ
- **WHEN** package có character/location candidates được chọn để handoff
- **THEN** hệ thống PHẢI tạo hoặc ánh xạ Character Profiles, địa điểm và quan hệ có liên kết evidence
- **AND** trạng thái cuối chương, sự kiện quan trọng và quan hệ PHẢI được chuẩn bị dưới dạng current-state hoặc memory draft phù hợp

#### Scenario: Ánh xạ canon và continuity
- **WHEN** người dùng chọn canon candidates trong preview
- **THEN** hệ thống PHẢI tạo continuity-rule proposals hoặc cập nhật được người dùng xác nhận
- **AND** KHÔNG ĐƯỢC âm thầm ghi đè canon đã approved của Series hiện có

#### Scenario: Ánh xạ ảnh tham chiếu
- **WHEN** người dùng chọn ảnh nhân vật hoặc địa điểm để chuyển sang Series
- **THEN** hệ thống PHẢI tạo Reference Assets liên kết đúng entity, role, source asset và checksum
- **AND** các asset đó PHẢI tuân theo gate duyệt reference của Series

### Requirement: Handoff phải mang toàn bộ nội dung chương vào Story Episode
Hệ thống PHẢI (MUST) tạo một Story Episode và `StoryEpisodeSourceDocument` chứa toàn bộ nội dung nguồn đã duyệt; chỉ handoff synopsis hoặc một chuỗi `source_input` rút gọn là không đủ.

#### Scenario: Tạo Source Document đầy đủ
- **WHEN** handoff commit thành công
- **THEN** Source Document PHẢI chứa full text đã duyệt, văn bản đã trích và làm sạch từ HTML, OCR, lời thoại, narration, thứ tự trang, thứ tự panel, bong bóng thoại, mô tả hình ảnh, nhân vật/hành động/biểu cảm theo panel, địa điểm, plot beats, cấu trúc mở đầu-xung đột-cao trào-kết thúc, synopsis, metadata chương, limitation và provenance

#### Scenario: Raw HTML không thuộc creative source
- **WHEN** raw HTML/response được giữ để chẩn đoán hoặc provenance
- **THEN** dữ liệu đó PHẢI nằm trong vùng quarantine của Comic Source theo retention policy
- **AND** KHÔNG ĐƯỢC trở thành source chunk, render trực tiếp trong UI hoặc gửi tới AI

#### Scenario: Giữ nội dung raw và nội dung đã duyệt
- **WHEN** OCR hoặc text nguồn đã được người dùng sửa
- **THEN** hệ thống PHẢI giữ bản raw, bản AI và bản approved
- **AND** Story Episode PHẢI dùng bản approved làm nguồn sáng tạo mặc định

#### Scenario: Chương không có HTML text
- **WHEN** nguồn chỉ có ảnh và OCR/vision
- **THEN** Source Document vẫn PHẢI được tạo từ page/panel sequence, OCR, narration, dialogue và visual descriptions
- **AND** limitation PHẢI nêu rõ không có văn bản được trích từ HTML

#### Scenario: Ảnh và derivative của Episode
- **WHEN** Source Document tham chiếu ảnh nguồn, tile hoặc derivative
- **THEN** Story Episode Source PHẢI giữ source asset ID, revision, checksum, page/panel occurrence và evidence mapping
- **AND** KHÔNG ĐƯỢC sao chép mất provenance hoặc chỉ giữ thumbnail

### Requirement: Nội dung Episode được chia chunk có evidence và không bị giới hạn bởi source_input cũ
Hệ thống PHẢI (MUST) lưu nội dung chương dài thành source document và source chunks có thứ tự, thay vì cắt bỏ dữ liệu để vừa trường text cũ hoặc một prompt duy nhất.

#### Scenario: Chuyển current Source Document
- **WHEN** handoff tạo hoặc áp dụng một source revision mới cho Story Episode
- **THEN** hệ thống PHẢI tạo document revision mới và atomically cập nhật `current_source_document_id` của Episode
- **AND** mỗi Episode PHẢI có nhiều nhất một current approved Source Document, trong khi revision cũ vẫn truy xuất được

#### Scenario: Tạo source chunks
- **WHEN** Source Document được commit
- **THEN** hệ thống PHẢI tạo chunk có `chunk_order`, `chunk_type`, text, page/panel/bubble liên quan, speaker khi có, evidence IDs, confidence và source revision

#### Scenario: Nội dung vượt 50.000 ký tự
- **WHEN** tổng văn bản đã trích/làm sạch từ HTML, OCR và mô tả vượt giới hạn `source_input` hiện tại
- **THEN** hệ thống PHẢI lưu đầy đủ trong Source Document/chunks
- **AND** KHÔNG ĐƯỢC truncate im lặng hoặc chỉ lưu synopsis

#### Scenario: Chỉ item trong approval manifest được handoff
- **WHEN** handoff tạo Source Document và target items
- **THEN** hệ thống PHẢI chỉ dùng item `accepted` trong approval manifest đã khóa
- **AND** item `excluded` hoặc `unreviewed` KHÔNG ĐƯỢC xuất hiện trong nguồn approved hay dữ liệu Series đích

#### Scenario: Tương thích client cũ
- **WHEN** Story Episode vẫn cần `source_input` hoặc `source_digest` cho client cũ
- **THEN** hệ thống CÓ THỂ tạo một projection/tóm tắt có đánh dấu từ Source Document
- **AND** projection KHÔNG ĐƯỢC trở thành nguồn chuẩn thay thế document có cấu trúc

### Requirement: Handoff phát hiện trùng lặp và xung đột trước khi ghi
Hệ thống PHẢI (MUST) so sánh revision nguồn với target Series và yêu cầu quyết định rõ ràng cho mọi conflict ảnh hưởng dữ liệu đã có.

#### Scenario: Chương hoặc nguồn đã được nhập
- **WHEN** URL chuẩn hóa, source content hash, source revision, chapter identity hoặc episode number trùng dữ liệu đích
- **THEN** preview PHẢI đánh dấu `duplicate` hoặc `conflict`
- **AND** KHÔNG ĐƯỢC tự tạo thêm Story Episode trùng

#### Scenario: Nhân vật hoặc ảnh có thể trùng
- **WHEN** tên/alias trùng nhưng visual identity khác, tên khác nhưng evidence cho thấy có thể cùng người hoặc checksum ảnh trùng
- **THEN** preview PHẢI đề xuất merge/keep-separate/skip với confidence và evidence
- **AND** quyết định cuối PHẢI thuộc người dùng

#### Scenario: Canon hoặc trạng thái xung đột
- **WHEN** canon, quan hệ, địa điểm, episode number hoặc current state nguồn mâu thuẫn dữ liệu Series đã approved
- **THEN** preview PHẢI hiển thị giá trị nguồn, giá trị đích, evidence và tác động
- **AND** commit PHẢI bị chặn đến khi người dùng chọn giữ đích, dùng nguồn, merge hoặc bỏ item

### Requirement: Commit handoff phải atomic đối với dữ liệu quan sát được
Hệ thống PHẢI (MUST) dùng staging và transaction để hoặc ghi toàn bộ mapping đã xác nhận, hoặc không để lại Series, Story Episode hay artifact đích ở trạng thái tạo dở.

#### Scenario: Thứ tự commit file và database
- **WHEN** handoff bắt đầu commit
- **THEN** hệ thống PHẢI validate/stage file, ghi operation `committing`, promote file bằng atomic rename tới content-addressed final path rồi mới commit transaction target
- **AND** target Series/Episode chỉ được hiển thị sau khi mọi file bắt buộc đã tồn tại và DB commit thành công

#### Scenario: Commit thành công
- **WHEN** preview còn hiệu lực, conflict đã được giải quyết và mọi validation đạt
- **THEN** hệ thống PHẢI ghi Series, Story Episode, Source Document, chunks, mappings, proposals, assets và handoff record như một commit logic duy nhất
- **AND** response PHẢI trả `series_id`, `story_episode_id`, `source_document_id`, `handoff_id` và revision đã dùng

#### Scenario: Lỗi database trong commit
- **WHEN** bất kỳ thao tác database bắt buộc nào thất bại
- **THEN** transaction PHẢI rollback
- **AND** KHÔNG ĐƯỢC để Series hoặc Story Episode mới hiển thị một phần

#### Scenario: Lỗi khi chuyển asset từ staging
- **WHEN** một asset bắt buộc không thể finalize
- **THEN** commit PHẢI thất bại hoặc rollback trạng thái hiển thị
- **AND** file staging thừa PHẢI được cleanup an toàn hoặc đánh dấu để garbage collection

#### Scenario: Target thay đổi sau preview
- **WHEN** analysis revision, target dependency fingerprint hoặc expected revision của bất kỳ item đích khác với lúc tạo preview
- **THEN** commit PHẢI từ chối bằng lỗi stale preview
- **AND** yêu cầu tạo preview mới

#### Scenario: Operation bị gián đoạn khi đang committing
- **WHEN** ứng dụng khởi động lại và còn handoff operation ở trạng thái `committing`
- **THEN** recovery PHẢI kiểm tra idempotency result, DB target và staging/final manifest
- **AND** PHẢI hoàn tất cùng operation hoặc chuyển `failed/rolled_back` và cleanup an toàn, không tạo target trùng

### Requirement: Commit handoff phải idempotent
Hệ thống PHẢI (MUST) hỗ trợ `idempotency_key` gắn với analysis revision, target và fingerprint preview để retry không tạo dữ liệu trùng.

#### Scenario: Retry cùng request sau timeout
- **WHEN** client gửi lại cùng idempotency key và cùng payload
- **THEN** hệ thống PHẢI trả lại kết quả handoff đã commit hoặc tiếp tục cùng operation
- **AND** KHÔNG ĐƯỢC tạo thêm Series, Episode, Profile, Memory hoặc Asset

#### Scenario: Dùng lại key với payload khác
- **WHEN** cùng idempotency key được gửi với target, revision hoặc conflict resolution khác
- **THEN** hệ thống PHẢI từ chối bằng lỗi conflict

#### Scenario: Retry sau commit thất bại hoàn toàn
- **WHEN** operation trước đã rollback và không có commit thành công
- **THEN** cùng idempotency key và cùng payload PHẢI ánh xạ tới cùng operation ID và trả terminal failure đã lưu
- **AND** muốn bắt đầu attempt logic mới sau terminal failure PHẢI dùng idempotency key mới

#### Scenario: Retry operation còn retryable
- **WHEN** operation cùng key đang interrupted hoặc retryable nhưng chưa terminal
- **THEN** hệ thống PHẢI resume cùng operation từ checkpoint an toàn
- **AND** kết quả cuối vẫn PHẢI có nhiều nhất một handoff thành công

### Requirement: Handoff phải chốt development mode và quyền sử dụng vào Story Episode
Hệ thống PHẢI (MUST) hiển thị development mode trong preview và lưu mode đã xác nhận cùng rights attestation revision vào Story Episode khi commit.

#### Scenario: Commit mode viết mới
- **WHEN** preview dùng `lay_cam_hung_va_viet_moi`
- **THEN** Story Episode PHẢI lưu mode đó làm nguồn chuẩn cho candidate generation
- **AND** preview fingerprint/idempotency payload PHẢI chứa mode và rights attestation revision

#### Scenario: Commit mode bám canon
- **WHEN** người dùng chọn `bam_canon_va_phat_trien_tiep`
- **THEN** preview PHẢI yêu cầu rights attestation phù hợp còn hiệu lực
- **AND** commit PHẢI lưu attestation revision cùng provenance

### Requirement: Approval phân tích không tự động kích hoạt mọi dữ liệu Series
Hệ thống PHẢI (MUST) phân biệt `được duyệt để handoff` với `được kích hoạt làm canon hoặc reference dùng trong prompt`.

#### Scenario: Đề xuất AI chưa được chọn
- **WHEN** một character, canon, location hoặc memory candidate không được người dùng chọn trong preview
- **THEN** hệ thống KHÔNG ĐƯỢC tạo item đích từ candidate đó

#### Scenario: Tạo dữ liệu nháp trong Series
- **WHEN** item được chọn để chuyển nhưng chưa có approval đích theo policy Series
- **THEN** item PHẢI được tạo ở trạng thái `draft`, `pending_approval` hoặc `inactive` phù hợp
- **AND** KHÔNG ĐƯỢC tham gia prompt canon trước khi qua gate hiện có

#### Scenario: Ghi field canonical ở cổng handoff
- **WHEN** preview đề xuất ghi Series Bible, Continuity Rules hoặc field Character Profile canonical
- **THEN** người dùng PHẢI có quyết định field-level rõ ràng tại cổng handoff thứ hai
- **AND** item không được chọn KHÔNG ĐƯỢC ghi trực tiếp vào field canonical

#### Scenario: Dữ liệu đã approved của Series hiện có
- **WHEN** handoff thêm dữ liệu vào Series đã có
- **THEN** commit KHÔNG ĐƯỢC hạ approval, xóa hoặc ghi đè artifact approved nếu preview không có quyết định rõ ràng của người dùng

### Requirement: Handoff chỉ kết thúc ở Series và Story Studio
Hệ thống PHẢI (MUST) kết thúc flow bằng Series/Story Episode và không tạo hoặc handoff trực tiếp sang AI Video.

#### Scenario: Commit handoff thành công
- **WHEN** operation hoàn tất
- **THEN** UI PHẢI cung cấp hành động mở Story Studio tại đúng `series_id` và `story_episode_id`
- **AND** PHẢI cho phép chỉ lưu kết quả mà chưa chạy AI sáng tạo

#### Scenario: Người dùng tiếp tục phát triển kịch bản
- **WHEN** người dùng chủ động bắt đầu trong Story Studio
- **THEN** Story Studio PHẢI dùng Source Document đã approved để tạo đúng ba candidate và Master Story theo workflow hiện có

#### Scenario: Không tạo AI Video project
- **WHEN** preview hoặc commit Comic Series handoff chạy
- **THEN** hệ thống KHÔNG ĐƯỢC tạo Video Inspiration handoff, AI Video project, scene, shot, prompt video, voice, subtitle hoặc render job

### Requirement: Phân tích lại nguồn không tự động sửa Series đã handoff
Hệ thống PHẢI (MUST) giữ quan hệ phiên bản giữa source revision, analysis revision, handoff và target artifacts; revision mới chỉ được áp dụng sau review, preview và commit mới.

#### Scenario: Nguồn web có revision mới
- **WHEN** cùng nguồn được nhập lại và tạo analysis revision mới
- **THEN** UI PHẢI hiển thị có phiên bản mới và diff text, ảnh, nhân vật, canon, plot và limitation
- **AND** Series/Story Episode hiện tại KHÔNG ĐƯỢC tự thay đổi

#### Scenario: Áp dụng revision mới vào cùng Series
- **WHEN** người dùng duyệt revision mới và yêu cầu handoff
- **THEN** hệ thống PHẢI tạo preview update mới với conflict detection
- **AND** commit PHẢI lưu handoff revision mới thay vì sửa lịch sử handoff cũ

#### Scenario: Truy xuất nguồn của dữ liệu đích
- **WHEN** người dùng xem Story Episode, Character Profile, Canon, Memory hoặc Reference Asset được nhập
- **THEN** hệ thống PHẢI cho biết analysis ID, source revision, handoff ID và evidence liên quan
