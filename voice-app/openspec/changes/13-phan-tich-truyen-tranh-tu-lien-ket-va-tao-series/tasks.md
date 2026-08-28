## 1. Ranh giới tính năng và hợp đồng công khai

- [x] 1.1 Tạo module tính năng độc lập `comic_series_analysis`, route frontend `/comic-series-analysis` và backend prefix `/comic-series-analysis`; không đặt UI hoặc API mới dưới Video Inspiration.
- [x] 1.2 Thêm kiểm thử boundary chứng minh module mới không import `video_inspiration.py`, route/model Video Inspiration hoặc handoff AI Video.
- [x] 1.3 Chỉ cho phép kết quả đã duyệt handoff sang Series và Story Studio; không thêm endpoint hoặc nút handoff trực tiếp sang AI Video.
- [x] 1.4 Định nghĩa schema version cho gói nguồn, kết quả phân tích và handoff, kèm revision, evidence ID, confidence, coverage và limitations.
- [x] 1.5 Chuẩn hóa trạng thái job, bước tiến độ, trạng thái partial/interrupted/cancelled và bộ mã lỗi tiếng Việt ổn định.
- [x] 1.6 Thêm cấu hình typed cho feature flag, timeout, redirect, dung lượng HTML, số ảnh, tổng byte, tổng pixel, số frame/page, concurrency và số lần cuộn browser.
- [x] 1.7 Định nghĩa hai chế độ sử dụng nguồn: `lay_cam_hung_va_viet_moi` mặc định và `bam_canon_va_phat_trien_tiep` chỉ khi người dùng xác nhận quyền sử dụng.
- [x] 1.8 Ghi tài liệu ranh giới rõ rằng mọi domain HTTP/HTTPS công khai được tiếp nhận theo best-effort, không phải cam kết vượt kiểm soát truy cập.
- [ ] 1.9 Chốt invariant trước migration: mỗi Story Episode có tối đa một `current_source_document_id` trỏ tới Source Document approved; revision cũ bất biến và Episode legacy có pointer null dùng `source_input`.
- [ ] 1.10 Chốt `development_mode` và rights attestation là dữ liệu cấp Story Episode; ingestion chỉ lưu requested mode, còn handoff commit mới tạo nguồn chuẩn.
- [x] 1.11 Chốt biểu diễn stale: candidate dùng generation/evaluation status `stale` và bỏ selected; Master Story dùng approval status `stale`; adaptation tiếp tục dùng status stale.
- [ ] 1.12 Định nghĩa approval manifest bất biến với item `accepted/excluded/unreviewed`, limitation được chấp nhận, manifest hash và quy tắc chỉ accepted item được handoff/compiler dùng.
- [x] 1.13 Chuẩn hóa confidence thành `[0,1] | null`, lưu method/model/threshold version và mapping nhãn thấp/vừa/cao.

## 2. Mô hình dữ liệu và migration

- [x] 2.1 Thêm model `ComicAnalysisJob` lưu nguồn, trạng thái, bước hiện tại, tiến độ, revision, schema version, coverage, limitations, lỗi và thời gian.
- [x] 2.2 Thêm `ComicSourceDocument`, `ComicSourcePage` và `ComicSourceAsset` để lưu snapshot, text đã làm sạch, thứ tự trang/ảnh, đường dẫn artifact, checksum và provenance.
- [x] 2.3 Thêm `ComicPanel` và `ComicSpeechBubble` để lưu reading order, bounding box, OCR, lời thoại đã duyệt, người nói, mô tả hình ảnh và confidence.
- [x] 2.4 Thêm model cho nhân vật, địa điểm, quan hệ, canon candidate, plot analysis và hướng phát triển; mọi nhận định phải liên kết được với evidence.
- [x] 2.5 Thêm `ComicSeriesHandoff` và `ComicSeriesHandoffItem` để lưu preview, quyết định giải quyết xung đột, item đã tạo/cập nhật/bỏ qua và idempotency key.
- [x] 2.6 Thêm `StoryEpisodeSourceDocument`, `StoryEpisodeSourceChunk` và `StoryEpisodeSourceAsset` để lưu toàn bộ nội dung đã duyệt, HTML text, OCR, dialogue, narration, page/panel sequence, ảnh và provenance.
- [x] 2.7 Thêm index cho job status, source hash, page/asset order, checksum, character evidence, handoff idempotency và source document revision.
- [x] 2.8 Export toàn bộ model mới qua lớp database hiện có và thêm request/response Pydantic mà không nhồi payload dài vào response danh sách/polling.
- [x] 2.9 Thêm migration SQLite idempotent riêng, gọi trong `run_migrations()`, cập nhật normalize-storage-path và kiểm tra chạy hai lần không thay đổi dữ liệu cũ.
- [x] 2.10 Không dựa riêng vào foreign key cascade; bổ sung cleanup tường minh và test orphan vì runtime hiện chưa bảo đảm SQLite foreign-key enforcement.
- [x] 2.11 Thêm revision, approval, source/analysis schema version và optimistic-lock fields cho các entity người dùng có thể chỉnh sửa.
- [x] 2.12 Thêm mapping/version record để truy ngược target Series/Episode/Profile/Memory/Reference về analysis revision, handoff ID và evidence nguồn.
- [x] 2.13 Thêm `current_source_document_id` và `development_mode` vào Story Episode; thêm unique revision chain, approval status và previous revision cho Source Document, kèm thao tác đổi pointer nguyên tử.
- [x] 2.14 Mở rộng Story Scenario Candidate/Master Story contract để lưu source document revision, development mode, dependency fingerprint và trạng thái stale có thể chặn sử dụng.
- [x] 2.15 Thêm source lifecycle `collecting|finalized`; content hash, ordered asset manifest và original checksums phải bất biến sau finalize.
- [x] 2.16 Thêm approval manifest model/table hoặc immutable JSON artifact liên kết analysis revision, item revisions, rights attestation revision và requested development mode.
- [ ] 2.17 Chốt policy target approval phù hợp model hiện tại: cổng handoff thứ hai là approval field-level cho Bible/Profile được chọn; item chưa chọn chỉ tạo proposal/memory/current-state draft, reference luôn pending/inactive.

