## Context

AI Video Assistant phase 2 hiện tạo được source blocks, story, scene/shot, prompt video, voice theo shot, subtitle SRT và ZIP nguyên liệu. Luồng này cố ý chưa render MP4; người dùng phải copy prompt sang công cụ tạo video, tải clip về rồi tự ghép clip, voice và phụ đề trong Premiere/CapCut/DaVinci.

Codebase hiện đã có các mảnh quan trọng để dựng timeline:

- `VideoShot` có `shot_order`, `duration_seconds`, `english_narration`, `audio_path`, `audio_duration`, `voice_status`, `subtitle_status`.
- `video_subtitles.py` sinh cue SRT bằng cách cộng dồn `audio_duration` thật theo scene/shot.
- `video_packages.py` đã có readiness pattern, artifact storage và download output.
- `video_storage.py` quản lý thư mục artifact theo project.
- Database dùng SQLite local với migration idempotent trong `backend/database/migrations.py`, không dùng Alembic.
- Frontend AI Video Assistant đang là một component lớn nhưng đã có pattern API client, async state, readiness checklist, upload preview image và download artifact.

Change này thêm bước render local sau khi người dùng đã có clip video từng shot. Đây là capability mới, không thay thế export ZIP nguyên liệu hiện có.

## Goals / Non-Goals

**Goals:**

- Cho phép người dùng upload video clip cho từng shot phase 2 và lưu metadata cần thiết để render.
- Dùng voice duration thật làm nguồn timer chính để clip, voice và subtitle khớp timeline.
- Render MP4 hoàn chỉnh bằng FFmpeg từ shot clips, voice audio và subtitle.
- Cung cấp readiness rõ ràng bằng tiếng Việt trước khi render.
- Cung cấp render job có trạng thái, lỗi, output download và setting đủ tái hiện.
- Thêm UI “Dựng nhanh MP4” trong AI Video Assistant mà không phá workflow prompt/package hiện tại.
- Giữ đường mở cho provider-generated clip sau này bằng cách thiết kế clip source/metadata tổng quát.

**Non-Goals:**

- Không tích hợp Runway, Kling, Veo, Pika, Luma hoặc provider video trực tiếp trong MVP.
- Không thêm timeline editor kéo-thả nhiều track.
- Không hỗ trợ nhạc nền, SFX, B-roll phụ hoặc overlay nâng cao trong phase này.
- Không render realtime preview trong browser.
- Không thay thế ZIP package export; package vẫn dùng cho người muốn dựng ngoài app.
- Không thay đổi TTS engine hoặc logic tạo prompt video.

## Decisions

### 1. MVP upload-first, provider để sau

Người dùng sẽ tạo clip bằng công cụ AI video bên ngoài rồi upload clip vào từng shot. `video_shot_clips` vẫn có field `source` và `provider_metadata` để phase sau có thể lưu clip do provider trả về mà không cần đổi schema lớn.

Phương án khác đã cân nhắc: tích hợp provider ngay. Cách đó hấp dẫn nhưng kéo theo API key, polling, billing, quota, asset expiry, lỗi provider và policy riêng từng bên. Upload-first cho phép render timeline có giá trị ngay và kiểm chứng model dữ liệu trước.

### 2. Thêm `video_shot_clips` thay vì nhét file vào `VideoShot`

Clip là artifact có vòng đời riêng: upload, probe metadata, thay thế, xóa, invalid, có thể có nhiều version. Vì vậy dùng bảng riêng:

- `id`, `project_id`, `shot_id`, `source`, `status`
- `file_path`, `original_filename`, `mime_type`, `size_bytes`
- `duration_seconds`, `width`, `height`, `fps`, `codec`, `has_audio`
- `is_active`, `failure_reason`, `provider`, `provider_asset_id`, `provider_metadata`
- `created_at`, `updated_at`

Mỗi shot render dùng clip active mới nhất. Khi upload clip mới cho shot, clip cũ chuyển `is_active=false` thay vì xóa ngay để tránh phá render job cũ đang tham chiếu file.

### 3. Thêm `video_render_jobs` làm artifact render có trạng thái

Render MP4 có thể mất thời gian và fail ở nhiều điểm, nên không trả file trực tiếp trong request create. Bảng `video_render_jobs` lưu:

- `id`, `project_id`, `status`: `queued|running|completed|failed|cancelled`
- `progress`, `current_step`, `failure_reason`, `error_code`
- `settings_json`: resolution, fps, subtitle mode, normalize mode, mute clip audio, background color
- `readiness_json` snapshot lúc bắt đầu render
- `timeline_manifest_path`, `output_path`, `subtitle_ass_path`
- `started_at`, `completed_at`, `created_at`, `updated_at`

