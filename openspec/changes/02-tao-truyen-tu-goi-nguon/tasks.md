# Công việc

## 1. OpenSpec

- [x] Tạo proposal tiếng Việt cho change `02-tao-truyen-tu-goi-nguon`.
- [x] Tạo design tiếng Việt.
- [x] Tạo tasks tiếng Việt.
- [x] Tạo spec delta tiếng Việt.
- [x] Validate OpenSpec change.

## 2. Backend refactor

- [x] Dùng Gói nguồn chuẩn trong Story Studio khi compile nguồn cho candidate.
- [x] Đưa structured source của candidate sang shape rõ ràng hơn, bám vào Gói nguồn.
- [x] Tách rõ UI tiếng Việt và ngôn ngữ nội dung trong prompt/code liên quan.
- [x] Mở lựa chọn `target_language` cho truyện/video và Video Inspiration, không khóa cứng `vi/en`.
- [x] Giữ 3 candidate, select master và synthesize master như cũ.
- [x] Giữ API và DB schema không đổi.

## 3. Kiểm thử

- [x] Test Story Studio candidate payload có Gói nguồn và fingerprint.
- [x] Test candidate generation vẫn tạo đúng 3 candidate.
- [x] Test chọn/synthesize master vẫn không đổi hành vi.
- [x] Test ngôn ngữ nội dung khác `vi/en` được giữ nguyên, trong khi UI/review field vẫn dùng tiếng Việt.
- [x] Chạy targeted tests.
- [x] Fix lỗi nếu có.
- [x] Test lại sau khi fix.

## 4. Hoàn tất lát 02

- [x] Cập nhật tasks sau khi code/test xong.
- [x] Báo rõ phần đã làm, test đã chạy, phần còn lại của refactor tổng.