## 3. Tải URL an toàn

- [x] 3.1 Xây bộ xác thực URL dùng chung chỉ nhận HTTP/HTTPS công khai, từ chối userinfo, scheme nguy hiểm, localhost, loopback, private, link-local, multicast, reserved và cloud metadata.
- [x] 3.2 Resolve và kiểm tra cả IPv4/IPv6; kiểm tra lại từng redirect, URL ảnh và request con trước khi kết nối.
- [x] 3.3 Chống DNS rebinding bằng cách xác thực địa chỉ đã resolve và địa chỉ peer thực tế hoặc dùng transport có cơ chế pin đích phù hợp.
- [x] 3.4 Dùng HTTP client streaming với `trust_env=False`, timeout theo pha, redirect hữu hạn và giới hạn byte sau giải nén.
- [x] 3.5 Phân loại response thành HTML, direct image hoặc unsupported bằng header kết hợp magic bytes; không tin riêng extension hay Content-Type.
- [x] 3.6 Làm sạch URL lưu trữ và log, loại userinfo cùng query nhạy cảm; vẫn lưu URL nguồn đã redaction, thời điểm tải, HTTP metadata và content hash.
- [x] 3.7 Không lấy cookie trình duyệt, không vượt đăng nhập, CAPTCHA, paywall, DRM hoặc anti-bot; trả trạng thái và hướng xử lý rõ ràng.
- [ ] 3.8 Kiểm tra robots/chính sách nhập nguồn theo policy cấu hình; rule disallow phải chặn automated retrieval hoặc chuyển `needs_upload`, đồng thời yêu cầu người dùng xác nhận quyền trước khi chạy AI.
- [ ] 3.9 Cho phép kết quả `partial` khi chỉ lấy được một phần text/ảnh, đồng thời lưu chính xác asset nào lỗi và lý do.
- [x] 3.10 Thêm budget theo job cho số trang, số ảnh, tổng byte, redirect, timeout, concurrency và retry; vượt budget phải dừng có kiểm soát.
- [x] 3.11 Viết policy testable cho port, carrier-grade NAT, peer verification, browser-generated subresource, userinfo và URL redaction; không dùng mô tả chung chung `transport phù hợp` làm acceptance.

## 4. Trích xuất HTML và browser fallback

