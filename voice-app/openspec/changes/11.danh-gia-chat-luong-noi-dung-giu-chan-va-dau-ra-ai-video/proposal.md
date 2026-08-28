## Bối cảnh

Sau change 9 và 10, hệ thống có phân tích video theo timeline, retention beat tập trung vào nội dung, handoff có cấu trúc và Bộ nhớ Dự án. Tuy nhiên vẫn cần một lớp kiểm định chung để biết dữ liệu phân tích có đủ độ phủ không, ba phương án có thực sự khác nhau không, kịch bản có tiến triển và trả đúng lời hứa không, prompt có bám nội dung không, voice có đúng nhịp không và phụ đề có khớp bản cuối không.

Phân tích từ video chỉ dự đoán nguy cơ giữ chân. Nếu người dùng có biểu đồ retention hoặc số liệu nền tảng, hệ thống cần so sánh dữ liệu thực tế với timeline để tìm đoạn tụt, đoạn xem lại và cơ chế nội dung có khả năng liên quan. Hệ thống phải phân biệt tương quan với nguyên nhân, không khẳng định quá mức.

## Mục tiêu

- Tạo báo cáo chất lượng xuyên suốt từ VideoAnalysisPackage, handoff, Project Memory, timeline đích, kịch bản, candidate, prompt, voice tới subtitle.
- Dùng rubric giữ chân lấy nội dung làm chính với tỷ trọng mặc định 75% nội dung và 25% cách thể hiện.
- Chấm hook đa lớp: nội dung, hình ảnh, lời nói, chữ, âm thanh và tâm lý người xem.
- Kiểm tra lời hứa hook, câu hỏi trung tâm, thông tin mới, diễn tiến, micro-payoff, payoff, CTA và đoạn lặp hoặc lan man.
- Dùng chung cơ chế ba candidate, đánh giá độc lập và tổng hợp từ change 7 cho Video Inspiration và AI Video.
- Chấm độ nguyên bản để học cơ chế nhưng không copy câu thoại, nhân vật hoặc chuỗi cảnh nguồn.
- Kiểm tra prompt bám đúng content beat, retention role, continuity, thời lượng và narration.
- Kiểm tra voice về nội dung, phát âm, tốc độ, khoảng ngắt, độ dài và nguy cơ bị âm thanh che.
- Kiểm tra subtitle về văn bản, timing, độ đọc, từ khóa, vùng hiển thị và khớp voice cuối.
- Cho phép nhập retention analytics thật từ nền tảng bằng dữ liệu có cấu trúc hoặc nhập tay.
- Xây kiểm thử end-to-end tới voice và subtitle nhưng không gọi Veo hoặc tạo clip provider.

## Ngoài phạm vi

- Không tuyên bố một yếu tố chắc chắn gây tụt retention chỉ từ tương quan.
- Không tự truy cập tài khoản TikTok, YouTube, Facebook hoặc nền tảng khác.
- Không yêu cầu dữ liệu analytics thật để workflow cơ bản hoạt động.
- Không tạo clip Veo hoặc dùng clip provider làm điều kiện vượt kiểm thử.
- Không tự duyệt kịch bản, prompt, voice hoặc subtitle thay người dùng.

## Khả năng mới

- `danh-gia-chat-luong-noi-dung-giu-chan-va-dau-ra-ai-video`: chấm chất lượng nội dung và sản xuất, so sánh retention dự đoán với dữ liệu thật và kiểm thử toàn luồng không gọi Veo.

## Phụ thuộc

- Phụ thuộc vào change 9 để có timeline và retention beat nguồn.
- Phụ thuộc vào change 10 để có handoff, Project Memory, target timeline và context snapshot.
- Tái sử dụng candidate, critic, prompt quality và repair của change 7; dependency và stale của change 8.

## Kết quả mong muốn

Người dùng nhận một báo cáo tiếng Việt dễ hiểu: nội dung có giữ đúng lời hứa không, đoạn nào thiếu giá trị mới, phương án nào tốt hơn và vì sao, prompt nào lệch beat, voice hoặc phụ đề nào cần sửa. Khi có retention thật, hệ thống chỉ ra mốc tụt hoặc xem lại và đối chiếu với nội dung tại thời điểm đó. Bộ kiểm thử xác nhận toàn pipeline tới voice và subtitle mà không gọi Veo.

## Tên change

`11.danh-gia-chat-luong-noi-dung-giu-chan-va-dau-ra-ai-video`
