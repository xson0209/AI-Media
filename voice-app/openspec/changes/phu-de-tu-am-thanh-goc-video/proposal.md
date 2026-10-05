## Why
Khi chọn Âm thanh gốc, người dùng cần chọn có hoặc không có phụ đề rồi dựng MP4. Phụ đề phải lấy từ lời nói thực tế trong audio của clip và giữ cùng kiểu hiển thị với luồng Voice.

## What changes
- Trích audio từ clip active và nhận dạng lời nói theo timestamp.
- Cho phép tạo subtitle từ clip audio mà không yêu cầu voice/TTS.
- Giữ lựa chọn subtitle `burn_in`, `sidecar`, `none`; `none` bỏ qua subtitle.
- Render clip-only giữ nguyên audio gốc; burn-in dùng cùng ASS/karaoke style hiện tại.
- Đánh dấu subtitle stale khi clip nguồn thay đổi.

## Scope
Backend subtitle/transcription/render readiness và UI copy/flow liên quan. Không thay đổi mặc định Voice hiện có.