- [x] 4.1 Thêm parser HTML có cấu trúc và bộ chọn nội dung chính; loại script, style, iframe, form, menu, quảng cáo, comment và nội dung ẩn không liên quan.
- [x] 4.2 Trích tiêu đề, tác giả, tên chương, đoạn văn, lời thoại và heading thành các chunk có thứ tự và evidence ID ổn định.
- [x] 4.3 Phát hiện ảnh từ `src`, `srcset`, `picture/source`, lazy-load attributes, Open Graph, CSS background và URL tương đối theo `base`.
- [x] 4.4 Giữ thứ tự ảnh theo DOM và hỗ trợ chế độ tự động, truyện dọc, trang trái-phải và trang phải-trái.
- [x] 4.5 Chạy static HTTP trước; chỉ dùng browser fallback khi coverage thấp, trang cần JavaScript hoặc ảnh lazy-load chưa xuất hiện.
- [x] 4.6 Browser fallback phải dùng profile tạm, không cookie, không extension, không tài khoản, không truy cập file local và không tái sử dụng profile provider video.
- [x] 4.7 Chặn request browser tới mạng riêng và scheme nguy hiểm bằng request interception; áp dụng cùng giới hạn host, redirect, byte và concurrency như static fetch.
- [x] 4.8 Cuộn trang/infinite scroll theo giới hạn số vòng, chiều cao, thời gian và số asset; phát hiện khi trang không còn thay đổi để dừng.
- [x] 4.9 Coi toàn bộ HTML/text là dữ liệu không tin cậy, đánh dấu prompt injection và không cho nội dung website trở thành chỉ dẫn điều khiển hệ thống.
- [x] 4.10 Hỗ trợ direct-image URL như nguồn một trang và trả `unsupported_content` cho loại nội dung ngoài HTML/ảnh mà không tạo job Video Inspiration.
- [ ] 4.11 Hỗ trợ fallback dán text đã có quyền sử dụng vào job bị login/CAPTCHA; text này có provenance `manual_text`, revision và review chung với nguồn ảnh.
- [ ] 4.12 Finalize source revision sau collection; refetch cùng hash/manifest tái sử dụng snapshot, còn bytes/manifest khác bắt buộc tạo source revision mới.

## 5. Pipeline ảnh và codec

- [x] 5.1 Tạo `ImageCodecRegistry` phát hiện khả năng runtime cho PNG, JPEG, WebP, HEIC/HEIF, AVIF, GIF/APNG, TIFF, BMP, MPO và SVG.
- [ ] 5.2 Bổ sung dependency và đóng gói cần thiết cho HEIC/HEIF, AVIF và SVG; kiểm tra codec thật trong sidecar đóng gói thay vì chỉ kiểm tra môi trường dev.
- [x] 5.2a Thêm startup/health fixture cho từng codec bắt buộc; full codec capability không được báo ready nếu thiếu bất kỳ baseline decoder/encoder/rasterizer nào.
- [x] 5.3 Luôn lưu nguyên bytes ảnh gốc, checksum và format thật; không resize, đổi màu hoặc ghi đè file original.
- [x] 5.4 Kiểm tra magic bytes, decode thật, số frame/page, kích thước, tổng pixel và decompression bomb trước khi đưa ảnh vào phân tích.
- [x] 5.5 Chuẩn hóa EXIF orientation, ICC/sRGB và alpha thành bản analysis phù hợp; tạo preview WebP riêng cho UI.
- [x] 5.6 Hỗ trợ export full-resolution PNG, WebP hoặc HEIC theo yêu cầu mà không thay đổi bản gốc; lỗi một export không làm mất original.
- [x] 5.7 Với webtoon dài, giữ ảnh gốc và tạo tile có overlap để OCR/vision đọc được chữ nhỏ; lưu tọa độ tile về ảnh nguồn.
- [ ] 5.7a Hợp nhất OCR/vision từ tile về ảnh nguồn, loại trùng vùng overlap nhưng giữ tile evidence và tọa độ.
- [x] 5.8 Với GIF/APNG/animated WebP/TIFF/HEIF/MPO nhiều frame hoặc page, giữ bản gốc và trích frame/page theo giới hạn; báo coverage nếu không phân tích toàn bộ.
- [x] 5.9 Sanitize và rasterize SVG trong process cách ly, tắt network/filesystem, loại script, event handler, external entity, `foreignObject`, external image/font/style URL và không inline-render raw SVG.
- [x] 5.10 Loại ảnh trùng bằng checksum/perceptual hash nhưng vẫn giữ evidence về vị trí xuất hiện; trạng thái `codec_unavailable` vẫn cho tải original.
- [x] 5.11 Lưu codec/transform version trên mọi derivative và tạo revision mới khi pipeline chuyển đổi thay đổi.
- [x] 5.12 Thêm endpoint original/preview/export với canonical storage path, MIME và Content-Disposition an toàn; không nhận path tùy ý từ client.
- [x] 5.13 Tính `decoded_pixel_hash` sau orientation/colorspace normalization, lưu transform version và chỉ dùng perceptual hash khi algorithm/version/threshold được ghi rõ.

## 6. OCR, vision và phân tích truyện

