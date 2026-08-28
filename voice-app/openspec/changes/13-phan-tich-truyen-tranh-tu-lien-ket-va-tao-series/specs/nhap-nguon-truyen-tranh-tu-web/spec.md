## ADDED Requirements

### Requirement: Phân tích truyện tranh có route và job độc lập
Hệ thống PHẢI (MUST) cung cấp workspace frontend `/comic-series-analysis`, trang chi tiết `/comic-series-analysis/$analysisId` và API prefix `/comic-series-analysis` dành riêng cho việc nhập, phân tích và chuẩn bị truyện tranh để tạo Series.

#### Scenario: Mở workspace phân tích truyện tranh
- **WHEN** người dùng chọn `Phân tích truyện tranh` trong điều hướng
- **THEN** hệ thống PHẢI mở route `/comic-series-analysis`
- **AND** giao diện PHẢI cho phép dán liên kết, upload ảnh và theo dõi các lần phân tích

#### Scenario: Tạo job độc lập
- **WHEN** người dùng bắt đầu phân tích một nguồn truyện
- **THEN** hệ thống PHẢI tạo job và dữ liệu nguồn thuộc module Comic Series Analysis
- **AND** job KHÔNG ĐƯỢC dùng bảng, route, trạng thái hoặc handoff của Video Inspiration

#### Scenario: Không định tuyến sang Video Inspiration
- **WHEN** URL nguồn không phải trang truyện hoặc chứa loại nội dung không được capability này hỗ trợ
- **THEN** hệ thống PHẢI báo `unsupported_content` hoặc hướng dẫn nhập thủ công
- **AND** hệ thống KHÔNG ĐƯỢC tự tạo job Video Inspiration hay AI Video

### Requirement: Mọi domain HTTP hoặc HTTPS công khai đều được tiếp nhận theo best-effort
Hệ thống PHẢI (MUST) thử nhập URL từ mọi domain công khai hợp lệ mà không phụ thuộc allowlist domain, nhưng KHÔNG ĐƯỢC cam kết mọi URL đều phân tích thành công.

#### Scenario: URL thuộc domain công khai bất kỳ
- **WHEN** người dùng gửi URL `http` hoặc `https` có host công khai và vượt qua kiểm tra an toàn
- **THEN** hệ thống PHẢI tiếp nhận URL và thử tải nguồn
- **AND** hệ thống KHÔNG ĐƯỢC từ chối chỉ vì domain chưa từng được cấu hình

#### Scenario: URL trỏ thẳng tới ảnh
- **WHEN** URL công khai trả về một định dạng ảnh được hỗ trợ
- **THEN** hệ thống PHẢI nhập ảnh đó như một nguồn truyện một ảnh
- **AND** PHẢI chạy cùng quy trình xác thực, lưu bản gốc, chuyển đổi và phân tích ảnh

#### Scenario: Nguồn không thể truy cập đầy đủ
- **WHEN** nguồn yêu cầu đăng nhập, paywall, CAPTCHA, DRM, đã bị xóa hoặc máy chủ từ chối truy cập
- **THEN** job PHẢI dùng `run_status` phù hợp cùng outcome/error code như `authentication_required`, `captcha_required`, `access_denied` hoặc `needs_upload`
- **AND** UI PHẢI giải thích bằng tiếng Việt phần nào đã lấy được và phần nào chưa lấy được

### Requirement: Người dùng có thể upload nhiều ảnh làm nguồn truyện
Hệ thống PHẢI (MUST) nhận nhiều ảnh trong một job upload, giữ thứ tự người dùng chọn và áp dụng cùng quy trình codec, original, derivative, OCR và review như ảnh tải từ web.

#### Scenario: Upload nhiều ảnh theo thứ tự
- **WHEN** người dùng chọn nhiều file ảnh và bắt đầu import
- **THEN** hệ thống PHẢI lưu thứ tự đầu vào ổn định
- **AND** PHẢI cho phép người dùng đổi thứ tự trước khi chạy phân tích

#### Scenario: Một file upload không hợp lệ
- **WHEN** một file rỗng, giả ảnh, vượt giới hạn hoặc bị hỏng dù codec bắt buộc tương ứng đã sẵn sàng
- **THEN** hệ thống PHẢI báo lỗi tại đúng file
- **AND** KHÔNG ĐƯỢC tạo artifact mồ côi hoặc làm mất các file hợp lệ còn lại

