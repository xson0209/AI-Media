# Hiệu năng `/ai-video` và mở rộng sang 3 dạng content mới

Ngày kiểm tra: 2026-08-23

## Kết luận ngắn

1. **Hiệu năng (A):** nút thắt render đã dịch chỗ. Sau khi song song hoá 6 worker + mặc định `cv2`, render 18 clip giảm từ 1070 giây xuống **128 giây** (số đo thật trong DB). Phần còn lại đáng cắt là **watermark cleanup (~79 giây)** và **burn-in phụ đề (~43 giây, đo được)**. Cả hai đều có đường thay thế gần như miễn phí: `delogo` gộp vào pass normalize đang có. Nhưng nút thắt *wall-clock* lớn nhất của cả sản phẩm không phải render — là **sinh clip Veo tuần tự từng clip một qua Chrome CDP**, timeout 20 phút/clip, không có song song.
2. **3 dạng content mới (B):** cả ba video tham chiếu đều là **một shot Veo 8 giây, 720x1280, 24fps**, và ít nhất hai video cần **ảnh sản phẩm thật làm input**. Pipeline hiện tại **không có chỗ nào lưu hay gửi ảnh tham chiếu** — không có cột DB, không có field API, không có primitive upload file trong CDP client. Đây là gap thật, không phải cờ cấu hình. Điểm tốt: Google Flow — thứ mà app đang tự động hoá — **đã hỗ trợ sẵn** Frames to Video và Ingredients/References to Video, nên không cần đổi provider.
3. **GitHub repo → video thuyết minh (C):** **chưa tồn tại**. Không có adapter GitHub ở bất kỳ đâu trong `backend/`. Một URL GitHub hôm nay sẽ hoặc bị `VIDEO_INSPIRATION_PLATFORM_UNSUPPORTED`, hoặc rơi vào `docs_url` và bị scrape như một trang HTML thường. Chỗ đúng để thêm là adapter thứ tư trong `research_source_adapters.py`, không phải trong `/video-inspiration`.

## Phạm vi và phương pháp

Ba loại bằng chứng, tách riêng để không lẫn:

- **Mã nguồn** repo hiện tại, dẫn `file:line`. Đây là nguồn sở hữu hành vi runtime.
- **Số đo thật**: 4 render job có trong `data/voicebox.db` + benchmark ffmpeg tôi chạy hôm nay trên chính 18 clip của project `Sơn test` và trên 3 video tham chiếu.
- **Tài liệu nhà cung cấp** (Google Gemini API, Google Flow Help, FFmpeg, GitHub REST), liệt kê ở mục Nguồn.

Chưa làm: chưa chạy một job sinh clip Veo thật để đo thời gian mỗi clip (bảng `video_clip_generation_items` trống, xem mục 4.4). Chưa sửa code.

## Mục lục

1. Hiện trạng pipeline hai luồng
2. Đặc tả 3 video tham chiếu
3. (A) Điểm nghẽn hiệu năng
4. (B) Gap để làm được 3 dạng content
5. (C) Luồng GitHub repo → video thuyết minh
6. Roadmap ưu tiên
7. Phạm vi xác minh
8. Nguồn

## 1. Hiện trạng pipeline hai luồng

### 1.1 `/ai-video` — từ ý tưởng tới MP4

Route `/ai-video` → `AIVideoAssistant` (`app/src/router.tsx:180-184`, component `app/src/components/AIVideoAssistant/AIVideoAssistant.tsx:2135`). Backend: `backend/routes/ai_video.py:45`.

| Bước | Ở đâu | Số lần gọi LLM |
| --- | --- | --- |
| Phase 1 plan (nếu project bắt đầu ở `phase1`) | `backend/services/video_planning.py:153` | 1 |
| `develop_story` | `backend/services/video_phase2.py:2815`, gọi Codex ở `:2859` | 1 |
| `generate_shots` | `video_phase2.py:3162`, gọi ở `:3274` | 1 |
| `generate_video_prompt_pack` | `video_phase2.py:3654`, gọi ở `:3760` | 1 (tối đa 3 vòng mapping) |
| Publishing metadata (nếu auto-run full) | `backend/services/video_publishing_metadata.py:930` | 1 |
| Sinh clip Veo | `backend/services/video_clip_generation.py:936` | 0 (không phải LLM) |
| TTS mỗi shot | `backend/services/video_voice.py:540` | 0 |
| Dựng MP4 | `backend/services/video_rendering.py:2144` | 0 |

Tổng đường thẳng: **3 lượt Codex cho phase 2** (4 nếu có phase 1, 5 nếu có publishing kit), tất cả tuần tự. Xấu nhất khi retry: **≤15 lượt** `run_codex_exec`, và mỗi lượt còn có thể spawn tới 4 process `codex exec` (`backend/services/ai_planning.py:1149-1181`).

Điểm quan trọng về LLM planning: **không phải API HTTP**. `run_codex_exec` (`ai_planning.py:739`) chạy `codex exec` như một subprocess, prompt đi qua stdin, kết quả đọc từ file tạm (`:792-822`). Model mặc định `DEFAULT_CODEX_MODEL = "gpt-5.6-sol"`, reasoning effort `"ultra"` (`ai_planning.py:25-26`). Timeout bị **hard-cap 600 giây** ở `:775`, nên `VOICEBOX_PHASE2_CODEX_TIMEOUT` đặt trên 600 không có tác dụng. Không có caching ở lớp này.

### 1.2 Sinh clip: Chrome DevTools Protocol lái Google Flow, không phải Veo REST API

Đây là chi tiết kiến trúc quan trọng nhất và dễ hiểu sai nhất.

