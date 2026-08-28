## Bối cảnh

Story Studio hiện chỉ nhận `source_input` dạng văn bản tối đa 50.000 ký tự. Ứng dụng chưa có workspace riêng để nhận liên kết truyện tranh hoặc nhiều ảnh, tải nội dung web, giữ ảnh gốc, OCR, xác định trang, panel, lời thoại, nhân vật, bối cảnh, cốt truyện và canon rồi chuyển kết quả đã duyệt thành Series và Story Episode.

Video Inspiration là pipeline dành cho video, audio, transcript, keyframe, shot timeline và retention. Dùng lại route, bảng job, service hoặc handoff của pipeline đó cho truyện tranh sẽ làm lẫn domain, kéo theo phụ thuộc không cần thiết và trái với mục tiêu tạo Series truyện. Khả năng mới phải có route, dữ liệu, job, schema phân tích và handoff riêng; chỉ giao nhau với hệ thống hiện có tại domain Series và Story Studio.

Người dùng cần một route độc lập cho **Phân tích truyện tranh AI**. Route này tiếp nhận URL HTTP/HTTPS công khai từ mọi domain theo chế độ best-effort hoặc nhận nhiều ảnh upload. Hệ thống phải tải ảnh chất lượng gốc nếu máy chủ nguồn cung cấp, giữ nguyên bytes và độ phân giải trong hạn mức an toàn, tạo bản chuẩn hóa để OCR/AI đọc, cho người dùng duyệt kết quả, sau đó handoff duy nhất sang tạo Series mới hoặc bổ sung một Series hiện có. Handoff phải mang toàn bộ nội dung chương, không chỉ tên truyện, nhân vật và bản tóm tắt.

## Mục tiêu

- Thêm workspace frontend `/comic-series-analysis`, route chi tiết theo analysis ID và API prefix `/comic-series-analysis`, độc lập hoàn toàn với `/video-inspiration`.
- Nhận URL công khai từ mọi domain HTTP/HTTPS và direct-image URL; mọi URL hợp lệ đều được tiếp nhận và thử, nhưng kết quả có thể hoàn tất, một phần hoặc không truy cập được.
- Thử static fetch trước; dùng browser cách ly khi trang cần JavaScript, lazy-load hoặc cuộn trang trong giới hạn cấu hình.
- Nhận upload nhiều ảnh truyện và giữ đúng thứ tự người dùng chọn.
- Trích title, tác giả, chương, văn bản đã làm sạch từ HTML, ảnh theo thứ tự DOM, `src`, `srcset`, `picture`, lazy-load và ảnh quan sát được sau browser render.
- Chống SSRF cho URL ban đầu, redirect, DNS rebinding, URL ảnh và mọi subresource do browser fallback phát sinh.
- Lưu file ảnh gốc byte-for-byte, full resolution trong hạn mức an toàn; nhận diện format bằng magic bytes, không tin extension hoặc MIME khai báo.
- Hỗ trợ tối thiểu PNG, JPEG/JPG, WebP, HEIC/HEIF, AVIF, GIF/APNG, TIFF, BMP và SVG đã làm sạch/rasterize; nếu tải được format chưa có codec, vẫn giữ file gốc và báo `codec_unavailable`.
- Tạo bản phân tích PNG/JPEG, preview WebP, tile có overlap cho webtoon/ảnh cực dài; cho phép export PNG, WebP hoặc HEIC theo yêu cầu mà không ghi đè file gốc.
- Bảo đảm AI vision nhận ảnh hoặc tile qua input đa phương thức thật; chỉ đưa đường dẫn local vào prompt text không được coi là đã xem ảnh.
- Phân tích trang, reading order, panel, bong bóng thoại, OCR, narration, SFX, người nói, nhân vật lặp lại, đặc điểm ngoại hình, bối cảnh, quan hệ, plot beat, canon candidate, uncertainty và limitation.
- Mọi kết luận AI quan trọng phải có `evidence_ids`, confidence và phân biệt `observed`, `inferred` với `user_edited`.
- Cung cấp review UI cho Nội dung truyện, Trang và panel, Lời thoại, Nhân vật, Bối cảnh, Cốt truyện, Canon, Ảnh nguồn và Cảnh báo; cho phép sửa, gộp, tách, chọn hoặc bỏ trước khi duyệt.
- Tạo hai cổng duyệt riêng: duyệt revision phân tích và duyệt preview handoff.
- Handoff duy nhất sang Series/Story Studio: tạo Series mới hoặc thêm vào Series `image_story_only`/`hybrid` hiện có; không tạo AI Video project.
- Tạo `StoryEpisodeSourceDocument`, source chunks và source assets để lưu toàn bộ văn bản đã trích/làm sạch từ HTML, OCR, lời thoại, narration, panel sequence, visual description, ảnh nguồn, evidence, URL, hash và revision; `source_input` chỉ còn là projection tương thích.
- Cho preview `create`, `update`, `merge`, `skip`, `duplicate` và `conflict` trước commit; commit phải có optimistic lock, fingerprint, idempotency, staging file và transaction.
- Sau handoff thành công, mở Story Studio đúng Series và Story Episode vừa tạo để người dùng chủ động tạo đúng ba candidate và Master Story.
- Lưu chế độ phát triển `lay_cam_hung_va_viet_moi` hoặc `bam_canon_va_phat_trien_tiep`; nguồn bên ngoài mặc định dùng chế độ viết mới trừ khi người dùng xác nhận quyền phát triển tiếp canon.