#### Scenario: Kết hợp URL và upload
- **WHEN** người dùng bổ sung ảnh upload vào một nguồn URL đã nhập
- **THEN** hệ thống PHẢI lưu rõ provenance `web` hoặc `upload` cho từng asset
- **AND** PHẢI cho review thứ tự chung trước khi duyệt analysis revision

### Requirement: Mọi yêu cầu mạng phải chống SSRF
Hệ thống PHẢI (MUST) kiểm tra URL ban đầu, mọi redirect và từng URL tài nguyên trước khi kết nối để ngăn truy cập trái phép vào máy cục bộ, mạng riêng hoặc dịch vụ hạ tầng.

#### Scenario: Scheme hoặc thông tin xác thực không hợp lệ
- **WHEN** URL không dùng `http` hoặc `https`, chứa username/password hoặc vi phạm chính sách port
- **THEN** hệ thống PHẢI từ chối trước khi phát sinh yêu cầu mạng

#### Scenario: Host trỏ tới địa chỉ không công khai
- **WHEN** DNS hoặc IP literal trỏ tới loopback, private, link-local, multicast, unspecified, reserved, carrier-grade NAT hoặc cloud metadata trên IPv4 hay IPv6
- **THEN** hệ thống PHẢI chặn kết nối
- **AND** PHẢI ghi mã lỗi an toàn mà không làm lộ bí mật hạ tầng

#### Scenario: Redirect đổi sang đích không an toàn
- **WHEN** một response redirect tới URL hoặc địa chỉ IP bị chặn
- **THEN** hệ thống PHẢI dừng chuỗi redirect
- **AND** KHÔNG ĐƯỢC tải nội dung tại đích mới

#### Scenario: DNS rebinding hoặc URL ảnh đổi đích
- **WHEN** địa chỉ DNS thay đổi giữa bước kiểm tra và kết nối hoặc một URL ảnh/subresource trỏ tới đích không công khai
- **THEN** hệ thống PHẢI xác minh địa chỉ peer thực tế và chặn request đó
- **AND** từng tài nguyên PHẢI được kiểm tra độc lập với trang chính

### Requirement: Hệ thống dùng static fetch trước và browser fallback có kiểm soát
Hệ thống PHẢI (MUST) ưu tiên tải HTML tĩnh và chỉ dùng browser render cách ly khi dữ liệu tĩnh không đạt ngưỡng coverage hoặc trang phụ thuộc JavaScript, lazy-load hay cuộn trang.

#### Scenario: Static fetch lấy đủ nội dung
- **WHEN** HTML tĩnh cung cấp đủ text và ảnh theo ngưỡng cấu hình
- **THEN** hệ thống PHẢI hoàn tất bước nhập bằng static extractor
- **AND** KHÔNG ĐƯỢC khởi chạy browser fallback không cần thiết

#### Scenario: Trang dùng JavaScript hoặc lazy-load
- **WHEN** static extractor không tìm thấy nội dung chính, tìm thấy quá ít ảnh hoặc phát hiện nội dung được render phía client
- **THEN** hệ thống PHẢI có thể chuyển sang browser fallback
- **AND** browser PHẢI cuộn và chờ tài nguyên theo giới hạn số lượt, thời gian và dung lượng cấu hình

#### Scenario: Browser fallback bị cô lập
- **WHEN** browser fallback chạy
- **THEN** browser PHẢI dùng context tạm không có cookie, mật khẩu, token hoặc hồ sơ trình duyệt của người dùng
- **AND** mọi request phát sinh từ browser PHẢI đi qua cùng chính sách URL, redirect, SSRF và dung lượng

#### Scenario: Browser fallback vẫn không lấy đủ dữ liệu
- **WHEN** trang tiếp tục chặn bot, yêu cầu tương tác đăng nhập hoặc vượt giới hạn cuộn
- **THEN** hệ thống PHẢI trả kết quả `partial` hoặc `needs_upload`
- **AND** KHÔNG ĐƯỢC cố vượt CAPTCHA, paywall hoặc cơ chế kiểm soát truy cập

