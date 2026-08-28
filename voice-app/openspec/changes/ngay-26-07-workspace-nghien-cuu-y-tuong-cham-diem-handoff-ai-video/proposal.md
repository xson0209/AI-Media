## Why

Voicebox hiện có các luồng phân tích video, phân tích truyện tranh, Story Studio và AI Video nhưng chưa có một workspace bền vững để gom nhiều nguồn nghiên cứu, lưu phần đã duyệt, phát triển tiếp nội dung qua hội thoại và so sánh nhiều phương án trước khi sản xuất. Người dùng cần một nơi có thể mở lại memory của nhiều dự án nghiên cứu, nhận đề xuất có chấm điểm và phương án khuyên chọn, sau đó handoff thẳng sang AI Video để tiếp tục viết kịch bản bằng luồng hiện có.

## What Changes

- Thêm route mới `/research` với tab "Nghiên cứu ý tưởng" độc lập, không thay đổi route hoặc hành vi mặc định của các workspace hiện có.
- Thêm Research Project có trạng thái, revision, danh sách nguồn, các lần chạy, ý tưởng, kịch bản nháp, kịch bản đã duyệt và file memory dễ đọc/export.
- Cho phép thêm nguồn bằng link video, upload video, link truyện, upload ảnh, dán text hoặc docs; chuẩn hóa kết quả về một gói nguồn nghiên cứu chung và tái sử dụng adapter của các luồng hiện có.
- Cho phép liên kết trực tiếp một Series hiện có làm nguồn `series_memory`; Research đọc memory/canon đã duyệt qua Series Brain, không yêu cầu người dùng dán tóm tắt, không sao chép nội dung thủ công và không sửa ngược Series nguồn.
- Cho phép chạy nghiên cứu theo ba chế độ: AI nghiên cứu tài liệu, AI phát triển nội dung, hoặc cả hai; lưu riêng từng kết quả trước khi hợp nhất.
- Thêm chat phát triển nội dung theo memory đã chọn, có draft, nhánh phát triển, duyệt ý tưởng/kịch bản và không tự ghi nội dung chưa duyệt vào memory chuẩn.
- Thêm chấm điểm kịch bản/ý tưởng theo các tiêu chí có giải thích, hiển thị điểm tổng hợp, điểm mạnh, rủi ro và phương án khuyên chọn; người dùng vẫn là người quyết định cuối cùng.
- Cho phép chọn nhiều Research Project làm ngữ cảnh, compile phần đã duyệt theo ngân sách, và hiển thị rõ project nào đang ảnh hưởng đến phương án.
- Thêm Research Handoff có revision, provenance, accepted items, score/recommendation, must-have/avoid và giới hạn phân tích; chỉ handoff nội dung đã duyệt.
- Khi người dùng xác nhận handoff, tạo AI Video project mới và source blocks qua hợp đồng hiện có, mở thẳng `/ai-video` với project vừa tạo để AI Video tiếp tục viết story, continuity, script, scene, shot và prompt.
- Mặc định handoff chỉ tạo project, không tự chạy hàng loạt generation; nếu nội dung research đổi sau handoff, chỉ đánh dấu đúng các artifact AI Video phụ thuộc là stale.
- Bổ sung kiểm thử route mới, isolated backend/API, memory revision, scoring/recommendation, handoff idempotency, stale propagation và regression để các luồng video inspiration, comic analysis, Story Studio và AI Video hiện tại vẫn hoạt động bình thường.

## Capabilities

### New Capabilities

- `research-workspace`: Research Project CRUD, route `/research`, multi-project selection, trạng thái, revision, memory file và UI workspace.
- `research-source-ingestion`: Nguồn video/truyện/ảnh/text/docs/Series Memory, trạng thái xử lý, provenance, giới hạn và gói nguồn nghiên cứu chuẩn hóa.
- `research-dual-ai-runs`: Chạy riêng hoặc phối hợp hai luồng AI, lưu raw run, merge options, metadata an toàn và compile context theo ngân sách.
- `research-content-development`: Chat phát triển series/ý tưởng/kịch bản, nhánh nội dung, approval, memory promotion và tiếp tục phát triển sau Series drama 3 phút.
- `research-script-scoring`: Chấm điểm ý tưởng/kịch bản, giải thích điểm, phát hiện rủi ro, xếp hạng phương án và tạo recommendation có thể duyệt.
- `research-to-ai-video-handoff`: Đóng gói nội dung đã duyệt sang AI Video project/source blocks, deep-link sang `/ai-video`, provenance và stale behavior sau handoff.

### Modified Capabilities

- Không thay đổi requirement của capability hiện có. AI Video, Video Inspiration, Comic Series Analysis và Story Studio được dùng qua API/primitive hiện tại; mọi thay đổi cần thiết để nhận handoff phải tương thích ngược và được kiểm thử hồi quy.

## Impact

- Frontend: thêm route, navigation item, workspace nghiên cứu, source picker, run/review tabs, score/recommendation panel, chat, memory preview và handoff confirmation; giữ giao diện tiếng Việt.
- Backend: thêm model/migration/service/route cho Research Project và Research Handoff; thêm API schemas, file storage dưới data directory hiện tại và adapter read-only tới Series Brain để compile memory theo revision.
- AI planning: thêm adapter gọi các luồng AI nghiên cứu và phát triển content, giữ cấu hình hiện tại ở chế độ đọc và không ghi secret vào memory/log.
- AI Video: tích hợp qua primitive tạo project/source block và Project Memory hiện có; không tạo pipeline kịch bản thứ hai và không auto-run mặc định.
- Storage: database là nguồn chuẩn cho list/filter/status/revision/link; file markdown/json là memory, export, prompt context và chẩn đoán.
- Verification: backend unit/integration tests, frontend typecheck/build/lint, route smoke test và một lượt AI thực tế có ghi nhận token/cost metadata đã redaction.
