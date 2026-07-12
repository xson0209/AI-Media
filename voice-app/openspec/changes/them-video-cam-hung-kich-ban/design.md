## Approach

Tạo một workflow độc lập với AI Video route hiện tại:

```text
/video-inspiration UI
  -> /video-inspiration API
  -> ingest video từ upload hoặc link
  -> extract audio + frames
  -> transcribe speech
  -> analyze visuals
  -> synthesize analysis
  -> write bold new script
  -> build AI Video form draft from final script + analysis
  -> open /ai-video?draft=video-inspiration
  -> fill AI Video input fields only; user configures market/language/duration/run mode before creating
```

Route mới vẫn có thể tái sử dụng service nền như Whisper, FFmpeg và AI planning, nhưng không thêm màn hình mới vào `AIVideoAssistant` và không thêm endpoint ingestion dưới `/ai-video`. Handoff mặc định là draft frontend vào form AI Video, không tạo project/chạy auto-run cho tới khi người dùng bấm tạo trong AI Video.

## Naming

- Frontend route: `/video-inspiration`.
- Backend router prefix: `/video-inspiration`.
- UI label: `Lấy cảm hứng từ video`.
- Change/capability: `video-cam-hung-kich-ban`.

Tên này dễ hiểu cho người không rành kỹ thuật: mục tiêu là lấy cảm hứng và viết lại kịch bản, không phải “transcode”, “ASR”, “vision pipeline”.

## Data Model

Thêm bảng mới cho workflow riêng, ví dụ:

- `video_inspiration_jobs`
  - `id`
  - `source_type`: `upload` hoặc `url`
  - `source_url`
  - `original_filename`
  - `source_platform`: `youtube`, `tiktok`, `facebook`, `instagram`, `unknown`
  - `source_path`
  - `audio_path`
  - `status`
  - `current_step`
  - `progress`
  - `target_language`: `vi` hoặc `en`
  - `rewrite_mode`: mặc định `bold_remix`
  - `transcript_text`
  - `transcript_language`
  - `visual_summary`
  - `analysis_json`
  - `rewritten_script`
  - `created_video_project_id`
  - `failure_reason`, `error_code`
  - timestamps

- `video_inspiration_frames`
  - `id`
  - `job_id`
  - `frame_path`
  - `timestamp_seconds`
  - `description_vi`
  - `technical_metadata_json`

Artifact file nên nằm dưới:

```text
data/video_inspiration/{job_id}/
  source/
  audio/
  frames/
  transcript.txt
  analysis.json
  rewritten-script.txt
```

## API Design

Đề xuất endpoint riêng:

- `POST /video-inspiration/jobs/upload`
  - nhận `.mp4`, target language, tùy chọn model Whisper.
- `POST /video-inspiration/jobs/from-url`
  - nhận URL công khai từ YouTube/TikTok/Facebook/Instagram.
- `GET /video-inspiration/jobs`
  - danh sách job gần đây.
- `GET /video-inspiration/jobs/{job_id}`
  - trạng thái, transcript, analysis, script.
- `POST /video-inspiration/jobs/{job_id}/analyze`
  - chạy hoặc chạy lại transcript + visual analysis.
- `PUT /video-inspiration/jobs/{job_id}/transcript`
  - cho người dùng sửa transcript trước khi viết lại.
- `POST /video-inspiration/jobs/{job_id}/rewrite`
  - viết kịch bản mới theo target language.
- `POST /video-inspiration/jobs/{job_id}/create-ai-video-project`
  - endpoint API cũ để tạo AI Video project phase 2 từ kịch bản mới khi caller thật sự muốn tạo project từ backend.
  - mặc định `start_full_materials = false`; chỉ chạy tiếp AI Video auto-run khi caller đặt rõ `start_full_materials = true`.

Endpoint tạo AI Video project vẫn nằm dưới `/video-inspiration` để giữ route mới độc lập. UI chính của Video Inspiration không gọi endpoint này khi người dùng chỉ muốn đưa dữ liệu sang form AI Video để cấu hình.

## Link Import

Link YouTube/TikTok/Facebook/Instagram là best-effort:

- Chỉ nhận link công khai.
- Không xử lý video riêng tư, cần đăng nhập, DRM, livestream hoặc CAPTCHA.
- Nếu tải thất bại, UI báo bằng tiếng Việt và đề nghị upload `.mp4`.
- Không lưu cookie hoặc credential nền tảng trong MVP.
- Không log full URL nếu có token nhạy cảm; technical details phải redaction.

Implementation có thể dùng một downloader adapter. Adapter phải có timeout, giới hạn dung lượng/thời lượng và error code thân thiện.

## Audio And Transcript

Audio path dùng FFmpeg để trích âm thanh từ `.mp4` hoặc video tải từ link:

- Convert về WAV mono 16 kHz hoặc định dạng mà Whisper backend đọc ổn định.
- Tái sử dụng Whisper STT hiện có.
- Lưu transcript raw.
- Cho phép người dùng sửa transcript trước khi viết lại, vì STT có thể sai với tiếng ồn hoặc giọng khó.

Nếu video không có lời nói:

- Transcript status là `empty`.
- App vẫn có thể chạy visual-only analysis nếu visual provider sẵn sàng.
- UI nói rõ “video này không có lời nói rõ ràng”.

## Visual Analysis

Visual analysis cần làm thật, không bịa từ transcript:

- Dùng FFmpeg/FFprobe lấy metadata và frame đại diện.
- Lấy frame theo khoảng thời gian đều nhau và/hoặc scene-change.
- Giới hạn số frame để không tốn tài nguyên, ví dụ 8-20 frame cho MVP.
- Gửi frame cho một `vision analyzer` abstraction để tạo mô tả tiếng Việt.
- Nếu chưa có vision provider, workflow dừng ở trạng thái `needs_vision_provider` hoặc cho phép người dùng tiếp tục audio-only với cảnh báo rõ.

Visual analysis cần trả về:

- Bối cảnh/chủ thể chính.
- Nhân vật, trang phục, đạo cụ nếu thấy rõ.
- Mood, màu sắc, ánh sáng, camera/framing.
- Nhịp hình ảnh và các khoảnh khắc nổi bật.
- Các điểm có thể lấy cảm hứng cho kịch bản mới.

## Script Rewrite

Rewrite mode mặc định là `bold_remix`:

- Không copy lại nguyên văn video gốc.
- Không chỉ đổi câu chữ.
- Có thể thay hook, cấu trúc, ví dụ, nhịp kể, cách mở và payoff.
- Giữ lại insight/cảm hứng chính đã phân tích.
- Output script theo `target_language`: `vi` hoặc `en`.
- UI giải thích và analysis vẫn luôn tiếng Việt.

Prompt viết lại nên yêu cầu output có cấu trúc:

- Tên ý tưởng mới.
- Big idea.
- Hook 0-3 giây.
- Kịch bản/narration chính.
- Cấu trúc cảnh hoặc segment.
- Gợi ý hình ảnh theo từng đoạn.
- Ghi chú tránh copy quá sát video gốc.

## AI Video Handoff

Khi người dùng bấm `Đưa vào form AI Video`:

- Frontend tạo một draft trong `sessionStorage` và mở `/ai-video?draft=video-inspiration`.
- Không gọi endpoint tạo project và không gọi AI Video auto-run trong hành động này.
- AI Video đọc draft, bỏ chọn project hiện tại, chuyển `Cách chạy` về `Thủ công` và điền form tạo dự án mới.
- Draft điền đủ các ô: `Tên dự án`, `Ý tưởng chính`, `Kịch bản thô`, `Nhân vật và bối cảnh`, `Phong cách video`, `Bắt buộc phải có`, `Cần tránh` và `Phong cách hình ảnh`.
- Nội dung draft phải gom rewritten script, big idea, hook, segment outline, transcript gốc, visual summary, mô tả frame đại diện, nhịp hình ảnh, điểm mạnh, điểm yếu, cơ hội viết mới, ghi chú phân tích và định hướng người dùng khi có.
- Draft không ghi đè các cấu hình người dùng cần tự chọn sau đó: thị trường/mục đích video, ngôn ngữ cuối cùng, số prompt, giây/prompt, cảnh nhỏ/prompt, tỷ lệ, voice và output auto-run.
- Người dùng tự chọn thị trường/mục đích video, ngôn ngữ, số prompt, giây/prompt, cảnh nhỏ/prompt, tỷ lệ, voice và cách chạy trước khi bấm tạo project trong AI Video.
- Endpoint `/video-inspiration/jobs/{job_id}/create-ai-video-project` có thể giữ cho API cũ, nhưng default `start_full_materials = false`; chỉ auto-run khi caller đặt rõ `start_full_materials = true`.
- Luồng này không yêu cầu tạo MP4 cuối; Video Inspiration chỉ chuẩn bị input để AI Video phát triển tiếp khi người dùng cấu hình xong.

## UI Direction

Route mới là workspace thật, không phải landing page:

- Khu nhập nguồn: upload file hoặc dán link.
- Khu chọn ngôn ngữ kịch bản mới: tiếng Việt / tiếng Anh.
- Progress rõ ràng bằng tiếng Việt.
- Tabs hoặc sections: Transcript, Hình ảnh, Phân tích, Kịch bản mới.
- Nút chính: `Phân tích video`, `Viết kịch bản mới`, `Đưa vào form AI Video`.
- Sau khi chuyển thành công, AI Video hiển thị form đã điền sẵn và thông báo người dùng cần tự chọn thị trường, ngôn ngữ, thời lượng, tỷ lệ, voice và cách chạy trước khi tạo dự án.
- Error inline: link không tải được, thiếu FFmpeg, thiếu Whisper, thiếu vision provider, video quá dài/quá nặng.

## Safety And Privacy

- Không log full video content, transcript dài, full URL có token hoặc frame binary trong technical details.
- Giới hạn dung lượng upload và thời lượng video.
- Xóa temp file khi job fail trước khi persist.
- Người dùng phải có quyền sử dụng nội dung video đưa vào.
- Với link mạng xã hội, app không cố bypass nền tảng.

## Risks

- Link social thay đổi liên tục và có thể fail: giảm rủi ro bằng upload fallback.
- Visual analysis cần provider ảnh; nếu thiếu provider mà vẫn cho chạy sẽ tạo phân tích giả: phải chặn hoặc cảnh báo rõ.
- Video dài có thể tốn RAM/GPU: giới hạn thời lượng, sampling frame và chạy theo background job.
- Viết lại quá sát video gốc có rủi ro bản quyền: default `bold_remix` phải yêu cầu biến đổi mạnh và tránh sao chép nguyên văn.
- Tách route mới nhưng vẫn chuyển sang AI Video có thể gây nhầm: UI phải nói rõ bước đầu là “lấy cảm hứng và viết kịch bản”, bước sau là “AI Video tạo prompt, voice và SRT”.
- Chạy full materials có thể tốn thời gian hoặc fail do thiếu voice/provider: cần trạng thái tiến trình rõ, lỗi tiếng Việt và khả năng chạy lại trong AI Video.
