## Why

AI Video Assistant hiện đã tạo được kịch bản, shot ngắn, prompt video, voice và phụ đề, nhưng người dùng vẫn phải tự ghép video trong công cụ bên ngoài. Cơ hội hiện tại là thêm bước dựng nhanh MP4 ngay trong Voicebox bằng cách nhận clip video theo từng shot, dùng thời lượng voice thật làm nguồn timer và tự ghép clip, voice, phụ đề thành video hoàn chỉnh.

## What Changes

- Thêm luồng “Dựng nhanh MP4” cho AI Video project phase 2 sau khi đã có shot, prompt video, voice và subtitle.
- Cho phép người dùng upload video clip cho từng shot, hoặc lưu clip do provider trả về trong tương lai, vào một artifact riêng theo shot.
- Thêm kiểm tra readiness trước render: thiếu clip, thiếu voice bắt buộc, thiếu subtitle khi bật phụ đề, clip không đọc được, FFmpeg chưa sẵn sàng, aspect ratio/resolution không thể chuẩn hóa.
- Thêm render job có trạng thái, tiến độ, output MP4, lỗi tiếng Việt và lịch sử render gần nhất.
- Dùng `audio_duration` thật của voice theo shot làm nguồn thời lượng chính; shot không có narration dùng `duration_seconds` dự kiến.
- Chuẩn hóa clip bằng FFmpeg trước khi concat: resize/crop/pad theo aspect ratio project, chuẩn hóa fps/resolution, trim clip dài, kéo clip ngắn bằng freeze frame cuối, mute audio gốc mặc định.
- Ghép voice track theo thứ tự shot, tạo timeline audio liên tục và mux vào MP4 cuối.
- Hỗ trợ subtitle bằng hai chế độ: burn-in ASS cho video social và sidecar SRT khi người dùng muốn phụ đề rời.
- Thêm UI panel “Dựng nhanh MP4” trong AI Video Assistant để upload clip, xem checklist, chọn tùy chọn render, bắt đầu render, theo dõi trạng thái và tải MP4.
- Không tích hợp provider tạo video trực tiếp trong MVP; provider generation sẽ là phase sau dùng cùng `video_shot_clips`.

## Capabilities

### New Capabilities

- `ai-video-timeline-render`: Quản lý clip video theo shot và render timeline MP4 từ shot clips, voice duration thật, voice audio và phụ đề của AI Video project phase 2.

### Modified Capabilities

- Không có. Capability mới sử dụng output của `ai-video-video-prompt-studio` nhưng không thay đổi contract tạo prompt/voice/subtitle/package nguyên liệu hiện có.

## Impact

- Backend: thêm model/migration cho `video_shot_clips` và `video_render_jobs`, service render timeline, readiness, upload/download/delete clip, render job API và download MP4.
- Backend dependency/runtime: yêu cầu kiểm tra FFmpeg/FFprobe khả dụng; nếu chưa có, backend phải báo lỗi tiếng Việt rõ ràng thay vì crash.
- Storage: thêm thư mục artifact cho shot clips, normalized clips, render manifests, subtitle ASS tạm và MP4 output.
- API: thêm endpoint trong `/ai-video` cho clip theo shot, render readiness, create render job, poll render status và download output.
- Frontend: mở rộng `AIVideoAssistant.tsx` và `apiClient` với panel dựng nhanh, upload clip, checklist, render settings, progress/error/download states.
- Tests: thêm test backend cho readiness, metadata probe, duration normalization plan, render command building, job status, API lỗi; thêm test frontend cho checklist và trạng thái render.
- Documentation: cập nhật hướng dẫn AI Video Assistant để nói rõ Voicebox có thể render MP4 nhanh khi người dùng đã có clip theo shot.
