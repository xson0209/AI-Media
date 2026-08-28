## Why

Điều kiện dựng MP4 hiện suy ra "shot này bắt buộc phải có giọng đọc" chỉ từ việc `english_narration` có chữ, không có bất kỳ thiết lập nào để tắt. Với project mà mọi shot đều có lời kể nhưng người dùng không cần đọc thành tiếng, checklist luôn báo thiếu giọng đọc và thiếu thời lượng render, nút Dựng MP4 bị khóa cứng và không có đường thoát nào từ giao diện.

Hai thông báo lỗi đó thực chất là một nguyên nhân: shot có narration thì thời lượng render chỉ được lấy từ file audio của giọng đọc, không bao giờ quay về `duration_seconds` hay thời lượng clip. Không có giọng đọc nghĩa là không có thời lượng, nên chặn thêm lần thứ hai.

## What Changes

- Danh sách chọn nguồn tiếng gốc trong bảng dựng nhanh MP4 đổi thành danh sách "Âm thanh" với **ba** mức thay vì hai: "Kết hợp" (giọng đọc + tiếng gốc làm nền, hạ mức khi có giọng), "Voice" (chỉ giọng đọc, bỏ tiếng gốc), "Âm thanh gốc" (chỉ tiếng gốc ở mức nguyên bản, không dùng giọng đọc).
- Cấu hình dựng MP4 nhận thêm một field mức âm thanh ba giá trị. Field boolean cũ được giữ lại làm bản phản chiếu tương thích ngược, không bị bỏ.
- Ở mức "Âm thanh gốc", checklist readiness **không** còn đòi giọng đọc hoàn tất cho shot có narration, và thời lượng render lấy từ thời lượng clip.
- Ở mức "Âm thanh gốc", tiếng gốc trở thành nguồn audio chính ở mức nguyên bản: không hạ mức, không trộn với timeline giọng đọc.
- Ở mức "Âm thanh gốc", việc tạo phụ đề không còn đòi giọng đọc hoàn tất. Chế độ phụ đề vẫn do người dùng chọn như hiện tại, hệ thống không tự bật hay tự tắt.
- Giá trị mặc định giữ nguyên ở mức "Voice", nên mọi project cũ và mọi luồng dựng tự động cho ra kết quả không đổi.

## Capabilities

### New Capabilities
- `ai-video-clip-audio-mode`: Mức âm thanh ba giá trị của bản dựng MP4 — cách phân giải mức từ cấu hình cũ và mới, cách dựng audio ở mức chỉ dùng tiếng gốc, và việc mở điều kiện tạo phụ đề ở mức đó.

### Modified Capabilities
- `ai-video-render-settings-ui`: Requirement "Danh sách chọn tiếng Việt cho nguồn tiếng gốc" hiện chốt danh sách chỉ có hai lựa chọn và kiểu dữ liệu field API không đổi. Cả hai điều kiện đó đều thay đổi.
- `ai-video-original-audio-bed`: Requirement "Người dùng bật tắt tiếng gốc từ bảng dựng MP4" đổi từ công tắc hai trạng thái thành ba mức. Requirement "Chọn nguồn tiếng nền theo speech source của project" cần loại trừ mức chỉ dùng tiếng gốc khỏi quy tắc bỏ tiếng nền cho phân đoạn có giọng trích từ clip.
- `ai-video-timeline-render`: Requirement "Kiểm tra readiness trước khi render MP4" và "Tạo timeline duration từ voice thật" đang chốt rằng shot có narration bắt buộc phải có voice completed và thời lượng phải bằng `audio_duration`.

## Impact

**Backend**
- `backend/models.py` — `VideoRenderSettings` thêm field mức âm thanh.
- `backend/services/video_rendering.py` — phân giải mức âm thanh, điều kiện readiness, nguồn thời lượng shot, timeline manifest, quyết định nguồn tiếng nền theo phân đoạn, nhánh dựng audio.
- `backend/services/video_subtitles.py` — điều kiện tạo phụ đề theo mức âm thanh.
- `backend/routes/ai_video.py` — endpoint readiness nhận mức âm thanh qua query param.

**Frontend**
- `app/src/lib/api/types.ts`, `app/src/lib/api/client.ts` — kiểu dữ liệu và tham số gửi lên readiness.
- `app/src/lib/renderSettingsStore.ts` — giá trị mặc định, validator, và suy mức từ thiết lập đã lưu của bản cũ.
- `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` — danh sách chọn ba mức và phần diễn giải bên dưới.

**Tương thích ngược cần giữ**
- Job đã lưu trong database không có field mới: mức âm thanh phải được suy từ field boolean cũ, không được rơi về mức mặc định.
- Thiết lập đã lưu ở máy người dùng không có field mới: danh sách chọn phải hiện đúng mức tương ứng với lựa chọn cũ.
- Luồng dựng tự động đã đọc lại thiết lập của project nên tự động thừa hưởng mức mới, không cần thay đổi thêm.

**Ngoài phạm vi**
- Không đổi giá trị mặc định của mức âm thanh.
- Không đổi cách trộn SFX/BGM của enhanced audio.
- Không thêm mức thứ tư.
- Không sửa `english_narration` của shot.
- Không đổi bước làm sạch watermark.
