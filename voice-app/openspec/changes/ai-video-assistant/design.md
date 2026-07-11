## Bối cảnh

Voicebox hiện tập trung vào luồng voice: voice profile, cloned/preset TTS, generation history, import audio và story timeline dạng audio với export WAV. Hiện chưa có video project model, luồng tạo prompt ảnh theo scene, upload ảnh preview, tạo phụ đề `.srt` theo scene hoặc đóng gói nguyên liệu cho phần mềm dựng phim.

Người dùng mục tiêu là non-tech và đang dựng video bằng Premiere hoặc phần mềm tương đương. Workflow mới phải giúp người dùng đi từ một ý tưởng ngắn đến bộ nguyên liệu sạch: kịch bản chia cảnh, prompt ảnh dễ copy, ảnh preview theo scene nếu người dùng upload, file voice từng scene và phụ đề `.srt` khớp timing audio. MVP không render MP4 trong app, không cần FFmpeg và không thay thế Premiere.

## Mục tiêu / Không thuộc phạm vi

**Mục tiêu:**
- Tạo AI Video Assistant dạng wizard, bắt đầu từ một chủ đề ngắn và xuất ra bộ nguyên liệu sẵn sàng mang vào Premiere.
- Dùng **Codex CLI trong máy** qua `codex exec` để tạo structured planning: creative brief, script, scene breakdown, style bible, character consistency note và image prompt.
- Cho phép cấu hình provider qua settings, mặc định là `codex-cli`, với `codex_path`, model mặc định, timeout và output schema path.
- Giữ tạo ảnh ở dạng thủ công trong MVP: app tạo prompt, người dùng render ảnh ở tool ngoài, rồi có thể upload ảnh vào từng scene chỉ để preview/kiểm tra nội dung.
- Tái sử dụng Voicebox voice generation hiện có cho narration và cloned/preset voice, không thêm voice engine mới.
- Tạo subtitle `.srt` từ lời thoại scene và duration thật của audio đã sinh.
- Cho phép lấy nguyên liệu theo hai cách: copy/tải lẻ prompt, audio, subtitle; hoặc tải một file `.zip` gồm toàn bộ prompt, voice, subtitle và manifest dễ đọc.
- Lưu trạng thái project để người dùng có thể dừng, quay lại, regenerate từng scene/prompt/voice và tải lại gói nguyên liệu.
- Dùng tiếng Việt cho text mặc định trong workflow và tên file người dùng tải về.
- Ghi log lỗi chi tiết để người phát triển có thể trace lỗi theo project, scene, asset, generation, subtitle và export package.

**Không thuộc phạm vi:**
- Không render MP4 trong app ở MVP.
- Không thêm FFmpeg hoặc renderer media ở MVP.
- Không mix nhạc nền, burn subtitle vào video, transition, pan/zoom hoặc Ken Burns trong MVP.
- Không tích hợp image generation provider trong app ở MVP.
- Không tự điều khiển Premiere hoặc dựng timeline thay người dùng.
- Không thay thế TTS engine hiện có của Voicebox.
- Không tự động publish lên TikTok/YouTube/Facebook trong bản đầu.

## Quyết định thiết kế

### 1. Tạo model video project riêng, không nhét vào Stories

Tạo entity riêng cho video project, scene, prompt artifact, preview image asset, subtitle data và export package. Story hiện tại là audio-first và tham chiếu `Generation`. Video Assistant cần prompt version, trạng thái duyệt scene, ảnh preview, narration theo scene, subtitle và package tải về.

Phương án đã cân nhắc:
- Mở rộng `Story` và `StoryItem`: nhanh lúc đầu, nhưng trộn audio timeline với video planning state và khó mở rộng.
- Lưu mọi thứ trong một JSON blob: migration đơn giản, nhưng khó query, resume, validate và test.

Quyết định: dùng bảng video riêng và artifact files dưới configured data dir. Không tạo bảng `render_jobs` cho MVP vì chưa render MP4.

### 2. Dùng Codex CLI để tạo artifact có cấu trúc, không gọi provider ngoài trực tiếp trong MVP

Assistant sẽ gọi Codex CLI bằng `codex exec` để lấy JSON có cấu trúc: `creative_brief`, `scenes`, `style_bible`, `character_bible`, `image_prompts`. Backend đọc setting như `provider="codex-cli"`, `codex_path="/opt/homebrew/bin/codex"`, model, timeout và schema file. UI hiển thị tiếng Việt dễ hiểu, còn backend lưu structured data để regenerate và tải về ổn định.