- [x] 6.1 Tạo `ComicOcrAdapter` và `ComicVisionAdapter` với capability check, image attachment manifest và API bytes/multipart/provider-file thực; không coi đường dẫn file trong prompt text là bằng chứng AI đã xem ảnh.
- [x] 6.2 Khi provider không hỗ trợ vision hoặc ảnh không được đính kèm thành công, dừng bước visual với mã lỗi rõ ràng thay vì tạo nhận định giả.
- [x] 6.3 Phân tích trang/panel theo reading order, phát hiện bong bóng thoại, narration box, SFX, hành động, biểu cảm, nhân vật và bối cảnh.
- [x] 6.4 OCR từng vùng có evidence, bounding box, language và confidence; giữ riêng text raw, text AI normalize và text người dùng đã sửa.
- [x] 6.5 Suy luận speaker với confidence/evidence riêng, không coi nhân vật gần nhất là chắc chắn.
- [x] 6.6 Nhóm nhân vật xuất hiện nhiều lần, đề xuất tên/bí danh, vai trò, ngoại hình, trang phục, tính cách, cách nói và ảnh bằng chứng.
- [x] 6.7 Phân tích địa điểm, quan hệ, quy tắc thế giới, canon fact, plot beat, mở đầu, xung đột, cao trào, kết thúc và trạng thái cuối chương.
- [x] 6.8 Tạo các hướng phát triển tiếp nhưng không tự ghi chúng thành canon, candidate hoặc Master Story.
- [x] 6.9 Mọi kết luận quan trọng phải có evidence IDs, confidence và limitations; không gộp hai nhân vật khi bằng chứng không đủ.
- [x] 6.10 Chạy các AI call qua planning pool chung với work key riêng, batch ảnh theo thứ tự, retry phần lỗi và không log full source/full prompt.
- [x] 6.11 Thêm kiểm tra tính nguyên bản cho chế độ viết mới, cảnh báo độ trùng lặp cao và không tự sao chép nguyên văn nguồn dài.
- [x] 6.12 Thêm acceptance fixture có dữ kiện chỉ đọc được từ pixel để chứng minh vision attachment hoạt động thật.
- [x] 6.13 Tạo validator structured output trước khi ghi DB: kiểm type/required field, stable ID, evidence ID tồn tại, confidence range và cross-batch reference.
- [ ] 6.14 Persist context nhận dạng liên batch và batch manifest để retry một batch không làm đổi identity/evidence của batch hợp lệ.
- [x] 6.15 Tạo approval manifest service khóa accepted/excluded/unreviewed item; sửa item hoặc selection sau approval phải tạo analysis revision mới và vô hiệu manifest cũ.
- [x] 6.16 Tạo originality-check artifact gồm longest verbatim span, source-chunk overlap, semantic similarity, algorithm/threshold version, allowlist và override reason.

## 7. Background runner và API riêng

- [x] 7.1 Tạo background runner riêng cho Comic Analysis, dùng DB session riêng và `create_background_task`; không giữ request session giữa thread/task.
- [x] 7.2 Dùng workflow coordinator chung với key `comic-series-analysis:<job_id>`; không dùng hàng đợi STT, FFmpeg hoặc runner Video Inspiration.
- [ ] 7.3 Persist tiến độ theo các checkpoint fetch, extract, download, normalize, layout/OCR, story analysis, review và handoff.
- [x] 7.4 Thêm create-from-URL và multi-image upload; upload phải giữ thứ tự người dùng và không tạo artifact mồ côi khi validation thất bại.
- [ ] 7.4a Thêm API reorder ảnh upload trước phân tích, bổ sung upload vào job URL hiện có và lưu provenance `web|upload|manual_text` cho từng occurrence trong sequence chung.
- [x] 7.5 Thêm API list/get job, cancel, retry, delete và run/analyze; endpoint bắt đầu job trả nhanh với HTTP 202.
- [x] 7.6 Thêm API phân trang cho source text, page, asset, panel, dialogue, character, location, canon và warning để không trả toàn bộ chương trong mỗi poll.
- [x] 7.7 Thêm API sửa panel order, OCR/dialogue, speaker, character/location/canon; dùng expected revision để phát hiện ghi đè đồng thời.
- [x] 7.8 Thêm API merge/split character và cập nhật toàn bộ evidence reference trong cùng transaction.
- [x] 7.9 Khi backend restart, job active không còn runtime task phải chuyển thành interrupted/failed retryable; cancel phải dừng trước bước nặng tiếp theo.
- [x] 7.10 Chặn hai run đồng thời trên cùng job/source revision và không nhân đôi artifact khi request lặp.
- [x] 7.11 Mọi mutation review, reorder, merge/split và edit OCR phải tạo immutable analysis revision mới hoặc vô hiệu approval hiện tại; không sửa revision approved tại chỗ.
- [x] 7.12 Retry chỉ chạy checkpoint thiếu/lỗi và tái sử dụng artifact có checksum hợp lệ; cancel không được để snapshot/asset trở thành approved.
- [ ] 7.13 Thêm re-import endpoint/state machine: unchanged hash/manifest tái sử dụng source revision, changed bytes/manifest tạo revision mới và diff.
- [x] 7.14 Ghi điểm kiểm tra `rewrite_story` khi máy chủ đang viết kịch bản tối ưu, cập nhật tiến độ rõ ràng, và khôi phục trạng thái cũ nếu bước viết lại lỗi để giao diện không kẹt ở trạng thái đang chạy.

