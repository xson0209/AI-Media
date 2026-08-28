## 1. Sửa mức âm lượng khi trộn

- [x] 1.1 Tắt normalize ở bước trộn SFX/BGM để giọng đọc không bị chia theo số input
- [x] 1.2 Thêm assertion mới cho mức âm lượng khi trộn, giữ nguyên assertion chuỗi trộn hiện có
- [x] 1.3 Chạy test trộn SFX/BGM để tách biệt tác động của thay đổi này ← (verify: giọng đọc giữ mức khi trộn 1 và nhiều asset; mức từng asset vẫn theo cấu hình; test cũ về chuỗi trộn không bị sửa)

## 2. Bảng quyết định nguồn tiếng nền

- [x] 2.1 Thêm hàm quyết định có thêm tiếng nền cho một phân đoạn, dựa trên speech source của project và việc phân đoạn có narration
- [x] 2.2 Thêm nhánh không thêm nền khi giọng đọc đã được trích từ chính clip đó
- [x] 2.3 Thêm nhánh nền đầy đủ cho phân đoạn không có narration
- [x] 2.4 Thêm nhánh nền đã hạ mức cho phân đoạn có giọng đọc tổng hợp
- [x] 2.5 Thêm nhánh im lặng khi clip không có audio ← (verify: đủ 5 nhánh theo bảng quyết định trong design; project tiếng Việt có narration tuyệt đối không được thêm nền)

## 3. Dựng timeline tiếng nền

- [x] 3.1 Thêm builder đoạn tiếng nền rút audio từ clip gốc, không dùng bản đã làm sạch watermark
- [x] 3.2 Kéo dài đoạn nền bằng khoảng lặng khi audio clip ngắn hơn phân đoạn
- [x] 3.3 Cắt đoạn nền khi audio clip dài hơn phân đoạn
- [x] 3.4 Dùng nguồn im lặng khi clip không có audio hoặc thiếu file
- [x] 3.5 Bỏ qua sinh câu lệnh khi thời lượng phân đoạn không hợp lệ
- [x] 3.6 Ghép các đoạn nền thành một timeline khớp tổng thời lượng timeline giọng đọc ← (verify: tổng thời lượng nền khớp timeline; đoạn nền lấy từ clip gốc; clip gốc không bị ghi đè)

## 4. Hạ mức và trộn tiếng nền

- [x] 4.1 Thêm builder câu lệnh hạ mức nền theo tín hiệu giọng đọc bằng nén sidechain
- [x] 4.2 Trộn nền với giọng đọc một lần trên toàn timeline, không trộn theo từng phân đoạn
- [x] 4.3 Tắt normalize ở bước trộn nền để giọng đọc giữ nguyên mức
- [x] 4.4 Bỏ hẳn bước trộn khi timeline nền toàn im lặng ← (verify: hạ mức áp dụng một lần cho cả timeline; nền hạ khi có giọng và phục hồi khi hết giọng; timeline nền toàn im lặng thì dùng trực tiếp timeline giọng đọc)

## 5. Nối cấu hình vào luồng render

- [x] 5.1 Thêm bảng ánh xạ từ cấu hình tiếng gốc sang khái niệm nguồn audio nội bộ ba mức, hiện dùng hai mức
- [x] 5.2 Nối bước dựng và trộn tiếng nền vào luồng render sau bước ghép audio
- [x] 5.3 Tính tổng thời lượng từ timeline, không đọc từ enhanced render plan
- [x] 5.4 Cho tiếng nền chạy độc lập với enhanced render và trộn SFX/BGM
- [x] 5.5 Giữ mặc định là bỏ tiếng gốc để project cũ không đổi hành vi ← (verify: bật tiếng gốc có tác dụng thật lên MP4; enhanced render tắt vẫn dựng được nền; mặc định cho kết quả giống trước change)

## 6. Xử lý lỗi và fallback

- [x] 6.1 Fallback về timeline giọng đọc khi dựng tiếng nền thất bại
- [x] 6.2 Fallback về timeline giọng đọc khi trộn tiếng nền thất bại
- [x] 6.3 Thêm đường ghi lý do fallback không phụ thuộc enhanced render plan ← (verify: lỗi nền không làm job render thất bại; lý do fallback được ghi lại cả khi enhanced render tắt)

## 7. Giao diện

- [x] 7.1 Thêm công tắc tiếng gốc vào bảng dựng nhanh MP4 với nhãn tiếng Việt
- [x] 7.2 Đồng bộ giá trị mặc định của công tắc với mặc định phía backend ← (verify: công tắc đổi kết quả MP4 thật; client không gửi cấu hình tiếng gốc vẫn chạy bình thường)

## 8. Kiểm thử và xác minh

- [x] 8.1 Thêm test cho từng nhánh trong bảng quyết định nguồn tiếng nền
- [x] 8.2 Thêm test cho builder đoạn tiếng nền, gồm ca kéo dài và ca cắt bớt
- [x] 8.3 Thêm test cho builder hạ mức và trộn nền
- [x] 8.4 Thêm test cho ca timeline nền toàn im lặng bỏ hẳn bước trộn
- [x] 8.5 Thêm test cho fallback khi dựng hoặc trộn nền thất bại
- [x] 8.6 Thêm test xác nhận tiếng nền lấy từ clip gốc khi làm sạch watermark đang bật
- [x] 8.7 Chạy toàn bộ test render và audio hiện có, xác nhận không hồi quy
- [x] 8.8 Chạy build và kiểm tra kiểu dữ liệu frontend
- [ ] 8.9 Dựng thử MP4 trên project tiếng Việt xác nhận không vọng tiếng, và trên project dùng giọng đọc tổng hợp xác nhận nền hạ đúng ← (verify: test cũ xanh, test mới phủ đủ 5 nhánh và các ca biên, bản dựng thật không có hiện tượng vọng tiếng hay giọng méo)
  - CHƯA XÁC MINH ĐƯỢC: môi trường chỉ có 1 project thật (target_language=`en`, 18 clip đều có audio, nhưng 0 shot có narration và 0 shot có giọng đọc hoàn tất) và không có project tiếng Việt nào. Không đủ dữ liệu để dựng MP4 thật cho nhánh (a) VI-có-thoại và nhánh (c) TTS-ducked.
  - ĐÃ xác minh ở mức FFmpeg thật trên clip thật của project đó: rút audio từ clip gốc, ca pad (clip 8s → phân đoạn 12s), ca trim, ghép timeline nền đúng tổng thời lượng, và duck+mix. Đo được: nền -32,3 dB khi không có giọng → -41,4 dB khi có giọng (hạ ~9,1 dB) → -33,9 dB sau khi giọng dứt; giọng giữ nguyên -18,0 dB; thời lượng ra đúng 12,00s. Nhánh guard sinh đoạn im lặng -91,0 dB.
  - Cần người dùng nghe thử trên project VI và project TTS thật trước khi chốt tham số.