Phương án đã cân nhắc:
- Gọi provider AI bên ngoài trực tiếp: rõ ràng cho server app, nhưng cần API key riêng, thêm cost/config và lệch với cách người dùng đang dùng Codex CLI trên máy.
- Free-form prose: dễ prompt nhưng dễ vỡ UI/package.
- Local script generator không dùng LLM: không cần provider nhưng chất lượng và tính nhất quán thấp hơn.

Quyết định: MVP dùng `codex exec` qua service riêng, validate output trước khi lưu, lỗi invalid output phải có log chi tiết và retry path. Thiết kế provider interface đủ hẹp để sau này đổi sang provider khác hoặc local LLM mà không sửa UI.

### 3. Ảnh trong MVP là prompt-first, upload chỉ để preview

App tạo prompt ảnh hoàn chỉnh cho từng scene, gồm main prompt, negative prompt, aspect ratio, style note và character consistency note. Người dùng copy prompt sang công cụ tạo ảnh bên ngoài, render ảnh, tải ảnh về rồi upload vào scene nếu muốn xem trước trong project.

Phương án đã cân nhắc:
- Tích hợp GPT Image/Flux/SDXL ngay: hữu ích về sau nhưng tăng phức tạp key, chi phí, retry, provider error và UI.
- Bắt buộc upload ảnh trước khi tiếp tục: không cần thiết vì MVP không render video trong app.

Quyết định: image upload là optional preview. Project vẫn có thể xuất prompt/voice/subtitle package khi chưa upload ảnh.

### 4. Tái sử dụng Voicebox generation cho narration

Mỗi scene đã duyệt có dialogue sẽ dùng flow TTS hiện có và lưu `generation_id`, audio path/URL, duration, status và voice/profile settings. Duration thật của audio là nguồn sự thật để tính timing subtitle.

Phương án đã cân nhắc:
- Tạo một file narration dài: đơn giản hơn nhưng khó sửa một scene và khó đặt tên file theo cảnh.
- Tạo TTS path riêng cho video: trùng logic ổn định đang có.

Quyết định: generate voice theo từng scene bằng semantics tương đương `/generate`, tận dụng audio serving/history khi phù hợp, và không thêm voice engine mới.

### 5. Export là gói nguyên liệu cho Premiere, không phải video cuối

Khi người dùng đã có scene/prompt và narration, hệ thống tạo subtitle `.srt`, manifest dễ đọc và file `.zip`. Package cần giữ thứ tự cảnh rõ ràng để kéo vào Premiere dễ hơn.

Ví dụ cấu trúc `.zip`:

```text
AI Video - Ten du an/
  00 - Huong dan.txt
  01 - Prompt anh/
    Canh 01 - Prompt anh.txt
    Canh 02 - Prompt anh.txt
  02 - Giong doc/
    Canh 01 - Giong doc.wav
    Canh 02 - Giong doc.wav
  03 - Phu de/
    Phu de - Ten du an.srt
  04 - Anh preview/
    Canh 01 - Anh preview.png
  Manifest - Ten du an.json
```

Phương án đã cân nhắc:
- Render MP4 bằng FFmpeg: phù hợp phase sau, nhưng MVP hiện người dùng muốn dựng trong Premiere nên thêm dependency và rủi ro không cần thiết.
- Chỉ cho copy prompt từng scene: quá ít, người dùng vẫn phải tự gom file audio/subtitle.

Quyết định: hỗ trợ cả copy/tải lẻ và `Tải tất cả (.zip)`. ZIP là export chính của MVP.

### 6. Tên file người dùng tải về dùng tiếng Việt, storage nội bộ vẫn an toàn

File nội bộ dùng ID/UUID để tránh lỗi path, duplicate, Unicode filesystem và security. File người dùng tải về dùng tên tiếng Việt dễ hiểu như `Prompt ảnh - Cảnh 01.txt`, `Giọng đọc - Cảnh 01.wav`, `Phụ đề - {ten-du-an}.srt`, `Bộ nguyên liệu - {ten-du-an}.zip`.

Phương án đã cân nhắc:
- Dùng ID làm tên file tải về: dễ implement nhưng khó hiểu với non-tech.
- Dùng tiếng Việt cả storage nội bộ: thân thiện nhưng dễ lỗi path và duplicate.

Quyết định: storage nội bộ dùng ID an toàn; API response/download header cung cấp filename tiếng Việt đã sanitize.

### 7. Log lỗi chi tiết nhưng thông báo UI thân thiện

Mọi API/job chính phải ghi log có cấu trúc: `request_id`, `project_id`, `scene_id`, `asset_id`, `generation_id`, `export_package_id`, step name, provider/model, thời gian chạy, error code, exception class và stack trace server-side. Với Codex CLI, log thêm exit code, timeout và stderr đã giới hạn kích thước. UI chỉ hiển thị thông báo ngắn, dễ hiểu và mã lỗi/request ID để người dùng gửi lại.

