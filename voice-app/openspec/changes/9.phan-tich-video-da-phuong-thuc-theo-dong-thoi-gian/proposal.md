## Bối cảnh

Video Inspiration hiện đã tách âm thanh, chuyển lời nói thành transcript, lấy tối đa 12 frame, phân tích hình ảnh và viết lại kịch bản. Tuy nhiên transcript không giữ mốc thời gian, frame được lấy cách đều thay vì theo ranh giới shot, và kết quả phân tích chủ yếu là các đoạn văn tổng quát. Hệ thống chưa giữ được quan hệ chính xác giữa nội dung được nói, hình ảnh đang xuất hiện, chuyển động, chữ trên màn hình, nhạc, hiệu ứng âm thanh và vai trò giữ chân tại từng thời điểm.

Với video dài, số frame giới hạn có thể bỏ qua hook, cao trào hoặc payoff. AI có thể mô tả “nhịp hình ảnh” nhưng chưa có dữ liệu khách quan về độ dài shot, tốc độ cắt, khoảng im lặng, mức năng lượng hoặc điểm thay đổi nội dung.

## Mục tiêu

- Phân tích video theo dòng thời gian thay vì chỉ dùng transcript và frame rời rạc.
- Phát hiện ranh giới shot, thời lượng shot và keyframe đại diện theo từng shot.
- Lưu transcript theo segment có thời gian bắt đầu, kết thúc và người nói khi xác định được.
- Phân tích hình ảnh, chuyển động chủ thể, camera, chuyển cảnh, chữ trên màn hình và mức tin cậy.
- Phân tích nhạc, lời nói, khoảng im lặng, hiệu ứng âm thanh, mức năng lượng và nguy cơ âm thanh che lời.
- Phân tích giữ chân toàn video theo nội dung là chính: lời hứa, câu hỏi trung tâm, thông tin mới, diễn tiến, micro-payoff, cao trào, payoff và CTA.
- Phân biệt dữ liệu quan sát được, suy luận có mức tin cậy và phần không thể xác định.
- Tạo một `VideoAnalysisPackage` có cấu trúc, có phiên bản và bằng chứng theo timestamp để phase 10 truyền sang AI Video.
- Hoạt động mà không cần API tạo ảnh và không gọi Veo.

## Ngoài phạm vi

- Chưa thay đổi cách AI Video nhận và dùng gói phân tích; việc này thuộc change 10.
- Chưa tạo Bộ nhớ Dự án; việc này thuộc change 10.
- Chưa chấm chất lượng kịch bản, prompt, voice và phụ đề toàn luồng; việc này thuộc change 11.
- Chưa dùng biểu đồ retention thật từ nền tảng để kết luận hiệu quả; change này chỉ tạo phân tích dự đoán từ nội dung video.
- Không tạo ảnh, clip hoặc MP4 mới.

## Khả năng mới

- `phan-tich-video-da-phuong-thuc-theo-dong-thoi-gian`: trích xuất timeline shot, transcript có thời gian, hình ảnh, chuyển động, chữ, âm thanh và bản đồ nội dung giữ chân có bằng chứng.

## Phụ thuộc

- Dùng workflow Video Inspiration, FFmpeg/FFprobe, Whisper và lớp AI planning hiện có.
- Có thể dùng quét ảnh/vision hiện có; không phụ thuộc API sinh ảnh.
- Tạo hợp đồng dữ liệu đầu vào bắt buộc cho change 10.

## Kết quả mong muốn

Người dùng mở một video và thấy timeline gồm các shot, lời nói, hình ảnh, chữ, âm thanh và vai trò nội dung. Mỗi kết luận quan trọng có timestamp, bằng chứng và mức tin cậy. Hệ thống chỉ ra video giữ người xem bằng nội dung nào, đoạn nào lặp hoặc thiếu giá trị, và phần nào không phân tích được thay vì bịa dữ liệu.

## Tên change

`9.phan-tich-video-da-phuong-thuc-theo-dong-thoi-gian`
