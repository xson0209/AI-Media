## Context

Voicebox đang có các workspace độc lập cho AI Video, Video Inspiration, Comic Series Analysis và Story Studio. Database hiện là nguồn chuẩn cho dữ liệu có trạng thái; các file markdown như memory của series là artifact được dựng lại để đọc, export và chẩn đoán. Luồng planning hiện tại có thể tạo story/script/scene/shot từ source blocks và có cơ chế Project Memory, vì vậy Research Workspace cần đứng phía trước các luồng đó, không tạo một pipeline AI Video thứ hai.

Change này là cross-cutting nhưng route mới phải được cô lập. Research Project quản lý nguồn, run, ý tưởng, score, chat draft, approval và memory. Khi handoff, hệ thống chuyển phần đã duyệt sang source blocks và Project Memory của AI Video, tạo project mới rồi deep-link tới route AI Video; việc chạy planning/generation vẫn do người dùng khởi động trong AI Video.

## Goals / Non-Goals

**Goals:**

- Tạo workspace `/research` bằng tiếng Việt, có danh sách nhiều Research Project và deep-link tới từng project.
- Lưu DB làm nguồn chuẩn cho UI/filter/status/revision/link; compile các phần đã duyệt thành `research-memory.md` và JSON manifest dễ đọc, export và làm prompt context.
- Nhận link video, upload video, link truyện, upload ảnh, text/docs hoặc liên kết trực tiếp Series Memory; giữ original bất biến và chuẩn hóa kết quả về Research Source Package.
- Hỗ trợ ba mode chạy: nghiên cứu tài liệu, phát triển nội dung, cả hai; lưu riêng kết quả rồi merge thành nhiều phương án.
- Phát triển series drama 3 phút bằng chat, có draft, nhánh, approval và memory promotion.
- Chấm điểm ý tưởng/kịch bản theo tiêu chí cố định, giải thích điểm, cảnh báo rủi ro và đề xuất phương án khuyên chọn có thể override.
- Handoff chỉ từ accepted content, tạo AI Video project bằng primitive hiện tại, giữ provenance và đánh dấu stale đúng phạm vi khi nguồn thay đổi.
- Giữ các route cũ và các request/response hiện có tương thích; lỗi research không được làm hỏng worker hoặc queue của luồng khác.

**Non-Goals:**

- Không thay thế hoặc đổi hành vi nội bộ của Video Inspiration, Comic Series Analysis, Story Studio hay AI Video.
- Không tự publish, render, tạo voice, tạo subtitle hoặc chạy toàn bộ AI Video sau handoff.
- Không đưa raw source dài, raw provider output hoặc secret/config vào memory chuẩn.
- Không coi điểm số là quyết định tự động bắt buộc; người dùng luôn có thể chọn phương án khác hoặc sửa điểm override.
- Không xây hệ phân tích analytics/retention từ dữ liệu lượt xem trong change này.

## Decisions

### 1. Database-first, file-backed memory

Thêm các bảng Research Project, Source, Run, Idea, Script, Score, Chat Thread/Message và Handoff bằng SQLAlchemy model; migration phải additive và idempotent. Mỗi project có thư mục storage riêng với `manifest.json`, `research-memory.md`, `runs/`, `ideas/`, `scripts/`, `sources/` và `handoffs/`. DB giữ path tương đối, revision, status và quan hệ; file được compile từ DB sau các thao tác duyệt.

Lý do: quét thư mục không đủ cho multi-select, filter, stale, idempotency và liên kết AI Video. File vẫn được giữ vì người dùng cần mở lại, export và dùng làm prompt context.

### 2. Source adapter boundary

Research route không copy UI hoặc pipeline của các luồng phân tích hiện có. Source ingestion lưu input và tạo job riêng; adapter dùng lại service/contract hiện có khi loại nguồn tương ứng đã được hỗ trợ. Kết quả được chuyển về `ResearchSourcePackage` gồm summary, observations, plot/character/style lessons, evidence refs, limitations và provenance. Khi adapter chưa thể phân tích nguồn, source vẫn giữ trạng thái `needs_review` hoặc `partial` với lý do rõ ràng, không giả tạo kết quả.