Phương án đã cân nhắc:
- Chỉ trả message lỗi cho UI: dễ làm nhưng khó debug.
- Hiển thị toàn bộ stack trace cho người dùng: nguy hiểm và gây rối.

Quyết định: log chi tiết ở backend, response có error code/request ID/message thân thiện, advanced view có thông tin debug an toàn.

### 8. UI tối ưu cho non-tech bằng review gates

UI dùng wizard rõ ràng: ý tưởng, duyệt kịch bản, prompt/ảnh preview, voice, tải gói nguyên liệu. Nút chính là Copy prompt, Upload ảnh preview, Tạo giọng đọc, Tải subtitle, Tải tất cả. Không hiển thị API name, JSON, internal ID hoặc model jargon trừ khi mở advanced/debug view.

Phương án đã cân nhắc:
- Một màn hình editor nâng cao: nhanh hơn nhưng khó dùng.
- Full auto không duyệt: nhanh nhưng dễ tạo sai nội dung, sau đó người dùng phải sửa nhiều ở Premiere.

Quyết định: có các điểm duyệt đơn giản: kịch bản, prompt/ảnh preview, voice/subtitle trước khi tải package.

### 9. Áp dụng chuẩn UI `design-taste-frontend-v1` cho màn hình mới

Các UI mới của AI Video Assistant phải theo hướng premium, rõ ràng và không generic. Baseline dùng `DESIGN_VARIANCE=8`, `MOTION_INTENSITY=6`, `VISUAL_DENSITY=4`: layout desktop có nhịp bất đối xứng có kiểm soát, motion vừa đủ sống động, mật độ thông tin vừa phải cho người non-tech.

Yêu cầu cụ thể:
- Không dùng hero/content căn giữa kiểu landing page. Màn hình đầu tiên là workflow usable ngay: bên trái là nhập ý tưởng và thông tin cơ bản, bên phải là preview/progress hoặc project summary.
- Không dùng palette tím/xanh AI sáo mòn, neon glow hoặc gradient text quá đà. Dùng nền neutral sáng, một accent duy nhất có saturation thấp, ví dụ emerald hoặc deep rose, và giữ nhất quán toàn workflow.
- Không lạm dụng card. Dùng card cho scene/prompt/image item thật sự cần framed tool; dùng border, divide-y, spacing và section band cho grouping lớn.
- Trên mobile, mọi layout bất đối xứng phải collapse thành một cột rõ ràng, không horizontal scroll và không dùng `h-screen`; nếu cần chiều cao viewport, dùng `min-h-[100dvh]`.
- Bắt buộc có loading skeleton theo đúng layout, empty state đẹp và error state inline cho từng bước wizard.
- Tất cả form field phải có label ở trên input, helper/error text dưới input và khoảng cách nhất quán.
- Motion chỉ dùng transform/opacity, ưu tiên transition CSS hoặc Framer Motion đã có trong app; không animate top/left/width/height.
- Các animation liên tục như shimmer, status pulse hoặc typewriter phải cô lập trong component nhỏ để tránh re-render nặng.
- Không dùng emoji trong UI text, code, alt text hoặc empty state; dùng icon chất lượng thay thế.
- Theo `design-taste-frontend-v1`, trước khi dùng icon library mới phải kiểm tra dependency. App hiện có `lucide-react`; nếu implementation muốn dùng đúng Phosphor/Radix icon style của skill thì phải thêm dependency rõ ràng trước, không import package chưa tồn tại.

Phương án đã cân nhắc:
- Dùng UI wizard cơ bản với card đều nhau: dễ implement nhưng dễ trông như giao diện AI generic.
- Làm motion/cinematic quá mạnh: đẹp nhưng có thể làm workflow non-tech rối và giảm performance.

Quyết định: thiết kế wizard như một production tool cao cấp, asymmetric vừa đủ, motion vừa đủ, copy tiếng Việt rõ ràng, và đầy đủ loading/empty/error states.

### 10. Luồng làm cuốn chiếu theo từng scene, không gate toàn cục

Workflow cho phép duyệt và làm việc theo từng scene độc lập thay vì bắt duyệt hết toàn bộ kịch bản mới được tiếp tục. Khi một scene đã được duyệt, người dùng có thể tạo prompt và tạo giọng đọc cho riêng scene đó, không cần chờ các scene khác.