## Ngoài phạm vi

- Không dùng route, bảng job, source block, handoff hoặc service private của Video Inspiration.
- Không phân tích video, audio, STT, keyframe, shot timeline hoặc retention video.
- Không handoff trực tiếp sang AI Video; không tạo scene, shot, prompt video, voice, subtitle, clip hoặc render trong workspace này.
- Không cam kết mọi URL đều phân tích thành công và không vượt đăng nhập, CAPTCHA, paywall, DRM, anti-bot, hotlink protection hoặc máy chủ đã xóa/từ chối nội dung.
- Không lấy cookie, token, mật khẩu hoặc hồ sơ trình duyệt cá nhân; browser fallback dùng context tạm và không lưu session.
- Không crawl vô hạn toàn website hoặc tự nhập toàn bộ series; phạm vi mặc định là document/chương hiện tại và pagination cùng chương có giới hạn.
- Không tự công khai, tái đăng hoặc cấp quyền sử dụng nội dung nguồn.
- Không tự biến ảnh web thành Reference Asset đang hoạt động; ảnh được chọn vẫn qua gate `pending_approval` và `inactive` của Series Reference.
- Không tự ghi đè canon, fixed traits, Character Profile hoặc Current State đã duyệt của Series hiện có.
- Không gửi toàn bộ nguồn dài vào một prompt; toàn bộ dữ liệu được lưu, còn từng tác vụ AI chỉ nhận summary và chunks liên quan có dấu vết.
- Không tự chạy tạo ba candidate hoặc Master Story ngay sau handoff; người dùng tiếp tục chủ động trong Story Studio.

## Khả năng mới

- `nhap-nguon-truyen-tranh-tu-web`: route/job nhập URL hoặc upload ảnh, fetch an toàn, static/browser fallback, snapshot provenance, codec đa định dạng, original/derivative/tile và tiến độ hủy/retry.
- `phan-tich-truyen-tranh-da-phuong-thuc`: OCR/vision thật, reading order, panel, lời thoại, nhân vật, bối cảnh, cốt truyện, canon, evidence/confidence và review theo revision.
- `handoff-truyen-tranh-sang-series`: preview/resolve conflict/commit đầy đủ sang Series và Story Episode Source, có transaction, idempotency, provenance và mở Story Studio.

## Khả năng thay đổi

