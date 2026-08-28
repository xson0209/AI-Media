## Bối cảnh

Video Inspiration hiện truyền kết quả sang AI Video bằng các source block văn bản như ý tưởng, kịch bản thô, nhân vật, phong cách, bắt buộc, cần tránh, transcript và analysis. Mỗi block có thể bị rút gọn, dữ liệu bị lặp và quan hệ theo timestamp bị mất. AI Video phải đọc lại các đoạn văn rồi tự suy luận timeline, dẫn đến nguy cơ lệch hook, bỏ sót beat nội dung, dùng transcript nguồn như narration mới hoặc không biết kết luận nào có bằng chứng.

Dự án đơn lẻ không có Series Memory nên hiện thiếu một nguồn chuẩn gọn để giữ khách hàng mục tiêu, mục tiêu video, trục nội dung, retention map, quyết định đã duyệt, trạng thái scene/shot và phiên bản narration, prompt, voice, subtitle. Change 6 tạo nền bộ nhớ cho series; change này mở rộng cùng nguyên tắc cho phạm vi dự án và chuẩn hóa handoff từ gói phân tích của change 9.

## Mục tiêu

- Tạo handoff bền vững phía backend, có mã, phiên bản và trạng thái duyệt; không phụ thuộc duy nhất vào `sessionStorage`.
- Truyền `VideoAnalysisPackage` có cấu trúc từ Video Inspiration sang AI Video mà không làm phẳng toàn bộ thành văn bản.
- Tách rõ dữ liệu nguồn, bài học được phép học, nội dung không được copy và kịch bản mới đã duyệt.
- Thêm Bộ nhớ Dự án cho cả dự án đơn lẻ và dự án thuộc series.
- Giữ khách hàng mục tiêu, mục đích, nền tảng, hook, lời hứa, content spine, retention map, nhân vật, phong cách, voice, phụ đề, điều bắt buộc và quyết định đã duyệt.
- Biên dịch ngữ cảnh theo nhiệm vụ cho story, shot, prompt, voice và subtitle.
- Ánh xạ timeline nguồn thành timeline đích theo thời lượng và cấu hình người dùng, không sao chép từng shot hoặc câu thoại.
- Lưu dấu vết nguồn và phiên bản để người dùng biết AI Video đã dùng phân tích nào.
- Không tự chọn thị trường, thời lượng, tỷ lệ, voice hoặc tự chạy AI Video khi người dùng chưa xác nhận.

## Ngoài phạm vi

- Không phân tích lại shot, transcript, hình ảnh hoặc âm thanh nguồn; việc này thuộc change 9.
- Không chấm điểm chất lượng toàn luồng hoặc nhập retention analytics thật; việc này thuộc change 11.
- Không tạo clip Veo hoặc render MP4.
- Không biến mọi bản nháp AI thành memory đã duyệt.
- Không cho dữ liệu dự án ghi đè canon cố định của series.

## Khả năng mới

- `chuan-hoa-handoff-va-bo-nho-du-an-ai-video`: handoff có cấu trúc từ Video Inspiration, Bộ nhớ Dự án, biên dịch ngữ cảnh theo nhiệm vụ và ánh xạ timeline nguồn sang video đích.

## Phụ thuộc

- Phụ thuộc vào change `9.phan-tich-video-da-phuong-thuc-theo-dong-thoi-gian` để nhận `VideoAnalysisPackage`.
- Dùng nền chọn ngữ cảnh và canon của change 6, sáng tạo và kiểm tra prompt của change 7, phiên bản và dependency của change 8.
- Dùng AI Video phase 2, source blocks, story, shot, prompt, voice và subtitle hiện có.

## Kết quả mong muốn

Khi người dùng chuyển một video đã phân tích sang AI Video, project nhận đúng timeline nội dung, hook, retention, hình ảnh, âm thanh và bằng chứng mà không bị biến thành một khối text dài. Dự án đơn lẻ có Bộ nhớ Dự án làm nguồn chuẩn; dự án thuộc series kết hợp Series Canon với quyết định riêng của tập. Mỗi bước AI chỉ nhận dữ liệu cần thiết và không tự dùng transcript nguồn làm narration cuối.

## Tên change

`10.chuan-hoa-handoff-va-bo-nho-du-an-ai-video`
