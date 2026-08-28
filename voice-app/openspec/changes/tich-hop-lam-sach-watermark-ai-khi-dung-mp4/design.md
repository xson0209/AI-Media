## Context

Pipeline dựng MP4 hiện lấy active clip theo shot, normalize bằng FFmpeg vào `render_cache/normalized`, áp dụng enhanced effects nếu có, concat video, dựng audio timeline và mux phụ đề/audio thành `final.mp4`. Clip provider đã có `provider`, hiện luồng tự động chỉ tạo clip `veo`. Render settings được lưu trong `VideoRenderJob.settings_json`; render thủ công truyền settings từ UI, còn auto-render dùng defaults backend.

Repo `D:/AI Media/AI Media Project/remove watermark` cung cấp Python API `remove_video_all` cho visible provider marks và metadata, nhưng video API hiện nằm trên revision chưa có release tag chứa đầy đủ feature. Runtime video kéo PyAV/OpenCV/C2PA, còn diffusion/SynthID yêu cầu dependency xung đột với backend Voicebox. Voicebox cũng tự tìm FFmpeg qua env/PATH/imageio-ffmpeg, trong khi worker bên ngoài chỉ nhìn thấy PATH.

Các file render/API/UI đã có thay đổi chưa commit từ những change khác, đặc biệt Veo native Vietnamese speech và enhanced render. Implementation phải patch trên trạng thái hiện tại, giữ nguyên audio source và các behavior đang có.

## Goals / Non-Goals

**Goals:**

- Cho người dùng chủ động bật làm sạch visible AI mark và verified AI metadata khi dựng MP4.
- Xử lý từng clip trước normalize, định tuyến rõ `veo` cho provider clip và giữ nguyên source artifact.
- Cô lập dependency qua một Python worker có contract JSON, readiness, timeout và revision rõ ràng.
- Cache derivative theo source identity + policy + worker revision để render lại không xử lý pixel lặp lại.
- Fail rõ khi cleanup được yêu cầu nhưng worker không sẵn sàng hoặc encode thất bại; no-signal là no-op hợp lệ.
- Giữ pipeline cũ không đổi khi setting tắt và để auto-render mặc định an toàn là tắt cleanup.
- Ghi kết quả theo shot vào timeline manifest/render cache summary để debug và audit được.

**Non-Goals:**

- Không chạy video SynthID/invisible regeneration, diffusion, GPU model hoặc provider oracle.
- Không tự động xóa stock/agency/marketplace watermark, generic logo hoặc asset bên thứ ba.
- Không thay thế UI dựng timeline bằng editor nhiều track.
- Không xóa hoặc ghi đè clip gốc.
- Không tự cài dependency/network model trong readiness hoặc render job.
- Không bảo đảm một video không còn mọi loại watermark khi detector không tìm thấy signal được hỗ trợ.

## Decisions

### 1. Worker process cô lập với JSON contract

Thêm `backend/workers/video_watermark_worker.py` chỉ dùng stdlib và import `remove_ai_watermarks` bên trong action. Backend service mới chịu trách nhiệm tìm Python/package root, truyền `PYTHONPATH`, thêm thư mục FFmpeg/FFprobe vào `PATH`, chạy `--check` hoặc gửi JSON request qua stdin, giới hạn timeout và parse đúng một JSON response.

Development root mặc định là sibling `../remove watermark`, nhưng có thể override bằng `VOICEBOX_WATERMARK_ROOT`; Python có thể override bằng `VOICEBOX_WATERMARK_PYTHON`. Không hard-code drive/path vào product logic. Worker revision lấy từ Git SHA khi có và trở thành một phần cache/report.

Phương án import trực tiếp vào backend đơn giản hơn nhưng làm PyInstaller/runtime chính kéo PyAV/OpenCV/C2PA và không tạo boundary cho dependency conflict tương lai. Phương án gọi CLI thô không có JSON result đầy đủ cho `video all` và khó phân biệt no-signal/failure một cách ổn định.

### 2. Dùng public API `remove_video_all`, không dùng invisible

Worker gọi `remove_video_all(source, output, mark=..., backend=..., temporal_consistency=True, include_invisible=False)`. API luôn tạo same-container output, xử lý một stable visible mark khi có và strip verified metadata. Kết quả được serialize thành JSON gồm mark/frame counts/metadata.

`include_invisible` không xuất hiện trong render settings và worker luôn cưỡng bức false. Điều này ngăn vô tình chạy VAE profile 512px/12fps hoặc kéo transformers 5.x vào backend hiện tại.

### 3. Xử lý trước normalize theo từng clip

Trong `_render_job_steps`, cleanup chạy sau khi resolve source clip nhưng trước `_normalize_clip_with_cache`. Clip provider `veo` dùng mark explicit `veo`; source upload hoặc provider không nằm trong registry dùng `auto`. Audio timeline tiếp tục đọc active source clip hiện có, đặc biệt Veo native speech, nên derivative chỉ ảnh hưởng video path và không tạo hồi quy audio.