## 8. Review, approval và handoff Series

- [x] 8.1 Chỉ cho approve khi job có source package hợp lệ và người dùng đã duyệt/cảnh báo các phần không chắc chắn.
- [x] 8.2 Tạo handoff preview cho `Tạo Series mới` và `Thêm vào Series hiện có`, không ghi DB Series trong bước preview.
- [x] 8.3 Preview phải liệt kê item sẽ tạo, cập nhật, merge, bỏ qua, ảnh trùng, source hash trùng, episode number trùng, nhân vật có thể trùng và canon xung đột.
- [x] 8.4 Cho người dùng chọn cách giải quyết từng conflict và ràng buộc preview hash/revision để commit không dùng quyết định cũ.
- [x] 8.4a Tính `target_dependency_fingerprint` từ Series, Episode, Profile, approved Memory/Current State, relevant Reference và item đích; commit kiểm lại fingerprint tổng và expected revision từng item.
- [ ] 8.5 Refactor hoặc thêm primitive `commit=False/flush` cho Series, profile, memory, reference và episode để handoff commit trong một transaction duy nhất.
- [ ] 8.6 Triển khai protocol atomic: stage manifest, persist operation `committing`, atomic promote tới content-addressed path, DB commit sau cùng, cleanup orphan và startup recovery cho `committing`.
- [x] 8.7 Khi tạo Series mới, mặc định `image_story_only`; cho phép chọn `hybrid` nhưng không tự tạo AI Video project.
- [ ] 8.8 Chỉ ghi dữ liệu đã được người dùng duyệt; canon/memory chưa duyệt giữ pending, reference asset luôn `pending_approval` và `active=false`.
- [x] 8.9 Handoff toàn bộ nội dung đã duyệt sang `StoryEpisodeSourceDocument/Chunk/Asset`, không chỉ bản tóm tắt hoặc `source_digest`.
- [ ] 8.10 Ánh xạ title, style, world, character profile, relationship, location, canon, current state, reference image, episode metadata và provenance đúng boundary Series/Episode.
- [ ] 8.10a Ánh xạ overview/thể loại thành `series_summary`, market/language vào Episode, synopsis chương vào Episode source/memory proposal và không tự ghi synopsis hiện tại vào `previous_episode_summary`.
- [x] 8.10b Chỉ item `accepted` và được chọn trong preview mới được tạo ở target; Source Document giữ raw-extracted/AI-normalized/approved content và nguồn >50.000 ký tự không bị truncate.
- [x] 8.11 Commit phải idempotent; retry cùng analysis revision/idempotency key trả lại kết quả đã tạo thay vì tạo Series/Episode trùng.
- [x] 8.12 Lưu version record, source revision và dependency snapshot để lần phân tích lại sau này tạo diff, không tự ghi đè Series đã duyệt.
- [x] 8.13 Response handoff trả `series_id`, `story_episode_id`, `source_document_id`, `handoff_id` và URL Story Studio; tuyệt đối không trả `video_project_id`.
- [x] 8.14 Chặn preview/commit khi approval analysis đã cũ, target Series đổi revision hoặc Series target là `video_story_only`.
- [ ] 8.15 Preview fingerprint phải gồm analysis revision, approval manifest hash, rights attestation, development mode, target dependency fingerprint, selected items, conflict resolutions và mapping/schema version; AI matching nếu có phải persist/version hóa.
- [ ] 8.16 Cùng idempotency key/payload luôn dùng cùng operation ID qua restart; retryable resume, terminal result được trả lại, attempt mới sau terminal failure phải dùng key mới.
- [ ] 8.17 Thêm durable reconciliation/outbox cho bước sync `series-memory.md` và cleanup manifest sau commit; restart không được mất marker retry.

## 9. Tích hợp Story Studio và Bộ não Series

