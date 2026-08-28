## 1. Mô hình dữ liệu và migration

- [x] 1.1 Thêm phiên bản schema cho gói phân tích video.
- [x] 1.2 Thêm dữ liệu shot nguồn với thời gian, keyframe, hình ảnh, camera, chuyển động, chuyển cảnh, chữ và mức tin cậy.
- [x] 1.3 Thêm transcript segment có thời gian, ngôn ngữ, người nói, nguồn chỉnh sửa và mức tin cậy.
- [x] 1.4 Thêm sự kiện âm thanh và chữ trên màn hình theo timeline.
- [x] 1.5 Thêm beat nội dung giữ chân, hook analysis, coverage metrics và limitations.
- [x] 1.6 Viết migration tương thích job Video Inspiration cũ.

## 2. Phát hiện shot và chọn keyframe

- [x] 2.1 Thêm phát hiện ranh giới shot bằng công cụ phù hợp trong hạ tầng hiện có.
- [x] 2.2 Tính thời lượng và thứ tự shot ổn định.
- [x] 2.3 Chọn keyframe theo shot thay vì chỉ lấy frame cách đều.
- [x] 2.4 Cho shot dài hoặc biến động cao dùng nhiều keyframe trong giới hạn cấu hình.
- [x] 2.5 Giữ chế độ nhanh và chất lượng cao dùng cùng schema đầu ra.
- [x] 2.6 Báo độ phủ shot và frame, không báo hoàn tất đầy đủ khi trích xuất thiếu nghiêm trọng.

## 3. Transcript có timestamp

- [x] 3.1 Lưu timestamp cấp segment hoặc từ theo khả năng STT.
- [x] 3.2 Lưu cấp chính xác timestamp và không giả lập độ chính xác cao hơn dữ liệu nguồn.
- [x] 3.3 Hỗ trợ nhãn người nói khi công cụ xác định được.
- [x] 3.4 Cho người dùng sửa segment nhưng vẫn giữ bản transcript thô.
- [x] 3.5 Liên kết transcript segment với shot chồng lấp theo thời gian.

## 4. Phân tích hình ảnh, chuyển động và chữ

- [x] 4.1 Phân tích chủ thể, bối cảnh, đạo cụ, ánh sáng, màu sắc và bố cục theo shot.
- [x] 4.2 Phân tích camera motion và subject motion với mức tin cậy.
- [x] 4.3 Nhận diện chuyển cảnh và nhịp cắt.
- [x] 4.4 Trích chữ trên màn hình bằng OCR hoặc vision, kèm thời gian và vùng tương đối.
- [x] 4.5 Cho người dùng sửa chữ nhận diện sai.
- [x] 4.6 Ghi rõ frame không xem được hoặc phần phân tích chỉ là suy luận.

## 5. Phân tích âm thanh

- [x] 5.1 Tách timeline speech, music, ambience, SFX và silence.
- [x] 5.2 Phân tích mức năng lượng và điểm thay đổi âm thanh.
- [x] 5.3 Phát hiện nguy cơ nhạc hoặc SFX che lời bằng chỉ số kỹ thuật phù hợp.
- [x] 5.4 Liên kết sự kiện âm thanh với shot và transcript theo thời gian.
- [x] 5.5 Không khẳng định tên hoặc nguồn âm thanh khi không có bằng chứng.

## 6. Phân tích nội dung giữ chân

- [x] 6.1 Xác định đối tượng, vấn đề, lời hứa, câu hỏi trung tâm và payoff của video nguồn.
- [x] 6.2 Chia timeline thành beat nội dung có vai trò rõ.
- [x] 6.3 Với mỗi beat, lưu thông tin mới, thay đổi cảm xúc/mức độ quan trọng, câu hỏi được trả lời, vòng mở mới, micro-payoff và lý do xem tiếp.
- [x] 6.4 Phát hiện đoạn lặp, lan man, thiếu giá trị mới hoặc có thể xóa mà không ảnh hưởng nội dung.
- [x] 6.5 Chấm dự đoán theo tỷ trọng 75% nội dung và 25% cách thể hiện.
- [x] 6.6 Đánh dấu kết quả là dự đoán, chưa phải retention thực tế.
- [x] 6.7 Gắn timestamp, shot, transcript, frame hoặc audio event làm bằng chứng.

## 7. API và giao diện tiếng Việt

- [x] 7.1 Thêm API trả timeline shot, transcript, âm thanh, chữ và beat nội dung.
- [x] 7.2 Thêm chế độ phân tích nhanh và chất lượng cao.
- [x] 7.3 Hiển thị timeline đồng bộ video, lời nói, shot, chữ, âm thanh và retention beat.
- [x] 7.4 Hiển thị coverage, confidence, limitations và phần người dùng có thể sửa.
- [x] 7.5 Dùng ngôn ngữ “dự đoán nguy cơ” thay vì khẳng định retention thật.
- [x] 7.6 Không yêu cầu người dùng xem hoặc sửa JSON.

## 8. Kiểm thử và tài liệu

- [x] 8.1 Kiểm thử video nhiều shot không còn bị đại diện chỉ bằng frame cách đều.
- [x] 8.2 Kiểm thử transcript giữ timestamp và bản sửa không xóa bản thô.
- [x] 8.3 Kiểm thử liên kết shot, transcript, chữ và âm thanh theo thời gian.
- [x] 8.4 Kiểm thử video không lời, chỉ lời, ít cảnh và nhiều cảnh.
- [x] 8.5 Kiểm thử retention beat tập trung vào thông tin mới và payoff, không chỉ số lần cắt.
- [x] 8.6 Kiểm thử coverage thấp tạo cảnh báo đúng.
- [x] 8.7 Xác nhận không gọi API tạo ảnh, không gọi Veo và không tạo clip.
- [x] 8.8 Viết tài liệu tiếng Việt giải thích timeline, confidence và retention dự đoán.
