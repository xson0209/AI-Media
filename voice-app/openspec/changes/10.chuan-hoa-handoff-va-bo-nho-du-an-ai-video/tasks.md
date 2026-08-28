## 1. Hợp đồng handoff và migration

- [x] 1.1 Thêm bảng handoff với job, analysis package, phiên bản, trạng thái, script revision và project đích.
- [x] 1.2 Thêm schema payload có target audience, mục tiêu, content spine, hook, retention, script, visual, audio, originality và evidence.
- [x] 1.3 Viết migration tương thích handoff sessionStorage và endpoint tạo project hiện có.
- [x] 1.4 Dựng source blocks cũ từ payload mới để giữ tương thích.
- [x] 1.5 Chặn tạo project từ handoff thiếu analysis package hoặc script đã duyệt.

## 2. Bộ nhớ Dự án

- [x] 2.1 Mở rộng nền memory để hỗ trợ phạm vi `project` hoặc thêm mô hình tương đương dùng chung hợp đồng.
- [x] 2.2 Thêm thẻ khách hàng mục tiêu, mục tiêu video, content spine, hook-payoff, retention map, trạng thái nhân vật/bối cảnh, visual, audio, voice, quyết định, must-have và avoid.
- [x] 2.3 Chỉ đưa dữ liệu người dùng hoặc kết quả đã duyệt vào memory chuẩn.
- [x] 2.4 Giữ candidate bị loại, prompt lỗi và suy luận chưa duyệt ngoài memory chuẩn.
- [x] 2.5 Hỗ trợ dự án đơn lẻ không có series.
- [x] 2.6 Với dự án series, kết hợp Project Memory và Series Canon theo thứ tự ưu tiên.
- [x] 2.7 Tạo đề xuất cập nhật series khi dự án phát sinh thay đổi dài hạn, không tự ghi ngược.

## 3. Handoff có cấu trúc

- [x] 3.1 Tạo handoff backend từ VideoAnalysisPackage và bản rewrite đã duyệt.
- [x] 3.2 Tách nguồn quan sát, bài học được phép học và nội dung đích.
- [x] 3.3 Lưu evidence refs, confidence và limitations thay vì chỉ truyền mô tả chung.
- [x] 3.4 Không truyền transcript nguồn như narration đích.
- [x] 3.5 Cho người dùng xem và duyệt các mục Nội dung, Giữ chân, Hình ảnh, Âm thanh, Điều giữ lại và Điều tránh.
- [x] 3.6 Tạo project mặc định thủ công và không auto-run nếu người dùng chưa yêu cầu rõ.

## 4. Lập timeline đích

- [x] 4.1 Xây dịch vụ lập timeline đích từ content spine, retention map, mục đích, nền tảng và thời lượng.
- [x] 4.2 Tái cấu trúc beat theo thời lượng đích, không sao chép từng shot nguồn.
- [x] 4.3 Mỗi beat đích phải có vai trò, câu hỏi, thông tin mới, micro-payoff, hình ảnh và âm thanh.
- [x] 4.4 Gắn nguồn bài học hoặc evidence khi beat học một cơ chế từ video gốc.
- [x] 4.5 Kiểm tra tổng thời lượng, thứ tự và hook-payoff của timeline đích.

## 5. Bộ biên dịch ngữ cảnh theo nhiệm vụ

- [x] 5.1 Biên dịch ngữ cảnh riêng cho story development.
- [x] 5.2 Biên dịch ngữ cảnh riêng cho shot breakdown.
- [x] 5.3 Biên dịch ngữ cảnh riêng cho prompt ảnh và prompt video.
- [x] 5.4 Biên dịch ngữ cảnh riêng cho voice và subtitle.
- [x] 5.5 Ghim hook, payoff, content spine, narration đích, canon và quyết định đã duyệt.
- [x] 5.6 Chỉ lấy transcript, shot nguồn, frame và audio event liên quan.
- [x] 5.7 Lưu context snapshot và nguồn dữ liệu đã dùng.

## 6. Phiên bản, dependency và stale

- [x] 6.1 Lưu revision analysis package, handoff, script, Project Memory và target timeline.
- [x] 6.2 Ghi dependency snapshot cho story, shot, prompt, voice và subtitle.
- [x] 6.3 Sửa transcript nguồn chỉ stale artifact thực sự phụ thuộc nội dung đó.
- [x] 6.4 Sửa narration đích stale voice, subtitle và package liên quan.
- [x] 6.5 Hiển thị lý do stale và cho tạo lại đúng phạm vi.

## 7. Giao diện tiếng Việt

- [x] 7.1 Thêm màn xem và duyệt handoff trước khi tạo project.
- [x] 7.2 Thêm khu vực Bộ nhớ Dự án trong AI Video.
- [x] 7.3 Hiển thị dữ liệu nào đến từ video nguồn, dữ liệu nào là bài học và dữ liệu nào là nội dung mới.
- [x] 7.4 Hiển thị timeline đích và liên kết evidence khi có.
- [x] 7.5 Giữ các lựa chọn thị trường, ngôn ngữ, thời lượng, tỷ lệ, voice và cách chạy cho người dùng xác nhận.
- [x] 7.6 Không yêu cầu người dùng chỉnh JSON hoặc hiểu source block kỹ thuật.

## 8. Kiểm thử và tài liệu

- [x] 8.1 Kiểm thử reload trình duyệt không làm mất handoff backend.
- [x] 8.2 Kiểm thử dữ liệu timeline, retention và evidence không bị làm phẳng hoặc cắt mất phần bắt buộc.
- [x] 8.3 Kiểm thử project đơn lẻ dùng Project Memory làm nguồn chuẩn.
- [x] 8.4 Kiểm thử project series không được dùng Project Memory để phá fixed trait.
- [x] 8.5 Kiểm thử story, shot, prompt, voice và subtitle nhận đúng gói ngữ cảnh.
- [x] 8.6 Kiểm thử transcript nguồn không trở thành voice cuối nếu narration đích khác.
- [x] 8.7 Kiểm thử tạo project mặc định không auto-run và không gọi Veo.
- [x] 8.8 Viết tài liệu tiếng Việt về handoff, Project Memory và dữ liệu nguồn so với nội dung đích.