Original upload phải immutable; derivative/transcript/OCR/thumbnail nằm dưới source artifact directory. URL phải được kiểm tra SSRF, không lấy cookie/login/paywall/DRM và log phải redaction.

### 2a. Series Memory là nguồn liên kết read-only

Người dùng có thể chọn một Series hiện có ngay trong source picker thay vì dán tóm tắt. Research lưu `series_id`, revision/fingerprint nguồn và provenance, sau đó gọi Series Brain compiler hiện có để lấy canon đã duyệt, character profile, relationship, current state, open thread, episode/arc summary, continuity và negative rules theo context budget. Research không đọc draft chưa duyệt và không ghi ngược vào Series.

Source package giữ một snapshot có thể tái lập cho lần nghiên cứu, đồng thời vẫn là một liên kết có thể làm mới. Khi fingerprint của Series Memory thay đổi, source chuyển `stale`; người dùng bấm `Làm mới memory` để tạo revision source mới. Làm mới không tự promotion nội dung mới vào Research Memory và không làm stale các luồng ngoài Research nếu chưa có dependency tương ứng.

### 3. Hai vai trò AI và merge có kiểm soát

Mode nghiên cứu tài liệu tạo evidence, docs insight, comparison và risks. Mode phát triển nội dung tạo concept, hook, beat, script seed và production notes. Mode cả hai chạy hai attempt độc lập, lưu provider metadata an toàn, sau đó merge service tạo 3-5 options có mapping contribution và evidence.

Không gửi raw output của một attempt vào attempt còn lại như instruction. Merge nhận context đã chuẩn hóa và giới hạn budget. Cấu hình người dùng được đọc ở chế độ chỉ đọc; không ghi token, đường dẫn nhạy cảm hoặc toàn bộ output dài vào log.

### 4. Draft, approval và revision

Chat/message, idea và script có trạng thái draft/candidate/accepted/rejected/stale. Chỉ thao tác approve mới promotion vào memory chuẩn. Mỗi promotion tạo revision mới, lưu accepted ids trong manifest và compile markdown; không ghi đè âm thầm. Nhánh thay thế giữ lịch sử nhưng không ảnh hưởng canon hiện tại.

### 5. Scoring và recommendation

Mỗi idea/script được chấm 0-10 theo rubric mặc định:

- Hook và lời hứa người xem: 20%.
- Cấu trúc, rõ ràng và nhịp 3 phút: 15%.
- Xung đột và sức kéo cảm xúc: 15%.
- Retention, open loop và payoff: 15%.
- Độ mới và khoảng cách với nguồn: 15%.
- Chủ động của nhân vật và khả năng phát triển series: 10%.
- Khả năng sản xuất bằng AI Video: 10%.

Điểm tổng là weighted score 0-100 và phải giữ từng điểm thành phần, lý do, evidence refs, limitations, confidence và rubric revision. Recommendation ưu tiên điểm tổng nhưng có safety gate: thiếu hook, vi phạm constraint, độ mới quá thấp hoặc production feasibility dưới ngưỡng thì không được gắn `recommended` dù điểm tổng cao. Nếu nhiều phương án gần nhau, hiển thị nhóm đồng hạng và lý do khác biệt. User override được lưu riêng, không sửa điểm AI gốc.

### 6. Handoff trực tiếp vào AI Video hiện tại

Research Handoff là artifact bất biến theo revision, chỉ tạo từ accepted ideas/scripts/memory và brief người dùng. Service handoff chuyển thành các source blocks tương thích với AI Video, gọi service tạo project hiện có trong cùng transaction hoặc có idempotency/recovery, rồi trả `project_id` và URL `/ai-video?projectId=...`.

Handoff không tự gọi generate plan. Sau khi project được tạo, AI Video đọc Project Memory/source blocks hiện tại để người dùng bấm chạy planning bằng Codex. Khi accepted research revision thay đổi, dependency marker của handoff/project được cập nhật stale nhưng không sửa ngược script/render đã publish; chỉ các artifact phụ thuộc mới bị yêu cầu regenerate.

### 7. Route và UI/UX