- [x] 9.1 Mở rộng Story Episode response bằng source summary/count/current revision, nhưng cung cấp full source và chunk qua endpoint phân trang riêng.
- [x] 9.2 Giữ `source_input` làm đường tương thích cho episode nhập tay; episode nhập truyện dùng Source Document làm nguồn chuẩn.
- [x] 9.3 Xây source-context compiler lấy synopsis, plot beat và các chunk/evidence liên quan trong budget thay vì đưa toàn bộ chương vào một prompt.
- [x] 9.4 Ghi source document revision vào context trace và bảo đảm ba candidate dùng cùng một snapshot nguồn.
- [x] 9.5 Khi source đã duyệt thay đổi, tăng revision, hủy approval Master Story khi cần và đánh stale đúng candidate/adaptation phụ thuộc.
- [ ] 9.6 Không thay đổi Series Bible hoặc hồ sơ nhân vật chỉ vì source được phân tích lại; hiển thị diff và yêu cầu duyệt.
- [x] 9.7 Cho `/story-studio` đọc search params `seriesId` và `episodeId` để mở đúng Series/Episode sau handoff.
- [x] 9.8 Hiển thị badge nguồn Comic Analysis, revision, số trang/panel/dialogue và link quay lại màn hình phân tích.
- [x] 9.9 Chỉ lưu full chapter ở Episode Source; Series Memory nhận summary/index và các memory/current-state proposal đã được duyệt.
- [x] 9.10 Đổi development mode phải làm stale candidate/Master Story phụ thuộc mode cũ.
- [x] 9.11 Compiler mặc định chỉ dùng item/chunk `accepted` trong approval manifest; item `unreviewed` bị loại và limitation partial được truyền vào context.
- [x] 9.12 Context fingerprint/cache phải gồm current source document revision, development mode, approval manifest hash và selected chunk revisions; retry candidate pin đúng snapshot cũ.
- [x] 9.13 Context trace phải phân biệt Series Memory với Episode Source và mở được page/panel/evidence; chunk không liên quan đổi không stale artifact nếu synopsis/plot toàn chương không đổi.
- [x] 9.14 Implement current source pointer swap nguyên tử; API không tự chọn source revision mới nhất chưa approved.
- [x] 9.15 Implement status stale cụ thể cho candidate/Master Story và chặn select/synthesize/adaptation từ artifact stale.

## 10. Frontend route Phân tích truyện tranh

- [x] 10.1 Thêm icon/menu `Phân tích truyện tranh`, route danh sách/chi tiết và đưa route vào wide-workspace; không import component Video Inspiration.
- [x] 10.2 Thêm form `Link web truyện` và `Upload nhiều ảnh`, lựa chọn reading mode, mục tiêu phân tích và xác nhận quyền sử dụng.
- [ ] 10.2a Thêm fallback `Dán nội dung` và UI reorder sequence URL/upload trước khi phân tích.
- [x] 10.3 Hiển thị danh sách job, tiến độ, bước hiện tại, cancel, retry, partial, access denied, CAPTCHA, codec unavailable và browser unavailable bằng tiếng Việt.
- [ ] 10.4 Tạo các tab Nội dung truyện, Trang và panel, Lời thoại, Nhân vật, Bối cảnh, Cốt truyện, Canon, Ảnh nguồn và Cảnh báo.
- [ ] 10.5 Cho sửa OCR, speaker và panel order; merge/split nhân vật; chọn ảnh đại diện/reference; mọi mutation xử lý revision conflict.
- [ ] 10.6 Cho xem/tải original, analysis, preview và export PNG/WebP/HEIC; không tải full original vào DOM khi chỉ cần thumbnail.
- [ ] 10.7 Tạo handoff wizard có preview, lựa chọn Series mới/hiện có, conflict resolution và xác nhận commit.
- [x] 10.8 Sau handoff điều hướng tới đúng Story Studio Series/Episode; không hiển thị hành động chuyển thẳng sang AI Video.
- [x] 10.9 Bổ sung apiClient/types/query keys riêng, polling chỉ job active và không tải payload ảnh/text dài trong mỗi lần poll.
- [ ] 10.10 Kiểm tra keyboard, focus, tooltip icon, text wrapping, mobile/desktop và không để bảng, ảnh, nút hoặc nội dung dài chồng lấn.
- [ ] 10.11 Hiển thị evidence/confidence bằng tương tác mở đúng text, panel, bubble hoặc vùng ảnh, không yêu cầu người dùng đọc JSON.
- [x] 10.12 Bổ sung luồng hành động sau phân tích theo thứ tự `Phân tích lại truyện` → `Viết kịch bản tối ưu` → `Đưa vào Story Studio`, chỉ có một primary CTA và có loading/disabled state rõ ràng.
- [x] 10.13 Trên mobile, ưu tiên job đang chọn và cụm hành động trước lịch sử phân tích; desktop vẫn giữ sidebar hai cột và không tràn ngang.
- [x] 10.14 Làm rõ cấu hình Story Studio trong Comic Analysis: thị trường dùng dropdown, ngôn ngữ là ngôn ngữ truyện/video, CTA hiển thị nhãn Việt hóa, cấu hình thời lượng/prompt có summary tự tính.
- [x] 10.15 Nâng cấp tiến trình Phân tích truyện tranh theo mẫu AI Video: khung tiến trình có nhãn trạng thái, mô tả bước hiện tại, hướng dẫn bước tiếp theo, phần trăm lớn, mốc từng chặng, thanh tiến trình nhỏ trong danh sách job và cập nhật tức thì khi bấm lấy nguồn, phân tích, viết kịch bản tối ưu hoặc đưa vào Story Studio.

