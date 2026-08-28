## Tổng quan thiết kế

```text
/comic-series-analysis
  -> Link công khai hoặc upload nhiều ảnh
  -> Comic Web Ingestion độc lập
  -> Source snapshot + ảnh gốc đã xác thực
  -> Normalize/convert/tile + OCR/vision
  -> ComicAnalysisPackage có cấu trúc và revision
  -> Người dùng review, sửa và duyệt
  -> Preview handoff: Series mới hoặc Series hiện có
  -> Commit có optimistic lock, transaction và idempotency
  -> Series + StoryEpisode + toàn bộ SourceDocument/Chunk/Asset
  -> /story-studio?seriesId=...&episodeId=...
```

Change được chia thành ba module sâu, giao tiếp qua contract có phiên bản:

```text
ComicWebIngestion
    -> ComicSourcePackage.v1

ComicMultimodalAnalysis
    -> ComicAnalysisPackage.v1

ComicSeriesHandoff
    -> Series + StoryEpisodeSourceDocument.v1
```

## Quyết định thiết kế

### 1. Module độc lập, chỉ giao nhau ở domain Series

Frontend dùng component/workspace `ComicSeriesAnalysis` tại `/comic-series-analysis` và route chi tiết `/comic-series-analysis/$analysisId`. Backend dùng router/tag riêng `/comic-series-analysis`.

Model, service và job mới:

- Không có foreign key tới `video_inspiration_jobs`.
- Không import `video_inspiration.py`, `video_inspiration_runs.py` hoặc handoff AI Video.
- Không dùng status, schema timeline, transcript, frame hoặc retention của video.
- Không tạo source block AI Video và không có endpoint handoff trực tiếp AI Video.

Chỉ tái sử dụng hạ tầng trung lập như DB session, artifact storage, background coordinator, planning concurrency, observability, versioning và stale propagation. Nếu helper hiện mang tên video nhưng thực chất dùng chung, implementation phải tách facade `ai_media_*` hoặc module trung lập trước khi dùng.

Series đích vẫn dùng `VideoSeries` hiện có như kho Series canonical dù tên class là legacy. Không tạo bảng ComicSeries song song. Series mới từ luồng này chỉ cho `image_story_only` hoặc `hybrid`. Series `video_story_only` không phải target hợp lệ và không được tự đổi mode.

### 2. Route và điều hướng riêng

Frontend thêm:

```text
/comic-series-analysis
/comic-series-analysis/$analysisId
```

Sidebar hiển thị nhãn tiếng Việt `Phân tích truyện tranh`, độc lập với `Lấy cảm hứng từ video` và `Story Studio`.

Route danh sách chịu trách nhiệm tạo/chọn job. Route chi tiết chịu trách nhiệm progress, review và handoff. Sau commit, ứng dụng điều hướng tới:

```text
/story-studio?seriesId=<series_id>&episodeId=<story_episode_id>
```

Story Studio phải đọc deep-link, chọn đúng Series/Episode và vẫn hoạt động khi query không có hoặc ID không còn tồn tại.

### 3. URL là dữ liệu không tin cậy

`ComicWebIngestionService` chỉ nhận `http` và `https`, từ chối URL có userinfo, scheme khác, localhost, loopback, private, link-local, multicast, unspecified, reserved, carrier-grade NAT, cloud metadata và port ngoài policy.

Kiểm tra mạng áp dụng cho:

- URL người dùng nhập.
- Mỗi redirect.
- Canonical URL nếu được theo.
- Từng URL ảnh và subresource.
- Mọi request do browser fallback phát sinh.

DNS được kiểm tra trước kết nối và peer thực tế phải được xác nhận để giảm DNS rebinding. Fetch dùng streaming, timeout, redirect cap, response cap, page count, image count, total byte, pixel, concurrency và retry cap có cấu hình.

Log/debug phải redaction query nhạy cảm, userinfo, cookie, authorization header và không ghi full HTML, full chapter hoặc binary ảnh.

### 4. Không vượt kiểm soát truy cập