Các hệ quả về trạng thái:
- **Prompt ảnh cũng bị đánh stale như voice/subtitle/package.** Khi người dùng sửa lời thoại hoặc mô tả hình ảnh của một scene đã có prompt, hệ thống đánh dấu prompt ảnh của scene đó là cần làm lại, song song với việc đánh stale voice, subtitle và package liên quan.
- **Scene có thể "cố ý không lời".** Người dùng có thể đánh dấu một scene là không cần narration (ví dụ title card, cảnh chuyển, b-roll). Scene loại này không bị coi là "thiếu voice" và không chặn export package. Package readiness chỉ yêu cầu narration ở các scene có lời thoại và chưa được đánh dấu không lời.
- **Lỗi provider hiển thị inline trong wizard.** Khi Codex CLI chưa sẵn sàng, thông báo và nút kiểm tra/thử lại hiển thị ngay tại bước đang làm trong wizard, không bắt người dùng non-tech tự tìm vào Settings. Settings vẫn có nơi cấu hình, nhưng không phải điểm chặn duy nhất.

Phương án đã cân nhắc:
- Gate toàn cục (duyệt hết mới làm tiếp): đơn giản để hiểu nhưng một scene cần sửa sẽ chặn cả workflow.
- Bắt mọi scene phải có narration: đơn giản hoá readiness nhưng chặn các video có cảnh không lời hợp lệ.

Quyết định: per-scene approval và per-scene generation, prompt stale đồng bộ với voice/subtitle, hỗ trợ scene không lời, và lỗi provider hiển thị inline.

## Rủi ro / Trade-off

- Codex CLI có thể chưa cài, chưa đăng nhập hoặc không nằm đúng path → Settings phải có nút kiểm tra, lỗi tiếng Việt rõ ràng và log exit code/stderr an toàn.
- Codex CLI output có thể invalid JSON → Validate structured output, log validation error server-side, UI có nút retry.
- Duration TTS khác duration dự kiến → Dùng duration thật của audio để tạo `.srt`, không dùng duration ước lượng.
- Người dùng chưa upload ảnh preview → Không chặn export package vì ảnh preview chỉ để tham khảo.
- Tool ảnh bên ngoài làm nhân vật không nhất quán → Mỗi prompt đều nhắc style bible và character consistency.
- Subtitle có thể quá dài → Chia cue theo độ dài chữ và duration audio để dễ kéo vào Premiere.
- ZIP có thể thiếu file nếu một scene voice failed → UI phải hiển thị checklist trước khi tải package và chặn package khi thiếu narration bắt buộc.
- Log quá nhiều có thể lộ dữ liệu → Không log token, full uploaded binary hoặc secret; giới hạn stderr/raw output và chỉ log metadata cần debug.
- UI premium quá phức tạp có thể làm người non-tech khó dùng → Giữ wizard theo 5 bước rõ ràng, motion chỉ hỗ trợ trạng thái/progress, không biến workflow thành landing page.
- Thêm icon library mới có thể tăng dependency → Kiểm tra package trước; nếu dùng library mới theo chuẩn design-taste thì thêm dependency có chủ đích và không trộn nhiều icon style.

## Migration Plan

1. Thêm schema/migration video project theo pattern `_migrate_*` hiện có trong `backend/database/migrations.py`; không thêm Alembic.
2. Thêm thư mục artifact dưới `data/video_projects/{project_id}/` cho prompts, preview images, subtitles và package manifests.
3. Thêm backend API route mới để behavior voice/profile/story hiện tại không đổi.
4. Thêm service gọi Codex CLI và settings/check endpoint trước khi mở workflow planning cho người dùng.
5. Thêm service tái dùng voice generation hiện có theo từng scene.
6. Thêm subtitle/package service để tạo `.srt`, file tải lẻ và `.zip`.
7. Thêm wizard frontend mới, không xóa editor/story hiện có.
8. Thêm structured logging/error response format trước khi mở rộng workflow.
9. Rollback an toàn bằng cách ẩn/xóa route UI video; dữ liệu voice hiện có không bị ảnh hưởng.

## Câu hỏi mở

- Bản đầu nên chỉ hỗ trợ tỷ lệ `9:16`, hay thêm `16:9` và `1:1` ngay?
- ZIP package có cần luôn kèm `00 - Hướng dẫn import vào Premiere.txt` không?
- Package export nên lưu vĩnh viễn, hay có chính sách cleanup cache sau một số ngày?
- Image QA tự động nên nằm trong MVP hay phase sau?
- Có cần cho người dùng chọn format tên file tải về, ví dụ `Bộ nguyên liệu - Tên dự án.zip` hay `Tên dự án - 2026-06-29.zip`?
- Có chấp nhận thêm `@phosphor-icons/react` hoặc `@radix-ui/react-icons` để bám sát `design-taste-frontend-v1`, hay dùng `lucide-react` hiện có làm ngoại lệ theo design system hiện tại?
