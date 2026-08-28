## Bối cảnh

Change 4 đã tạo nền tảng series dùng chung cho Story Studio và AI Video, gồm Series Bible, Hồ sơ nhân vật có cấu trúc, Master Story đã duyệt và `series-memory.md`. Tuy nhiên bộ nhớ hiện vẫn được dựng thành một văn bản dài rồi lấy tối đa 24.000 ký tự đầu để đưa vào AI. Khi series dài, thông tin mới nhất hoặc thông tin liên quan trực tiếp tới tập đang làm có thể nằm ngoài phần được đọc, trong khi dữ liệu không liên quan vẫn chiếm chỗ.

Các trường `world_bible`, `continuity_rules`, `negative_rules` và tóm tắt tập trước chủ yếu là văn bản tự do. Hệ thống chưa có cấu trúc thống nhất cho địa điểm, đạo cụ, quan hệ, mạch truyện đang mở, trạng thái hiện tại và nguồn gốc của từng ký ức. Vì vậy AI có thể bỏ sót canon, dùng sai trạng thái nhân vật hoặc tạo prompt mâu thuẫn với các tập trước.

## Mục tiêu

- Tạo các thẻ nhớ có cấu trúc cho danh tính series, nhân vật, quan hệ, địa điểm, đạo cụ, mạch truyện, quy tắc canon, phong cách hình ảnh, tóm tắt tập và tóm tắt chặng.
- Giữ cơ sở dữ liệu là nguồn chuẩn; các tệp Markdown chỉ là bản dựng để người dùng đọc, xuất hoặc chẩn đoán.
- Thêm trạng thái hiện tại của series sau tập đã duyệt, gồm trạng thái nhân vật, quan hệ, địa điểm, đạo cụ và mạch truyện đang mở.
- Thay cách cắt 24.000 ký tự theo vị trí bằng bộ phân bổ dung lượng theo nhóm dữ liệu và mức quan trọng.
- Chọn đúng thẻ nhớ cho từng nhiệm vụ: phát triển truyện, tạo panel ảnh, phân shot, tạo prompt video, tạo giọng đọc và phụ đề.
- Lưu dấu vết thẻ nhớ nào đã được dùng để có thể giải thích và chẩn đoán kết quả AI.
- Kiểm tra mâu thuẫn canon sau khi tạo prompt ảnh hoặc prompt video, trả về lỗi chặn, cảnh báo và bằng chứng liên quan.
- Chỉ cập nhật canon hoặc trạng thái series sau khi người dùng duyệt đề xuất.

## Ngoài phạm vi

- Chưa thay ba candidate mẫu bằng ba candidate AI thật; việc này thuộc change 7.
- Chưa thêm vòng AI chấm điểm, tổng hợp candidate hoặc tự sửa prompt; việc này thuộc change 7.
- Chưa thêm ảnh tham chiếu cố định, đồ thị phiên bản hoặc đánh dấu stale theo ảnh hưởng; việc này thuộc change 8.
- Chưa dùng cơ sở dữ liệu tìm kiếm theo vector. Giai đoạn này ưu tiên chọn thẻ bằng quan hệ, nhãn, tập, nhân vật, địa điểm và mạch truyện có cấu trúc.
- Không gọi Veo hoặc provider tạo video thật.

## Khả năng mới

- `bo-nao-series-va-truy-xuat-ky-uc`: quản lý thẻ nhớ có cấu trúc, trạng thái hiện tại, biên dịch ngữ cảnh theo nhiệm vụ và kiểm tra mâu thuẫn canon.

## Phụ thuộc

- Phụ thuộc vào change `4.tao-truyen-anh-va-video-truyen-theo-series` và các mô hình Series, Hồ sơ nhân vật, Story Episode, Master Story, Image Story Adaptation và AI Video Project hiện có.
- Là nền tảng bắt buộc cho change 7 và change 8.

## Kết quả mong muốn

Khi người dùng tạo một tập mới, hệ thống vẫn lưu đầy đủ lịch sử toàn series nhưng chỉ đưa vào AI những dữ liệu liên quan và bắt buộc. Người dùng có thể xem AI đã dùng nhân vật, địa điểm, mạch truyện và tập cũ nào. Prompt vi phạm đặc điểm cố định, trạng thái hiện tại hoặc quy tắc canon bị chặn hoặc cảnh báo trước khi duyệt và trước khi gửi sang renderer.

## Tên change

`6.toi-uu-bo-nao-series-va-truy-xuat-ky-uc`
