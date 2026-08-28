## Why

Khi dựng MP4, phân đoạn nào không có narration thì audio thành im lặng hoàn toàn, dù clip gốc có tiếng thật (tiếng bước chân, gió, ambience do provider sinh ra). Nhánh `anullsrc` hiện tại là nhánh "còn lại" chứ không phải một lựa chọn có chủ ý, nên video bị ngắt quãng âm thanh giữa các đoạn.

Cùng vùng code này còn một lỗi đang tồn tại: bước mix SFX/BGM không tắt `normalize` của `amix`, mà mặc định của FFmpeg là bật. Hệ quả là mỗi asset thêm vào lại chia nhỏ giọng đọc — thêm 1 SFX thì giọng còn khoảng một nửa, thêm 3 SFX thì còn khoảng một phần tư. Hai việc phải làm cùng lúc: nếu chỉ thêm tiếng gốc mà không sửa `normalize`, tiếng gốc sẽ bị hiểu nhầm là nguyên nhân làm giọng đọc chìm.

## What Changes

- Dựng một timeline tiếng gốc song song với timeline giọng đọc, rút audio từ clip gốc của từng phân đoạn, rồi trộn một lần duy nhất ở cuối thay vì trộn theo từng đoạn.
- Tự động hạ tiếng gốc xuống khi có giọng đọc bằng nén sidechain, để tiếng gốc làm nền chứ không lấn giọng.
- Phân đoạn không có narration mà clip có tiếng: phát tiếng gốc thay vì im lặng.
- Phân đoạn mà giọng đọc vốn đã chính là audio của clip: không thêm tiếng gốc, tránh cộng trùng một nguồn gây vọng tiếng và méo giọng.
- **BREAKING (hành vi, không phải API)**: `mute_clip_audio` từ nay có tác dụng thật lên MP4. Trước đây field này tồn tại xuyên suốt API nhưng pipeline render không bao giờ đọc. Kiểu dữ liệu và giá trị mặc định không đổi nên client cũ không cần sửa, và mặc định hiện tại tương ứng với hành vi cũ.
- Bổ sung công tắc bật/tắt tiếng gốc trong bảng dựng nhanh MP4.
- Tắt `normalize` khi trộn SFX/BGM để giọng đọc không bị chia nhỏ theo số lượng asset.

## Capabilities

### New Capabilities

- `ai-video-original-audio-bed`: Nguồn audio nền lấy từ clip gốc theo từng phân đoạn, quy tắc chọn nguồn theo speech source để tránh cộng trùng, cơ chế hạ tiếng nền khi có giọng đọc, và hành vi trộn mức âm lượng khi có SFX/BGM.

### Modified Capabilities

- Không có. `openspec/specs/` chưa có capability nào được sync; change này mở rộng nhánh audio của pipeline render hiện hữu và giữ nguyên hành vi khi tiếng gốc bị tắt.

## Impact

- Pipeline render audio: `backend/services/video_rendering.py` — thêm bước dựng timeline tiếng gốc, bước hạ tiếng nền và trộn cuối; sửa mức âm lượng khi trộn SFX/BGM.
- Cấu hình render: `backend/models.py` — `mute_clip_audio` được ánh xạ sang khái niệm nguồn audio nội bộ ở tầng render, kiểu dữ liệu trên API giữ nguyên.
- Frontend: `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` — công tắc tiếng gốc.
- Kiểm thử: `backend/tests/test_ai_video_backend.py` — thêm ca cho từng nhánh chọn nguồn audio, builder câu lệnh tiếng nền, và mức âm lượng khi trộn.
- Phụ thuộc: cần FFmpeg có `sidechaincompress` (đã có trong bản FFmpeg đi kèm dự án).
- Không đổi: nhánh video vẫn strip audio và mux ở cuối như hiện tại, hợp đồng lấy audio từ clip gốc chứ không phải bản đã làm sạch watermark, cơ chế phụ đề, và toàn bộ phần làm sạch watermark.