- `backend/services/video_veo_chrome.py:1` — *"Veo/Flow provider adapter driven through Chrome DevTools Protocol."*
- Chrome được spawn thật với debug port: `backend/services/video_provider_sessions.py:303-315`.
- Đích là web app Flow: `DEFAULT_FLOW_URL = "https://labs.google/fx/tools/flow"` (`video_provider_sessions.py:27`), allowlist bắt buộc host `labs.google` + path chứa `/tools/flow/project/` (`backend/services/video_provider_project_bindings.py:50-53`).
- Prompt được **gõ vào trang** bằng `Input.insertText` (`video_veo_chrome.py:826-833`), nút bấm được tìm theo **text nhãn tiếng Việt/Anh** rồi click bằng `Input.dispatchMouseEvent` (`:322-353`, `:866-875`, `:1434-1438`).
- Không có model id nào trong code. Code **cố ý không chọn model**, chỉ đọc model đang chọn trong UI Flow: `FLOW_MODEL_SELECTION_MODE = "use_current_flow_selection"`, `FLOW_ALLOW_AUTOMATIC_MODEL_CHANGE = False` (`video_provider_project_bindings.py:24-25`), hàm đọc nhãn `_read_current_flow_model` (`video_veo_chrome.py:747-791`). Chuỗi `veo3_flow` ở `video_provider_sessions.py:25` chỉ là identifier nội bộ, không phải model id.

Hệ quả: mọi phán đoán "xong chưa / lỗi gì / có hộp credit không" đều là so khớp chuỗi trong `document.body.innerText` (`video_veo_chrome.py:1136-1179`). Flow đổi copy hoặc DOM là một lớp lỗi im lặng — đó là lý do có ~15 error code `VIDEO_PROVIDER_*`.

### 1.3 `/video-inspiration` — input là *một video*, không phải một chủ đề

Route ở `app/src/router.tsx:210-214`, backend `backend/routes/video_inspiration.py` (27 endpoint, prefix `/video-inspiration`).

Đầu vào: upload `.mp4` (`backend/services/video_inspiration.py:788-835`, cap 700 MB / 30 phút) hoặc URL social trong allowlist youtube/youtu.be/tiktok/facebook/fb.watch/instagram (`_SOCIAL_PLATFORMS`, `:96-103`) tải bằng yt-dlp.

`analyze_job` (`:3020-3145`) theo thứ tự: tách audio → STT Whisper `turbo` theo cửa sổ 25 giây **tuần tự** (`:1122-1123`) → keyframe + shot detection → **2 lượt Codex** (visual `:3096`, content `:3115`). `rewrite_job` (`:3274-3365`) thêm **4 lượt Codex** tuần tự. Đường quick→handoff = **6 lượt Codex**; bật variant pipeline lên tới **10**.

Output là `VideoAnalysisPackage v1` (`_build_analysis_package` `:2883-3011`): timeline, shot list, retention beat map, script đã rewrite. **Không phải** danh sách prompt sẵn sàng render.

### 1.4 Handoff giữa hai luồng: hai đường độc lập

**Đường A — sessionStorage (không qua API, không qua DB).** Key `'voicebox.aiVideoDraft.v1'` (`app/src/lib/aiVideoDraft.ts:9`). `buildAIVideoDraft` gom 6 block từ `analysis_json.rewrite` (`app/src/components/VideoInspiration/VideoInspiration.tsx:395-436`), ghi sessionStorage rồi **reload cả trang** sang `/ai-video?draft=video-inspiration` (`:979-983`). Bên `/ai-video` đọc và xoá key (`AIVideoAssistant.tsx:2477-2511`).

**Đường B — tạo project thật trong DB.** `POST /video-inspiration/jobs/{id}/create-ai-video-project` → `create_ai_video_project` (`backend/services/video_inspiration.py:3427-3500`), ghi bảng `video_inspiration_handoffs` (`backend/database/models.py:1247-1266`), tạo project `phase="phase2"`, trả `ai_video_url = /ai-video?projectId={id}` (`:3494`).

**Một bug đã xác thực:** `handoff_to_ai_video` được khai báo (`backend/models.py:2550`), bị route ép `True` (`backend/routes/video_inspiration.py:201-203`) và client cũng gửi `true` (`app/src/lib/api/client.ts:712`), nhưng **không service nào đọc nó**. Grep toàn repo chỉ ra 5 chỗ, tất cả là khai báo/ghi, không có chỗ đọc. Auto-handoff sau deep research thực chất chạy hoàn toàn ở client (`VideoInspiration.tsx:1028-1040`), nên nó **âm thầm không xảy ra** nếu user rời trang, reload, hoặc mất sessionStorage của tab.

Ngoài ra còn workspace `/research` (`docs/nghien-cuu-y-tuong-handoff-ai-video.md`) với đúng mô hình "gom nguồn → nghiên cứu → handoff sang AI Video". Registry source type: `SOURCE_TYPES = {"video_url", "video_upload", "story_url", "image_upload", "text", "docs_url", "series_memory"}` (`backend/services/research.py:56`), dispatch adapter là một chuỗi `if/elif` ở `backend/services/research_source_adapters.py:359-366` với **đúng ba** adapter: video, comic, document.

## 2. Đặc tả 3 video tham chiếu

Đo bằng chính FFmpeg 7.1 đi kèm backend (`backend/venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe`). Không có `ffprobe` trên máy này nên dùng banner `ffmpeg -i`.

Ba video giống nhau ở mọi thông số kỹ thuật quan trọng:

| | Video 1 `Create_professional_product_vide…` | Video 2 `Quay_video_cận_cảnh_sản…` | Video 3 `Man_presenting_product_advertise…` |
| --- | --- | --- | --- |
| Thời lượng | 8.00 s | 8.00 s | 8.00 s |
| Khung hình | 720x1280 (9:16), 24 fps | 720x1280, 24 fps | 720x1280, 24 fps |
| Codec | h264 High, yuv420p progressive | như trên | như trên |
| Bitrate video | 1901 kb/s | 2365 kb/s | 3170 kb/s |
| Audio | **không có** | aac LC 48 kHz stereo 139 kb/s | aac LC 48 kHz stereo 139 kb/s |
| Tag `encoder` | `Google` | `Google` | `Google` |
| Watermark | chữ `Veo` góc dưới-phải | như trên | như trên |

Kết luận từ đặc tả: **cả ba là một shot Veo đơn 8 giây tải trực tiếp từ Flow, chưa qua bất kỳ hậu kỳ nào của Voicebox** — chưa normalize (vẫn 24 fps, vẫn 720p), chưa xoá watermark, chưa ghép, chưa burn-in phụ đề. Đây là "nguyên liệu", không phải "thành phẩm" theo nghĩa pipeline hiện tại.

Nội dung và vì sao nó đòi hỏi tính năng mới:

- **Video 1 — UGC cầm sản phẩm.** Một bàn tay giơ hai hộp `KHÔ GÀ` (nhãn trắng, logo con gà vàng) trên phố cổ Hà Nội, xe máy và người bán hàng chuyển động phía sau. Nhãn sản phẩm **giữ nguyên chữ và bố cục xuyên suốt 8 giây**. Text-to-video không giữ được nhãn thật như vậy; đây gần như chắc chắn là image-to-video hoặc ingredients từ ảnh sản phẩm thật.
- **Video 2 — beauty shot studio.** Túi đeo chéo đen chữ `FASHION` có cổng sạc USB, đặt trên bàn gaming đèn RGB, camera dolly/orbit chậm. Cũng giữ nguyên chi tiết sản phẩm. Audio là ambience, không có lời (Whisper trả về nhiễu).
- **Video 3 — người thật thuyết minh, có lời tiếng Việt do model sinh.** Nam nhân viên áo xanh `LIBITU` trong nhà máy, giới thiệu phụ gia súc đéc xăng, màn TV bên cạnh hiện `COMBO 2 CHAI 99K`. Whisper (local, `base`) trả về: *"Cô bô hai trai tặng kèm khăn lao chỉ 99.000 kèm free-ship ưu đại có hạt anh em bấm vào góc trái rộ hàng mua ngay"* — tức Veo tự sinh audio hội thoại tiếng Việt khớp với promo trên màn hình. Cũng thấy được hiện tượng chữ trên màn TV **biến dạng dần** giữa frame 1 và frame 3 (`LIBITU` → chuỗi vô nghĩa), đúng đặc tính drift chữ của model.

Điểm cần lưu ý cho hướng (B): video 3 chứng minh **đường Veo native speech tiếng Việt đã có và hoạt động** trong repo. `video_speech.py:16-39` đặt `VEO_NATIVE_LANGUAGE = "vi"`, và `create_shot_narration` từ chối tạo TTS riêng cho project tiếng Việt (`backend/services/video_voice.py:551-555`, error `VIDEO_VOICE_VEO_NATIVE_SPEECH`), thay vào đó chèn block hội thoại tiếng Việt vào prompt Flow (`video_speech.py:187-260`) và lấy audio trực tiếp từ track của clip khi render (`video_rendering.py:2825-2848`).

## 3. (A) Điểm nghẽn hiệu năng

### 3.1 Số đo thật của 4 render job trong `data/voicebox.db`

Cùng project `Sơn test`, cùng 18 clip, cache **lạnh hoàn toàn** ở cả bốn lần (`render-cache-summary.json`: `normalized_hits: 0, normalized_misses: 18` mọi lần).

| Job | Cấu hình | Thời gian | Kết quả |
| --- | --- | --- | --- |
| `76de76ff` | `watermark_cleanup: false` | **49,1 giây** | completed |
| `c99cd09a` | cleanup `cv2`, chưa song song | **1070,4 giây** (17,8 phút) | completed |
| `57c71a07` | cleanup `migan` | **2635,4 giây** (43,9 phút) | **failed** — `VIDEO_RENDER_WATERMARK_PROTOCOL_INVALID` |
| `aca6a6f1` | cleanup `cv2`, 6 worker song song | **128,3 giây** | completed |

Ba việc mà note đo hiệu năng trước đây đề xuất **đã được áp dụng**: song song hoá vòng lặp per-clip (`resolve_clip_worker_count`, `video_rendering.py:2681-2702`, trần `_MAX_CLIP_WORKERS = 6` ở `:60`), mặc định `watermark_backend` chuyển `cv2` (`backend/models.py:667`, `app/src/lib/renderSettingsStore.ts:26`), và render settings đã có persistence (`renderSettingsStore.ts`). Kết quả: 1070 → 128 giây, nhanh hơn 8,3 lần.

`timeline-manifest.json` của job 128 giây cho biết chi tiết đáng chú ý: `"provider": null` nhưng `"requested_mark": "veo"`, tức tier-2 cache lookup theo tên file đã tự cứu được mark (`video_watermark_cleanup.py:359-388`). `visible_mark: "veo"`, `192/192` frame được xử lý. Và `"invisible_removed": false` cùng `detected_metadata` ghi `C2PA manifest store (4763 bytes)`, `issuer: Google LLC`, `synthid_watermark: likely present` — **cleanup không và không thể xử lý SynthID**, đúng như `docs/ai-video-watermark-cleanup.md` đã nêu.