#### Scenario: Theo pagination trong cùng chương
- **WHEN** extractor phát hiện nhiều trang thuộc cùng chapter identity và người dùng cho phép theo pagination
- **THEN** hệ thống CÓ THỂ nhập các trang đó theo thứ tự trong giới hạn cấu hình
- **AND** KHÔNG ĐƯỢC tự mở rộng sang chương khác hoặc crawl toàn bộ series

### Requirement: HTML được làm sạch và trích xuất thành nội dung có thứ tự
Hệ thống PHẢI (MUST) trích tiêu đề, tác giả, chương, đoạn văn và URL ảnh từ HTML đã làm sạch, đồng thời coi toàn bộ nội dung website là dữ liệu không tin cậy.

#### Scenario: Trích nội dung chính
- **WHEN** trang chứa `article`, `main`, vùng chương truyện hoặc cấu trúc tương đương
- **THEN** extractor PHẢI ưu tiên nội dung chính và loại menu, quảng cáo, bình luận, footer, script, style, form, iframe và nội dung ẩn không liên quan

#### Scenario: Tìm ảnh từ nhiều cơ chế web
- **WHEN** ảnh xuất hiện qua `src`, `srcset`, `picture/source`, Open Graph, CSS background an toàn, thuộc tính lazy-load thông dụng hoặc response ảnh quan sát được trong browser fallback
- **THEN** hệ thống PHẢI thu thập URL ảnh có thứ tự và ghi nguồn phát hiện
- **AND** PHẢI chuẩn hóa URL tương đối theo URL trang tại thời điểm phát hiện

#### Scenario: Ảnh nhúng bằng data URI
- **WHEN** trang chứa `data:image` hợp lệ trong giới hạn byte cấu hình
- **THEN** hệ thống PHẢI có thể nhập bytes đó như source asset không có network URL
- **AND** PHẢI áp dụng cùng kiểm tra magic bytes, codec, checksum và decompression bomb

#### Scenario: HTML chứa chỉ dẫn cho AI
- **WHEN** text hoặc thuộc tính HTML chứa câu lệnh yêu cầu AI bỏ qua quy tắc hệ thống, gọi công cụ hoặc tiết lộ dữ liệu
- **THEN** hệ thống PHẢI lưu chúng như nội dung nguồn không tin cậy
- **AND** KHÔNG ĐƯỢC biến chúng thành chỉ dẫn điều khiển pipeline hoặc prompt hệ thống

### Requirement: Mỗi lần nhập tạo snapshot có provenance
Hệ thống PHẢI (MUST) lưu dấu vết đủ để tái hiện nguồn đã được phân tích tại một thời điểm.

#### Scenario: Hoàn tất tải trang
- **WHEN** một lần fetch kết thúc toàn bộ hoặc một phần
- **THEN** snapshot PHẢI lưu URL người dùng nhập, canonical URL nếu có, URL cuối sau redirect, thời điểm tải, HTTP status, retrieval mode, extractor version, content hash và danh sách limitation

#### Scenario: Nhập lại nguồn đã thay đổi
- **WHEN** cùng URL được tải lại và content hash hoặc tập tài nguyên thay đổi
- **THEN** hệ thống PHẢI tạo revision nguồn mới
- **AND** revision cũ PHẢI còn truy xuất được cho các phân tích và handoff đã dùng nó

#### Scenario: Nhập lại nguồn không thay đổi
- **WHEN** content hash và manifest tài nguyên không đổi
- **THEN** hệ thống PHẢI có thể tái sử dụng snapshot hiện có
- **AND** KHÔNG ĐƯỢC tạo revision hoặc artifact trùng không cần thiết

### Requirement: Source revision phải được finalize và bất biến trước khi phân tích
Hệ thống PHẢI (MUST) phân biệt source revision đang thu thập với revision đã finalize; chỉ revision đã finalize mới được dùng cho analysis, approval hoặc handoff.

#### Scenario: Source revision đang collecting
- **WHEN** hệ thống vẫn đang tải text, ảnh hoặc manifest tài nguyên
- **THEN** revision PHẢI ở trạng thái `collecting`
- **AND** KHÔNG ĐƯỢC dùng revision đó làm input cho analysis/handoff hiện hành