Người dùng phải xác nhận họ có quyền phân tích hoặc tái sử dụng nguồn theo mục đích đã chọn. Hệ thống lưu thời điểm xác nhận, usage/development mode và provenance.

Hệ thống không:

- Lấy cookie hoặc profile trình duyệt cá nhân.
- Tự đăng nhập.
- Vượt CAPTCHA, paywall, DRM hoặc anti-bot.
- Đánh cắp session hoặc credential.
- Tự tái đăng nội dung nguồn.

Browser fallback dùng context tạm, không có cookie, token hoặc mật khẩu; đóng và xóa profile sau job. Trạng thái chạy, độ đầy đủ và lý do được tách riêng: `run_status` mô tả vòng đời job, `result_completeness` mô tả `complete|partial|unavailable`, còn `authentication_required`, `captcha_required`, `access_denied` hoặc `needs_upload` là outcome/error code.

### 5. Static-first, browser fallback có điều kiện

Pipeline thử HTTP tĩnh trước. Nếu HTML tĩnh đạt ngưỡng coverage text/ảnh, không chạy browser.

Browser fallback chỉ chạy khi:

- Trang là shell JavaScript.
- Ảnh lazy-load chưa xuất hiện.
- Nội dung chỉ xuất hiện sau cuộn.
- Coverage dưới ngưỡng.
- Người dùng chủ động yêu cầu render mode.

Browser cách ly cuộn có giới hạn, theo dõi DOM/network image response và áp dụng cùng chính sách SSRF/dung lượng cho mọi request. Phạm vi mặc định là document/chương hiện tại; pagination cùng chương chỉ được theo trong giới hạn. Không tự crawl toàn bộ series hoặc toàn site.

Direct-image URL tạo một source document một trang. Content type khác HTML/ảnh trả `unsupported_content` hoặc hướng dẫn upload phù hợp, không tự định tuyến sang Video Inspiration.

### 6. HTML được parse và làm sạch trước khi AI thấy nội dung

Raw HTML được lưu tạm trong vùng cách ly theo retention policy và không đưa trực tiếp vào prompt. DOM extractor:

- Ưu tiên `article`, `main`, vùng chapter/story và metadata có bằng chứng.
- Loại `script`, `style`, `iframe`, `form`, menu, quảng cáo, bình luận, footer và nội dung ẩn không liên quan.
- Trích title, author, chapter identity, paragraph, dialogue text và ordered text chunks.
- Thu thập ảnh qua `src`, `srcset`, `picture/source`, Open Graph, lazy-load và network observation.
- Chuẩn hóa URL tương đối theo page URL tại thời điểm phát hiện.
- Giữ occurrence, DOM order, caption, alt text và provenance.

Text HTML, OCR và metadata luôn được bao trong cấu trúc dữ liệu nguồn không tin cậy. Câu như “bỏ qua quy tắc”, “đọc file hệ thống” hoặc “gọi công cụ” chỉ là dữ liệu, không phải instruction điều khiển AI.

### 7. Ảnh gốc và derivative là hai lớp khác nhau

Mỗi `ComicSourceAsset` giữ:

```text
original_path
source_url và referrer an toàn
detected_format
sniffed_mime_type
byte_size
width/height
frame/page count
checksum
source revision
occurrences và provenance
```

Original được lưu byte-for-byte, không resize, không đổi orientation và không ghi đè. “Full resolution” nghĩa là giữ đúng file máy chủ trả về trong quota cấu hình; file vượt hard limit tạo kết quả partial rõ ràng thay vì decode vô hạn.

Derivative gồm:

```text
analysis/   PNG hoặc JPEG đã áp EXIF orientation và chuẩn hóa ICC/sRGB
preview/    WebP dùng cho UI
tiles/      Tile có overlap và tọa độ cho webtoon/ảnh cực dài
exports/    PNG, WebP hoặc HEIC tạo theo yêu cầu
```

