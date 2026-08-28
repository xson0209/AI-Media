## 1. Mô hình dữ liệu và di chuyển

- [x] 1.1 Thêm bảng thẻ nhớ series với loại thẻ, nội dung có cấu trúc, nhãn, liên kết thực thể, mức quan trọng, hiệu lực theo tập, nguồn, phiên bản và trạng thái duyệt.
- [x] 1.2 Thêm bảng trạng thái hiện tại của series với trạng thái nhân vật, quan hệ, địa điểm, đạo cụ, mạch truyện mở và xung đột chưa giải quyết.
- [x] 1.3 Thêm bảng hoặc trường lưu dấu vết gói ngữ cảnh đã biên dịch, gồm loại nhiệm vụ, thẻ đã dùng, phiên bản và thống kê dung lượng.
- [x] 1.4 Viết migration tương thích với series cũ và không xóa các trường Series Bible hiện tại.
- [x] 1.5 Thêm mô hình yêu cầu và phản hồi API bằng tiếng Việt cho thẻ nhớ, trạng thái, đề xuất cập nhật và kết quả kiểm tra canon.

## 2. Quản lý thẻ nhớ

- [x] 2.1 Thêm API tạo, sửa, duyệt, từ chối, lưu trữ và liệt kê thẻ nhớ theo series.
- [x] 2.2 Thêm API lọc thẻ theo loại, nhân vật, địa điểm, mạch truyện, số tập, trạng thái và mức quan trọng.
- [x] 2.3 Thêm chức năng đề xuất thẻ nháp từ Series Bible và continuity cũ nhưng không tự duyệt.
- [x] 2.4 Dùng Hồ sơ nhân vật hiện có làm nguồn chuẩn và chuyển thành ngữ cảnh thống nhất mà không tạo bản nhân vật trùng lặp.
- [x] 2.5 Chặn việc một thẻ chưa duyệt trở thành canon bắt buộc trong các lần tạo nội dung sau.

## 3. Trạng thái hiện tại và tóm tắt phân tầng

- [x] 3.1 Tạo đề xuất trạng thái mới từ Master Story đã duyệt hoặc AI Video project đã duyệt.
- [x] 3.2 Thêm màn so sánh trạng thái cũ và trạng thái đề xuất trước khi người dùng duyệt.
- [x] 3.3 Lưu tóm tắt riêng từng tập, tóm tắt chặng và tóm tắt toàn series mà không ghi đè mất lịch sử chi tiết.
- [x] 3.4 Cập nhật danh sách mạch truyện mở, đã giải quyết và bị tạm dừng sau khi người dùng duyệt.
- [x] 3.5 Dựng lại các tệp Markdown bộ nhớ từ cơ sở dữ liệu và ghi rõ phiên bản định dạng.

## 4. Bộ chọn và biên dịch ngữ cảnh

- [x] 4.1 Xây dịch vụ biên dịch ngữ cảnh dùng chung cho Story Studio và AI Video.
- [x] 4.2 Hỗ trợ các loại nhiệm vụ story candidate, Master Story, panel ảnh, phát triển video, phân shot, prompt video, voice và subtitle.
- [x] 4.3 Chọn thẻ bằng liên kết thực thể, nhãn, mạch truyện, số tập, trạng thái hiệu lực và mức quan trọng.
- [x] 4.4 Thay việc cắt 24.000 ký tự đầu bằng phân bổ dung lượng theo nhóm, có chuyển phần dư và bảo vệ nhóm bắt buộc.
- [x] 4.5 Trả về danh sách thẻ đã chọn, lý do chọn, dữ liệu thiếu và nhóm bị rút gọn.
- [x] 4.6 Tích hợp gói ngữ cảnh mới vào Story Studio và các bước AI Video mà không làm thay đổi ngôn ngữ video đã chọn.
- [x] 4.7 Giữ chế độ tương thích để quay về Series Bible hiện tại khi bộ chọn mới bị tắt.

## 5. Kiểm tra mâu thuẫn canon

- [x] 5.1 Xây bộ kiểm tra prompt ảnh đối với nhân vật, địa điểm, đạo cụ, trạng thái, mạch truyện, phong cách và điều cấm.
- [x] 5.2 Xây bộ kiểm tra prompt video với trạng thái đầu/cuối segment và continuity giữa các segment.
- [x] 5.3 Phân loại lỗi chặn và cảnh báo; gắn bằng chứng tới thẻ hoặc Hồ sơ nhân vật liên quan.
- [x] 5.4 Chặn duyệt hoặc gửi render khi còn lỗi canon chặn.
- [x] 5.5 Cho phép ghi đè thủ công bằng lý do và lưu nhật ký người thực hiện, thời điểm và lỗi được ghi đè.

## 6. Giao diện tiếng Việt

- [x] 6.1 Thêm khu vực Bộ não Series gồm Thẻ nhớ, Trạng thái hiện tại, Mạch truyện và Lịch sử tập.
- [x] 6.2 Hiển thị thẻ nào được dùng cho tập, panel hoặc prompt hiện tại.
- [x] 6.3 Hiển thị dung lượng từng nhóm, phần bị rút gọn và dữ liệu bắt buộc còn thiếu.
- [x] 6.4 Hiển thị lỗi canon bằng ngôn ngữ dễ hiểu, kèm dữ liệu nguồn và hành động sửa hoặc ghi đè.
- [x] 6.5 Không yêu cầu người dùng chỉnh trực tiếp JSON hoặc tệp Markdown.

## 7. Kiểm thử và tài liệu

- [x] 7.1 Kiểm thử migration và tương thích với series cũ chưa có thẻ nhớ.
- [x] 7.2 Kiểm thử phân bổ dung lượng để dữ liệu cuối file không bị mất chỉ vì vượt 24.000 ký tự.
- [x] 7.3 Kiểm thử chọn đúng nhân vật, địa điểm, đạo cụ và mạch truyện theo từng nhiệm vụ.
- [x] 7.4 Kiểm thử trạng thái chỉ đổi sau khi người dùng duyệt.
- [x] 7.5 Kiểm thử lỗi canon chặn prompt sai fixed trait, sai đạo cụ, sai bí mật hoặc sai trạng thái.
- [x] 7.6 Kiểm thử voice và subtitle không nhận dữ liệu hình ảnh không cần thiết.
- [x] 7.7 Cập nhật tài liệu tiếng Việt về cách Bộ não Series lưu đầy đủ lịch sử nhưng chỉ chọn ký ức liên quan cho mỗi lần tạo.
