## 1. Ảnh tham chiếu nhân vật và địa điểm

- [x] 1.1 Thêm bảng ảnh tham chiếu với thực thể, vai trò, đường dẫn, metadata ảnh, checksum, nguồn, phiên bản, trạng thái duyệt và trạng thái hoạt động.
- [x] 1.2 Thêm API tải lên, liệt kê, duyệt, từ chối, kích hoạt, vô hiệu hóa và xóa an toàn ảnh tham chiếu.
- [x] 1.3 Hỗ trợ nhiều vai trò ảnh cho khuôn mặt, toàn thân, trang phục, biểu cảm, toàn cảnh địa điểm, nội thất, chi tiết và ánh sáng.
- [x] 1.4 Tạo thumbnail hoặc bản xem trước mà không thay đổi tệp gốc.
- [x] 1.5 Kiểm tra loại tệp, dung lượng, kích thước, tên tệp và đường dẫn lưu trữ.
- [x] 1.6 Chỉ đưa ảnh đã duyệt và đang hoạt động vào gói prompt.
- [x] 1.7 Cho adapter provider báo rõ ảnh đã được gửi, bị bỏ qua hay fallback sang mô tả văn bản.

## 2. Phiên bản dữ liệu

- [x] 2.1 Thêm revision cho Hồ sơ nhân vật, thẻ nhớ, trạng thái, ảnh tham chiếu, Series Bible/style và Master Story.
- [x] 2.2 Giữ phiên bản cũ có thể truy xuất và không sửa ngược lịch sử artifact đã tạo.
- [x] 2.3 Thêm API xem lịch sử phiên bản và so sánh thay đổi bằng tiếng Việt.
- [x] 2.4 Ngăn xóa phiên bản đang được artifact hoặc dependency snapshot tham chiếu.
- [x] 2.5 Ghi người thực hiện, nguồn thay đổi, thời điểm và lý do cho thay đổi đã duyệt.

## 3. Quan hệ phụ thuộc và stale có mục tiêu

- [x] 3.1 Thêm cấu trúc lưu dependency của panel, shot, prompt, voice, subtitle, package và render vào đúng revision nguồn.
- [x] 3.2 Ghi dependency snapshot khi tạo hoặc sửa mỗi artifact.
- [x] 3.3 Xây quy tắc lan truyền stale theo phạm vi visual identity, story state, dialogue, language, camera style và reference image.
- [x] 3.4 Chỉ stale panel và prompt chứa nhân vật hoặc địa điểm bị thay đổi.
- [x] 3.5 Chỉ stale voice và subtitle khi narration, người nói, voice profile, timing hoặc ngôn ngữ liên quan thay đổi.
- [x] 3.6 Lưu sự kiện stale với nguồn thay đổi, revision cũ/mới, artifact bị ảnh hưởng và lý do.
- [x] 3.7 Cho phép tạo lại đúng artifact hoặc nhóm artifact bị ảnh hưởng mà không bắt buộc tạo lại toàn project.

## 4. Giao diện tiếng Việt

- [x] 4.1 Thêm thư viện ảnh tham chiếu trong Hồ sơ nhân vật và khu vực địa điểm.
- [x] 4.2 Hiển thị vai trò ảnh, trạng thái duyệt, phiên bản và nơi đang được sử dụng.
- [x] 4.3 Hiển thị lịch sử phiên bản và thay đổi giữa hai phiên bản.
- [x] 4.4 Hiển thị danh sách artifact stale, lý do và dữ liệu nguồn đã thay đổi.
- [x] 4.5 Thêm hành động tạo lại đúng phạm vi và cảnh báo khi người dùng cố dùng artifact stale.

## 5. Bộ dữ liệu kiểm thử series dài

- [x] 5.1 Tạo bộ dữ liệu chuẩn tối thiểu 30 tập với nhiều nhân vật, địa điểm, đạo cụ, quan hệ và mạch truyện.
- [x] 5.2 Thêm bộ 100 tập tùy chọn để kiểm thử dung lượng và tìm lại sự kiện rất cũ.
- [x] 5.3 Gắn đáp án chuẩn về thẻ bắt buộc, thẻ gây nhiễu, trạng thái, bí mật, canon và dependency mong đợi.
- [x] 5.4 Tạo các trường hợp thay đổi tóc, trang phục, địa điểm, style, narration, ngôn ngữ và nhân vật không liên quan.
- [x] 5.5 Tạo dữ liệu voice và timing giả lập để sinh subtitle mà không cần tạo clip.

## 6. Kiểm thử hồi quy không gọi Veo

- [x] 6.1 Kiểm thử chọn ký ức đúng cho tập gần và sự kiện từ tập rất cũ.
- [x] 6.2 Kiểm thử trạng thái chưa duyệt không ảnh hưởng lần tạo tiếp theo.
- [x] 6.3 Kiểm thử ba candidate, đánh giá, tổng hợp và tự sửa prompt bằng phản hồi AI cố định.
- [x] 6.4 Kiểm thử ảnh tham chiếu đúng nhân vật và địa điểm được gắn vào gói prompt.
- [x] 6.5 Kiểm thử thay đổi một nhân vật chỉ stale artifact có nhân vật đó.
- [x] 6.6 Kiểm thử đổi style stale prompt hình ảnh/video nhưng không stale voice không liên quan.
- [x] 6.7 Kiểm thử đổi narration stale voice, subtitle và package liên quan.
- [x] 6.8 Kiểm thử pipeline tới voice và subtitle nhưng xác nhận không tạo clip, không tạo job Veo và không tiêu credit provider.
- [x] 6.9 Báo chỉ số lấy đúng ký ức, lỗi canon, độ khác biệt candidate, sửa prompt, stale đúng và stale thừa.
- [x] 6.10 Tách bộ 30 tập chạy thường xuyên và bộ 100 tập chạy theo lịch hoặc khi phát hành.

## 7. Tài liệu và vận hành

- [x] 7.1 Viết tài liệu tiếng Việt về cách chọn và duyệt ảnh tham chiếu.
- [x] 7.2 Viết tài liệu về phiên bản, dependency và lý do artifact bị stale.
- [x] 7.3 Viết hướng dẫn chạy bộ kiểm thử 30 tập và 100 tập mà không cấu hình Veo.
- [x] 7.4 Thêm báo cáo kiểm thử dễ đọc cho người không viết mã, gồm lỗi, ảnh hưởng và bước xử lý tiếp theo.