Derivative luôn lưu source asset ID, source checksum, codec/transform version, kích thước và mục đích. Thay codec hoặc transform tạo derivative revision mới; artifact cũ còn truy xuất được cho analysis/handoff đã dùng nó.

### 8. Registry codec thay vì nhánh if theo extension

`ImageCodecRegistry` phát hiện magic bytes và khai báo decoder, encoder, frame/page support, alpha, color profile và capability status.

Baseline:

- Pillow: PNG, JPEG/JPG, WebP, GIF/APNG, TIFF, BMP.
- HEIF adapter: HEIC/HEIF.
- AVIF adapter: AVIF.
- SVG adapter: sanitize rồi rasterize trong process cách ly.

Ảnh động hoặc multi-page giữ bản gốc và lấy frame/page đại diện hoặc tập frame/page theo giới hạn. SVG thô không được render hoặc thực thi trực tiếp trong UI; rasterizer tắt network/filesystem và loại script, event handler, external entity, `foreignObject` cùng external image/font/style URL.

Health check phải decode/encode fixture cho mọi codec bắt buộc. Full codec capability chỉ ready khi baseline PNG/JPEG/WebP/HEIC/HEIF/AVIF/GIF/APNG/TIFF/BMP/MPO/SVG đạt kiểm tra. Format ngoài baseline, optional codec thiếu hoặc runtime degraded vẫn giữ original với `codec_unavailable`; trạng thái này không được dùng để coi deployment đã đáp ứng acceptance codec bắt buộc.

Codec native và browser runtime phải được đóng gói/smoke-test trong build frozen. Thiếu native library phải làm capability unavailable có thông báo, không làm backend crash lúc import.

### 9. Ảnh dài được tile mà không mất bản full

Ảnh webtoon hoặc ảnh vượt ngưỡng pixel/ratio được chia tile theo reading direction, có overlap, stable ID và tọa độ trong ảnh gốc. OCR/vision chạy theo tile rồi hợp nhất về source asset, loại trùng ở vùng overlap nhưng giữ evidence tile.

Original vẫn được giữ nguyên. UI cho mở/download original, xem preview và xem tile dùng cho evidence.

### 10. Source snapshot và analysis revision tách nhau

Một lần fetch/upload bắt đầu source revision ở trạng thái `collecting`. Chỉ khi content hash, ordered asset manifest, original checksums, coverage và limitations được đóng băng, revision mới chuyển `finalized` và đủ điều kiện analysis/handoff. Retry nhận bytes/manifest khác phải tạo revision mới; chỉ derivative/checkpoint từ cùng original checksum mới được tái sử dụng trong revision cũ.

Revision finalized tạo `ComicSourcePackage.v1` bất biến gồm source metadata, ordered text chunks, ordered pages/assets, coverage, limitations và evidence IDs.

Re-fetch tạo source revision mới, không sửa snapshot cũ. Analysis revision tách khỏi source revision để người dùng có thể sửa OCR, panel order, speaker hoặc character grouping mà vẫn truy vết dữ liệu gốc.

Các bảng khái niệm:

```text
ComicAnalysisJob
ComicSourceDocument
ComicSourcePage
ComicSourceAsset
ComicPanel
ComicSpeechBubble
ComicDetectedCharacter
ComicDetectedLocation
ComicPlotAnalysis
ComicSeriesHandoff
ComicSeriesHandoffItem
StoryEpisodeSourceDocument
StoryEpisodeSourceChunk
StoryEpisodeSourceAsset
```

Các collection lớn được lưu theo row/chunk thay vì một JSON khổng lồ; analysis package có thể giữ summary/index và stable IDs.

### 11. OCR/vision phải thật sự đọc pixel

Không coi việc ghi đường dẫn ảnh vào prompt text là phân tích multimodal đáng tin cậy. `ComicOcrAdapter` và `ComicVisionAdapter` có capability check riêng.

AI adapter phải nhận ảnh qua image input chính thức, bytes, multipart/file handle thực sự gắn vào trường image input hoặc provider file ID tương đương. Request manifest ánh xạ attachment với `asset_id`, `tile_id`, page order và tọa độ nguồn.