### 3.2 Hai khoản còn cắt được, đã đo

**Khoản 1 — watermark cleanup còn ~79 giây.** 128,3 − 49,1 = 79,2 giây cho 18 clip với 6 worker. Cách thay: dùng filter `delogo` của FFmpeg, nhét ngay đầu chuỗi filter của pass normalize đang có. Đo trên đúng 18 clip thật của project, 1920x1080@60, `fit_mode=pad`, 6 tiến trình song song:

| | Wall-clock 18 clip |
| --- | --- |
| Chỉ normalize (như hiện tại) | **54,99 giây** |
| Normalize + `delogo` | **50,50 giây** |

`delogo` **miễn phí trong sai số đo**. Nó cũng xoá luôn một pass encode: worker cv2 hiện đang xuất một MP4 trung gian re-encode (`encoder: Lavf61.7.100`, 4459 kb/s) rồi normalize encode lần nữa.

Toạ độ đã hiệu chuẩn và kiểm tra bằng mắt (crop phóng 5-6x, cả trước và sau):

- Clip landscape 1280x720 (clip thật của project): `delogo=x=1230:y=686:w=44:h=28`
- Clip portrait 720x1280 (3 video tham chiếu): `delogo=x=674:y=1238:w=44:h=38`

Cả hai đều xoá sạch chữ `Veo`, không để lại vệt sáng viền. Hộp nhỏ hơn (`w=34:h=24`) **có** để lại một vệt sáng ngang — nên biên độ dư là cần thiết. PSNR vùng logo 80x50 giữa `delogo` và output cv2 là Y 38,55 dB: hai cách lấp khác nhau, nhưng cả hai đều sạch với mắt thường.

**Khoản 2 — burn-in phụ đề ~43 giây, và nó là mặc định.** `subtitle_mode: 'burn_in'` là mặc định frontend (`app/src/lib/renderSettingsStore.ts:18`). Có file `.ass` thì `build_final_mux_command` đổi từ `-c:v copy` sang re-encode toàn timeline bằng libx264 (`video_rendering.py:3240-3243`). Đo trên timeline 143,12 giây 1920x1080@60 vừa dựng:

| Final mux | Thời gian |
| --- | --- |
| `-c:v copy` (không phụ đề) | **0,71 giây** |
| `subtitles=…` + libx264 veryfast | **42,71 giây** |

Đây là một pass **tuần tự, một luồng công việc duy nhất, cuối job** — không được hưởng lợi từ 6 worker. Job 128,3 giây ở trên có `subtitle_mode: "none"`, nên với mặc định thật của UI thì render là **~171 giây**, và ~43 giây trong đó là cái đuôi serial này.

Ghép cả hai: render 18 clip có thể từ ~171 giây về **~55 giây** mà không đổi codec, không đổi preset, không cần GPU.

### 3.3 Nút thắt wall-clock lớn nhất không nằm ở render

Render 18 clip = ~2 phút. Nhưng **sinh** 18 clip đó là hoàn toàn tuần tự:

- `_run_job_sync` lặp `for item in runnable:` (`backend/services/video_clip_generation.py:936`), một `asyncio.to_thread` duy nhất (`:874`). **Không semaphore, không pool, không `asyncio.gather`.**
- Bất kỳ lỗi provider nào `return` ra khỏi cả vòng lặp (`:1102`, `:1106`, `:1109`) — một clip lỗi là dừng phần còn lại của job.
- Chrome là singleton theo provider (`video_provider_sessions.py:73-74`), tab Flow cũ bị đóng trước khi làm việc (`video_veo_chrome.py:1903`).
- Mỗi item: `DEFAULT_GENERATION_TIMEOUT_SECONDS = 20 * 60`, `DEFAULT_DOWNLOAD_TIMEOUT_SECONDS = 10 * 60`, poll 1 giây/lần bằng cách đọc lại `document.body.innerText` (`video_veo_chrome.py:21-27`, `:1761-1875`).

**Chưa xác thực được** thời gian thực tế mỗi clip: bảng `video_clip_generation_items` trong `data/voicebox.db` **trống** (0 dòng), và cả 18 clip của project `Sơn test` là `('upload', None)` — upload tay, không phải sinh qua job. Tài liệu Gemini API ghi latency sinh video min 11 giây, max 6 phút giờ cao điểm; Flow UI không có số công bố. Muốn có số thật phải chạy một job sinh clip và đọc `started_at`/`completed_at` của từng item.

Điều đó nói rằng: kể cả ở mức lạc quan 60 giây/clip, 18 clip tuần tự = 18 phút, gấp 9 lần thời gian render. Đây là nơi nên đo trước khi tối ưu tiếp bất cứ thứ gì trong render.

Song song hoá phần này **không phải** việc nên làm bừa: nó tiêu Flow credits thật, một tài khoản Google, và code đang cố ý dùng một profile Chrome duy nhất. Bước an toàn là **đo trước**, sau đó mới cân nhắc 2 tab Flow song song với hạn mức credit rõ ràng.

### 3.4 Ba khoản khác đáng ghi nhận

**Event loop bị block ở `/video-inspiration`.** `POST /jobs/from-url` là `async def` nhưng gọi `create_url_job` đồng bộ, không `asyncio.to_thread` (`backend/routes/video_inspiration.py:159-171` → `video_inspiration.py:837`). Nghĩa là tới 2 (hoặc 2 + 2×số browser) tiến trình yt-dlp, mỗi cái tới 600 giây, chạy ngay trong request coroutine. Mọi API request khác trên worker đó xếp hàng phía sau. `POST /jobs/upload` cùng dạng, thêm việc `file.read(MAX_VIDEO_BYTES + 1)` nạp tới ~700 MB vào một object bytes (`:147`).

