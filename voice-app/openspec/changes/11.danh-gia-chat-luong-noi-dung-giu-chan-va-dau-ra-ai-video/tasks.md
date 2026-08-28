## 1. Mô hình báo cáo và trạng thái

- [x] 1.1 Thêm bảng hoặc artifact báo cáo chất lượng với trạng thái, điểm từng tầng, lỗi chặn, cảnh báo, bằng chứng và hành động đề xuất.
- [x] 1.2 Thêm revision và dependency tới analysis package, handoff, Project Memory, script, timeline, prompt, voice và subtitle.
- [x] 1.3 Thêm trạng thái `not_checked`, `checking`, `passed`, `needs_review`, `blocked`, `stale`.
- [x] 1.4 Viết API yêu cầu kiểm tra, xem báo cáo, chạy lại và ghi đè có lý do.
- [x] 1.5 Không cho tổng điểm che lỗi chặn.

## 2. Rubric nội dung và giữ chân

- [x] 2.1 Xây rubric mặc định 75% nội dung, 25% cách thể hiện.
- [x] 2.2 Thêm tiêu chí khách hàng, vấn đề, hook, lời hứa, câu hỏi, logic, thông tin mới, cảm xúc/mức độ quan trọng, micro-payoff, payoff và CTA.
- [x] 2.3 Kiểm tra sáu câu hỏi đóng góp cho từng content beat.
- [x] 2.4 Phát hiện content stagnation, lặp, lan man và đoạn có thể xóa mà không mất giá trị.
- [x] 2.5 Cho phép rubric riêng cho kể chuyện, bán hàng, giáo dục và truyền cảm hứng.
- [x] 2.6 Không cho trọng số nội dung thấp hơn 60% nếu người dùng chưa xác nhận cấu hình đặc biệt.

## 3. Hook và hook-payoff

- [x] 3.1 Chấm hook nội dung, lời nói, hình ảnh, chữ, âm thanh, tâm lý và lời hứa.
- [x] 3.2 Kiểm tra hook phù hợp đối tượng và mục tiêu video.
- [x] 3.3 Kiểm tra payoff trả đúng lời hứa và câu hỏi trung tâm.
- [x] 3.4 Chặn clickbait nghiêm trọng hoặc thông tin sai.
- [x] 3.5 Cho phép tạo ba biến thể hook mới và chấm bằng critic độc lập.
- [x] 3.6 Lưu hook được chọn và lý do vào Project Memory sau khi người dùng duyệt.

## 4. Candidate và tổng hợp

- [x] 4.1 Dùng chung engine ba candidate của change 7 cho Video Inspiration và AI Video.
- [x] 4.2 Đảm bảo ba candidate dùng cùng context snapshot và khác nhau thật.
- [x] 4.3 Chấm candidate theo nội dung, giữ chân, khả năng sản xuất, originality và khách hàng mục tiêu.
- [x] 4.4 Lưu điểm, lý do, bằng chứng, điểm mạnh, điểm yếu và rủi ro.
- [x] 4.5 Tổng hợp phần tốt nhất nhưng kiểm tra lại tính liền mạch, canon, hook-payoff và originality.
- [x] 4.6 Không tự duyệt bản tổng hợp.

## 5. Kiểm tra originality

- [x] 5.1 So sánh narration/câu thoại nguồn và đích.
- [x] 5.2 So sánh thứ tự beat, nhân vật, bối cảnh, chuỗi shot, hook, payoff, chữ và visual motif.
- [x] 5.3 Phân biệt học insight/ngôn ngữ điện ảnh với sao chép chi tiết cụ thể.
- [x] 5.4 Trả bằng chứng phần giống và mức rủi ro.
- [x] 5.5 Chặn nội dung vượt chính sách originality cấu hình.

## 6. Kiểm tra story, shot và prompt

- [x] 6.1 Kiểm tra story bám content spine, target audience, mục tiêu, hook, retention và payoff.
- [x] 6.2 Kiểm tra mỗi shot ánh xạ đúng target content beat và continuity.
- [x] 6.3 Kiểm tra prompt thể hiện đúng thông tin mới, cảm xúc, hành động, micro-payoff và narration liên quan.
- [x] 6.4 Kết hợp canon, kỹ thuật prompt và repair từ change 7.
- [x] 6.5 Ngăn repair kỹ thuật tự đổi hook, payoff hoặc narration đã duyệt.
- [x] 6.6 Hiển thị prompt đẹp hình thức nhưng thiếu nội dung như lỗi chất lượng.