Nếu attachment vượt giới hạn request, hệ thống chia batch có thứ tự, giữ context nhận dạng liên batch và tổng hợp theo stable ID. Nếu provider không thể đọc ảnh, job giữ ảnh, dùng OCR deterministic nếu có và đánh `vision_unavailable`/`partial`; không bịa visual description.

Acceptance test phải dùng fixture có thông tin chỉ suy ra được từ pixel để chứng minh adapter thực sự xem ảnh.

### 12. Phân tích đa phương thức có evidence và confidence

Pipeline phân tích:

```text
ordered page/asset
  -> tile/frame/page selection
  -> panel detection và reading order
  -> bubble/text region
  -> OCR + language + content role
  -> speaker inference
  -> character clustering
  -> location/world analysis
  -> plot/canon/state synthesis
  -> ComicAnalysisPackage.v1
```

Reading mode gồm `auto`, `vertical`, `page_ltr`, `page_rtl`; người dùng có thể override và kéo sắp xếp lại.

Mỗi item quan trọng có:

```text
stable ID
evidence_ids
source modality
page/panel/tile/bounding region
confidence
observed | inferred | user_edited
limitations
```

Confidence dùng scale `[0,1]` hoặc `null`, lưu method/model version và threshold config version. UI chỉ ánh xạ nhãn thấp/vừa/cao từ threshold có version, không tự suy diễn.

Nhân vật được nhóm qua hình ảnh, tên, alias, lời thoại và ngữ cảnh. Confidence thấp hoặc evidence mâu thuẫn tạo `possible_duplicate`/`uncertainty`; không tự gộp thành danh tính đã xác nhận.

### 13. Structured output và planning concurrency

Mọi bước AI trả JSON theo schema có version, validate trước khi ghi trạng thái completed. Output invalid không được ghi partial thành kết quả hợp lệ; output cũ được giữ nếu retry thất bại.

Các lần gọi AI đi qua planning pool chung với workflow type riêng `comic_series_analysis`. Không dùng work key hoặc step name của Video Inspiration. Log chỉ giữ job ID, step, duration, attachment count, schema keys, coverage và error code; không ghi full source/prompt.

### 14. Hai cổng duyệt, nguồn không tự thành canon

Cổng 1 duyệt analysis revision:

- Sửa/bỏ text, OCR, speaker, page/panel order.
- Gộp/tách/đặt tên nhân vật.
- Sửa bối cảnh, plot và canon candidate.
- Chọn ảnh có thể handoff.
- Chấp nhận limitation của kết quả partial.

Khi duyệt, hệ thống tạo approval manifest bất biến gồm hash/revision của mọi item `accepted`, danh sách `excluded`, item còn `unreviewed`, limitation đã chấp nhận, requested development mode và rights attestation revision. Item `unreviewed` không được handoff hoặc dùng làm nguồn approved. Sửa selection/nội dung sau approval tạo revision/manifest mới và vô hiệu approval cũ.

Cổng 2 duyệt handoff preview:

- Chọn item create/update/merge/skip.
- Giải quyết duplicate/conflict.
- Chọn Series mode, episode number/title và development mode.
- Xác nhận dữ liệu sẽ được ghi.

Approval analysis chỉ có nghĩa “đủ điều kiện handoff”. Cổng handoff thứ hai là approval đích theo từng item/field hiển thị trong preview: với Series mới, Bible/Profile field chỉ được ghi canonical khi người dùng chọn rõ; với Series hiện có, mọi thay đổi canonical hoặc Profile field phải có quyết định field-level. Item chưa được chọn chỉ tạo proposal/memory/current-state draft nếu người dùng yêu cầu. Reference Asset được chọn luôn bắt đầu `pending_approval`, `active=false`.

### 15. Handoff mang đầy đủ dữ liệu cấp Series và Episode

Mapping cấp Series:

```text
Tên truyện                    -> VideoSeries.title
Mô tả tổng quan/thể loại      -> SeriesMemoryCard loại series_summary
Phong cách kể/hình            -> style_bible + memory đã chọn
Bối cảnh/quy tắc thế giới     -> world_bible + location memory
Canon đã chọn                 -> continuity proposal/rule theo quyết định user
Nhân vật đã chọn              -> SeriesCharacterProfile
Quan hệ/trạng thái            -> SeriesMemoryCard/SeriesCurrentState
Ảnh nhân vật/địa điểm chọn    -> SeriesReferenceAsset pending + inactive
```

Mapping cấp Episode:

```text
Chương đang phân tích         -> StoryEpisode
Market/ngôn ngữ chương        -> StoryEpisode market_profile/language_profile
Văn bản HTML đã làm sạch      -> StoryEpisodeSourceDocument
Text/OCR/thoại/narration      -> StoryEpisodeSourceChunk có thứ tự/evidence
Trang/panel/bubble            -> source sequence + structured evidence
Ảnh gốc và derivative         -> StoryEpisodeSourceAsset/link bất biến
Plot beat/structure           -> Episode creative brief/source analysis
Tóm tắt diễn biến chương      -> Episode synopsis + memory proposal của tập
URL/fetched_at/hash/revision  -> provenance
Limitation/uncertainty        -> source limitations
```

`previous_episode_summary` không được tự ghi bằng tóm tắt của chính chương vừa nhập. Field này chỉ được cập nhật theo workflow duyệt/hoàn tất tập hiện có hoặc khi nguồn cung cấp rõ phần diễn biến trước chương hiện tại.

Không nhét full source vào `StoryEpisode.source_input`. Field đó giữ projection <= 50.000 ký tự cho tương thích. Source Document là nguồn chuẩn.

### 16. Story Episode Source được chia chunk và truy xuất theo nhiệm vụ

`StoryEpisodeSourceDocument` giữ raw extracted text/OCR, AI-normalized content và approved content, cùng source/analysis/handoff revision, chapter metadata, coverage, limitations và provenance. `raw` tại Episode Source không phải raw HTML có script; raw HTML chỉ có thể nằm tạm trong `ComicSourceDocument` cách ly theo retention policy và không được handoff làm nội dung Episode.

`StoryEpisode` có nullable `current_source_document_id` và `development_mode`. Mỗi source document có `revision`, `approval_status`, `previous_revision_id` và unique revision per Episode. Có nhiều revision lịch sử nhưng nhiều nhất một current approved document; handoff/update phải tạo document mới và đổi pointer atomically. Episode legacy có pointer null tiếp tục dùng `source_input`.

`StoryEpisodeSourceChunk` giữ:

```text
chunk_order
chunk_type
approved text
raw/AI text khi cần
page/panel/bubble refs
speaker ref
evidence IDs
confidence
source revision
```

Story Studio context compiler ghim synopsis, plot beats và source revision, rồi chọn chunks liên quan theo nhiệm vụ và char budget. Full document vẫn lưu và xem được. Candidate, Master Story và adaptation lưu dependency tới source document/chunk revision thực sự đã dùng.

Stale được biểu diễn rõ trên model hiện có/migration mới: candidate dùng `generation_status = stale` và `evaluation_status = stale`, bỏ `selected`; Master Story giữ payload nhưng `approval_status = stale` và xóa `approved_at`; adaptation tiếp tục dùng `status = stale`. API không được cho chọn, synthesize hoặc tạo adaptation từ artifact stale.

Series Memory chỉ giữ index, summary và kiến thức dài hạn đã duyệt; không sao chép toàn bộ chương vào `series-memory.md`.

### 17. Development mode kiểm soát mức độ bám nguồn

Episode nhập từ truyện tranh lưu:

```text
lay_cam_hung_va_viet_moi
bam_canon_va_phat_trien_tiep
```

