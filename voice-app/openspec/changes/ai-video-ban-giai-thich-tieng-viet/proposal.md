## Why

AI Video phase 2 có thể tạo kịch bản, segment và prompt video bằng tiếng Anh để phục vụ video đầu ra hoặc tool tạo video bên ngoài, nhưng người dùng Việt không luôn hiểu được nội dung kỹ thuật đó trong lúc làm việc. Cần một lớp tiếng Việt để người dùng đọc hiểu, duyệt và chỉnh nội dung mà không làm thay đổi ngôn ngữ video cuối.

## What Changes

- Thêm lớp "bản tiếng Việt để duyệt" cho các nội dung AI tạo ra trong workflow AI Video phase 2.
- Story strategy, continuity bible và detailed script SHALL luôn có bản tiếng Việt dễ đọc cho người dùng Việt, kể cả khi bản sản xuất dùng tiếng Anh.
- Prompt segment 10 giây SHALL hiển thị mô tả tiếng Việt về timeline, hành động, camera, chuyển cảnh và nội dung narration để người dùng hiểu từng segment.
- Prompt video SHALL giữ prompt gốc để copy sang công cụ tạo video, đồng thời có bản giải thích hoặc bản dịch tiếng Việt bên dưới.
- Package/export SHALL kèm bản tiếng Việt để người dùng đọc lại khi làm việc ngoài Voicebox.
- Giữ phân tách rõ: bản tiếng Việt để duyệt không quyết định ngôn ngữ voice, phụ đề `.srt`, narration hoặc video cuối.
- Không đổi mặc định UI Voicebox: các nhãn, trạng thái, lỗi và hướng dẫn trong app vẫn bằng tiếng Việt.

## Capabilities

### New Capabilities

- `ai-video-vietnamese-review-layer`: Cung cấp bản tiếng Việt để người dùng đọc hiểu và duyệt story, continuity, kịch bản, segment 10 giây và prompt video trong AI Video phase 2.

### Modified Capabilities

- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Capability mới này bổ sung lớp review tiếng Việt cho workflow AI Video phase 2 và phối hợp với các change AI Video đang mở.

## Impact

- Backend: schema/normalization của AI planning cho story, shot/segment và prompt video; storage/model cho bản giải thích tiếng Việt của prompt video nếu cần; package manifest/export; download prompt.
- Frontend: AI Video Assistant hiển thị bản tiếng Việt để duyệt dưới các nội dung tiếng Anh/kỹ thuật; bỏ copy hardcode như "prompt tiếng Anh" hoặc "narration tiếng Anh" khi không còn đúng ngữ cảnh.
- API/type: có thể cần thêm field phản hồi cho bản giải thích tiếng Việt của prompt video hoặc mở rộng payload prompt content.
- Test: thêm test backend cho output song song bản sản xuất và bản tiếng Việt; test UI/type cho nhãn động; test package/download có bản tiếng Việt.
- Dữ liệu: nếu thêm field lưu bản giải thích prompt video, cần migration tương thích và fallback an toàn cho prompt cũ.