Đối lập: `analyze`/`rewrite` làm đúng — `create_background_task` + `asyncio.to_thread` (`video_inspiration_runs.py:223,244,348`).

**Frontend không có timeout HTTP nào.** `apiClient.request` là `fetch` trần, không `AbortSignal` (`app/src/lib/api/client.ts:265-284`). Có một client thứ hai sinh từ OpenAPI *có* `AbortController` (`app/src/lib/api/core/request.ts:232-238`), nhưng cả `AIVideoAssistant.tsx:53` và `VideoInspiration.tsx:32` đều import `apiClient` từ `client.ts`, không dùng client kia.

**Không có cache cho analyze/rewrite.** `analyze_job` chủ động xoá `analysis_package_json`, `coverage_metrics_json`, `limitations_json` (`video_inspiration.py:3035-3040`) và `analysis_json`/`rewritten_script` (`:3074-3075`). Chạy lại deep-research trên job đã analyze là làm lại toàn bộ STT, ffmpeg và cả 2 lượt LLM. `rewrite_job` không có fingerprint gate nào. Chỉ variant stage mới có fingerprint (`:2052`, kiểm ở `:2157`, `:2199`, `:2232`).

### 3.5 Việc KHÔNG nên làm

**Đừng chuyển normalize sang NVENC.** Đã đo và ghi thẳng trong docstring: `h264_nvenc` 6,38 giây so với `libx264 -preset veryfast` 4,24 giây trên clip 8 giây 1080p60 thật, qua đúng chuỗi filter này (`video_rendering.py:2589-2599`). Clip ngắn nên overhead khởi tạo NVENC session ăn hết lợi ích, và libx264 không đặt `-threads` nên đã dùng hết core.

**Đừng chuyển `watermark_backend` sang `migan`.** Chênh lệch chất lượng không tương xứng: PSNR 50,7 dB / SSIM 0,9965 so với `cv2` (`backend/models.py:664-666`), nhưng chậm ~27 lần, và lần chạy migan duy nhất trong DB đã **fail** sau 44 phút.

## 4. (B) Gap để làm được 3 dạng content

### 4.1 Gap chặn: không có đường nào đưa ảnh sản phẩm vào generation

Ba lớp xác nhận độc lập, đều là "không":

1. **Không có cột DB nào giữ được ảnh input.** `video_shot_prompts` (`backend/database/models.py:872-907`) chỉ có text: `prompt`, `negative_prompt`, `duration_seconds`, `aspect_ratio`, `start_frame`, `end_frame`… trong đó `start_frame`/`end_frame` là **mô tả bằng chữ**, được render thành dòng `"Start frame:"` / `"End frame:"` trong prompt (`backend/services/video_clip_generation.py:112-113`), không phải pixel. `video_clip_generation_items` (`:710-738`) chỉ mang `prompt_id`. `video_projects` cũng không có.
2. **Không có field API.** `VideoClipGenerationJobStartRequest` (`backend/models.py:958-965`) có `session_id`, `force`, `auto_render`, `credit_approval_policy`, `max_credit_per_job`, `confirm_identity` — không có prompt, không có ảnh. `POST /projects/{id}/prompts` không có request body (`backend/routes/ai_video.py:1361`).
3. **Không có primitive upload trong CDP client.** `chrome_cdp.py` chỉ implement bốn method: `command`, `evaluate`, `navigate`, `set_download_behavior` (`:270-315`). Không `DOM.setFileInputFiles`, không `Page.setInterceptFileChooserDialog`, không `Input.dispatchDragEvent`. Grep `video_veo_chrome.py` cho `ingredient|reference[_ ]?image|first[_ ]?frame|image[_ ]?to[_ ]?video|upload` → **không match nào**; từ `upload` không xuất hiện trong file.

Ba bảng có ảnh đều nằm ngoài đường generation: `series_reference_assets.asset_path` (`database/models.py:391-392`) bị chính pipeline khai báo là provider không hỗ trợ — `generate_video_prompt_pack` truyền `provider_supports_references=False` (`video_phase2.py:3701`) và `build_reference_provider_report` đẩy mọi asset vào `skipped` với lý do *"Provider hiện tại chưa hỗ trợ gửi ảnh tham chiếu trực tiếp."* (`backend/services/series_references.py:557-563`); `video_scene_assets` `asset_type="preview_image"` chỉ dùng để upload/serve/package; `video_shot_clips.file_path` là video đã sinh.

Tin tốt: **`command` là generic**, nên `DOM.setFileInputFiles` gọi được ngay qua `client.command(...)` mà không phải viết lại WebSocket layer. Rào cản là plumbing, không phải kiến trúc.

### 4.2 Google Flow đã hỗ trợ sẵn — không cần đổi provider

Theo trang Flow Help về model và tính năng (xem Nguồn), Flow hỗ trợ:

| Tính năng | Veo 3.1 Fast / Quality | Gemini Omni Flash |
| --- | --- | --- |
| Text to Video | cả 2 tỉ lệ, 4/6/8 s | cả 2 tỉ lệ, 4/6/8/10 s |
| Frames to Video: First (ảnh → video) | cả 2 tỉ lệ, 4/6/8 s | 4/6/8/10 s |
| Frames to Video: First + last | cả 2 tỉ lệ, 4/6/8 s | coming soon |
| **Ingredients/References to Video** | cả 2 tỉ lệ, **chỉ video 8 s** | 4/6/8/10 s, hỗ trợ character/avatar & audio reference |
| Video to Video editing | không | tới 10 s |
| Extend videos | 8 s, phải dùng Veo 3.1 Lite để extend | coming soon |

