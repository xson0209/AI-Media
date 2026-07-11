## 1. Schema và Storage

- [x] 1.1 Thêm SQLAlchemy models `VideoShotClip` và `VideoRenderJob` với các field đã mô tả trong design.
- [x] 1.2 Thêm migration idempotent trong `_migrate_ai_video_assistant` để tạo bảng `video_shot_clips` và `video_render_jobs` cho SQLite cũ.
- [x] 1.3 Mở rộng `VIDEO_PROJECT_SUBDIRS` với thư mục `shot_clips`, `render_intermediates`, `render_outputs` và helper filename tiếng Việt an toàn cho MP4.
- [x] 1.4 Cập nhật cleanup khi xóa project để xóa clip upload, intermediate render, ASS tạm và MP4 output.
- [x] 1.5 Thêm Pydantic models cho clip response, clip upload status, render settings, readiness response và render job response.

## 2. FFmpeg và Clip Service

- [x] 2.1 Tạo service phát hiện `ffmpeg` và `ffprobe` từ `PATH` hoặc cấu hình runtime, trả lỗi tiếng Việt khi thiếu.
- [x] 2.2 Implement FFprobe metadata parser để đọc duration, width, height, fps, codec và has_audio từ file video.
- [x] 2.3 Implement upload clip theo shot: validate project/shot phase 2, lưu file, probe metadata, set clip active và deactivate clip active cũ.
- [x] 2.4 Implement delete/replace clip theo shot và đánh dấu render output cũ là stale khi clip thay đổi.
- [x] 2.5 Thêm giới hạn file size/duration/format an toàn và lỗi tiếng Việt cho file không hợp lệ.

## 3. Timeline Readiness và Manifest

- [x] 3.1 Implement render readiness riêng cho project: thiếu clip, clip lỗi, thiếu voice, thiếu subtitle khi burn-in, thiếu FFmpeg/FFprobe và thiếu timer.
- [x] 3.2 Implement duration resolver: shot có narration dùng `audio_duration`, shot không lời dùng `duration_seconds`, thiếu cả hai thì fail readiness.
- [x] 3.3 Implement timeline manifest theo `shot_order` với start/end seconds cộng dồn không gap mặc định.
- [x] 3.4 Thêm cảnh báo khi clip lệch duration quá ngưỡng so với target duration.
- [x] 3.5 Đảm bảo readiness trả danh sách `shot_id` liên quan để frontend highlight đúng shot cần xử lý.

## 4. Render Engine

- [x] 4.1 Implement command builder normalize clip: trim clip dài, freeze frame cuối cho clip ngắn, crop/pad theo aspect ratio, chuẩn hóa resolution/fps/pixel format/codec.
- [x] 4.2 Implement audio timeline builder: concat voice theo shot, thêm silence cho shot không lời và mute audio gốc của clip mặc định.
- [x] 4.3 Implement subtitle burn-in: chuyển SRT/cues sang ASS tạm với style phù hợp aspect ratio và gọi FFmpeg filter để burn vào MP4.
- [x] 4.4 Implement sidecar subtitle mode: render MP4 không burn subtitle và vẫn expose SRT download hiện có.
- [x] 4.5 Implement concat/mux final MP4 và lưu output path, manifest path, subtitle ASS path vào render job.
- [x] 4.6 Truncate/redact FFmpeg stderr trong technical details để debug được nhưng không làm log quá lớn.

## 5. Render Job Lifecycle

- [x] 5.1 Implement create render job API flow: validate readiness, lưu settings snapshot, enqueue background render và trả job id.
- [x] 5.2 Implement background render worker riêng, không dùng TTS serial queue, và giới hạn concurrency an toàn trong MVP.
- [x] 5.3 Cập nhật render job status/progress/current_step sau từng bước render.
- [x] 5.4 Implement failed state với `failure_reason`, `error_code` và output không tải được khi render lỗi.
- [x] 5.5 Implement startup/status sync để đánh failed các job còn running từ session trước.
- [x] 5.6 Implement download MP4 cho job completed mới nhất và lỗi tiếng Việt nếu file output mất.