## 11. Xóa dữ liệu, đóng gói và quan sát

- [x] 11.1 Tạo storage root riêng cho Comic Analysis gồm original, analysis, preview, tiles, snapshots, exports và staging.
- [ ] 11.2 Xóa analysis phải dọn đúng DB rows và artifact chưa handoff; không xóa bản reference hoặc source document đã được Series dùng.
- [ ] 11.3 Cập nhật delete Series để xử lý Story Episode, source documents/chunks/assets, character profiles và liên kết handoff mà không để orphan.
- [ ] 11.4 Thêm quota/retention và thống kê dung lượng theo job; không tự xóa original hoặc artifact đang được handoff/source revision tham chiếu.
- [x] 11.5 Redact URL nhạy cảm, cookie, token và nội dung dài trong log/debug; log count, byte, format, duration, step và error code an toàn.
- [ ] 11.6 Cập nhật resource status để Comic Analysis xuất hiện trong workflow/planning pool chung nhưng vẫn có nhãn tính năng riêng.
- [ ] 11.7 Cập nhật requirements, build binary/PyInstaller hooks và smoke test sidecar cho parser, codec native và browser capability.
- [x] 11.8 Thêm feature flag để tắt route/menu/runner mới mà Story Studio, Series và episode đã handoff vẫn mở được bình thường.
- [ ] 11.9 Chỉ sync `series-memory.md` sau handoff commit thành công; lỗi sync không được làm mất commit DB nhưng phải báo retryable.
- [ ] 11.10 Hiển thị provenance trên Story Episode, Character Profile, Canon/Memory và Reference Asset; delete bị chặn phải trả danh sách/count dependency đang giữ dữ liệu.
- [ ] 11.11 Tạo hoặc bắt buộc xác nhận backup SQLite trước migration production và thêm restore smoke test; không chỉ ghi “dùng backup” trong rollback.

## 12. Kiểm thử và xác minh