Nguồn bên ngoài mặc định `lay_cam_hung_va_viet_moi`; AI tránh sao chép nguyên văn đoạn dài, lời thoại dài hoặc trình tự cảnh đặc thù không cần thiết. `bam_canon_va_phat_trien_tiep` chỉ khả dụng khi người dùng xác nhận quyền phù hợp. Approval manifest, preview fingerprint và idempotency payload đều chứa mode + rights attestation revision; commit copy chúng vào Story Episode. Đổi mode tăng Episode revision và làm stale candidate/Master Story phụ thuộc mode cũ.

Mode viết mới tạo originality-check artifact gồm longest verbatim span, overlap theo source chunks, semantic similarity, algorithm/threshold version và allowlist tên riêng/trích dẫn ngắn. Vượt ngưỡng chặn approval hoặc yêu cầu override có lý do.

### 18. Handoff vào Series hiện có là merge có conflict

Preview nhận approved analysis revision và một `target_dependency_fingerprint`, phân loại `create`, `update`, `merge`, `skip`, `duplicate`, `conflict`. Fingerprint là revision vector/hash của Series row, Story Episodes liên quan, Character Profiles, approved Memory/Current State, relevant References và các entity đích mà preview đã đọc.

Kiểm tra tối thiểu:

- Source/content hash hoặc chapter đã nhập.
- Episode number/title trùng.
- Nhân vật cùng tên nhưng ngoại hình khác.
- Nhân vật khác tên nhưng có thể cùng người.
- Reference checksum trùng.
- Canon/world/style mâu thuẫn.
- Quan hệ/current state xung đột.

AI chỉ đề xuất match; người dùng chọn merge, create, skip hoặc field-level resolution. Không tự ghi đè fixed traits hoặc canon đã duyệt. Commit kiểm tra lại fingerprint tổng và expected revision của từng item được cập nhật.

New Series preview cho chọn `image_story_only` hoặc `hybrid`, episode number/title và output intent hợp lệ. Handoff không kích hoạt nhánh video.

### 19. Commit có fingerprint, optimistic lock và idempotency

`ComicSeriesHandoff` lưu analysis revision, approval manifest hash, rights attestation revision, development mode, target dependency fingerprint/revision vector, mapping/schema version, preview fingerprint, item decisions, idempotency key, status và created target IDs. Nếu matching dùng AI, kết quả matching phải được persist/version hóa thành input của preview; không gọi AI ngầm làm cùng input tạo fingerprint khác.

Commit từ preview cũ bị từ chối nếu analysis hoặc bất kỳ dependency đích liên quan đổi. Cùng idempotency key + payload luôn ánh xạ một operation ID qua restart: operation retryable được resume, terminal success/failure trả lại terminal result; muốn attempt logic mới sau terminal failure phải dùng key mới. Dùng lại key với payload khác bị từ chối.

DB records được ghi trong một transaction. Các service hiện commit nội bộ cần repository/`commit=False`/`flush` path dành cho orchestration; không gọi tuần tự public service rồi hy vọng rollback.

Protocol file/DB được chốt như sau:

1. Validate và ghi toàn bộ file bắt buộc vào staging manifest theo operation ID.
2. Ghi operation handoff bền vững ở trạng thái `committing`.
3. Promote file bằng atomic rename tới content-addressed final path; thao tác phải idempotent.
4. Mở một DB transaction, tạo/flush toàn bộ target rows tham chiếu final path rồi commit DB sau cùng.
5. Nếu promote hoặc DB commit lỗi, target rows rollback; manifest đánh dấu cleanup các final file mới không còn DB reference.
6. Startup recovery xử lý operation `committing`, kiểm tra idempotency result và cleanup/retry an toàn.

Handoff status dùng `previewed|committing|committed|failed|rolled_back`. Target Series/Episode chỉ xuất hiện sau khi file bắt buộc đã tồn tại và DB commit thành công. `series-memory.md` chỉ sync sau commit.

### 20. Revision, stale và re-import

Sửa review tăng analysis revision và làm stale mọi preview chưa commit. Re-fetch URL tạo source revision mới và hiển thị diff; không tự sửa Series đã handoff.

