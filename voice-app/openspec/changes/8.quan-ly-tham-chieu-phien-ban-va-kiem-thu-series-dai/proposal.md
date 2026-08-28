## Bối cảnh

Sau change 6 và 7, series có bộ nhớ có cấu trúc, trạng thái hiện tại, chọn ngữ cảnh theo nhiệm vụ, ba candidate AI thật và vòng kiểm tra, tự sửa prompt. Tuy nhiên tính nhất quán hình ảnh vẫn phụ thuộc chủ yếu vào mô tả văn bản. Hệ thống chưa có ảnh tham chiếu chuẩn cho nhân vật và địa điểm, chưa theo dõi phiên bản từng dữ liệu canon theo cách có thể xác định artifact nào thực sự bị ảnh hưởng, và chưa có bộ kiểm thử series dài để phát hiện việc quên sự kiện hoặc đánh dấu stale quá rộng.

Change này hoàn thiện khả năng vận hành lâu dài: quản lý ảnh tham chiếu đã duyệt, phiên bản dữ liệu, quan hệ phụ thuộc và bộ bài kiểm tra nhiều tập mà không gọi Veo.

## Mục tiêu

- Thêm ảnh tham chiếu cố định cho nhân vật và địa điểm, có vai trò ảnh, nguồn, trạng thái duyệt và metadata an toàn.
- Cho phép nhiều ảnh tham chiếu có mục đích rõ như chính diện, góc nghiêng, toàn thân, trang phục, toàn cảnh địa điểm và chi tiết nhận diện.
- Theo dõi phiên bản của Hồ sơ nhân vật, thẻ nhớ, trạng thái, Master Story, style, ảnh tham chiếu, panel, shot và prompt.
- Lưu dấu phụ thuộc của mỗi artifact vào đúng phiên bản dữ liệu đã dùng.
- Chỉ đánh dấu stale panel, shot, prompt, voice, subtitle, package hoặc render thực sự bị ảnh hưởng.
- Hiển thị cho người dùng lý do artifact bị stale và dữ liệu nguồn nào đã thay đổi.
- Xây bộ bài kiểm tra series dài gồm nhiều tập, mạch truyện, nhân vật, địa điểm và thay đổi canon.
- Chạy kiểm thử toàn bộ tới prompt, voice và subtitle bằng dữ liệu giả lập, không gọi Veo và không tạo clip provider thật.

## Ngoài phạm vi

- Không tự động huấn luyện model nhân vật hoặc model phong cách riêng.
- Không bắt buộc provider ảnh hoặc video nào phải hỗ trợ cùng một định dạng ảnh tham chiếu.
- Không tự động chọn ảnh chưa duyệt làm tham chiếu chuẩn.
- Không gọi Veo, không tạo clip thật và không đánh giá chất lượng hình ảnh bằng clip provider trong bộ kiểm thử này.
- Không xây hệ thống lưu trữ đám mây mới; tiếp tục dùng lớp lưu trữ artifact hiện có.

## Khả năng mới

- `tham-chieu-phien-ban-va-kiem-thu-series-dai`: quản lý ảnh tham chiếu canon, phiên bản dữ liệu, quan hệ phụ thuộc, stale có mục tiêu và bộ kiểm thử series dài không gọi provider video.

## Phụ thuộc

- Phụ thuộc vào change `6.toi-uu-bo-nao-series-va-truy-xuat-ky-uc` để dùng thẻ nhớ, trạng thái và ảnh chụp ngữ cảnh.
- Phụ thuộc vào change `7.nang-cap-sang-tao-kich-ban-va-tu-sua-prompt` để kiểm thử candidate, đánh giá, tổng hợp và tự sửa prompt.
- Dùng artifact, prompt, voice, subtitle và package hiện có của AI Video.

## Kết quả mong muốn

Người dùng có thể gắn ảnh chuẩn cho nhân vật và địa điểm, biết prompt nào đã dùng ảnh và phiên bản canon nào. Khi sửa một chi tiết, hệ thống chỉ yêu cầu tạo lại những đầu ra bị ảnh hưởng. Một bộ kiểm thử nhiều tập chứng minh series vẫn nhớ đúng nhân vật, mạch truyện và trạng thái mà không phải gọi Veo.

## Tên change

`8.quan-ly-tham-chieu-phien-ban-va-kiem-thu-series-dai`