Tài liệu Gemini API nói rõ về ingredients: *"Provide up to three asset images of a single person, character, or product. Veo preserves the subject's appearance in the output video."* Đúng đích cho video 1 và video 2.

Lưu ý ràng buộc quan trọng nếu dùng ingredients: **bắt buộc 8 giây**. Điều này khớp sẵn với `video_veo_chrome.py:286` (`allowed = [4, 6, 8, 10]`) nhưng xung đột với `VideoShotUpdate.duration_seconds` cho phép `ge=0.5, le=30` (`backend/models.py:508`) và `VIDEO_PROMPT_SEGMENT_SECONDS = 10` (`video_phase2.py:52`) — cần một validation mới khi bật đường ingredients.

### 4.3 `aspect_ratio` chỉ đi vào prompt dưới dạng chữ, không phải tham số

Đáng biết trước khi làm dạng content dọc: `aspect_ratio` được validate `^(9:16|16:9|1:1)$` ở boundary (`backend/models.py:1837`, `:1863`, `:1802`), nhưng **không bao giờ được click trong Flow**. Nó chỉ được nhét vào chuỗi prompt: `f"Aspect ratio: {prompt.aspect_ratio or project.aspect_ratio}"` (`video_phase2.py:3619`, `:4028`). Bên trong phase 2, `VideoPromptPlan.aspect_ratio` chỉ giới hạn `max_length=20` (`video_phase2.py:410`), nên một giá trị model tự bịa như `"21:9"` vẫn được ghi thẳng vào `video_shot_prompts.aspect_ratio` mà không ai chặn. Không có CHECK constraint nào ở DB.

Tương tự, độ phân giải tải về là click nhãn `["720p Kích thước gốc", "Original size", "Original", "720p"]` (`video_veo_chrome.py:1507-1530`) — và ở `:1531-1533` cả hai nhánh đều `return True`, nên **nếu chọn chất lượng thất bại thì code không phát hiện được**. Đây cũng là cơ hội chất lượng: theo Flow Help, upscale 1080p tốn **0 credit** cho subscriber Plus/Pro/Ultra.

### 4.4 Những gì đã có sẵn, không cần làm lại

- **Preset mục đích `sales_ad`** đã tồn tại: `backend/services/video_purpose.py:87-98`, `call_to_action_style="direct"`, `narration_density="light"`, `recommended_target_language="vi"`, tone guidance đúng kiểu quảng cáo. Alias `sales`/`ad`/`advertisement` cũng đã map (`:122-124`).
- **Preset `educational_explainer`** cho dạng thuyết minh: `video_purpose.py`, `narration_density="dense"`.
- **Veo native speech tiếng Việt** đã hoạt động (mục 2), nên video kiểu số 3 không cần TTS.
- **Render đơn shot** hoạt động bình thường; một project 1 shot vẫn đi qua normalize → concat → mux.

### 4.5 Bảng gap theo từng dạng content

| Dạng | Cần gì | Đã có? |
| --- | --- | --- |
| **1. UGC cầm sản phẩm ngoài đời** | ảnh sản phẩm làm ingredient; prompt bối cảnh đường phố VN; 8 s; 9:16 | ảnh: **không**. Còn lại: có |
| **2. Beauty shot studio** | ảnh sản phẩm làm ingredient/first frame; camera move; ambience audio | ảnh: **không**. Còn lại: có |
| **3. Người thuyết minh + lời Việt** | prompt hội thoại tiếng Việt; audio native; on-screen promo text | **có đủ** (đường `veo_native`), chỉ cần preset prompt |

Nghĩa là dạng 3 làm được **hôm nay** chỉ bằng prompt engineering. Dạng 1 và 2 bị chặn bởi một gap duy nhất, dùng chung một lời giải: đường ingredient/reference image.

## 5. (C) Luồng GitHub repo → video thuyết minh

### 5.1 Hiện trạng: không tồn tại

Grep `github|GitHub|GITHUB` toàn `backend/` chỉ ra ba nhóm hit, **không cái nào** là ingestion: một URL trong docstring (`backend/utils/dac_shim.py:10`), CUDA release downloader (`backend/services/cuda.py:30,241,288`), và một ví dụ sửa lỗi typo Whisper (`backend/services/refinement.py:151`). Trong `app/src` cũng không có gì.

Một URL GitHub hôm nay sẽ đi vào một trong hai ngõ cụt:

- Nếu vào `/video-inspiration` như video URL: bị chặn ở allowlist `_SOCIAL_PLATFORMS` với `VIDEO_INSPIRATION_PLATFORM_UNSUPPORTED` (`backend/services/video_inspiration.py:96-103`, `:851-855`).
- Nếu vào `/research` như `docs_url`: `_attach_document` (`research_source_adapters.py:201-341`) fetch HTML rồi `html_extractor.extract` (`:233`), cap 100 000 ký tự và 100 observation (`:39-40`). Kết quả là **trang HTML của repo bị scrape như một bài viết** — không đi cây file, không hiểu README/commit/language, không có API client, không auth.

### 5.2 Chỗ đúng để thêm

Không phải `/video-inspiration` (nó là công cụ phân tích *video*). Đúng chỗ là **adapter thứ tư trong `/research`**, cạnh video/comic/document:

