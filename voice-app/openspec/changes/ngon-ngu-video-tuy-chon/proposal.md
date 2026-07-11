## Vì sao

AI Video Assistant phase 2 hiện đang ngầm hiểu rằng người dùng thao tác bằng tiếng Việt nhưng video đầu ra luôn là tiếng Anh. Bạn cần làm cả video tiếng Việt lẫn video tiếng Anh, nên lựa chọn `Ngôn ngữ video` phải quyết định ngôn ngữ mà người xem nghe và đọc trong video cuối.

## Thay đổi

- Dùng `target_language` làm nguồn sự thật cho ngôn ngữ video trong AI Video phase 2.
- Khi `target_language = "en"`, hệ thống tạo kịch bản, narration, voice, phụ đề, nhãn nội dung video và metadata export cho video tiếng Anh.
- Khi `target_language = "vi"`, hệ thống tạo kịch bản, narration, voice, phụ đề, nhãn nội dung video và metadata export cho video tiếng Việt.
- Giữ giao diện app bằng tiếng Việt; thay đổi này chỉ điều khiển ngôn ngữ nội dung video, không phải ngôn ngữ UI của Voicebox.
- Bỏ các giả định hardcode tiếng Anh trong prompt AI planning, copy frontend, request tạo voice, tạo phụ đề, kiểm tra readiness và nội dung package.
- Giữ field cũ `english_narration` để tương thích dữ liệu, nhưng trong logic mới coi đó là nội dung narration theo ngôn ngữ video đã chọn.
- Kiểm tra voice profile/engine/model có hỗ trợ ngôn ngữ video đã chọn hay không và hiển thị lỗi tiếng Việt rõ ràng nếu không hỗ trợ.
- Giữ hành vi tiếng Anh hiện tại cho project cũ nếu người dùng không chọn tiếng Việt.

## Capabilities

### Capability mới
- `ai-video-video-prompt-studio`: Mở rộng workflow AI Video phase 2 để người dùng chọn được ngôn ngữ video là tiếng Anh hoặc tiếng Việt; lựa chọn này điều khiển kịch bản, narration, voice, phụ đề, prompt video và export.

### Capability thay đổi
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Change này bổ sung requirement cho capability AI Video phase 2 hiện đang nằm trong các change AI Video trước đó.

## Ảnh hưởng

- Backend: xử lý `target_language` của video project, prompt builder phase 2, validation request tạo narration, chọn ngôn ngữ voice, text phụ đề, package readiness và manifest/export.
- Frontend: helper text của lựa chọn `Ngôn ngữ video`, tạo project, request tạo voice, nhãn động cho narration/prompt/subtitle, thông báo lỗi và checklist readiness.
- Dữ liệu: không cần migration phá dữ liệu. `target_language` đã tồn tại; `english_narration` được giữ lại để tương thích nhưng được hiểu là narration text theo ngôn ngữ video.
- Test: thêm test backend cho project tiếng Anh/tiếng Việt, prompt AI planning, voice language resolution, subtitle, stale/readiness, package manifest; chạy type/build frontend liên quan.
- Tài liệu: cập nhật hướng dẫn AI Video vì docs hiện đang nói phase 2 luôn tạo narration/prompt tiếng Anh.

## Ghi chú về tên file

Thư mục change đã dùng tên tiếng Việt không dấu: `ngon-ngu-video-tuy-chon`. Các file chuẩn như `proposal.md`, `design.md`, `tasks.md`, `spec.md` vẫn phải giữ tên này vì OpenSpec CLI dùng chúng để đọc status và apply.
