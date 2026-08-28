# Workspace Nghiên cứu ý tưởng và handoff AI Video

## Mục đích

Workspace mới nằm ở route `/research`. Đây là nơi gom nguồn tham khảo, chạy nghiên cứu, phát triển content,
chấm điểm và chỉ chuyển phần người dùng đã duyệt sang AI Video.

Database là nguồn chuẩn để hiển thị project, trạng thái, phiên bản và liên kết. Mỗi project đồng thời có file
memory để mở lại, export hoặc dùng làm context:

- `research-memory.md`: memory đã biên dịch từ nội dung accepted.
- `manifest.json`: schema, revision và các id đã duyệt.
- `runs/`: brief, kết quả từng lượt và merge.
- `ideas/`, `scripts/`, `sources/`, `handoffs/`: artifact theo project.

Draft, raw output, file upload gốc và log không tự trở thành memory chuẩn.

## Nguồn nghiên cứu

Một project có thể nhận:

- Link video public.
- Upload video.
- Link truyện hoặc trang truyện public.
- Upload ảnh.
- Text, brief hoặc docs URL.

Video/ảnh upload được lưu original bất biến. URL được redaction query nhạy cảm trước khi lưu. Nguồn chưa có
adapter phân tích sâu sẽ giữ trạng thái partial và nêu giới hạn thay vì giả tạo insight.

## Hai vai trò AI

Chọn một trong ba mode:

- **Nghiên cứu tài liệu**: dùng CLI nghiên cứu chỉ đọc, lấy cấu hình người dùng từ `~/.claude/settings.json`.
- **Phát triển content**: dùng planning engine hiện có để tạo concept, hook, beat và script seed.
- **Cả hai**: chạy hai attempt độc lập; lỗi một bên không làm mất kết quả bên còn lại.

Kết quả được lưu raw ở `runs/`, đồng thời các phương án được tạo thành ứng viên trong database. Ứng viên không
được approve tự động.

Metadata usage/cost chỉ được lưu ở dạng đã lọc nếu CLI trả về. Không lưu secret, config đầy đủ hoặc command path
nhạy cảm vào metadata hiển thị.

## Trò chuyện phát triển content

Trong project, tab **Phát triển content** dùng memory accepted, nguồn và các project liên quan đã chọn làm context.
Bạn có thể yêu cầu viết tập sau, tăng drama, đổi nhân vật, sửa logic hoặc phát triển series 3 phút.

Kết quả chat là draft. Người dùng có thể:

- Lưu thành ý tưởng ứng viên để chấm và duyệt.
- Tạo kịch bản seed nháp để review.
- Chọn phương án khác hoặc bỏ qua.

Chỉ khi bấm duyệt, nội dung mới được compile vào `research-memory.md` và tạo revision mới.

## Chấm điểm và khuyên chọn

Mỗi ý tưởng hoặc kịch bản có thể được chấm theo bảy tiêu chí: hook, cấu trúc, xung đột/cảm xúc, retention,
độ mới, tiềm năng series và khả năng sản xuất AI Video. Điểm tổng là 0-100.

Hệ thống có safety gate cho hook, độ mới và feasibility. Điểm cao nhưng vi phạm gate sẽ là `Cần chỉnh`, không
phải `Khuyên chọn`. Điểm AI và lựa chọn người dùng được lưu tách nhau.

## Handoff sang AI Video

Handoff chỉ nhận ý tưởng/kịch bản đã accepted. Gói handoff chứa memory, nội dung accepted, score, evidence,
provenance, must-have, avoid và limitations. Hệ thống gọi primitive tạo project AI Video hiện có, tạo source
blocks tương thích và trả deep-link:

`/ai-video?projectId=<id>`

AI Video đồng thời nhận các thẻ Project Memory đã duyệt, gồm nhận diện dự án, mục tiêu video, trục nội dung,
hook/payoff, ý tưởng đã chọn, kịch bản seed nếu có, quyết định đã duyệt, research findings, must-have, avoid và
bằng chứng/provenance. Codex đọc các thẻ phù hợp theo tác vụ story, shot, prompt, voice hoặc subtitle qua context
compiler hiện có của AI Video.

Project mới ở trạng thái draft; không tự chạy planning, scene, shot hay generation. Khi mở AI Video, người dùng
bấm workflow hiện có để Codex phát triển story, continuity, script và shot/prompt.

Nếu Research revision thay đổi sau handoff, handoff cũ và trạng thái planning/package của AI Video project liên
quan được đánh stale để người dùng chủ động handoff revision mới hoặc chạy lại. Hệ thống không tự gọi planning
hay generation. Project AI Video đã tạo vẫn mở được kể cả khi Research Workspace bị tắt.

## Tắt workspace mới

Backend dùng cờ runtime `VOICEBOX_FEATURE_RESEARCH=false`. Frontend dùng `VITE_FEATURE_RESEARCH=false`. Khi tắt,
route và menu Research bị ẩn/redirect; các route AI Video, Video Inspiration, Comic Series Analysis và Story
Studio không đổi hành vi.