- `tao-truyen-anh-video-theo-series`: Story Episode nhận nguồn truyện tranh có cấu trúc, dùng source revision đã duyệt để tạo đúng ba candidate và làm stale đúng dependency.
- `bo-nao-series-va-truy-xuat-ky-uc`: full content nằm ở Episode Source; Series Memory chỉ giữ kiến thức dài hạn, còn context compiler truy xuất chunks theo nhiệm vụ.
- `tham-chieu-phien-ban-va-kiem-thu-series-dai`: quản lý original/derivative/tile, provenance ảnh nhập, reference gate, dependency revision và stale đúng phạm vi.

## Luồng mong muốn

    /comic-series-analysis
        -> Link công khai hoặc upload nhiều ảnh
        -> Comic Web Ingestion độc lập
        -> Source snapshot + ảnh gốc đã xác thực
        -> Normalize/convert/tile + OCR/vision
        -> ComicAnalysisPackage có cấu trúc và revision
        -> Người dùng review, sửa và duyệt
        -> Preview handoff: Series mới hoặc Series hiện có
        -> Người dùng giải quyết conflict và xác nhận
        -> Commit transaction/idempotency
        -> Series + Story Episode + SourceDocument/Chunk/Asset đầy đủ
        -> Mở Story Studio đúng Series/Episode
        -> Người dùng chủ động tạo ba candidate và Master Story

## Ranh giới với Video Inspiration và AI Video

- Không có foreign key tới `video_inspiration_jobs`.
- Không import `video_inspiration.py`, `video_inspiration_runs.py` hoặc handoff Video Inspiration.
- Không có endpoint `handoff/ai-video` trong module mới.
- Chỉ dùng hạ tầng trung lập như DB session, storage, background run, planning concurrency, observability và dependency/versioning.
- Nếu một helper hiện mang tên video nhưng thực chất dùng chung, implementation phải tách facade trung lập thay vì gọi private helper của Video Inspiration.
- AI Video chỉ có thể xuất hiện về sau qua workflow Story Studio hiện có, ngoài phạm vi change này.

## Phụ thuộc

- Dùng Series, Story Episode, Hồ sơ nhân vật và Story Studio từ change `4.tao-truyen-anh-va-video-truyen-theo-series`.
- Dùng Bộ não Series, Memory Card, Current State và context compiler từ change `6.toi-uu-bo-nao-series-va-truy-xuat-ky-uc`.
- Dùng contract đúng ba candidate và Master Story từ change `7.nang-cap-sang-tao-kich-ban-va-tu-sua-prompt`.
- Dùng approval, Reference Asset, immutable version, dependency snapshot và stale propagation từ change `8.quan-ly-tham-chieu-phien-ban-va-kiem-thu-series-dai`.
- Dùng planning pool chung của change `chay-song-song-codex-planning`, nhưng không phụ thuộc domain Video Inspiration.
- Có thể tham khảo contract nhận HEIC phía client của change `ho-tro-upload-live-photo-heic-client`; server-side decode/convert trong change 13 là capability riêng.
- Không phụ thuộc change 12; metadata đăng video chỉ nằm ở pipeline khác sau này.

## Kết quả mong muốn

Người dùng mở Phân tích truyện tranh, dán link hoặc upload ảnh, theo dõi tiến độ tải, convert, OCR và phân tích; xem rõ phần thành công, phần thiếu và bằng chứng; sửa kết quả AI rồi duyệt. Hệ thống hiển thị preview handoff đầy đủ, tạo hoặc cập nhật Series theo lựa chọn, tạo một Story Episode có toàn bộ nội dung và provenance, giữ ảnh gốc, đưa ảnh tham chiếu được chọn vào trạng thái chờ duyệt và mở Story Studio đúng tập.

Không có bước nào gọi hoặc phụ thuộc Video Inspiration, không có handoff thẳng sang AI Video và không được làm mất nội dung chương chỉ vì `source_input` cũ có giới hạn ký tự.

## Tên change

`13.phan-tich-truyen-tranh-tu-lien-ket-va-tao-series`
