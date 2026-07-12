## 1. Scope And Architecture

- [x] 1.1 Tạo backend router riêng `/video-inspiration`, đăng ký trong `backend/routes/__init__.py`, không thêm endpoint ingestion dưới `/ai-video`.
- [x] 1.2 Tạo frontend route riêng `/video-inspiration` và thêm entry sidebar/menu tiếng Việt phù hợp.
- [x] 1.3 Định nghĩa trạng thái job, error code và step label tiếng Việt cho toàn workflow.
- [x] 1.4 Thêm models/schema Pydantic và TypeScript types cho job, frame, transcript, analysis và rewritten script.

## 2. Storage And Migrations

- [x] 2.1 Thêm ORM models cho `video_inspiration_jobs` và `video_inspiration_frames`.
- [x] 2.2 Thêm migration idempotent tạo bảng/index mới theo pattern `backend/database/migrations.py`.
- [x] 2.3 Thêm helper storage dưới `data/video_inspiration/{job_id}` cho source, audio, frames, transcript, analysis và script.
- [x] 2.4 Đảm bảo cleanup file tạm khi upload/link import/analyze fail trước khi job persist hoàn chỉnh.

## 3. Input Ingestion

- [x] 3.1 Implement upload `.mp4` với kiểm tra extension, MIME, size, duration và lỗi tiếng Việt.
- [x] 3.2 Implement link import best-effort cho URL công khai YouTube/TikTok/Facebook/Instagram qua downloader adapter.
- [x] 3.3 Không xử lý link cần login, private, DRM, livestream hoặc CAPTCHA; trả lỗi rõ và đề nghị upload file.
- [x] 3.4 Redact URL/token nhạy cảm trong logs và technical details.
- [x] 3.5 Đóng gói `yt-dlp` trong backend dependency và cho downloader adapter dùng module `yt_dlp` trong venv khi máy không có lệnh `yt-dlp` toàn hệ thống.
- [x] 3.6 Thêm lượt tải dự phòng và phân loại lỗi link mạng xã hội rõ hơn khi nền tảng chặn, yêu cầu đăng nhập/xác minh, video quá nặng hoặc link không khả dụng.
- [x] 3.7 Thêm fallback YouTube player client `android/ios/web/tv`, giới hạn tải khoảng 720p và tùy chọn dùng phiên đăng nhập trình duyệt khi người dùng bật rõ ràng.
- [x] 3.8 Đóng gói FFmpeg trong backend venv qua dependency project, cho `yt-dlp` dùng FFmpeg đó và fallback đọc metadata bằng FFmpeg khi máy chưa có FFprobe global.
- [x] 3.9 Ghép lại video/audio khi nền tảng trả stream tách riêng để job link import lưu một MP4 có cả hình và tiếng.

## 4. Audio And Transcript

- [x] 4.1 Dùng FFmpeg trích audio từ video thành WAV mono 16 kHz hoặc format Whisper đọc ổn định.
- [x] 4.2 Tái sử dụng Whisper backend hiện có để transcribe audio.
- [x] 4.3 Lưu transcript raw, language hint/result, duration và status.
- [x] 4.4 Thêm API cho người dùng sửa transcript trước khi rewrite.
- [x] 4.5 Xử lý video không có lời nói rõ ràng bằng trạng thái thân thiện, không crash.

## 5. Visual Analysis

- [x] 5.1 Dùng FFmpeg/FFprobe lấy metadata video và frame đại diện theo thời gian/scene-change.
- [x] 5.2 Giới hạn số frame phân tích để tránh quá tải tài nguyên.
- [x] 5.3 Tạo vision analyzer abstraction và readiness check.
- [x] 5.4 Nếu vision provider chưa sẵn sàng, báo `needs_vision_provider` hoặc cho audio-only khi người dùng xác nhận.
- [x] 5.5 Lưu mô tả hình ảnh tiếng Việt theo từng frame và visual summary tổng.

## 6. Analysis And Rewrite

- [x] 6.1 Tạo structured prompt/schema phân tích video từ transcript + visual summary.
- [x] 6.2 Analysis phải trả về ý chính, hook, cấu trúc, nhân vật/bối cảnh, nhịp dựng, điểm mạnh/yếu và cơ hội viết mới.
- [x] 6.3 Tạo rewrite mode `bold_remix` mặc định: viết mới mạnh tay, không paraphrase sát.
- [x] 6.4 Cho chọn output language `vi` hoặc `en`; UI/analysis helper vẫn tiếng Việt.
- [x] 6.5 Lưu rewritten script, big idea, hook, segment/scene outline và visual suggestions.
- [x] 6.6 Cho chạy lại rewrite sau khi user sửa transcript hoặc đổi ngôn ngữ đầu ra.
- [x] 6.7 Thêm định hướng ý tưởng không bắt buộc của người dùng vào job, rewrite prompt và draft/form chuyển sang AI Video.

