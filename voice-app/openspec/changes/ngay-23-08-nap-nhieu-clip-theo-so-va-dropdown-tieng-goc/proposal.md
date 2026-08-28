## Why

Nạp clip Veo về dự án hiện phải làm từng shot một: mỗi shot là một nút "Chọn clip video" riêng, mỗi lần chỉ nhận một file. Với 18 shot là 18 lượt bấm và chọn, dễ nhầm shot và không có cách nào kiểm tra lại trước khi nạp. Google Flow không cho đặt tên file khi tải về và prompt không tác động được tới tên file, nên người dùng tự đổi tên thành `1.mp4`, `2.mp4`, … theo số segment — cách khớp này đã được dùng thực tế và khớp tuyệt đối với thứ tự shot trong dữ liệu hiện có.

Cùng vùng giao diện này còn hai vấn đề. Công tắc "Giữ tiếng gốc của clip làm nền" là một checkbox đảo dấu so với field API nên khó đọc nghĩa; và thiết lập dựng không được lưu lại, nên bật xong mà tải lại trang là mất, khiến người dùng tưởng công tắc không có tác dụng. Ngoài ra luồng chạy tự động dựng MP4 bằng thiết lập mặc định, không đọc lựa chọn trên giao diện, nên MP4 từ luồng đó vĩnh viễn không có tiếng gốc.

Nạp clip theo đường mới còn giải quyết một nguyên nhân gốc của hiệu năng: clip nạp bằng tay không lưu hãng phát hành, khiến bước làm sạch dấu AI phải dò cả 6 hãng thay vì đúng một hãng.

## What Changes

- Cho chọn nhiều file clip trong một lần, khớp tên file dạng số với số thứ tự segment.
- Hiện bảng khớp để người dùng xem trước và xác nhận, nêu rõ file nào khớp shot nào, file nào bị bỏ qua và vì sao.
- Nạp từng file đã khớp qua đường nạp clip theo hãng, có ghi hãng phát hành, thay vì đường nạp tay không ghi hãng.
- Báo kết quả theo từng file: file lỗi không làm đổ cả lô, các file còn lại vẫn được nạp.
- Đổi công tắc tiếng gốc thành danh sách chọn tiếng Việt hai lựa chọn, bỏ cách đọc đảo dấu.
- Lưu lại thiết lập dựng để tải lại trang không mất lựa chọn.
- Nối lựa chọn tiếng gốc vào luồng chạy tự động và luồng tự dựng sau khi sinh clip.
- Giữ nguyên nút nạp một clip cho từng shot để thay lẻ một segment.

## Capabilities

### New Capabilities

- `ai-video-batch-clip-import`: Quy tắc khớp tên file dạng số với số thứ tự segment, hợp đồng xem trước và xác nhận trước khi nạp, quy tắc bỏ qua file không khớp, hành vi báo lỗi theo từng file, và việc ghi hãng phát hành khi nạp theo lô.
- `ai-video-render-settings-ui`: Cách trình bày lựa chọn nguồn tiếng gốc bằng danh sách chọn tiếng Việt, việc lưu lại thiết lập dựng giữa các lần mở, và quy tắc luồng tự động phải dùng thiết lập người dùng đã chọn.

### Modified Capabilities

- Không có. `openspec/specs/` chưa sync capability nào; change này mở rộng giao diện và luồng nạp clip hiện hữu.

## Impact

- Giao diện: `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` — chọn nhiều file, bảng khớp, danh sách chọn tiếng gốc, lưu thiết lập.
- Client API: `app/src/lib/api/client.ts` và `app/src/lib/api/types.ts` — phương thức nạp clip theo lô.
- Luồng nạp clip: `backend/routes/ai_video.py` và `backend/services/video_rendering.py` — đường nạp có ghi hãng phát hành cho clip do người dùng chọn.
- Luồng tự động: `backend/services/video_auto_runs.py` và `backend/services/video_clip_generation.py` — dùng thiết lập người dùng thay vì thiết lập mặc định.
- Kiểm thử: `backend/tests/test_ai_video_backend.py` và kiểm thử frontend — ca khớp tên file, ca bỏ qua file không khớp, ca lỗi từng file, ca lưu thiết lập.
- Không đổi: giới hạn dung lượng và thời lượng clip, danh sách định dạng được nhận, cơ chế vô hiệu clip cũ khi nạp clip mới cho cùng shot, luồng sinh clip tự động qua trình duyệt.