#### Scenario: Finalize source revision
- **WHEN** collection kết thúc toàn bộ hoặc partial theo policy
- **THEN** content hash, ordered asset manifest, original checksums, coverage và limitations PHẢI được đóng băng
- **AND** revision PHẢI chuyển `finalized` và trở thành bất biến

#### Scenario: Retry nhận bytes hoặc manifest khác
- **WHEN** retry/refetch tạo nội dung, original checksum hoặc ordered manifest khác revision đã finalized
- **THEN** hệ thống PHẢI tạo source revision mới
- **AND** KHÔNG ĐƯỢC thay bytes dưới cùng revision cũ

#### Scenario: Retry derivative cùng original
- **WHEN** chỉ derivative, OCR hoặc checkpoint được tạo lại từ cùng original checksum của revision finalized
- **THEN** hệ thống CÓ THỂ giữ source revision cũ
- **AND** derivative/analysis revision PHẢI phản ánh lần xử lý mới

### Requirement: Ảnh nguồn được tải và giữ nguyên bản gốc
Hệ thống PHẢI (MUST) tải ảnh bằng streaming, giữ nguyên bytes và độ phân giải nguồn trong giới hạn an toàn, đồng thời KHÔNG ĐƯỢC ghi đè bản gốc khi chuyển đổi.

#### Scenario: Tải ảnh thành công
- **WHEN** một URL ảnh vượt qua kiểm tra mạng và giới hạn tải
- **THEN** hệ thống PHẢI lưu artifact `original` bất biến, MIME được sniff từ nội dung, kích thước byte, kích thước pixel, checksum và URL provenance
- **AND** tên mở rộng từ URL KHÔNG ĐƯỢC là căn cứ duy nhất xác định định dạng

#### Scenario: Nhiều vị trí dùng cùng một ảnh
- **WHEN** nhiều URL hoặc nhiều vị trí DOM có cùng checksum
- **THEN** hệ thống CÓ THỂ dùng chung một blob gốc
- **AND** PHẢI giữ từng occurrence, thứ tự và bằng chứng vị trí riêng

#### Scenario: Một ảnh tải thất bại
- **WHEN** một ảnh bị từ chối, timeout, quá giới hạn hoặc hỏng
- **THEN** hệ thống PHẢI tiếp tục xử lý các ảnh còn lại khi có thể
- **AND** kết quả PHẢI ghi rõ URL, lý do lỗi và coverage ảnh

### Requirement: Registry codec hỗ trợ đầy đủ các định dạng ảnh mục tiêu
Hệ thống PHẢI (MUST) có registry codec hỗ trợ tối thiểu PNG, JPEG/JPG, WebP, HEIC, HEIF, AVIF, GIF, APNG, TIFF, BMP, MPO và SVG; file gốc luôn được giữ, còn bản phân tích và preview được tạo riêng.

#### Scenario: Kiểm tra readiness codec bắt buộc
- **WHEN** backend khởi động hoặc chạy health check Comic Analysis
- **THEN** mọi codec bắt buộc trong registry PHẢI được kiểm tra bằng fixture decode/encode phù hợp
- **AND** full codec capability chỉ được báo ready khi PNG, JPEG, WebP, HEIC/HEIF, AVIF, GIF/APNG, TIFF, BMP/MPO và SVG rasterization đạt kiểm tra

#### Scenario: Ảnh raster tĩnh được hỗ trợ
- **WHEN** nguồn là PNG, JPEG, WebP, HEIC, HEIF, AVIF hoặc BMP hợp lệ
- **THEN** hệ thống PHẢI decode, áp dụng orientation, chuẩn hóa màu cho bản phân tích và tạo preview WebP
- **AND** PHẢI giữ file gốc không thay đổi

#### Scenario: Ảnh động hoặc nhiều trang
- **WHEN** nguồn là GIF, WebP động, APNG, MPO hoặc TIFF/HEIF nhiều trang hoặc frame
- **THEN** hệ thống PHẢI giữ animation/page sequence trong bản gốc
- **AND** PHẢI trích frame/page đại diện hoặc tập frame/page theo giới hạn cấu hình để phân tích

