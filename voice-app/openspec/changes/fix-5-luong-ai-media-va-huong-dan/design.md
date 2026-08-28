## Context

Voicebox đang chạy Vite tại `127.0.0.1:4000` và FastAPI tại `127.0.0.1:17493`, dùng SQLite thật trong `data/`. Năm workspace cần xác minh đã có dữ liệu người dùng: Story Studio, Comic Series Analysis, AI Video, Research và Video Inspiration. Worktree đồng thời chứa nhiều thay đổi chưa commit trong đúng các module này, vì vậy mọi sửa lỗi phải tối thiểu, dựa trên lỗi tái hiện và không được hoàn tác thay đổi ngoài phạm vi.

Research có project thật **“Nghiên cứu Series: Người Que”** với nguồn Series Memory, các lần chạy và ý tưởng đã duyệt. Đây là dữ liệu chuẩn cho kiểm thử Research và handoff sang AI Video; không tạo dữ liệu giả kiểu `codex_test`.

## Goals / Non-Goals

**Goals:**

- Chứng minh năm route tải được và các luồng nghiệp vụ chính hoạt động trên browser/backend thật.
- Dùng dữ liệu hiện có trước; dữ liệu phụ chỉ được tạo khi thao tác ghi là điều kiện bắt buộc để kiểm chứng, phải có giá trị sử dụng thật và không phá dữ liệu gốc.
- Tái hiện lỗi bằng console/network/backend log, sửa đúng nguyên nhân và chạy lại cùng kịch bản.
- Kiểm tra các handoff quan trọng: Comic → Story/Series, Story → AI Video, Research → AI Video và Video Inspiration → AI Video.
- Xuất HTML tiếng Việt độc lập, dễ tra cứu, nêu cách dùng và ma trận chọn workspace theo mục tiêu/chủ đề.

**Non-Goals:**

- Không xóa, reset hoặc seed lại cơ sở dữ liệu người dùng.
- Không đại tu kiến trúc, giao diện hay đổi yêu cầu sản phẩm nếu không cần để sửa lỗi tái hiện.
- Không giả lập thành công của dịch vụ ngoài như Veo/login; bước phụ thuộc tài khoản phải được kiểm tra readiness và ghi rõ bằng chứng/trở ngại thật.
- Không coi việc route trả `200` là đủ nếu UI, dữ liệu hoặc hành động nghiệp vụ chưa được xác minh.

## Decisions

### 1. Xác minh theo ma trận route → dữ liệu → hành động → đầu ra

Mỗi workspace có một kịch bản chính dùng dữ liệu thật, các hành động đọc/ghi quan trọng và bằng chứng đầu ra. Cách này được chọn thay vì chỉ smoke test route vì lỗi AI/media thường xuất hiện sau nhiều bước hoặc tại handoff.

### 2. Dữ liệu Research cố định ở chủ đề Người Que

Project `Nghiên cứu Series: Người Que` là nguồn chuẩn. Ưu tiên ý tưởng đã duyệt, memory và source hiện có. Nếu cần tạo nội dung mới để chạy AI, nội dung phải tiếp nối canon Người Que và có tên mô tả thật; không dùng prefix/suffix kiểm thử chung chung.

### 3. Playwright CLI là bằng chứng browser chính

Mỗi route được mở bằng session riêng hoặc session có snapshot mới, chờ điều kiện nội dung thật thay vì timeout cứng ngắn, rồi lưu snapshot/screenshot, console và request liên quan trong `output/playwright/full-flow-2026-08-11/`. HTTP trực tiếp và backend log bổ sung bằng chứng cho payload/trạng thái mà UI không hiển thị đủ.

### 4. Sửa lỗi theo vòng tái hiện → kiểm thử hẹp → chạy lại flow

Chỉ chỉnh code sau khi có lỗi cụ thể. Mỗi lỗi phải có kiểm thử tự động phù hợp nếu có điểm seam ổn định; sau đó chạy lại thao tác browser đã thất bại. Điều này giảm rủi ro đè lên lượng thay đổi dở dang lớn trong worktree.

### 5. Handoff được kiểm tra bằng tính toàn vẹn nội dung, không chỉ ID

Đầu ra handoff phải giữ chủ đề, title/brief, nguồn, lựa chọn đã duyệt, ngôn ngữ/mục đích và liên kết nguồn khi API có hỗ trợ. Bản ghi đích phải mở được trong workspace nhận. Đây là tiêu chí quan trọng hơn việc endpoint chỉ trả thành công.

### 6. HTML là tài liệu tĩnh tự chứa

Tạo `docs/huong-dan-5-luong-ai-media.html` với CSS/JS nội tuyến, mục lục, quy trình từng workspace, luồng handoff, checklist đầu vào/đầu ra, lỗi thường gặp và ma trận khuyến nghị. File không phụ thuộc build docs và có thể mở trực tiếp; các link route dùng `http://localhost:4000` theo yêu cầu người dùng.

## Risks / Trade-offs

- **[AI/model hoặc dịch vụ ngoài tốn thời gian hay thiếu phiên đăng nhập]** → Kiểm tra readiness trước, chỉ chạy bước thật khi cấu hình sẵn; lưu lỗi thật và sửa phần ứng dụng nếu lỗi nằm trong phạm vi repo.
- **[Thao tác ghi tạo bản ghi trùng]** → Tái sử dụng dữ liệu hiện có; nếu bắt buộc tạo mới thì dùng tiêu đề Người Que có ý nghĩa và ghi lại ID để người dùng nhận diện.
- **[Worktree có thay đổi chồng lấn]** → Kiểm tra diff trước mỗi edit, patch nhỏ và không format/bulk rewrite module liên quan.
- **[Trang Research lazy-load lâu gây false negative]** → Chờ heading/project Người Que thay vì chờ thời gian cố định; đo request và chỉ coi là lỗi khi nội dung không xuất hiện trong ngưỡng hợp lý.
- **[Kiểm thử browser quá rộng]** → Chia theo kịch bản nghiệp vụ và ghi bằng chứng cho từng gate; không tuyên bố toàn bộ đạt nếu bất kỳ bước yêu cầu nào còn thiếu bằng chứng.

## Migration Plan

1. Ghi baseline runtime/data và chụp trạng thái từng route.
2. Chạy các kịch bản thật, lập danh sách lỗi có bằng chứng.
3. Áp dụng patch nhỏ và kiểm thử hẹp cho từng lỗi.
4. Khởi động lại backend nếu Python thay đổi; Vite tự reload thay đổi frontend.
5. Chạy lại đủ năm route, handoff và gate build/test.
6. Tạo, mở và kiểm tra HTML ở desktop/mobile.
7. Nếu patch gây hồi quy, hoàn nguyên riêng patch do change này tạo; không reset worktree hay dữ liệu.

## Open Questions

- Phiên Veo/Google hiện có sẵn để tạo clip thật hay chỉ có thể xác minh readiness/login flow?
- Một số hành động AI dài có thể cần thời gian/model ngoài phiên làm việc; trạng thái thực tế sẽ được quyết định bằng provider check và log thay vì giả định.
