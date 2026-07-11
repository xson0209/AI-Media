## 1. Backend cắt đoạn audio

- [x] 1.1 Thêm constant dùng chung cho giới hạn sample tham chiếu 30 giây trong `backend/utils/audio.py`.
- [x] 1.2 Thêm helper load/cắt audio theo `offset` và `duration`, dùng `librosa.load(..., offset=..., duration=...)` và trả về audio mono ở sample rate chuẩn.
- [x] 1.3 Cập nhật `validate_and_load_reference_audio` để nhận optional `trim_start_seconds` và `trim_duration_seconds`, cắt đoạn trước khi preprocess/validate.
- [x] 1.4 Validate tham số trim: start không âm, duration dương, duration không vượt 30 giây, đoạn cắt đọc được và không rỗng.
- [x] 1.5 Cập nhật comment/test liên quan tới giới hạn 30 giây để phản ánh đây là giới hạn sample sau khi cắt.

## 2. API upload sample và transcribe

- [x] 2.1 Mở rộng `POST /profiles/{profile_id}/samples` nhận optional form fields `trim_start_seconds` và `trim_duration_seconds`.
- [x] 2.2 Truyền trim params từ route upload sample xuống `profiles.add_profile_sample` và validator backend.
- [x] 2.3 Mở rộng `POST /transcribe` nhận optional trim params và chỉ transcribe đoạn đã chọn khi params được gửi.
- [x] 2.4 Đảm bảo request không có trim params vẫn giữ hành vi hiện tại cho file ngắn/recording.
- [x] 2.5 Chuẩn hóa lỗi 400 cho trim không hợp lệ để frontend hiển thị đúng nguyên nhân.

## 3. Frontend state và API client

- [x] 3.1 Thêm kiểu/state mô tả đoạn audio đã chọn: file, tổng duration, start, duration, trạng thái cần chọn/xác nhận.
- [x] 3.2 Cập nhật API client `addProfileSample` để gửi trim params khi có đoạn đã chọn.
- [x] 3.3 Cập nhật API client `transcribeAudio` và `useTranscription` để gửi trim params khi chép lời đoạn đã chọn.
- [x] 3.4 Điều chỉnh validation frontend: file dài hơn 30 giây mở luồng chọn đoạn thay vì set lỗi `sampleFile` ngay.
- [x] 3.5 Giữ validation submit: file dài chỉ được submit khi đã xác nhận đoạn hợp lệ.

## 4. UI chọn đoạn 30 giây

- [x] 4.1 Tạo component chọn đoạn audio dài, ví dụ `AudioSegmentPickerDialog`, dùng dialog + slider/audio preview sẵn có trong app.
- [x] 4.2 Hiển thị tên file, tổng thời lượng, khoảng đang chọn và thời lượng đoạn mẫu tối đa 30 giây.
- [x] 4.3 Cho người dùng kéo vị trí bắt đầu và clamp để đoạn 30 giây không vượt quá cuối file.
- [x] 4.4 Thêm nút nghe thử đoạn đã chọn và dừng phát khi hết đoạn.
- [x] 4.5 Tích hợp picker vào `ProfileForm` cho luồng tạo profile mới.
- [x] 4.6 Tích hợp picker vào `SampleUpload` cho luồng thêm sample vào profile đã có.
- [x] 4.7 Đảm bảo nút chép lời bị disabled cho file dài chưa xác nhận đoạn và dùng đúng đoạn sau khi xác nhận.

## 5. Nội dung hiển thị và i18n

- [x] 5.1 Cập nhật tiếng Việt cho upload hint: cho phép file dài nhưng yêu cầu chọn đoạn mẫu 30 giây.
- [x] 5.2 Cập nhật tiếng Anh tương ứng để không còn ngầm hiểu mọi file upload phải ngắn hơn 30 giây.
- [x] 5.3 Thêm text i18n cho dialog chọn đoạn, nghe thử, xác nhận, hủy, lỗi đoạn không hợp lệ.
- [x] 5.4 Kiểm tra các text hard-code trong `SampleUpload` để giữ nhất quán với ngôn ngữ hiện tại của app.

## 6. Kiểm thử và xác minh

- [x] 6.1 Thêm backend unit tests cho load/cắt đoạn hợp lệ từ file dài.
- [x] 6.2 Thêm backend unit tests cho trim params không hợp lệ: start âm, duration quá 30 giây, duration không dương.
- [x] 6.3 Thêm test hoặc kiểm tra manual cho `/transcribe` chỉ chép lời đoạn được chọn.
- [x] 6.4 Chạy targeted backend tests liên quan tới audio preprocess/validation.
- [x] 6.5 Chạy frontend typecheck/build để bắt lỗi type và bundling.
- [x] 6.6 Kiểm tra thủ công luồng: upload MP3 dài, chọn đoạn 30 giây, nghe thử, chép lời, lưu sample thành công.