Người dùng phải duyệt revision mới và tạo preview update mới. Chỉ sau commit update handoff, Story Episode chuyển source revision. Candidate, Master Story và adaptation phụ thuộc revision cũ mới stale theo dependency.

Re-analysis chưa commit chỉ hiển thị `Có phiên bản nguồn mới`, không lan stale sang Series.

Asset đang được Episode hoặc Reference tham chiếu không được xóa khi xóa job; retention dựa trên reference hoặc immutable asset link. Checksum dùng dedupe blob nhưng không gộp provenance của hai nguồn.

### 21. Job nền có checkpoint, cancel và retry

`run_status` cấp job:

```text
draft | queued | running | ready_for_review | approved | failed | cancelled | interrupted
```

Độ đầy đủ tách riêng:

```text
result_completeness = complete | partial | unavailable
```

`current_step`:

```text
validate_source
fetch_html
render_browser
extract_content
download_assets
normalize_images
ocr
panel_analysis
character_analysis
story_analysis
build_review
```

Mỗi bước lưu progress, coverage, result completeness, error code và checkpoint. Kết quả partial vẫn có thể đi tới `ready_for_review`, rồi `approved` nếu người dùng chấp nhận limitation. Cancel là cooperative; subprocess/adapter dài cần cancellation hook hoặc timeout rõ. Retry tái sử dụng artifact checksum hợp lệ và chỉ chạy lại bước thiếu/lỗi. Startup recovery chuyển run dở sang retryable/interrupted thay vì giả định task cũ còn sống.

### 22. API khái niệm

```text
POST /comic-series-analysis/jobs/from-url
POST /comic-series-analysis/jobs/from-upload
GET  /comic-series-analysis/jobs
GET  /comic-series-analysis/jobs/{job_id}
POST /comic-series-analysis/jobs/{job_id}/run
POST /comic-series-analysis/jobs/{job_id}/cancel
POST /comic-series-analysis/jobs/{job_id}/retry

PUT  /comic-series-analysis/jobs/{job_id}/pages/reorder
PUT  /comic-series-analysis/jobs/{job_id}/panels/{panel_id}
PUT  /comic-series-analysis/jobs/{job_id}/dialogues/{dialogue_id}
PUT  /comic-series-analysis/jobs/{job_id}/characters/{character_id}
POST /comic-series-analysis/jobs/{job_id}/characters/merge
POST /comic-series-analysis/jobs/{job_id}/characters/split
PUT  /comic-series-analysis/jobs/{job_id}/analysis
POST /comic-series-analysis/jobs/{job_id}/approve

GET  /comic-series-analysis/assets/{asset_id}/original
GET  /comic-series-analysis/assets/{asset_id}/preview
POST /comic-series-analysis/assets/{asset_id}/exports

POST /comic-series-analysis/jobs/{job_id}/series-handoff/preview
POST /comic-series-analysis/jobs/{job_id}/series-handoff/commit
GET  /comic-series-analysis/jobs/{job_id}/series-handoff
```

Không có endpoint `handoff/ai-video`.

### 23. UI review và handoff preview

Input:

- Tab `Link web truyện` và `Upload ảnh`.
- Scope document/chương hiện tại hoặc pagination cùng chương có giới hạn.
- Reading mode auto/dọc/theo trang trái-phải/phải-trái.
- Development mode.
- Xác nhận quyền sử dụng.

Progress hiển thị bước, text chunks, ảnh tìm thấy/tải/convert/lỗi, page/panel/bubble count và modality coverage.

Review tabs:

```text
Nội dung truyện
Trang và panel
Lời thoại
Nhân vật
Bối cảnh
Cốt truyện
Canon
Ảnh nguồn
Cảnh báo
```

Handoff preview hiển thị counts full Episode content, item decisions, conflict, target revision và limitation. UI không yêu cầu người dùng đọc raw JSON. Mobile/desktop không chồng lấp; grid/panel có kích thước ổn định; thao tác reorder/merge/split có keyboard/focus hợp lý.