- Thêm `"repo_url"` vào `SOURCE_TYPES` (`backend/services/research.py:56`).
- Thêm vào pattern API `^(text|docs_url|video_url|story_url)$` (`backend/models.py:3511`) và mirror TS (`app/src/lib/api/types.ts:18`).
- Thêm nhánh `elif source.source_type == "repo_url": _attach_repo(...)` vào chuỗi dispatch (`research_source_adapters.py:359-366`).
- Adapter mới đọc GitHub REST: `GET /repos/{owner}/{repo}` (metadata), `/readme`, `/contents/{path}`, `/languages`, `/releases`. Rate limit: **60 req/giờ không auth, 5 000 req/giờ với PAT**. `contents` giới hạn 1 000 file/directory và file >100 MB không hỗ trợ; đi cây sâu thì dùng Git Trees API.
- Output map vào đúng shape mà `_attach_document` đã dùng (`observations`, `coverage`, `limitations`), nên phần handoff sang AI Video, memory card, quality report **không phải sửa gì**.

Sau đó đường sang video là đường đã có: research handoff → `/ai-video?projectId=…` (`docs/nghien-cuu-y-tuong-handoff-ai-video.md`), purpose `educational_explainer`, target language `vi` → Veo native speech. Không cần tính năng render mới.

### 5.3 Rủi ro cần cân nhắc trước khi làm

- **Auth.** 60 req/giờ không đủ cho một lần đi cây repo thật. Cần chỗ lưu PAT — repo hiện chưa có secret store cho GitHub token, phải thiết kế mới.
- **Repo private / nội dung không thuộc sở hữu.** Nên chặn hoặc yêu cầu xác nhận rõ, tương tự cách `research_source_security.py` đang xử lý nguồn khác.
- **Nội dung repo là dữ liệu không đáng tin.** README có thể chứa chuỗi trông như chỉ thị cho model. Cần đi qua đúng lớp sanitize mà `_attach_document` đang dùng, không truyền thô vào prompt.
- **Cap ký tự.** 100 000 ký tự của `_attach_document` sẽ tràn với repo trung bình; cần chiến lược chọn lọc (README + cấu trúc thư mục + language stats + N file quan trọng), không phải nạp hết.

## 6. Roadmap ưu tiên

Xếp theo tỉ lệ lợi ích trên rủi ro, không theo thứ tự câu hỏi.

**P0 — đo thời gian sinh clip Veo thật.** Chạy một job `POST /projects/{id}/clip-generation/jobs` với 3-4 shot, rồi đọc `started_at`/`completed_at` từng dòng `video_clip_generation_items`. Không sửa code. Đây là con số duy nhất còn thiếu để biết render có đáng tối ưu tiếp không. Nếu mỗi clip mất 60-120 giây thì 43 giây burn-in và 79 giây watermark là chuyện nhỏ, và trọng tâm phải chuyển sang lớp provider.

**P1 — `delogo` fast path cho clip đã biết là Veo.** Khi `resolve_clip_mark` trả `"veo"` và độ phân giải khớp một hộp đã hiệu chuẩn, chèn `delogo=…` vào đầu chuỗi filter của `build_normalize_clip_command` và bỏ hẳn lần gọi worker. Giữ worker Python làm fallback cho mark `"auto"` hoặc độ phân giải chưa hiệu chuẩn. Lợi: ~79 giây/18 clip về ~0, bỏ luôn một pass encode và một process/clip. Rủi ro: `delogo` là lấp mù theo toạ độ, không phát hiện — nếu Flow đổi vị trí watermark thì nó âm thầm không xoá gì. Vì vậy **phải** kèm một bước verify (chạy detector trên 1 frame, hoặc giữ report `visible_detected_frames` như hiện nay) chứ không tin toạ độ vô điều kiện.

**P2 — không burn-in phụ đề bằng một pass toàn timeline.** Hai lựa chọn: (a) mặc định `subtitle_mode` về `'soft'`/`'none'` và để burn-in là lựa chọn có cảnh báo thời gian; (b) cắt `.ass` theo từng clip và burn ngay trong pass normalize song song, để final mux giữ `-c:v copy`. (b) đúng hơn về kiến trúc nhưng cần xử lý offset thời gian per-clip. Lợi đo được: ~43 giây/timeline 143 giây.

**P3 — đường ingredient/reference image cho Flow.** Mở khoá dạng content 1 và 2. Bốn phần việc: cột/JSON field lưu ảnh tham chiếu trên prompt hoặc project; endpoint upload ảnh; `client.command("DOM.setFileInputFiles", …)` trong `video_veo_chrome.py` nhắm vào control ingredients của Flow; và validation ép `duration_seconds = 8` khi dùng ingredients. Rủi ro cao nhất trong danh sách vì phụ thuộc DOM Flow — nên làm sau khi P0 cho biết ngân sách thời gian thật.

**P4 — sửa hai lỗi nhỏ đã xác thực.** (a) `handoff_to_ai_video` không được đọc ở đâu: hoặc implement server-side auto-handoff, hoặc bỏ field để không hứa hẹn sai. (b) `POST /video-inspiration/jobs/from-url` và `/jobs/upload` block event loop: bọc bằng `asyncio.to_thread`. (c) thêm `AbortSignal` + timeout cho `apiClient.request`.

**P5 — adapter GitHub trong `/research`.** Giá trị thật nhưng là tính năng mới hoàn toàn, và cần thiết kế lưu PAT trước. Không nên làm trước P0-P2.

**Không làm:** NVENC cho normalize; `migan` làm mặc định; song song hoá sinh clip Veo trước khi có số đo và hạn mức credit rõ ràng.

## 7. Phạm vi xác minh

