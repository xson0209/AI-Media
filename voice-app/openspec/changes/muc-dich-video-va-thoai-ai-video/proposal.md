## Why

AI Video hiện đã có hướng chọn `Ngôn ngữ video`, nhưng người dùng vẫn phải tự hiểu nên chọn tiếng Việt hay tiếng Anh cho từng mục đích. Cần một lớp `Mục đích video` để hệ thống gợi ý ngôn ngữ, giọng đọc, thoại/narration và phong cách script phù hợp với audience, thay vì chỉ đưa một dropdown ngôn ngữ rời rạc.

## What Changes

- Thêm lựa chọn `Mục đích video` trong AI Video phase 2 để người dùng chọn nhanh mục tiêu như thị trường Việt Nam, global/English short, giáo dục/giải thích, quảng cáo/bán hàng hoặc localize từ video có sẵn.
- Mỗi mục đích cung cấp preset mặc định hoặc gợi ý cho `target_language`, voice profile/engine phù hợp, mật độ thoại/narration, subtitle, tone script và prompt style.
- Giữ `target_language` là nguồn sự thật cuối cùng cho ngôn ngữ người xem nghe/đọc; preset chỉ gợi ý và có thể bị người dùng override.
- Mở rộng AI planning để tạo thoại/narration theo mục đích: voiceover rõ ràng cho video giải thích, hook/CTA mạnh cho quảng cáo, câu thoại tự nhiên hơn khi nội dung cần nhân vật nói, và tránh thoại sai ngôn ngữ video.
- Thêm lớp chuẩn hoá dữ liệu trước khi gửi Codex và sau khi nhận kết quả Codex: purpose/dialogue/language phải được đưa vào prompt context theo format ổn định, còn output Codex phải được map alias về field chuẩn trước khi ghi DB.
- UI phải hiển thị rõ preset đang tác động tới gì: ngôn ngữ video, giọng đọc, subtitle, độ dài thoại, phong cách script và các artifact sẽ cần tạo lại khi đổi mục đích.
- Khi đổi mục đích trên project đã có artifact, hệ thống đánh dấu stale các phần phụ thuộc như story/script, shot narration, voice, subtitle, prompt video và package nếu preset làm thay đổi language/style/dialogue contract.
- Không tự tạo nhiều bản export song ngữ trong cùng một project; nếu cần bản Việt và bản Anh, workflow nên hỗ trợ duplicate/localize project để mỗi project có một `target_language` rõ ràng.

## Capabilities

### New Capabilities
- `ai-video-purpose-dialogue-workflow`: Điều phối mục đích video, ngôn ngữ output, voice compatibility và thoại/narration để tạo AI Video phù hợp nhiều audience/use case.

### Modified Capabilities
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Change này xây trên change `ngon-ngu-video-tuy-chon` và các workflow AI Video phase 2 hiện có.

## Impact

- Backend: project model/API có thể cần thêm field purpose/preset, helper resolve preset, stale rules khi đổi purpose, prompt builder phase 2, validation voice/language và package metadata.
- Frontend: AI Video setup cần thêm selector `Mục đích video`, preview tác động của preset, cảnh báo voice không hợp ngôn ngữ và copy tiếng Việt giải thích rõ workflow.
- AI planning: story/shot/prompt instructions cần nhận purpose, target language, dialogue mode và narration density để sinh thoại đúng mục đích.
- Normalization: cần mở rộng các helper normalize hiện có cho phase 2 để chuẩn hoá outbound Codex context, inbound Codex aliases, conflict detection và validation errors liên quan đến purpose/dialogue.
- Data/storage: cần lưu purpose đã chọn hoặc snapshot preset để project có thể resume, duplicate/localize và debug vì sao AI tạo thoại theo style đó.
- Tests: thêm backend tests cho preset resolution, override language, prompt contains purpose/dialogue instructions, normalize input/output Codex, stale behavior, voice compatibility và frontend type/UI behavior.
