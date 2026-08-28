## Bối cảnh

Story Studio hiện lưu đúng ba hướng kịch bản nhưng phần triển khai đang dùng nội dung mẫu và điểm số cố định theo loại chiến lược. Điều này đáp ứng hình dạng workflow nhưng chưa tạo ra ba phương án sáng tạo thật sự, chưa có phản biện độc lập và chưa tổng hợp có dẫn chứng.

AI Video đã có schema prompt chi tiết và kiểm tra các trường bắt buộc, nhưng kiểm tra hiện thiên về đủ trường hơn là chất lượng nội dung. Một prompt có thể đầy đủ mà vẫn khó render, quá nhiều hành động, nối cảnh kém hoặc vi phạm canon. Change 6 cung cấp gói ngữ cảnh chọn lọc và bộ kiểm tra canon; change này dùng nền đó để nâng chất lượng sáng tạo và tự sửa có giới hạn.

## Mục tiêu

- Thay ba candidate mẫu bằng đúng ba candidate do AI tạo thật, khác nhau rõ về chiến lược nhưng dùng cùng một gói ngữ cảnh đã đóng băng.
- Tạo từng candidate bằng yêu cầu độc lập để giảm việc ba phương án chỉ đổi câu chữ.
- Cho một bước đánh giá độc lập chấm từng candidate theo tiêu chí phù hợp với mục tiêu đầu ra và giải thích bằng tiếng Việt.
- Cho phép tổng hợp phần tốt nhất của nhiều candidate thành Master Story thống nhất, không ghép cơ học và không phá canon.
- Mở rộng kiểm tra prompt từ đủ trường sang chất lượng ngữ nghĩa, khả năng render, continuity, thời lượng, camera, chuyển cảnh, âm thanh và vùng phụ đề.
- Tự sửa prompt khi chưa đạt ngưỡng, chỉ sửa lỗi được chỉ ra, giữ phiên bản và dừng sau số lần giới hạn.
- Hiển thị rõ điểm, lý do, phần đã sửa và phần còn cần người dùng quyết định.

## Ngoài phạm vi

- Không thay đổi cách tạo clip bằng Veo hoặc provider video khác.
- Không tự động render video để đánh giá chất lượng prompt.
- Không thêm ảnh tham chiếu cố định hoặc dependency graph; việc này thuộc change 8.
- Không để AI tự duyệt Master Story, prompt ảnh hoặc prompt video thay người dùng.
- Không cho vòng tự sửa chạy vô hạn.

## Khả năng mới

- `sang-tao-kich-ban-va-tu-sua-prompt`: tạo ba candidate AI độc lập, đánh giá có lý do, tổng hợp Master Story và tự sửa prompt theo bộ tiêu chí chất lượng.

## Phụ thuộc

- Phụ thuộc trực tiếp vào change `6.toi-uu-bo-nao-series-va-truy-xuat-ky-uc` để dùng gói ngữ cảnh có dấu vết và kiểm tra canon.
- Dùng các workflow Story Studio và AI Video từ change 4 cùng các capability prompt video hiện có.

## Kết quả mong muốn

Người dùng nhận ba hướng kịch bản thực sự khác nhau, thấy điểm và lý do cho từng hướng, có thể chọn một bản hoặc tổng hợp phần tốt nhất. Prompt ảnh và video được chấm theo chất lượng thực tế; prompt chưa đạt được sửa có kiểm soát và vẫn phải qua người dùng duyệt trước khi render.

## Tên change

`7.nang-cap-sang-tao-kich-ban-va-tu-sua-prompt`