Route `/research` là workspace content-first, density vừa cao để so sánh nhiều project nhưng không dùng layout marketing. Desktop dùng sidebar danh sách project và main review; mobile chuyển sidebar thành drawer/sheet, giữ filter/selection và primary action luôn truy cập được. Các khu chính: Dự án, Nguồn, Lần chạy, Phương án, Chấm điểm, Chat phát triển, Memory và Handoff.

Mỗi màn hình chỉ có một primary action theo trạng thái: `Tạo nghiên cứu`, `Chạy nghiên cứu`, `Duyệt phương án`, hoặc `Đóng gói sang AI Video`. Nút icon dùng Lucide kèm tooltip/aria-label; target tương tác tối thiểu 44px, focus rõ, keyboard có thể chọn nhiều project, loading/error/partial/stale có thông báo và hành động phục hồi. Dùng token UI hiện có, không tạo palette riêng chi phối toàn app; đảm bảo tương phản, wrapping, reduced motion, 375px/768px/1024px/1440px và không có horizontal scroll.

### 8. Cô lập với luồng hiện có

Router chỉ thêm child route/component mới. Backend đăng ký router `/research` riêng; không đổi prefix, schema hoặc default behavior của route cũ. Research gọi các service dùng chung qua adapter có boundary, không import ngược component/UI của AI Video. Feature flag có thể tắt menu/route/job research trong khi AI Video và các handoff đã tạo vẫn mở được. Regression tests phải chứng minh request cũ và route cũ không bị thay đổi.

## Risks / Trade-offs

- [Risk] Nhiều source hoặc project làm prompt vượt budget → compile theo accepted-first, giới hạn mỗi project/tổng context, báo rõ phần đã rút gọn.
- [Risk] Series thay đổi trong lúc Research đang dùng memory cũ → fingerprint theo canon đã compile, hiển thị revision nguồn và đánh dấu `stale`; chỉ làm mới khi người dùng xác nhận để giữ khả năng truy vết lần nghiên cứu.
- [Risk] Hai AI trả kết luận mâu thuẫn → lưu riêng attempt, merge có provenance, hiển thị bất đồng và không auto-approve.
- [Risk] Điểm cao nhưng ý tưởng khó sản xuất hoặc quá giống nguồn → safety gate cho feasibility/originality, cảnh báo bắt buộc và không tự khuyên chọn.
- [Risk] Handoff tạo project dở dang hoặc bấm lặp → idempotency key, dependency fingerprint, stage/commit và recovery test.
- [Risk] Migration trên DB cũ → migration additive/idempotent, tạo bảng thiếu thay vì đổi dữ liệu cũ, có startup smoke test.
- [Risk] Route mới làm sidebar/layout chật hoặc ảnh hưởng route cũ → lazy load workspace, giữ `isWideWorkspace` cũ chỉ mở rộng có chủ đích, test deep-link/back/filter state trên desktop/mobile.
- [Risk] Test AI thật tiêu token hoặc provider timeout → chỉ chạy một prompt fixture ngắn có cờ explicit, ghi token/cost metadata đã redaction, timeout có retry/skip rõ ràng và test unit không gọi AI.

## Migration Plan

1. Thêm migration/bảng/storage helper và route mới; chưa bật menu hoặc feature flag nếu schema chưa sẵn sàng.
2. Bật workspace ở trạng thái text/docs trước, chạy backend/frontend regression.
3. Bật adapter video/truyện/ảnh theo từng loại, giữ source partial nếu upstream không hỗ trợ.
4. Bật scoring/recommendation và chat approval; compile memory sau mỗi promotion.
5. Bật handoff tạo AI Video project/deep-link, mặc định không auto-run.
6. Rollback bằng cách tắt feature flag/menu; dữ liệu research giữ nguyên, route cũ và project AI Video đã tạo vẫn đọc được.

## Open Questions

- Upload video/ảnh ở bản đầu dùng giới hạn dung lượng nào theo runtime hiện tại?
- Có cần hiển thị chi phí/token thực tế cho người dùng hay chỉ lưu trong chi tiết run dành cho kiểm tra?
- Khi user chọn nhiều project có canon mâu thuẫn, UI mặc định dùng ưu tiên theo project hay bắt buộc user giải quyết từng conflict?