## 6. API Backend

- [x] 6.1 Thêm endpoints upload/get/delete clip cho từng shot dưới `/ai-video/projects/{project_id}/shots/{shot_id}/clip`.
- [x] 6.2 Thêm endpoint render readiness dưới `/ai-video/projects/{project_id}/render/readiness`.
- [x] 6.3 Thêm endpoints create/list/get render job dưới `/ai-video/projects/{project_id}/render/jobs`.
- [x] 6.4 Thêm endpoint download output dưới `/ai-video/projects/{project_id}/render/jobs/{job_id}/download`.
- [x] 6.5 Cập nhật debug details AI Video để hiển thị clip status và latest render job status.

## 7. Frontend theo design-taste-frontend-v1

- [x] 7.1 Kiểm tra `app/package.json` trước khi import bất kỳ dependency icon/motion/UI mới nào; ghi rõ quyết định dùng dependency hiện có hoặc thêm dependency nếu cần.
- [x] 7.2 Thêm API client methods và TypeScript types cho clip upload/delete, render readiness, render jobs và download MP4.
- [x] 7.3 Tách panel “Dựng nhanh MP4” thành component con của AI Video Assistant để tránh làm `AIVideoAssistant.tsx` phình thêm quá mức.
- [x] 7.4 Implement danh sách shot upload clip với label phía trên input, helper/error phía dưới, empty state, loading skeleton và inline error state.
- [x] 7.5 Implement readiness checklist tiếng Việt, highlight shot thiếu clip/voice/subtitle/timer và action dẫn người dùng tới bước cần xử lý.
- [x] 7.6 Implement render settings UI: resolution preset, fps, fit mode crop/pad, duration mode, subtitle burn-in/sidecar.
- [x] 7.7 Implement render job status/progress/download MP4 với tactile active feedback và motion chỉ dùng transform/opacity.
- [x] 7.8 Áp dụng baseline `design-taste-frontend-v1`: DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4, không emoji, không neon/glow tím-xanh, không `h-screen`, mobile collapse một cột dưới 768px.
- [x] 7.9 Nếu dùng animation liên tục hoặc Framer Motion, tách thành component nhỏ, không dùng React state cho motion liên tục và tránh re-render nặng.

## 8. Tests và Verification

- [x] 8.1 Thêm backend tests cho migration tạo bảng mới và model serialization.
- [x] 8.2 Thêm backend tests cho FFprobe parser và lỗi khi FFmpeg/FFprobe thiếu.
- [x] 8.3 Thêm backend tests cho clip upload/replace/delete và active clip behavior.
- [x] 8.4 Thêm backend tests cho render readiness đủ/thiếu clip/thiếu voice/thiếu subtitle/thiếu timer.
- [x] 8.5 Thêm unit tests cho timeline manifest start/end seconds theo `shot_order` và duration resolver dùng `audio_duration` thật.
- [x] 8.6 Thêm tests cho FFmpeg command builder normalize crop/pad, trim và freeze frame.
- [x] 8.7 Thêm API tests cho render job lifecycle completed/failed/download missing output.
- [x] 8.8 Thêm frontend tests hoặc targeted verification cho panel render: empty/loading/error states, readiness checklist và responsive layout.
- [x] 8.9 Chạy `pytest` backend liên quan, `npm run typecheck` trong `app`, và kiểm tra build/lint phù hợp với repo.

## 9. Documentation

- [x] 9.1 Cập nhật docs AI Video Assistant để mô tả luồng upload clip theo shot và dựng nhanh MP4.
- [x] 9.2 Ghi rõ FFmpeg/FFprobe là runtime requirement cho render MP4 và cách xử lý khi máy chưa có FFmpeg.
- [x] 9.3 Cập nhật changelog hoặc release notes nếu repo đang yêu cầu ghi nhận thay đổi user-facing.