- [x] 12.1 Test migration trên DB mới, DB legacy và chạy migration hai lần; xác nhận index, default, dữ liệu cũ và đường dẫn cũ không đổi.
- [x] 12.2 Test SSRF với localhost, private IPv4/IPv6, metadata, redirect sang private, image redirect, DNS rebinding, userinfo và URL query nhạy cảm.
- [x] 12.3 Test static HTML, relative URL, srcset, lazy-load, direct image, JavaScript fallback, infinite scroll hữu hạn và trang không có nội dung.
- [ ] 12.3a Test upload reorder, URL + upload chung job, paste-text fallback, provenance occurrence và data-image bounded.
- [x] 12.4 Test codec matrix PNG/JPEG/WebP/HEIC/HEIF/AVIF/GIF/APNG/TIFF/BMP/MPO/SVG, file hỏng, polyglot, ảnh quá lớn và codec thiếu.
- [x] 12.5 Xác nhận checksum original không đổi, preview/analysis/export đúng format, EXIF orientation đúng, alpha không hỏng và webtoon tile ghép đúng tọa độ.
- [x] 12.6 Test image attachment thật được truyền cho vision adapter; provider không có vision phải lỗi rõ và không tạo kết luận visual giả.
- [x] 12.7 Test OCR/panel/character/location/plot schema bằng fixture và AI mock cố định; kiểm tra evidence/confidence/limitations.
- [x] 12.7a Test AI JSON sai schema, evidence ID không tồn tại, confidence ngoài range, attachment manifest sai và cross-batch reference hỏng đều không ghi completed.
- [x] 12.8 Test background schedule trả nhanh, DB session riêng, workflow/planning cap, duplicate run, cancel queued/active, retry và restart recovery.
- [x] 12.9 Test review edits, optimistic revision, merge/split character, approval gate và source revision.
- [x] 12.9a Test source revision collecting/finalized, re-import unchanged/changed, approval manifest accepted/excluded/unreviewed và partial limitation acceptance.
- [x] 12.10 Test handoff preview/commit cho Series mới và hiện có, mọi conflict, idempotency, stale preview, rollback giữa chừng và cleanup file stage.
- [x] 12.11 Test Story Studio đọc full source có cấu trúc, ba candidate dùng cùng source revision và source thay đổi đánh stale đúng phạm vi.
- [x] 12.11a Test current source pointer, approved-only chunks, context fingerprint/cache, retry candidate pinned revision và chunk không liên quan không làm stale sai.
- [ ] 12.12 Test development mode mặc định viết mới, quyền dùng mode bám canon và stale khi đổi mode.
- [ ] 12.13 Test delete analysis/delete Series không orphan và không xóa nhầm artifact đã được handoff.
- [ ] 12.14 Thêm frontend verification hoặc Playwright cho route/menu, progress, tab review, edit, merge/split, download và handoff wizard.
- [ ] 12.14a Chạy Playwright bắt buộc trên desktop và mobile cho full flow URL/upload/review/handoff/deep-link; verification script đơn giản không thay thế visual/interaction QA.
- [x] 12.15 Chạy backend pytest tập trung, lint/format theo repo, frontend typecheck/build và test đóng gói sidecar.
- [ ] 12.16 Manual QA với một trang HTML tĩnh, một webtoon rất dài, một trang JavaScript/lazy-load, một direct HEIC/AVIF và một trang bị login/CAPTCHA.
- [x] 12.17 Xác nhận test không tạo Video Inspiration job, VideoProject, shot, voice, subtitle, clip hoặc render.
- [ ] 12.17a Test port policy, carrier-grade NAT, browser subresource SSRF, download ownership/path traversal, raw SVG không inline-render và log redaction.
- [ ] 12.17b Test source >50.000 ký tự, synopsis không ghi đè previous summary, item không chọn không tạo target, idempotency key payload khác và pixel-equivalent derivative.
- [x] 12.18 Chạy `openspec list --json` và `openspec validate --changes --strict --json`; xác nhận change 13 không có lỗi artifact trước khi apply.
- [x] 12.19 Thêm regression test xác nhận structured vision payload không bị loại bỏ và handoff mang analysis, optimized script, character/location context sang Story Studio.
- [x] 12.20 Chạy browser QA desktop/mobile cho action flow, codec warning, responsive ordering, horizontal overflow và console error/warning; giữ các hạng mục full-flow wizard/edit/download ở 12.14/12.14a chưa hoàn thành.

## 13. Migration, rollout và quay lui

- [ ] 13.1 Triển khai migration additive trước, sau đó bật backend API sau feature flag và cuối cùng mới bật route/menu frontend.
- [ ] 13.2 Khi codec/browser capability thiếu, giữ feature ở chế độ partial/upload-only thay vì làm ứng dụng không khởi động.
- [ ] 13.3 Xác nhận tắt feature flag dừng job mới nhưng không làm mất Series/Episode đã handoff.
- [ ] 13.4 Không tự drop bảng trong runtime rollback; dùng backup SQLite nếu cần quay lui DB hoàn toàn.
- [ ] 13.5 Ghi tài liệu vận hành về quota, retention, native codec/browser packaging, error code và cách retry/cleanup staging.
- [ ] 13.6 Test tắt feature flag khi có job queued/running: job mới bị chặn, job active được cancel/interrupted có kiểm soát và Series/Episode đã handoff vẫn mở bằng projection tương thích.
- [ ] 13.7 Thực hiện restore smoke test từ backup trên bản DB có source/handoff mới và xác nhận ứng dụng cũ hoặc feature-off vẫn mở Episode ở mức tương thích.

- [x] 12.21 Regression: response_format/output_schema sanitizer normalizes nested object unions and enforces additionalProperties=false before Codex/OpenAI structured output.
- [x] 12.22 Regression: Comic handoff mặc định ảnh dọc 720x1280 và prompt truyện ảnh giữ style anime/manga/webtoon khi source là comic analysis.
- [x] 12.23 Kiểm thử hồi quy: giao diện tiến trình Phân tích truyện tranh và điểm kiểm tra viết lại kịch bản phía máy chủ đã được xác minh bằng kiểm tra kiểu frontend, `py_compile` cho route backend và bộ kiểm thử route truyện tranh.
