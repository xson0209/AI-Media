## Context

Người dùng muốn một khu làm việc mới dành riêng cho việc lấy cảm hứng từ video có sẵn. Luồng này khác AI Video Assistant hiện tại: người dùng đưa vào một video `.mp4` hoặc link video công khai, app đọc lời nói và hình ảnh, sau đó viết mới mạnh tay thành một kịch bản mới. Giao diện phải dùng tiếng Việt vì người dùng không rành tiếng Anh, nhưng kịch bản đầu ra cần cho chọn tiếng Việt hoặc tiếng Anh.

Hiện app đã có Whisper để chuyển audio thành text, FFmpeg/FFprobe cho xử lý video, AI Video phase 2 cho source blocks, story, shot, prompt video, voice và subtitle. Tuy nhiên `/transcribe` hiện chủ yếu nhận audio, còn AI Video hiện là route `/ai-video`. Tính năng mới cần route riêng, không nhét UI vào màn AI Video hiện tại.

## Goals

- Thêm một route frontend mới, ví dụ `/video-inspiration`, hiển thị tên tiếng Việt như `Lấy cảm hứng từ video`.
- Thêm backend API prefix riêng, ví dụ `/video-inspiration`, không đặt endpoint mới dưới `/ai-video`.
- Cho phép nhập nguồn bằng upload `.mp4` và link công khai từ YouTube, TikTok, Facebook hoặc Instagram theo kiểu best-effort.
- Tách audio từ video, chuyển lời nói thành transcript bằng Whisper và lưu transcript để người dùng xem/sửa.
- Phân tích hình ảnh bằng cách lấy frame đại diện/keyframe từ video và chạy qua lớp phân tích hình ảnh.
- Phân tích nội dung video gốc: ý chính, hook, cấu trúc, nhân vật/bối cảnh, nhịp dựng, điểm mạnh, điểm yếu và cơ hội viết lại.
- Viết mới mạnh tay từ cảm hứng video gốc, không chỉ paraphrase. Kịch bản mới có thể khác cấu trúc, hook, cách kể và nhịp dựng, nhưng vẫn dựa trên insight/cảm hứng đã phân tích.
- Cho người dùng chọn ngôn ngữ kịch bản mới: tiếng Việt hoặc tiếng Anh. Giao diện, helper text, lỗi và phần giải thích vẫn là tiếng Việt.
- Cho phép đưa kịch bản mới, mô tả frame đại diện và toàn bộ phân tích sang form AI Video khi người dùng bấm xác nhận: mở `/ai-video` với các ô nội dung đã điền sẵn, nhưng chưa tạo project/chạy auto-run và không ghi đè cấu hình để người dùng tự chọn thị trường, ngôn ngữ, thời lượng, tỷ lệ, voice và cách chạy.
- Việc lấy cảm hứng/viết lại vẫn nằm ở route mới; `/ai-video` chỉ nhận kết quả cuối để phát triển thành nguyên liệu video.

## Non-Goals

- Không tự động tải hoặc phân tích video riêng tư, video cần đăng nhập, DRM, livestream hoặc nội dung bị nền tảng chặn.
- Không bypass paywall, CAPTCHA, login, quyền riêng tư hoặc điều khoản nền tảng.
- Không đảm bảo link YouTube/TikTok/Facebook/Instagram luôn tải được; nếu link fail thì app hướng dẫn upload file.
- Không tạo MP4 hoàn chỉnh trong change này; đích của luồng chuyển sang AI Video là prompt, voice và SRT.
- Không thay thế AI Video Assistant hiện tại và không di chuyển các endpoint `/ai-video` hiện có.
- Không tạo nhiều giọng nhân vật/lip-sync trong change này.

## User Flow

1. Người dùng mở route `Lấy cảm hứng từ video`.
2. Người dùng upload `.mp4` hoặc dán link video công khai.
3. App hiển thị tiến trình bằng tiếng Việt: lấy video, tách tiếng, chuyển lời nói thành chữ, lấy hình ảnh đại diện, phân tích, viết kịch bản mới.
4. Người dùng xem transcript gốc, bản tóm tắt hình ảnh và bản phân tích.
5. Người dùng chọn đầu ra tiếng Việt hoặc tiếng Anh.
6. App viết kịch bản mới mạnh tay, có hook, cấu trúc cảnh/đoạn, lời thoại/narration và gợi ý hình ảnh.
7. Người dùng có thể sửa kết quả hoặc bấm `Đưa vào form AI Video`.
8. App mở `/ai-video?draft=video-inspiration`, điền sẵn Tên dự án, Ý tưởng chính, Kịch bản thô, Nhân vật và bối cảnh, Phong cách video, Bắt buộc phải có, Cần tránh và Phong cách hình ảnh.
9. Người dùng tự chọn thị trường/mục đích video, ngôn ngữ, thời lượng, tỷ lệ, voice và cách chạy rồi mới bấm tạo/chạy trong AI Video.

## Open Questions

- Tên route tiếng Việt cuối cùng nên là `Lấy cảm hứng từ video`, `Video thành kịch bản`, hay `Remix kịch bản video`?
- Visual analysis nên dùng provider nào trong bản đầu: provider vision riêng, Codex nếu hỗ trợ ảnh trong môi trường hiện tại, hay cấu hình mở để người dùng chọn sau?
- Link import nên tải video đầy đủ hay chỉ lấy audio + frame đại diện khi nền tảng cho phép?