Chỉ job `completed` mới được download. Khi tạo job mới thành công, các job cũ vẫn giữ lịch sử nhưng UI ưu tiên job mới nhất.

### 4. Dùng FFmpeg/FFprobe subprocess trực tiếp

Backend gọi `ffprobe` để đọc metadata và `ffmpeg` để normalize/concat/mux. Không dùng MoviePy vì MoviePy kéo thêm dependency Python lớn, xử lý chậm hơn, khó đóng gói hơn và cuối cùng vẫn dựa vào FFmpeg.

Backend cần service nhỏ, ví dụ `video_rendering.py`, để:

- phát hiện `ffmpeg`/`ffprobe` bằng settings hoặc `PATH`
- chạy subprocess với timeout và log stderr đã truncate/redact
- parse JSON từ ffprobe bằng API có cấu trúc
- build command tách theo bước, dễ test bằng unit test command builder

Nếu FFmpeg thiếu, readiness và render API trả lỗi tiếng Việt như “Chưa tìm thấy FFmpeg. Hãy cài FFmpeg hoặc cấu hình đường dẫn trong Settings.”

### 5. Voice duration thật là nguồn thời gian chính

Timeline duration từng shot được tính như sau:

1. Nếu shot có narration bắt buộc: dùng `shot.audio_duration` sau khi voice completed.
2. Nếu shot không có narration: dùng `shot.duration_seconds`.
3. Nếu cả hai thiếu hoặc không hợp lệ: readiness fail.

Start/end time của shot và subtitle là tổng cộng dồn theo `shot_order`, không có gap mặc định. Điều này giữ voice, subtitle và video cùng một trục thời gian.

### 6. Normalize clip theo target duration trước khi concat

Mỗi clip upload được normalize thành một intermediate MP4 đồng nhất codec, fps, resolution, pixel format và audio policy. Mặc định:

- Clip dài hơn target: trim từ đầu về đúng target duration.
- Clip ngắn hơn target: giữ clip gốc rồi freeze frame cuối cho đủ target duration.
- Slow/fast chỉ là option khi lệch nhẹ theo ngưỡng cấu hình, không mặc định vì dễ làm clip AI méo motion.
- Loop chỉ là option cho clip không có narration hoặc clip ambience, không mặc định.

Normalize cũng xử lý aspect ratio theo project:

- `fit_mode=crop`: scale rồi crop center để đầy khung.
- `fit_mode=pad`: scale vừa khung rồi thêm nền màu.

Default nên là crop cho social video 9:16, nhưng UI cho phép đổi sang pad nếu người dùng không muốn mất mép hình.

### 7. Audio clip gốc mute mặc định

Voicebox voice là nguồn audio chính nên render mặc định mute toàn bộ audio gốc trong clip. Phase này không mix audio gốc để tránh lệch nhịp, echo hoặc âm thanh provider lẫn với voice. Có thể thêm option “giữ audio clip nền nhỏ” ở phase sau.

Voice audio được concat theo thứ tự shot có narration. Với shot không lời, render tạo silence cùng duration để giữ timeline audio khớp video.

### 8. Subtitle có hai mode: burn-in ASS và sidecar SRT

SRT hiện có đủ timing theo voice. Khi người dùng chọn burn-in, backend chuyển cue sang ASS tạm với style phù hợp aspect ratio, rồi dùng FFmpeg filter để burn vào video cuối. Khi chọn sidecar, MP4 không burn subtitle; UI vẫn cho tải SRT hiện có và render job lưu subtitle mode trong settings.

Default là burn-in vì mục tiêu là video social hoàn chỉnh có thể đăng ngay.

### 9. Render job chạy background, không dùng TTS serial queue

TTS queue hiện serialize inference để tránh tranh GPU. FFmpeg render là tác vụ IO/CPU và không nên chặn queue voice. Thêm cơ chế background task riêng cho render, có thể giới hạn một render job chạy cùng lúc cho mỗi project hoặc toàn app trong MVP.

Render job cập nhật trạng thái trong DB sau từng bước:

```text
queued -> running/probing -> normalizing clips -> concatenating -> muxing subtitle/audio -> completed
                                      │
                                      └── failed
```

Nếu app restart khi job đang running, startup hoặc status sync đánh job đó thành `failed` với thông báo “Render bị gián đoạn khi ứng dụng đóng.”

### 10. Readiness riêng cho render, không trộn với package readiness

Package readiness kiểm tra ZIP nguyên liệu; render readiness kiểm tra MP4 final. Tách endpoint giúp UI không nhầm:

- `/ai-video/projects/{project_id}/render/readiness`
- `/ai-video/projects/{project_id}/render/jobs`
- `/ai-video/projects/{project_id}/render/jobs/{job_id}`
- `/ai-video/projects/{project_id}/render/jobs/{job_id}/download`

Render readiness có reasons tiếng Việt và ID shot liên quan để UI scroll/highlight shot thiếu clip hoặc thiếu voice.

### 11. UI là panel vận hành, không phải timeline editor

Trong `AIVideoAssistant.tsx`, thêm section/panel “Dựng nhanh MP4” gần khu export. UI cần có:

- Danh sách shot với trạng thái clip: thiếu clip, clip lỗi, clip sẵn sàng.
- Upload/replace/delete clip từng shot.
- Checklist render readiness.
- Settings gọn: resolution preset, fps, fit mode, duration mode, subtitle mode.
- Nút “Dựng MP4”, trạng thái job, progress, lỗi và nút tải MP4.

Copy UI bằng tiếng Việt, tránh thuật ngữ nặng nếu không mở debug. Các lỗi kỹ thuật FFmpeg chi tiết chỉ nên nằm trong debug/details.

Panel render phải tích hợp baseline `design-taste-frontend-v1`: DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4. Khi implement frontend, developer phải kiểm tra `app/package.json` trước khi import thêm thư viện icon/motion/Tailwind helper; không dùng emoji; không dùng neon/glow tím-xanh kiểu AI; không dùng `h-screen`; form phải có label phía trên, helper/error phía dưới; loading dùng skeleton theo layout; empty/error states phải hoàn chỉnh. Vì app hiện dùng React/Vite/Tailwind 4, `framer-motion` và `lucide-react`, mọi animation phải tách thành component nhỏ và chỉ animate `transform`/`opacity`; nếu muốn dùng đúng icon path theo design-taste-v1 như `@phosphor-icons/react` hoặc `@radix-ui/react-icons`, dependency đó phải được thêm rõ ràng trong task implementation thay vì import ngầm.

## Risks / Trade-offs

- FFmpeg không có trên máy người dùng → Readiness check sớm, lỗi tiếng Việt rõ ràng, hướng dẫn cài/cấu hình; packaging có thể bundle FFmpeg ở phase sau.
- Clip AI có duration/aspect ratio/fps rất khác nhau → Normalize từng clip về intermediate thống nhất trước concat.
- Freeze frame cuối làm video đứng hình nếu clip thiếu quá nhiều → Readiness cảnh báo khi clip ngắn hơn target quá ngưỡng, UI gợi ý render lại clip dài hơn.
- Trim từ đầu có thể cắt mất khoảnh khắc quan trọng → MVP dùng trim đầu đơn giản; phase sau có thể cho chọn trim start hoặc upload lại clip.
- Burn-in subtitle phụ thuộc font có sẵn trong môi trường frozen app → Dùng ASS style với font fallback phổ biến, test packaged build, fallback sang SRT sidecar nếu filter fail.
- Render task bị gián đoạn khi app đóng → Job đang running được đánh failed khi sync lại, output tạm có thể cleanup an toàn.
- File upload lớn làm tốn disk → Giới hạn size/duration, hiển thị size, xóa artifact khi delete project, cleanup intermediate của job failed/cancelled.
- UI AI Video Assistant đang lớn → Giữ panel render thành component con nếu cần để tránh làm file chính khó bảo trì.

## Migration Plan

1. Thêm SQLAlchemy models `VideoShotClip` và `VideoRenderJob`.
2. Thêm migration idempotent trong `_migrate_ai_video_assistant` để tạo bảng mới nếu chưa tồn tại.
3. Mở rộng `VIDEO_PROJECT_SUBDIRS` với `shot_clips`, `render_intermediates`, `render_outputs`.
4. Thêm service render/readiness/upload clip nhưng không đổi dữ liệu project cũ.
5. Thêm API mới dưới `/ai-video` và frontend client methods.
6. Thêm UI panel, mặc định ẩn render action nếu project chưa phải phase 2 hoặc chưa có shot.
7. Cập nhật docs. Rollback an toàn: ẩn UI/API render; bảng mới và artifact mới không ảnh hưởng voice/prompt/package hiện có.

## Open Questions

- Có cần Settings UI để cấu hình đường dẫn FFmpeg ngay trong phase này không, hay chỉ kiểm tra `PATH` trước rồi bổ sung Settings sau?
- Có cần cancel render job trong MVP không, hay chỉ cần trạng thái running/failed/completed và cho phép render job mới sau khi job cũ kết thúc?
- Default resolution nên theo aspect ratio project với 1080x1920 cho 9:16, 1920x1080 cho 16:9 và 1080x1080 cho 1:1; có cần preset 720p để render nhanh hơn ngay từ MVP không?