#### Scenario: SVG được nhập
- **WHEN** nguồn là SVG hợp lệ
- **THEN** hệ thống PHẢI giữ file SVG gốc trong vùng cách ly
- **AND** PHẢI làm sạch rồi rasterize bằng renderer cách ly trước khi preview, OCR hoặc gửi AI
- **AND** KHÔNG ĐƯỢC hiển thị hoặc thực thi SVG thô chưa làm sạch trong UI

#### Scenario: SVG chứa tài nguyên hoặc mã bên ngoài
- **WHEN** SVG chứa script, event handler, external entity, `foreignObject`, external image/font/style URL hoặc file reference
- **THEN** sanitizer/rasterizer PHẢI loại hoặc chặn các thành phần đó, tắt network và filesystem access
- **AND** mọi inline resource còn lại PHẢI vượt qua cùng policy type, byte và decode trước khi rasterize

#### Scenario: Tạo các bản chuyển đổi
- **WHEN** ảnh đã decode thành công
- **THEN** hệ thống PHẢI tạo bản `analysis` dạng PNG hoặc JPEG và bản `preview` dạng WebP
- **AND** PHẢI cho phép tạo export PNG, WebP hoặc HEIC theo yêu cầu mà không thay đổi artifact gốc

#### Scenario: Codec chưa có hoặc định dạng khác
- **WHEN** file tải được nhưng thuộc format ngoài mandatory registry, optional codec chưa khả dụng hoặc runtime bắt buộc bị degraded ngoài dự kiến
- **THEN** hệ thống PHẢI giữ bản gốc nếu file vượt qua kiểm tra an toàn
- **AND** PHẢI đánh dấu `codec_unavailable` hoặc `unsupported_image_format`
- **AND** KHÔNG ĐƯỢC tuyên bố OCR hay vision đã đọc được ảnh đó

### Requirement: Ảnh dài được phân tích bằng tile mà không làm mất bản full resolution
Hệ thống PHẢI (MUST) chia ảnh truyện dọc hoặc ảnh vượt ngưỡng decode/phân tích thành tile có tọa độ và overlap, trong khi vẫn giữ nguyên artifact gốc.

#### Scenario: Ảnh webtoon rất dài
- **WHEN** chiều cao, tỷ lệ hoặc tổng pixel vượt ngưỡng phân tích trực tiếp
- **THEN** hệ thống PHẢI tạo các tile theo thứ tự từ trên xuống với overlap cấu hình
- **AND** mỗi tile PHẢI lưu tọa độ trong ảnh gốc và checksum của revision nguồn

#### Scenario: Tổng hợp kết quả tile
- **WHEN** OCR hoặc vision hoàn tất trên nhiều tile
- **THEN** hệ thống PHẢI hợp nhất kết quả về cùng ảnh nguồn
- **AND** PHẢI loại kết quả trùng trong vùng overlap mà vẫn giữ evidence tile

### Requirement: Tải và decode phải có giới hạn tài nguyên rõ ràng
Hệ thống PHẢI (MUST) áp dụng timeout, redirect limit, page count, image count, byte budget, pixel budget, concurrency và retry limit có cấu hình cho từng job.

#### Scenario: Nguồn vượt giới hạn
- **WHEN** trang, tổng ảnh hoặc một file vượt giới hạn cấu hình
- **THEN** hệ thống PHẢI dừng đúng phạm vi bị vượt và giữ các artifact hợp lệ đã hoàn tất
- **AND** job PHẢI trả `partial` với limitation cụ thể thay vì hết RAM hoặc chạy vô hạn

#### Scenario: Phát hiện decompression bomb hoặc file giả
- **WHEN** kích thước decode, magic bytes hoặc cấu trúc file cho thấy nguy cơ decompression bomb hay nội dung không phải ảnh
- **THEN** hệ thống PHẢI cách ly hoặc từ chối file
- **AND** KHÔNG ĐƯỢC chuyển file đó sang OCR, vision hoặc UI preview

### Requirement: Job nhập nguồn hỗ trợ tiến độ, hủy và retry theo checkpoint
Hệ thống PHẢI (MUST) lưu trạng thái từng bước của job và cho phép người dùng hủy hoặc thử lại mà không nhân đôi artifact đã hoàn tất.

