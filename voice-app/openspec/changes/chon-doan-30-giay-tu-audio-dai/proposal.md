## Lý do

Người dùng có thể có file MP3/audio dài chứa nhiều đoạn giọng tốt, nhưng hiện Voicebox chặn mẫu tham chiếu dài hơn 30 giây và chỉ báo lỗi "Âm thanh quá dài". Tính năng này cho phép upload file dài, chọn đúng đoạn 30 giây cần dùng, rồi chỉ lưu đoạn đã cắt làm mẫu giọng để giữ giới hạn chất lượng hiện tại.

## Thay đổi

- Cho phép người dùng chọn file audio dài hơn 30 giây trong luồng thêm mẫu giọng.
- Khi file vượt giới hạn mẫu giọng, hiển thị giao diện chọn đoạn tối đa 30 giây thay vì báo lỗi ngay.
- Gửi thông tin đoạn cần cắt cùng file upload để backend chỉ trích xuất đoạn đã chọn trước khi validate/lưu sample.
- Cho phép chép lời trên đúng đoạn đã chọn, không phải toàn bộ file audio dài.
- Cập nhật thông báo tiếng Việt/tiếng Anh để phân biệt "file upload có thể dài" và "đoạn mẫu dùng cho clone giọng tối đa 30 giây".
- Không thay đổi giới hạn mẫu tham chiếu cuối cùng: backend vẫn chỉ lưu sample tối đa 30 giây.

## Capabilities

### Capabilities mới

- `chon-doan-audio-dai`: Cho phép chọn, nghe thử, chép lời và lưu một đoạn mẫu tối đa 30 giây từ file audio dài.

### Capabilities thay đổi

- Không có, vì repo chưa có spec OpenSpec nền cho voice profile/sample upload.

## Ảnh hưởng

- Frontend voice profile: `ProfileForm`, `SampleUpload`, `AudioSampleUpload` và component chọn đoạn audio mới.
- API client/hook: gửi thêm tham số trim cho upload sample và transcribe.
- Backend routes: `/profiles/{profile_id}/samples` và `/transcribe` nhận thông tin đoạn cần cắt.
- Backend audio utils/services: load/cắt đoạn audio theo offset + duration trước khi validate/lưu.
- i18n: cập nhật text tiếng Việt và tiếng Anh cho upload sample/audio segment picker.
- Tests: bổ sung test backend cho validate/load đoạn audio và kiểm tra giới hạn 30 giây sau khi cắt.
