## 1. Suy ra hãng của clip khi làm sạch dấu AI

- [x] 1.1 Thêm bảng suy ra hãng theo thứ tự ưu tiên: hãng ghi trong dữ liệu clip trước, rồi hãng đã ghi trong báo cáo cache của lần làm sạch trước, cuối cùng mới dò tự động
- [x] 1.2 Nối bảng suy ra này vào chỗ gọi worker làm sạch, thay cho cách chỉ đọc hãng từ dữ liệu clip
- [x] 1.3 Giữ nhánh dò tự động nguyên vẹn cho clip không có nguồn thông tin nào
- [x] 1.4 Thêm test cho từng nhánh của bảng suy ra, gồm nhánh đọc từ báo cáo cache cũ ← (verify: clip có hãng thì chỉ dò một hãng; clip không rõ hãng vẫn dò tự động và không đổi kết quả so với trước)

## 2. Mặc định backend làm sạch nhanh

- [x] 2.1 Đổi mặc định backend làm sạch dấu AI sang lựa chọn nhanh ở tầng cấu hình backend
- [x] 2.2 Đồng bộ mặc định phía giao diện với mặc định backend
- [x] 2.3 Viết lại nhãn tiếng Việt cho hai lựa chọn backend, nói rõ lựa chọn nào nhanh và chất lượng tương đương, lựa chọn nào chậm hơn nhiều
- [x] 2.4 Thêm test xác nhận mặc định mới và xác nhận lựa chọn cũ vẫn dùng được ← (verify: project mới mặc định dùng backend nhanh; người dùng vẫn chọn được backend cũ; cache của backend cũ không bị mất hiệu lực)

## 3. Hạ tầng chạy song song theo từng clip

- [x] 3.1 Thêm hàm tính số luồng song song từ số nhân CPU với giới hạn trên và giá trị tối thiểu là một
- [x] 3.2 Cho phép ghi đè số luồng bằng biến môi trường, với giá trị không hợp lệ thì quay về giá trị tính từ CPU
- [x] 3.3 Thêm nhánh chạy tuần tự khi số luồng bằng một, dùng chung đường code với nhánh song song
- [x] 3.4 Thêm test cho hàm tính số luồng, gồm ca biến môi trường hợp lệ, không hợp lệ, và ca máy một nhân ← (verify: mặc định không vượt giới hạn trên; số luồng luôn tối thiểu là một; biến môi trường sai không làm đổ job)

## 4. Song song hoá vòng lặp làm sạch và chuẩn hoá clip

- [x] 4.1 Tách thân vòng lặp theo từng clip thành một hàm thuần nhận chỉ số và mục timeline, trả về kết quả cho clip đó, không chạm cơ sở dữ liệu và không cập nhật tiến độ
- [x] 4.2 Chạy hàm đó qua nhóm luồng, thu kết quả về theo đúng chỉ số timeline
- [x] 4.3 Ghép danh sách clip đã xử lý theo thứ tự chỉ số, không theo thứ tự hoàn thành
- [x] 4.4 Tổng hợp số lần dùng lại cache ở luồng chính sau khi tất cả clip đã xong, không cộng dồn từ nhiều luồng
- [x] 4.5 Gom cảnh báo và ghi chú làm sạch dấu AI theo thứ tự chỉ số để nội dung manifest không đổi thứ tự giữa các lần chạy
- [x] 4.6 Thêm test xác nhận thứ tự clip sau khi ghép đúng thứ tự timeline khi các clip hoàn thành lệch thứ tự ← (verify: MP4 ra có thứ tự cảnh đúng; manifest có nội dung ổn định giữa các lần chạy; số liệu cache khớp số clip)

## 5. Dừng sớm và xử lý lỗi khi chạy song song

- [x] 5.1 Thu lỗi của từng clip kèm chỉ số clip thay vì để lỗi thoát ra từ giữa nhóm luồng
- [x] 5.2 Khi có clip lỗi, không gửi thêm clip mới vào nhóm luồng và chờ các clip đang chạy kết thúc
- [x] 5.3 Báo lỗi theo clip có chỉ số nhỏ nhất, giữ nguyên mã lỗi và thông điệp tiếng Việt như luồng tuần tự
- [x] 5.4 Thêm test cho ca một clip lỗi và ca nhiều clip lỗi cùng lúc ← (verify: lỗi cho cùng mã và cùng thông điệp như trước khi song song hoá; không còn tiến trình con nào sót lại sau khi job đổ)

## 6. Báo tiến độ theo bước thực tế

- [x] 6.1 Cho hàm xử lý từng clip báo về luồng chính khi một clip hoàn thành, qua một hàng đợi an toàn nhiều luồng
- [x] 6.2 Cập nhật tiến độ ở luồng chính theo số clip đã xong trên tổng số clip, với nhãn nói rõ đang làm sạch dấu AI
- [x] 6.3 Đổi nhãn giai đoạn theo từng clip để không còn chỉ nêu bước chuẩn hoá khi làm sạch dấu AI đang bật
- [x] 6.4 Thêm mốc tiến độ cho bước ghép và xuất file cuối, và mốc riêng cho bước nhúng phụ đề khi bật
- [x] 6.5 Thêm test xác nhận tiến độ tăng đơn điệu và có ít nhất một mốc trong khoảng từ ghép voice tới hoàn tất ← (verify: thanh tiến độ không đứng im quá một clip; nhãn khớp bước đang chạy thật; tiến độ không giảm và không vượt một)

## 7. Ghi lại kết luận về NVENC

- [x] 7.1 Thêm ghi chú tại chỗ dựng câu lệnh chuẩn hoá clip, nêu rõ đã đo NVENC chậm hơn trên máy mục tiêu kèm hai số đo
- [x] 7.2 Nêu rõ điều kiện khiến kết luận này có thể đổi, là clip dài hơn nhiều hoặc độ phân giải cao hơn nhiều ← (verify: người đọc code sau này không thử lại NVENC mà không đo trước)

## 8. Kiểm thử và xác minh

- [ ] 8.1 Chạy toàn bộ test render hiện có, xác nhận không hồi quy
- [x] 8.2 Chạy build và kiểm tra kiểu dữ liệu frontend
- [ ] 8.3 Dựng thử MP4 thật với làm sạch dấu AI bật, xoá cache trước khi chạy, đo tổng thời gian và so với số đo trong design ← (verify: tổng thời gian giảm rõ rệt so với 72 phút; thứ tự cảnh đúng; không có clip nào bị thiếu)
- [ ] 8.4 So chất lượng ảnh giữa hai backend trên ít nhất năm clip có nền khác nhau, không chỉ một clip ← (verify: chênh lệch chất lượng vẫn ở mức không phân biệt được trên mọi clip đã thử; nếu có clip kém rõ rệt thì ghi lại và xem lại quyết định mặc định)
- [ ] 8.5 Đo mức chiếm dụng CPU trong lúc chạy song song, xác nhận máy vẫn dùng được việc khác ← (verify: số luồng mặc định không làm máy đứng; nếu có thì hạ giới hạn trên và ghi lại số đo)
- [x] 8.6 Điều tra riêng lỗi worker làm sạch trả về nội dung không đọc được, đã gặp ở job ngày 23-08 sau khoảng 45 phút chạy ← (verify: xác định được nguyên nhân, hoặc ghi lại thành change riêng nếu vượt phạm vi change này)