#### Scenario: Tách trạng thái chạy và độ đầy đủ
- **WHEN** API trả trạng thái một job
- **THEN** `run_status` PHẢI dùng vòng đời `draft`, `queued`, `running`, `ready_for_review`, `approved`, `failed`, `cancelled` hoặc `interrupted`
- **AND** `result_completeness` PHẢI tách riêng thành `complete`, `partial` hoặc `unavailable`

#### Scenario: Kết quả partial được duyệt
- **WHEN** job hoàn tất một phần nhưng có đủ dữ liệu để review
- **THEN** `run_status` PHẢI là `ready_for_review` và `result_completeness = partial`
- **AND** sau khi người dùng chấp nhận limitation, `run_status` CÓ THỂ chuyển `approved` mà vẫn giữ completeness partial

#### Scenario: Theo dõi tiến độ
- **WHEN** job đang chạy
- **THEN** API và UI PHẢI hiển thị bước hiện tại, số text chunk, số ảnh tìm thấy, tải thành công, chuyển đổi thành công, lỗi và coverage tạm thời

#### Scenario: Người dùng hủy job
- **WHEN** người dùng yêu cầu hủy
- **THEN** hệ thống PHẢI dừng ở checkpoint an toàn
- **AND** KHÔNG ĐƯỢC để snapshot hoặc asset ở trạng thái được duyệt

#### Scenario: Retry job partial hoặc failed
- **WHEN** người dùng retry cùng revision nguồn
- **THEN** hệ thống PHẢI tái sử dụng artifact có checksum hợp lệ
- **AND** chỉ chạy lại bước chưa hoàn tất hoặc đã lỗi

#### Scenario: Ứng dụng khởi động lại giữa job
- **WHEN** DB còn job active nhưng runtime task cũ không còn
- **THEN** hệ thống PHẢI chuyển job thành interrupted/retryable
- **AND** KHÔNG ĐƯỢC giả định task cũ vẫn chạy

### Requirement: Hệ thống tôn trọng quyền truy cập và quyền sử dụng nguồn
Hệ thống PHẢI (MUST) yêu cầu người dùng xác nhận họ có quyền phân tích hoặc tái sử dụng nội dung và KHÔNG ĐƯỢC vượt cơ chế kiểm soát truy cập của website.

#### Scenario: Xác nhận quyền sử dụng
- **WHEN** người dùng bắt đầu một import mới
- **THEN** UI PHẢI yêu cầu xác nhận quyền phân tích hoặc sử dụng nội dung theo mục đích của họ
- **AND** snapshot PHẢI lưu thời điểm xác nhận và development mode

#### Scenario: Website yêu cầu đăng nhập hoặc chặn tự động
- **WHEN** nguồn yêu cầu cookie riêng, CAPTCHA, paywall hoặc cơ chế chống tải
- **THEN** hệ thống KHÔNG ĐƯỢC lấy cookie trình duyệt, đánh cắp phiên, vượt CAPTCHA, phá paywall hoặc né DRM
- **AND** PHẢI cung cấp fallback dán text hoặc upload ảnh mà người dùng có quyền sử dụng

#### Scenario: Chính sách nguồn không cho phép nhập tự động
- **WHEN** policy hoặc robots rule được cấu hình áp dụng cho nguồn không cho phép automated retrieval
- **THEN** hệ thống PHẢI dừng hoặc chuyển sang `needs_upload`
- **AND** KHÔNG ĐƯỢC âm thầm bỏ qua policy đó

### Requirement: Log và dữ liệu chẩn đoán phải được redaction
Hệ thống PHẢI (MUST) ghi đủ thông tin vận hành mà không làm lộ credential, URL nhạy cảm, nội dung nguồn dài hoặc binary ảnh.

#### Scenario: Ghi lỗi tải nguồn
- **WHEN** fetch, redirect, browser hoặc asset download thất bại
- **THEN** log PHẢI chỉ lưu host/URL đã redaction, status, byte count, duration, step và error code cần thiết
- **AND** KHÔNG ĐƯỢC ghi cookie, authorization header, userinfo hoặc query token

#### Scenario: Ghi lỗi parser hoặc codec
- **WHEN** HTML, ảnh hoặc derivative không xử lý được
- **THEN** log PHẢI dùng asset ID, checksum rút gọn, detected format, kích thước và rule lỗi
- **AND** KHÔNG ĐƯỢC ghi full source text hoặc binary file
