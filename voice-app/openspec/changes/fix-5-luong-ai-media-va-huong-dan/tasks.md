## 1. Baseline và dữ liệu thật

- [x] 1.1 Xác minh Vite `:4000`, FastAPI `:17493`, Python/Node/Bun, CUDA và provider/codec readiness cơ bản
- [x] 1.2 Kiểm kê dữ liệu thật của năm workspace và cố định project Research “Nghiên cứu Series: Người Que” làm dữ liệu chuẩn
- [x] 1.3 Tạo thư mục bằng chứng `output/playwright/full-flow-2026-08-11/` và manifest ghi route, record ID, action, request, screenshot, kết quả
- [x] 1.4 Chụp baseline console/network/backend log của đủ năm route với điều kiện chờ nội dung thật

## 2. Story Studio

- [x] 2.1 Mở series/tập thật và xác minh nhân vật, reference, canon, memory, prompt hình và prompt video
- [x] 2.2 Chạy các hành động đọc/xuất không phá dữ liệu và ghi bằng chứng đầu ra
- [x] 2.3 Chạy handoff Story/Master sang AI Video trên record đủ điều kiện và kiểm tra provenance ở dự án đích
- [x] 2.4 Sửa lỗi Story Studio được tái hiện, bổ sung kiểm thử hẹp và chạy lại kịch bản

## 3. Comic Series Analysis

- [x] 3.1 Mở job thật đã phân tích, xác minh source, panel, analysis package, rewrite, review và state machine
- [x] 3.2 Chạy một hành động hợp lệ theo trạng thái và xác minh response/UI sau refresh
- [x] 3.3 Chạy hoặc mở handoff Comic sang series/Story Studio và kiểm tra title, revision, canon, nhân vật và source provenance
- [x] 3.4 Sửa lỗi Comic được tái hiện, bổ sung kiểm thử hẹp và chạy lại kịch bản

## 4. Research Người Que

- [x] 4.1 Mở project “Nghiên cứu Series: Người Que” và xác minh hai nguồn, các lần chạy, 21 ý tưởng, lựa chọn đã duyệt và memory
- [x] 4.2 Chạy luồng source → run/options → chấm điểm hoặc phát triển content bằng nội dung Người Que thật, không tạo tên `codex_test`
- [x] 4.3 Xác minh lựa chọn/memory sau thao tác ghi và bảo toàn dữ liệu gốc
- [x] 4.4 Handoff ý tưởng Người Que đã duyệt sang AI Video và kiểm tra nội dung/provenance ở dự án đích
- [x] 4.5 Sửa lỗi Research được tái hiện, bổ sung kiểm thử hẹp và chạy lại kịch bản

## 5. Video Inspiration

- [x] 5.1 Mở job thật ở trạng thái `analyzed`, `rewritten` hoặc `ai_video_ready` và xác minh transcript, hình, timeline, analysis, script, handoff
- [x] 5.2 Chạy rewrite hoặc hành động hợp lệ trên job thật và kiểm tra state/output sau refresh
- [x] 5.3 Handoff kịch bản tối ưu sang AI Video và kiểm tra source job/link/file provenance
- [x] 5.4 Sửa lỗi Video Inspiration được tái hiện, bổ sung kiểm thử hẹp và chạy lại kịch bản

## 6. AI Video

- [x] 6.1 Mở dự án thật hiện có và dự án Người Que được handoff; xác minh project status, story, scene, shot, prompt, resource/provider readiness
- [x] 6.2 Chạy bước planning/prompt hợp lệ bằng Codex provider thật và kiểm tra state/output sau refresh
- [x] 6.3 Kiểm tra publishing metadata, voice/subtitle, package/render readiness theo trạng thái dự án
- [x] 6.4 Kiểm tra Veo session/project binding/login action; chạy clip flow nếu ready hoặc lưu bằng chứng blocker thật nếu phụ thuộc tài khoản ngoài chưa sẵn sàng
- [x] 6.5 Sửa lỗi AI Video được tái hiện, bổ sung kiểm thử hẹp và chạy lại kịch bản

## 7. Handoff và tính toàn vẹn xuyên workspace

- [x] 7.1 Đối chiếu Comic → Story/Series, Story → AI Video, Research → AI Video và Video Inspiration → AI Video theo ID và nội dung
- [x] 7.2 Xác minh title/brief, nội dung đã duyệt, language/purpose/output config, series/episode/source link được giữ khi hợp đồng API hỗ trợ
- [x] 7.3 Sửa lỗi mapping/provenance được tái hiện và chạy lại handoff liên quan

## 8. Gate tự động và hồi quy

- [x] 8.1 Chạy test backend mục tiêu cho Story, Comic, Research, Video Inspiration và AI Video
- [x] 8.2 Chạy typecheck frontend, build web và các verifier chuyên biệt liên quan
- [x] 8.3 Chạy lại Playwright đủ năm route sau sửa lỗi, xác nhận không còn console error/request failure bắt buộc
- [x] 8.4 Lưu kết quả command, request và screenshot cuối vào manifest bằng chứng

## 9. HTML hướng dẫn

- [x] 9.1 Tạo `docs/huong-dan-5-luong-ai-media.html` tự chứa với mục lục và link năm route
- [x] 9.2 Viết quy trình, đầu vào/đầu ra, handoff và lỗi thường gặp cho từng workspace; dùng Người Que thật cho phần Research
- [x] 9.3 Thêm ma trận chọn workspace/chuỗi workspace tối ưu theo chủ đề, mục đích, loại nguồn, mức kiểm soát và đầu ra
- [x] 9.4 Mở HTML bằng browser ở desktop/mobile, kiểm tra responsive, link và nội dung tiếng Việt rồi lưu screenshot

## 10. Completion audit

- [x] 10.1 Đối chiếu từng requirement/scenario với bằng chứng trực tiếp và ghi rõ mọi residual risk
- [x] 10.2 Chạy `openspec validate fix-5-luong-ai-media-va-huong-dan --type change --strict --no-interactive` và cập nhật toàn bộ checkbox đúng trạng thái
- [x] 10.3 Chỉ archive/đánh dấu goal hoàn tất khi đủ năm flow, lỗi đã sửa, gate tự động và HTML đều được chứng minh