Đã xác thực bằng cách chạy thật:

- Đặc tả 3 video tham chiếu, kể cả việc video 3 có lời tiếng Việt do model sinh (Whisper local, model `base`).
- Toạ độ `delogo` cho cả 720x1280 và 1280x720, kiểm bằng mắt trên crop phóng đại trước/sau.
- Benchmark normalize 18 clip có/không `delogo`, 6 tiến trình song song.
- Benchmark final mux `-c:v copy` so với burn-in phụ đề.
- 4 render job trong `data/voicebox.db` cùng `render-cache-summary.json` và `timeline-manifest.json` tương ứng.
- Bug `handoff_to_ai_video` (grep toàn repo, 5 hit, không hit nào là đọc).
- Việc `chrome_cdp.py` không có primitive upload file.
- Việc không có GitHub ingestion ở bất kỳ đâu trong `backend/` và `app/src/`.

**Chưa xác thực được:**

- Thời gian sinh mỗi clip Veo qua Flow: bảng `video_clip_generation_items` trống, chưa có job nào chạy thật trên máy này.
- Ước tính "~171 giây cho render mặc định" là **phép cộng** 128,3 giây (đo, `subtitle_mode: none`) + 42,71 giây (đo riêng trên timeline tương đương), không phải một job thật đo end-to-end.
- Rate limit Veo trên Gemini API: trang rate limits không render bảng khi fetch, nên không có số.
- Việc `delogo` có ổn định trên mọi độ phân giải Flow xuất ra (4K, 1080p sau upscale) — chỉ hiệu chuẩn 2 kích thước.
- Chưa kiểm tra frontend `AIVideoAssistant.tsx` (~5 000 dòng) về hiệu năng render React; phạm vi câu hỏi là pipeline, không phải UI.

## 8. Nguồn

### Trong repo

Provider và sinh clip: `backend/services/video_veo_chrome.py`, `backend/services/chrome_cdp.py`, `backend/services/video_provider_sessions.py`, `backend/services/video_provider_project_bindings.py`, `backend/services/video_clip_generation.py`.

Planning: `backend/services/ai_planning.py`, `backend/services/video_phase2.py`, `backend/services/video_planning.py`, `backend/services/video_auto_runs.py`, `backend/services/video_planning_pool.py`, `backend/services/video_workflow_pool.py`.

Render và hậu kỳ: `backend/services/video_rendering.py`, `backend/services/video_watermark_cleanup.py`, `backend/workers/video_watermark_worker.py`, `backend/services/video_subtitles.py`.

Voice: `backend/services/video_voice.py`, `backend/services/video_speech.py`, `backend/services/qwen_vietnamese.py`, `backend/backends/__init__.py`.

Video Inspiration và research: `backend/routes/video_inspiration.py`, `backend/services/video_inspiration.py`, `backend/services/video_inspiration_runs.py`, `backend/services/research.py`, `backend/services/research_source_adapters.py`.

Model và schema: `backend/models.py`, `backend/database/models.py`, `backend/services/video_purpose.py`.

Frontend: `app/src/router.tsx`, `app/src/lib/api/client.ts`, `app/src/lib/aiVideoDraft.ts`, `app/src/lib/renderSettingsStore.ts`, `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx`, `app/src/components/VideoInspiration/VideoInspiration.tsx`.

Dữ liệu đo: `data/voicebox.db` (bảng `video_render_jobs`), `data/video_projects/05116e49-…/render_outputs/*/render-cache-summary.json`, `.../timeline-manifest.json`, 18 clip trong `.../shot_clips/`.

Tài liệu liên quan đã có: `docs/research/video-inspiration-runtime-timeouts.md`, `docs/ai-video-watermark-cleanup.md`, `docs/ai-video-quality-report.md`, `docs/nghien-cuu-y-tuong-handoff-ai-video.md`, `docs/research/google-flow-veo-credits-ultra.md`.

### Ngoài repo

- [Generate videos with Veo 3.1 in Gemini API](https://ai.google.dev/gemini-api/docs/video) — model id `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`; 8 giây, 24 fps, 720p/1080p/4k, 16:9 và 9:16; audio native luôn bật; `image`, `lastFrame`, `referenceImages` (tối đa 3 ảnh), `video` để extend; polling long-running operation 10 giây/lần; latency 11 giây tới 6 phút; video lưu trên server 2 ngày; watermark SynthID.
- [Learn about Google Flow models & supported features](https://support.google.com/flow/answer/16352836) — bảng tính năng theo model trong Flow: Text to Video, Frames to Video (First, First+last), Ingredients/References to Video, Video to Video editing, Extend videos.
- [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234) — credit cost mỗi generation; upscale 1080p 0 credit cho subscriber.
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) — Veo 3.1 tính theo giây, không có free tier; Veo 3 và Veo 2 deprecated, shutdown 2026-06-30.
- [Generate and edit videos with Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni) — `gemini-omni-flash-preview`, editing hội thoại nhiều lượt, aspect ratio 9:16/16:9, giới hạn theo vùng.
- [FFmpeg Filters — delogo](https://ffmpeg.org/ffmpeg-filters.html) — tham số `x`, `y`, `w`, `h`, `show`; nội suy từ các pixel ngay ngoài hình chữ nhật.
- [GitHub REST — rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) — 60 req/giờ không auth, 5 000 req/giờ với PAT.
- [GitHub REST — repository contents](https://docs.github.com/en/rest/repos/contents) — trần 1 000 file mỗi directory, file 1-100 MB chỉ hỗ trợ media type `raw`/`object`, >100 MB không hỗ trợ.

