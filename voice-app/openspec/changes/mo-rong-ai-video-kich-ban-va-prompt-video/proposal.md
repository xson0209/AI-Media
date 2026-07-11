## Why

Phase 1 của AI Video Assistant đã giúp người dùng đi từ một ý tưởng ngắn đến kịch bản, prompt ảnh, giọng đọc, phụ đề và gói nguyên liệu. Tuy nhiên người dùng hiện cần một bước mạnh hơn: nhập được nhiều ý tưởng hoặc kịch bản thô bằng tiếng Việt, để AI phát triển lại thành nội dung video tiếng Anh hấp dẫn, nhất quán từ đầu đến cuối và xuất ra prompt tạo video chi tiết có thể copy sang nhiều công cụ tạo video.

Thay đổi này biến AI Video Assistant từ luồng prompt ảnh đơn giản thành một **Script-to-Video-Prompt Studio**: UI vẫn dễ dùng bằng tiếng Việt, còn kịch bản tiếng Anh và prompt video tiếng Anh được AI tối ưu theo nội dung từng shot.

## What Changes

- Thay hoàn toàn luồng **prompt ảnh** bằng **prompt tạo video** làm output chính của phase 2.
- Cho phép nhập nhiều nguồn nội dung thay vì chỉ một chủ đề ngắn: ý tưởng chính, nhiều ý tưởng phụ, kịch bản thô, dàn ý, ghi chú nhân vật, phong cách video, đối tượng xem, điều bắt buộc và điều cần tránh.
- Thêm bước AI tổng hợp input thành brief rõ ràng, rồi phát triển lại nội dung thành kịch bản chi tiết, hấp dẫn hơn.
- AI phải tạo cấu trúc câu chuyện có hook, vấn đề/xung đột, cảm xúc, chi tiết thú vị, cao trào nhỏ, payoff/kết thúc và nhịp giữ chân người xem.
- AI phải giữ continuity từ đầu đến cuối bằng continuity bible: nhân vật, trang phục, đạo cụ, bối cảnh, mood, tone màu, phong cách camera và các chi tiết không được thay đổi giữa các shot.
- Tự chia scene dài thành nhiều shot rất ngắn, mặc định khoảng 1-5 giây, để tạo nhịp xem nhanh hơn, nhiều chuyển cảnh hơn và giảm cảm giác nhàm chán.
- Mỗi shot chỉ nên thể hiện một hành động chính hoặc một góc quay chính; không để một scene dài chỉ có một góc quay hoặc một cảnh đứng yên.
- Mỗi shot có mô tả tiếng Việt để người dùng hiểu, lời thoại/narration tiếng Anh nếu có, prompt video tiếng Anh dùng chung và negative prompt tiếng Anh.
- Prompt video phải dùng được cho nhiều công cụ tạo video, không khóa vào một provider cụ thể, nhưng vẫn rất chi tiết theo nội dung từng shot: duration, aspect ratio, subject, action, camera movement, subject motion, environment motion, lighting, mood, start frame, end frame, continuity notes và negative prompt.
- Thêm transition plan và shot variation để video có nhiều chuyển cảnh hấp dẫn: thay đổi góc máy, cỡ cảnh, bố cục và chuyển động camera liên tục bằng establishing shot, close-up, detail shot, over-the-shoulder, slow push-in, tracking shot, match cut, time-lapse ngắn hoặc transition qua ánh sáng/đạo cụ.
- Thiết kế UI phase 2 theo `design-taste-frontend-v1`: giao diện tiếng Việt thân thiện, màn đầu tiên là workflow sử dụng thật, có loading/empty/error states, responsive tốt trên mobile, không emoji, không `h-screen`, tránh giao diện tím/xanh kiểu AI và kiểm tra dependency trước khi import thư viện UI/motion/icon.
- Bổ sung logging/debug local có cấu trúc cho từng bước source/story/shot/prompt/export/voice/subtitle, kèm `request_id` và thông tin kỹ thuật đã redaction để người dùng dễ gửi lỗi khi chạy local.
- Cho phép regenerate từng shot hoặc từng nhóm prompt mà không phải tạo lại toàn bộ project.
- Cho phép lock nội dung đã duyệt để AI không sửa nhầm khi regenerate phần khác.
- Cập nhật ZIP/export: thư mục `Prompt ảnh` chuyển thành `Prompt video`, kèm kịch bản, shot list, continuity bible, transition plan, voice và subtitle.
- UI tiếng Việt tiếp tục là mặc định, nhưng phần script/narration và prompt video có thể xuất tiếng Anh để phục vụ nhu cầu làm video tiếng Anh.

## Capabilities

### New Capabilities
- `ai-video-video-prompt-studio`: Mở rộng AI Video Assistant thành workflow nhập nhiều nguồn nội dung, AI phát triển kịch bản hấp dẫn, chia scene thành shot ngắn, giữ continuity và xuất prompt tạo video tiếng Anh chi tiết dùng chung cho nhiều công cụ tạo video.

### Modified Capabilities
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Phase 2 sẽ tích hợp vào AI Video Assistant hiện có khi implementation bắt đầu.

## Impact

- Backend: mở rộng model/API video project để lưu nhiều source text block, script development artifact, continuity bible, scene/shot hierarchy, video prompt artifact, transition plan, lock state và prompt versioning.
- AI planning: cập nhật prompt/schema Codex CLI để sinh nội dung theo nhiều bước: input synthesis, story development, scene/shot breakdown, continuity bible và video prompt pack.
- Frontend: thay form nhập một chủ đề bằng khu nhập nhiều nguồn nội dung; thay màn prompt ảnh bằng màn prompt video theo scene/shot; thêm mô tả tiếng Việt, narration tiếng Anh, negative prompt, regenerate/lock/copy/download theo shot; áp dụng yêu cầu UI `design-taste-frontend-v1` để giao diện local đẹp, rõ, dễ dùng với người không rành kỹ thuật.
- Export/package: đổi cấu trúc gói nguyên liệu từ prompt ảnh sang prompt video; thêm kịch bản, shot list, continuity bible, transition plan và prompt video theo thứ tự scene/shot.
- Observability local: thêm log lỗi có cấu trúc, debug panel/endpoint và cơ chế copy `request_id` để truy lỗi AI planning, validate, export, voice và subtitle khi chạy trên máy cá nhân.
- Data/migration: cần thêm bảng/cột hoặc JSON artifact để lưu source blocks, shot rows, video prompt fields, continuity metadata và lock/version state.
- Compatibility: voice generation, subtitle, profile, audio history và package workflow hiện tại vẫn được tái sử dụng; phase 2 không render MP4 và không tích hợp provider tạo video trực tiếp.
