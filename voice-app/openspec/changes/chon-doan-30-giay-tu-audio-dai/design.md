## Bối cảnh

Voicebox hiện dùng mẫu âm thanh tham chiếu tối đa 30 giây cho profile clone giọng. Giới hạn này đang tồn tại ở cả frontend và backend: frontend chặn file upload dài hơn 30 giây, còn backend validate `max_duration=30.0` trước khi lưu sample. Điều này bảo vệ chất lượng mẫu giọng, nhưng UX chưa tốt khi người dùng có một file MP3 dài và chỉ muốn lấy một đoạn giọng tốt bên trong file đó.

Tính năng mới cần giữ nguyên giới hạn sample cuối cùng là 30 giây, nhưng bỏ trải nghiệm "upload dài là lỗi ngay". Với file dài, người dùng sẽ chọn một đoạn tối đa 30 giây, hệ thống cắt đoạn đó rồi tiếp tục xử lý như sample bình thường.

## Mục tiêu / Không mục tiêu

**Mục tiêu:**

- Cho phép upload file audio dài hơn 30 giây trong luồng thêm mẫu giọng.
- Cho người dùng chọn, nghe thử và xác nhận một đoạn tối đa 30 giây từ file dài.
- Backend chỉ lưu đoạn đã cắt làm WAV sample, không lưu toàn bộ file dài làm sample.
- Nút chép lời dùng đúng đoạn đã chọn để reference text khớp sample được lưu.
- Giữ giới hạn validate sample 30 giây ở backend như lớp bảo vệ cuối cùng.

**Không mục tiêu:**

- Không tăng giới hạn mẫu tham chiếu cuối cùng vượt quá 30 giây.
- Không thay đổi luồng generation hoặc độ dài audio được tạo ra.
- Không thêm editor audio đầy đủ như crop nhiều đoạn, fade, normalize thủ công, hoặc waveform editing nâng cao.
- Không thay đổi cơ chế ghi âm trực tiếp/ghi âm hệ thống; các luồng này có thể tiếp tục tự dừng ở khoảng 30 giây.
- Không tăng giới hạn kích thước upload 50 MB trong phạm vi thay đổi này, trừ khi implementation phát hiện đây là blocker thực tế.

## Quyết định

### 1. Cắt đoạn ở backend, không decode toàn bộ file dài ở frontend

Frontend sẽ dùng metadata/audio element và UI picker để chọn `start` + `duration`, nhưng backend sẽ là nơi load/cắt đoạn trước khi validate và lưu.

Lý do:

- File MP3 dài có thể tốn nhiều RAM nếu dùng Web Audio API decode toàn bộ trong trình duyệt.
- Backend đã có `librosa`/`soundfile`, có thể load đoạn cụ thể bằng offset/duration rồi lưu WAV chuẩn cho downstream.
- Backend vẫn kiểm soát được validate cuối cùng và không tin hoàn toàn vào dữ liệu trim từ client.

Phương án loại bỏ: cắt hoàn toàn ở frontend bằng `AudioContext.decodeAudioData`. Cách này đơn giản về API nhưng rủi ro với file dài, đặc biệt MP3 nhiều phút hoặc VBR.

### 2. Mở rộng API bằng form fields optional

`POST /profiles/{profile_id}/samples` nhận thêm:

- `trim_start_seconds?: float`
- `trim_duration_seconds?: float`

Nếu không có hai field này, backend giữ hành vi hiện tại. Nếu có, backend cắt file tạm theo đoạn chỉ định trước khi gọi validate sample.

`POST /transcribe` cũng nhận cùng cặp field để transcription khớp đoạn sample đã chọn.

Lý do:

- Không tạo endpoint mới cho một luồng đang gắn chặt với upload sample/transcribe.
- Giữ backwards compatibility cho các client hiện có.
- Frontend chỉ cần truyền thêm metadata khi file dài đã có đoạn được chọn.

### 3. Giới hạn 30 giây vẫn là invariant backend

Backend PHẢI reject đoạn trim nếu:

- `trim_start_seconds < 0`
- `trim_duration_seconds <= 0`
- `trim_duration_seconds > 30`
- đoạn sau khi load/cắt vẫn dài hơn giới hạn sample do sai số decode hoặc input không hợp lệ

Lý do: client-side picker là UX, không phải lớp bảo mật/đảm bảo dữ liệu.

### 4. Frontend dùng segment picker nhẹ, không editor audio đầy đủ

Khi file upload có duration > 30 giây, frontend mở dialog chọn đoạn. UI cần có:

- Tên file và tổng thời lượng.
- Thanh chọn vị trí bắt đầu đoạn.
- Hiển thị khoảng đang chọn, ví dụ `1:20 - 1:50`.
- Nút nghe thử đoạn đã chọn.
- Nút xác nhận dùng đoạn này và nút hủy/chọn file khác.

Repo đã có `@radix-ui/react-slider`, `@radix-ui/react-dialog`, `wavesurfer.js`; implementation có thể dùng các thư viện sẵn có này hoặc dùng audio element nếu đủ ổn định.

### 5. Trạng thái file cần kèm thông tin đoạn đã chọn

Frontend nên lưu trạng thái dạng rõ ràng thay vì chỉ giữ `File`:

- `file`
- `duration`
- `segmentStartSeconds?`
- `segmentDurationSeconds?`
- `isSegmentRequired`
- `isSegmentConfirmed`

Khi submit hoặc transcribe, nếu file dài thì chỉ cho tiếp tục sau khi đoạn đã được xác nhận.

## Rủi ro / Đánh đổi

- **Duration frontend và backend lệch nhau** → Backend clamp/validate trim và trả lỗi rõ ràng nếu đoạn không hợp lệ.
- **File dài vượt giới hạn 50 MB** → Hiển thị lỗi kích thước file riêng; không nhầm với lỗi 30 giây.
- **Đoạn chọn quá im lặng** → Backend giữ validate RMS/min duration hiện tại và trả lỗi để người dùng chọn đoạn khác.
- **Transcription không khớp sample** → `/transcribe` nhận cùng trim params để chỉ chép lời đoạn đã chọn.
- **MP3 VBR báo duration sai** → Frontend dùng duration để UX, backend mới là nguồn validate cuối cùng.
- **Tăng độ phức tạp form tạo profile/thêm sample** → Tách component picker riêng và helper API trim để tránh rải logic trong nhiều component.

## Kế hoạch chuyển đổi

1. Thêm helper backend để load/cắt đoạn audio theo offset + duration.
2. Mở rộng route upload sample và transcribe nhận trim form fields optional.
3. Cập nhật frontend API client/hook để truyền trim metadata.
4. Thêm component chọn đoạn audio và tích hợp vào luồng tạo profile/thêm sample.
5. Cập nhật i18n tiếng Việt/tiếng Anh.
6. Bổ sung test backend và chạy typecheck/build frontend.

Rollback đơn giản: vì field mới là optional, có thể revert frontend picker trước mà không phá API cũ. Backend giữ tương thích với request không có trim params.

## Câu hỏi mở

- Có cần tăng `SAMPLE_MAX_FILE_SIZE` từ 50 MB lên mức cao hơn cho MP3 dài không, hay giữ nguyên để tránh upload quá nặng?
- Có cần waveform trực quan ngay trong phiên đầu, hay slider + audio preview đủ cho bản đầu tiên?
- Với file dài hơn nhiều phút, có cần tự gợi ý đoạn có speech rõ nhất ở phiên bản sau không?