Phương án xử lý final MP4 bị loại vì chỉ có thể chọn một stable mark cho toàn compilation, có thể gặp nhiều provider, dễ ảnh hưởng phụ đề burn-in và phải transcode toàn output.

### 4. Cache riêng bên trong render cache

Derivative và report lưu dưới `render_cache/watermark/`. Cache key gồm:

- cache schema version;
- resolved source path, size và `mtime_ns`;
- provider/mark;
- fill backend;
- temporal consistency;
- package root/revision;
- worker protocol version.

Output được viết qua temp file cùng suffix, validate tồn tại/không rỗng rồi atomic replace. JSON report chỉ được publish sau output. Cache report hỏng hoặc thiếu output luôn là miss. Render cache prune/clear hiện có tự bao phủ subfolder này.

### 5. Settings/readiness an toàn

`VideoRenderSettings` thêm `watermark_cleanup` mặc định false và `watermark_backend` chỉ nhận `cv2|migan`, mặc định `cv2`. Readiness chỉ probe worker khi setting bật. Nếu worker thiếu Python/package/dependency/FFmpeg, `ready=false`, trả reason tiếng Việt cùng `watermark_cleanup_ready=false`.

Auto-render đang dùng `VideoRenderSettings()` nên cleanup vẫn tắt mặc định. Change này không tự bật thay người dùng; khi một caller sau này truyền/persist render settings, cùng model/contract sẽ được dùng.

### 6. Strict failure và truthful reporting

Khi setting bật, worker timeout, protocol invalid, encode failure hoặc output rỗng làm render fail với error code `VIDEO_RENDER_WATERMARK_*`. Trường hợp detector không tìm thấy mark vẫn thành công vì `remove_video_all` tạo passthrough/metadata-clean output; manifest ghi `visible_mark=null` và không dùng wording “sạch hoàn toàn”.

Timeline manifest thêm top-level `watermark_cleanup` gồm enabled/backend/runtime revision/items. `render-cache-summary.json` thêm hit/miss. UI mô tả đây là các dấu AI được hỗ trợ trên nội dung người dùng có quyền chỉnh sửa.

### 7. Backend chất lượng

MVP hỗ trợ `cv2` và `migan`; không cho `auto` để tránh vô tình chọn LaMa nặng. `cv2` là default không model. `migan` chỉ ready khi environment worker có dependency/model runtime cần thiết; model download không được tự kích hoạt trong readiness.

## Risks / Trade-offs

- [Video bị encode thêm một lần trước normalize] → Cache derivative độc lập, chỉ chạy khi người dùng bật và reuse khi subtitle/voice/settings khác thay đổi.
- [Upstream video API chưa có release tag ổn định] → Ghi exact Git SHA vào readiness/cache/manifest, hỗ trợ root override và đặt feature mặc định off.
- [Worker environment không có FFmpeg trên PATH] → Backend prepend directory của FFmpeg/FFprobe đã detect trước khi spawn.
- [No-signal bị hiểu nhầm là video sạch] → Dùng status/report trung thực, không hiển thị claim tuyệt đối.
- [Cleanup làm hỏng nền có cấu trúc] → Giữ original, cho chọn MI-GAN, không xóa derivative cũ trong lúc job đang dùng.
- [Worker treo hoặc log quá lớn] → Timeout cấu hình, capture stderr có giới hạn và atomic output.
- [Chồng lấn với Veo native speech] → Chỉ thay input video cho normalize; audio builder tiếp tục dùng active source clip.
- [Dirty worktree và active enhanced-render change] → Patch nhỏ theo current content, tests targeted và không refactor code ngoài capability.

## Migration Plan

1. Thêm worker/service và settings/readiness với default off; pipeline cũ chưa gọi worker.
2. Thêm cache + integration per clip + manifest/report.
3. Thêm query/API/types/UI toggle và backend selector.
4. Thêm setup documentation/script để chuẩn bị isolated worker environment; không auto-install runtime.
5. Chạy backend tests, frontend typecheck/build và worker smoke check khi dependency local sẵn sàng.

Rollback: đặt `watermark_cleanup=false` hoặc bỏ cấu hình worker; pipeline normalize/concat/mux cũ vẫn hoạt động. Cache watermark là derivative có thể dọn bằng render-cache cleanup và không ảnh hưởng source clip.

## Open Questions

- Production sẽ bundle worker environment hay phân phối một wheel/sidecar pin theo release upstream mới; implementation hiện hỗ trợ cấu hình cả hai.
- Project-level render preset để auto-render kế thừa lựa chọn UI nên là change tiếp theo nếu sản phẩm cần tự động bật cleanup; change này giữ auto-render mặc định off để không vượt quyền người dùng.