## 7. AI Video Bridge

- [x] 7.1 Giữ endpoint `/video-inspiration/jobs/{job_id}/create-ai-video-project` cho API cũ, nhưng đổi mặc định `start_full_materials = false` để không auto-run nếu caller không yêu cầu rõ.
- [x] 7.2 Thêm draft handoff frontend từ Video Inspiration sang AI Video bằng `sessionStorage` và query `?draft=video-inspiration`.
- [x] 7.3 Khi user bấm đưa sang AI Video, frontend mở `/ai-video` ở form tạo dự án mới, không tạo project, không chọn project vừa tạo và không gọi auto-run.
- [x] 7.4 Draft điền đủ `Tên dự án`, `Ý tưởng chính`, `Kịch bản thô`, `Nhân vật và bối cảnh`, `Phong cách video`, `Bắt buộc phải có`, `Cần tránh` và `Phong cách hình ảnh`.
- [x] 7.5 Draft phải đưa cả dữ liệu phân tích như nhịp hình ảnh, điểm mạnh, điểm yếu, cơ hội viết mới, ghi chú, visual summary, mô tả frame đại diện, transcript gốc và định hướng người dùng vào các ô phù hợp.
- [x] 7.6 AI Video tự chuyển sang chế độ `Thủ công` sau khi nhận draft, nhưng không ghi đè thị trường/mục đích, ngôn ngữ cuối cùng, thời lượng, tỷ lệ, voice và output auto-run để người dùng tự chọn trước khi bấm tạo.
- [x] 7.7 Nếu người dùng muốn chạy nhanh sau đó, họ phải tự chọn `Dựng nhanh` hoặc auto-run trong AI Video; Video Inspiration không tự kích hoạt.
- [x] 7.8 Không yêu cầu tạo MP4 cuối trong luồng này; Video Inspiration chỉ chuẩn bị input để AI Video phát triển tiếp khi người dùng cấu hình xong.

## 8. UI

- [x] 8.1 Xây UI route mới bằng tiếng Việt: upload/link input, chọn ngôn ngữ script mới, progress, transcript, hình ảnh, phân tích, kịch bản mới.
- [x] 8.2 Thêm loading skeleton/progress step rõ ràng cho non-tech user.
- [x] 8.3 Error inline cho link fail, file quá lớn, thiếu FFmpeg, thiếu Whisper, thiếu vision provider, video không có lời nói.
- [x] 8.4 Cho sửa transcript và chạy lại rewrite.
- [x] 8.5 Thêm nút `Đưa vào form AI Video` để chỉ điền form, chưa chạy.
- [x] 8.6 Thêm ô `Mong muốn phát triển thêm ý tưởng` không bắt buộc, có lưu định hướng và dùng khi viết kịch bản mới.

## 9. Tests And Verification

- [x] 9.1 Test upload MP4 valid/invalid và giới hạn size/duration.
- [x] 9.2 Test audio extraction và transcript path với Whisper mock/stub.
- [x] 9.3 Test link import fail trả lỗi tiếng Việt và không crash.
- [ ] 9.4 Test visual frame extraction và provider-not-ready behavior.
- [x] 9.5 Test rewrite prompt/schema có target language đúng và `bold_remix`.
- [x] 9.6 Test create AI Video project từ job không gọi `/ai-video` route ingestion và tạo source blocks đúng.
- [ ] 9.7 Test handoff mở `/ai-video?draft=video-inspiration`, điền đúng các ô nội dung/visual style, không chọn project cũ và không ghi đè cấu hình market/ngôn ngữ/thời lượng/cách chạy.
- [x] 9.8 Test backend handoff chỉ auto-run `full_materials` khi request đặt `start_full_materials = true`; mặc định không auto-run.
- [ ] 9.9 Test frontend route render, progress/error states và không làm hỏng `/ai-video`.
- [x] 9.10 Test định hướng người dùng được lưu, đưa vào rewrite prompt, xóa script cũ khi đổi, và đưa vào draft AI Video.