## 7. Kiểm tra voice và subtitle

- [x] 7.1 Kiểm tra voice dùng đúng narration revision, người nói, ngôn ngữ, cảm xúc và duration.
- [x] 7.2 Kiểm tra tốc độ, khoảng ngắt, từ khóa, câu bị cắt và nguy cơ audio clutter.
- [x] 7.3 Kiểm tra subtitle khớp voice cuối và timing không trùng hoặc vượt duration.
- [x] 7.4 Kiểm tra độ dài dòng, tốc độ đọc, từ khóa và thời điểm xuất hiện câu đầu.
- [x] 7.5 Kiểm tra subtitle không tiết lộ payoff quá sớm.
- [x] 7.6 Kiểm tra vùng subtitle không che chủ thể khi có metadata bố cục.

## 8. Retention analytics thực tế

- [x] 8.1 Thêm dữ liệu retention nền tảng gồm điểm timeline và các chỉ số xem trung bình, hoàn tất, xem lại, CTA và chuyển đổi khi có.
- [x] 8.2 Hỗ trợ nhập CSV/JSON định dạng cho phép và nhập tay.
- [x] 8.3 Chuẩn hóa timestamp và phần trăm thời lượng.
- [x] 8.4 Căn mốc tụt, ổn định và xem lại với beat, shot, transcript, chữ và âm thanh.
- [x] 8.5 So sánh predicted retention với actual retention.
- [x] 8.6 Báo tương quan và không khẳng định quan hệ nhân quả.
- [x] 8.7 Không tự đăng nhập hoặc lấy dữ liệu từ tài khoản nền tảng.

## 9. Giao diện báo cáo tiếng Việt

- [x] 9.1 Hiển thị tổng quan Đạt, Cần xem lại hoặc Bị chặn.
- [x] 9.2 Hiển thị điểm nội dung và cách thể hiện tách biệt.
- [x] 9.3 Hiển thị timeline với hook, beat, micro-payoff, payoff, nguy cơ và dữ liệu retention thật nếu có.
- [x] 9.4 Hiển thị bằng chứng và confidence cho từng kết luận.
- [x] 9.5 Hiển thị hành động sửa theo ưu tiên và phạm vi artifact bị ảnh hưởng.
- [x] 9.6 Cho ghi đè có lý do nhưng không xóa lịch sử lỗi.
- [x] 9.7 Không bắt người dùng hiểu mã lỗi hoặc JSON kỹ thuật.

## 10. Kiểm thử end-to-end không gọi Veo

- [x] 10.1 Tạo video fixture có shot, transcript, âm thanh, hook, content beat và payoff đáp án chuẩn.
- [x] 10.2 Kiểm thử analysis package, handoff, Project Memory và target timeline.
- [x] 10.3 Kiểm thử ba candidate, critic và tổng hợp.
- [x] 10.4 Kiểm thử content stagnation và hook-payoff mismatch.
- [x] 10.5 Kiểm thử originality với bản gần nguồn và bản biến đổi đủ mạnh.
- [x] 10.6 Kiểm thử prompt đẹp hình thức nhưng không truyền nội dung bị đánh trượt.
- [x] 10.7 Kiểm thử tạo hoặc giả lập voice và sinh subtitle từ narration cuối.
- [x] 10.8 Xác nhận không tạo job Veo, không submit prompt, không tạo clip và không tiêu credit provider.
- [x] 10.9 Kiểm thử nhập retention analytics và căn timeline.
- [x] 10.10 Viết báo cáo dễ đọc cho người không viết mã.

## 11. Tài liệu và vận hành

- [x] 11.1 Viết tài liệu tiếng Việt về điểm nội dung 75/25 và lỗi chặn.
- [x] 11.2 Giải thích predicted retention khác actual retention.
- [x] 11.3 Viết hướng dẫn nhập số liệu nền tảng mà không cung cấp tài khoản đăng nhập.
- [x] 11.4 Viết hướng dẫn chạy kiểm thử toàn luồng không gọi Veo.