### 24. Xóa dữ liệu và retention

Xóa analysis job phải:

- Chặn hoặc cảnh báo nếu source/asset đang được handoff tham chiếu.
- Xóa row/file không còn reference theo manifest.
- Không xóa Source Document, Reference Asset hoặc blob đang được Series/Episode dùng.
- Cleanup staging/derivative orphan rõ ràng.
- Trả counts tiếng Việt cho dữ liệu đã xóa/giữ.

SQLite foreign-key behavior không được giả định tự cleanup; migration/service phải có cleanup explicit và test orphan.

### 25. Bảo mật và observability

- URL, HTML và ảnh là dữ liệu không tin cậy.
- Không log cookie, credential, query nhạy cảm, raw HTML dài, full source hoặc full prompt.
- Debug dùng hash, length, counts, field path, attachment IDs và error code.
- Technical download endpoint kiểm tra ownership/scope ID và canonical storage path, không nhận path tùy ý.
- Original/preview/export có content disposition và MIME an toàn; SVG raw không inline-render.
- Browser/network/codec/AI failures trả mã ổn định và thông báo tiếng Việt.

## Rủi ro và giảm thiểu

- Website đa dạng hoặc anti-bot: static-first, isolated browser fallback, partial result và manual upload.
- SSRF/DNS rebinding: validate URL/redirect/subresource, pin/verify peer, caps và network interception.
- Codec không đồng đều: registry/capability status, giữ original dù chưa decode, native dependency smoke test.
- Ảnh cực lớn gây RAM/disk: streaming, quota, max pixels/frame, tiles, cancellation và GC.
- OCR/panel/character sai: evidence/confidence, hai cổng duyệt, reorder và merge/split thủ công.
- Handoff mất nội dung: SourceDocument/Chunk/Asset bắt buộc và test chứng minh không chỉ lưu synopsis.
- Ghi Series dở: transaction-aware repository, staging/compensation, optimistic lock và idempotency.
- Trùng hoặc ghi đè canon: conflict preview, field-level decision, không auto merge approved data.
- AI không thật sự xem ảnh: image attachment contract và pixel-only acceptance fixture.
- Prompt injection từ web: sanitize DOM, source envelope không tin cậy và cấm model tự duyệt URL/file.
- Trộn domain Video Inspiration: architecture/test chặn import, FK, route và direct AI Video handoff.
- Sao chép nguồn ngoài quyền: rights confirmation, development mode mặc định viết mới và provenance/originality review.

## Kế hoạch migration

1. Thêm bảng Comic Analysis, source/evidence, handoff và StoryEpisodeSourceDocument/Chunk/Asset bằng migration idempotent.
2. Thêm codec registry, URL security/fetcher, DOM extractor, isolated browser adapter và storage layout.
3. Thêm OCR/vision adapters và structured schemas có evidence/confidence.
4. Thêm background run/cancel/retry/startup recovery.
5. Thêm review APIs/UI route/menu.
6. Thêm handoff preview/commit transaction-aware, provenance, revision/stale và memory sync.
7. Mở rộng Story Studio deep-link/context compiler để dùng nguồn có cấu trúc.
8. Bổ sung build packaging cho native codec/browser runtime và smoke test frozen app.
9. Chạy test SSRF, redirect, DNS, HTML/JS/lazy-load, codec fixtures, webtoon tiles, prompt injection, partial/cancel/retry, review, handoff new/existing/conflict/idempotency/rollback và xác nhận không gọi Video Inspiration/AI Video.

## Khả năng quay lui

Có thể ẩn route bằng feature flag và dừng nhận job mới. Dữ liệu Comic Analysis và Story Episode Source là additive; Story Studio cũ vẫn dùng `source_input` fallback.

Handoff đã commit không bị xóa khi rollback feature. Source provenance và asset retention tiếp tục được giữ. Có thể tắt browser/codec/vision adapter riêng lẻ và trả trạng thái capability unavailable mà không làm mất original/source snapshot đã lưu.
