# Phát triển nội dung và tính năng để kiếm tiền từ nội dung

Ngày kiểm tra: **04-10-2026**, Asia/Saigon. Phạm vi: AI Media/Voicebox trong workspace hiện tại, phục vụ nhà sáng tạo tại Việt Nam; nguồn thu từ nội dung, affiliate, sản phẩm số và dịch vụ. Không nghiên cứu mô hình thu phí phần mềm SaaS.

## Kết luận và quyết định đề xuất

**Có, nhưng thứ tự đúng là tối ưu nội dung trước rồi mới mở rộng tính năng kiếm tiền.** Trong vòng đầu, chưa cần xây thêm marketplace, checkout hay đồng bộ analytics. Cần chứng minh một lời hứa nội dung có người xem đúng đối tượng, xem tiếp, làm theo và sẵn sàng thực hiện một hành động có giá trị. Sau khi format và offer có tín hiệu lặp lại mới mở rộng các điểm nối doanh thu. Repo đã có Research, sản xuất video, metadata xuất bản, Automation Hub, dữ liệu retention nhập thủ công và một số metadata chi phí; không cần xây lại trình tạo video. [C1–C7]

Đề xuất ưu tiên một vòng khép kín:

```text
Khán giả + nhu cầu + nguồn thu dự kiến
→ Brief nội dung + sản phẩm/dịch vụ + bằng chứng
→ Video nguyên bản + CTA dẫn đến hành động kinh doanh
→ Xuất bản có khai báo phù hợp và ghi lại ID bài đăng
→ Nhập lượt xem/click/lead/đơn/hoa hồng/chi phí
→ So sánh hiệu quả theo series, video và biến thể
→ Quyết định chủ đề tiếp theo
```

Khuyến nghị bắt đầu bằng **nội dung hướng dẫn công cụ/quy trình thực tế dẫn đến template, đào tạo hoặc dịch vụ**, đồng thời có thể thử một nhánh **video sản phẩm/affiliate có bằng chứng thật**. Đây là lựa chọn dựa trên độ phù hợp với mã nguồn hiện tại và khả năng đo chuyển đổi, **chưa phải kết luận đã có nhu cầu thị trường hay doanh thu**. Kênh truyện/nhân vật riêng là lựa chọn dài hạn. Các nội dung đọc lại tin, remake video hoặc hoạt hình trẻ em hàng loạt cần tiêu chuẩn biên tập riêng vì chính sách kiếm tiền không chỉ đánh giá việc có dùng AI hay không. [C1–C5, S1, S4, S8]

### Quyết định content-first

Trong giai đoạn đầu, mỗi video cần được xem như một thử nghiệm biên tập có giả thuyết, không phải một đơn vị sản xuất hàng loạt. Trước khi thêm field hoặc automation, đội nội dung cần làm rõ:

1. **Một audience cụ thể:** ví dụ chủ shop nhỏ đang bỏ sót đơn, hoặc nhân viên văn phòng muốn tự động hóa một việc lặp lại. Không bắt đầu bằng “tất cả người dùng mạng xã hội”.
2. **Một lời hứa có thể kiểm chứng:** sau video người xem làm được một việc, hiểu một lựa chọn hoặc giải quyết một lỗi. Tránh lời hứa chung như “thay đổi cuộc đời” hoặc “kiếm tiền dễ dàng”.
3. **Một format có nhận diện:** hook → tình huống/vấn đề → minh họa hoặc thao tác thật → kết quả → CTA. Format được lặp lại, nhưng ví dụ, lập luận và kết quả của từng tập phải khác nhau.
4. **Một đóng góp nguyên bản:** trải nghiệm, demo, phân tích, nguồn kiểm chứng, câu chuyện hoặc góc nhìn riêng. Đổi giọng, đổi ảnh và thêm phụ đề không đủ để biến nội dung sao chép thành nội dung mới.
5. **Một hành động tiếp theo phù hợp:** lưu, thử mẫu, tải tài liệu, gửi câu hỏi, đặt lịch hoặc mua. CTA phải nối với giá trị vừa hứa; không gắn link bán hàng vào mọi video.

Chuẩn tối thiểu để duyệt một video trước khi render: người xem mục tiêu được viết thành một câu; vấn đề và payoff quan sát được; hook không phụ thuộc vào lời hứa không có bằng chứng; mỗi claim thực tế có nguồn hoặc nhãn “trải nghiệm/minh họa”; hình, giọng và nhạc có quyền dùng; CTA chỉ yêu cầu một hành động. Đây là checklist biên tập thủ công trước khi biến thành tính năng tự động.

Vòng thử nghiệm đầu nên làm khoảng 6–10 video trong cùng một series, thay đổi từng biến chính giữa các nhóm: hook, angle, ví dụ, độ dài hoặc CTA. Giữ lời hứa kênh và offer ổn định để đọc kết quả. Sau mỗi mốc 48 giờ và 7 ngày, ghi lại retention, bình luận/câu hỏi, lượt lưu/chia sẻ, click hoặc lead nếu có; chưa cần kết luận từ một video hoặc từ view đơn lẻ. Chỉ gọi format là có tín hiệu khi có dấu hiệu lặp lại ở nhiều video và người xem đúng audience, không chỉ một video bất thường.

**Đã triển khai bước đầu:** `backend/services/content_profile.py` đưa content-first generation guidance và review checks vào context của mọi genre trước khi sinh kịch bản. Các kiểm tra này nhắc audience/vấn đề, hook/payoff, đóng góp nguyên bản, nguồn/quyền dùng của claim và asset, cùng một CTA phù hợp. Test hồi quy nằm trong `backend/tests/test_content_profile.py`; bước này chưa thêm database hay automation doanh thu.

**Đã triển khai tiếp theo:** quản lý project có lưu trữ mềm (`archived_at`). Project được lưu trữ khỏi danh sách đang làm nhưng vẫn giữ nguồn, script, clip, render và lịch sử; bộ chọn project có bộ lọc “Đã lưu trữ” để khôi phục. Migration được viết idempotent cho database cũ. Đây là thao tác quản lý vòng đời, không phải xóa dữ liệu và không thay đổi nội dung đã tạo.

## 1. Phương pháp và giới hạn

- Đọc mã nguồn hiện tại và các schema thực thi; tài liệu cũ chỉ là bối cảnh. Workspace đang có thay đổi chưa commit, nên kết quả là ảnh chụp của working tree ngày kiểm tra.
- Đọc trực tiếp trang chính thức YouTube Help, Google Developers, TikTok Newsroom, TikTok for Developers, TikTok Shop Việt Nam và Meta Newsroom. Mỗi nhận định về chính sách có nguồn sở hữu tương ứng ở cuối tài liệu.
- Không đăng nhập tài khoản nền tảng, không đăng video, không kiểm tra quyền kiếm tiền của tài khoản thật, không sửa mã ứng dụng.
- Một số trang TikTok Support chỉ trả về vỏ JavaScript trong lần truy cập này. Điều kiện Creator Rewards dẫn từ thông báo chính thức năm 2024 được ghi rõ là thông tin lịch sử; **không khẳng định đó là toàn bộ điều kiện hiện hành năm 2026, cũng không suy ra tài khoản Việt Nam được tham gia**. Tính sẵn có cần xác minh trong tài khoản trước khi đưa vào dự toán.
- Mọi thứ tự ưu tiên, format, chỉ số thử nghiệm và roadmap bên dưới là **đề xuất sản phẩm**, không phải yêu cầu bắt buộc từ nền tảng hay dự báo thu nhập.

## 2. Repo đã có gì và khoảng trống thực sự

| Năng lực | Bằng chứng hiện tại | Ý nghĩa cho phát triển tiếp |
|---|---|---|
| Nghiên cứu và phát triển nội dung | Research có project/source/run/idea/script/score/handoff; đã có bằng chứng nguồn và metadata chi phí cho một số bước. [C1] | Gắn mục tiêu kinh doanh vào brief và giữ mục tiêu đó khi handoff. Không cần một Research mới. |
| Video bán hàng | Product Video có purpose `sales_ad`, hook, retention plan, CTA style; có `render_project_id` để nối render MP4 sau khi người dùng upload clip. [C2] | Bổ sung dữ liệu sản phẩm/offer có cấu trúc và bằng chứng claim. Không kết luận route này chỉ có prompt và hoàn toàn không render theo tài liệu cũ. |
| CTA | Có CTA style và enum `none/comment/like/share/follow/save/subscribe`. [C3] | CTA hiện thiên về tương tác; cần đích `visit_offer`, `download_resource`, `request_quote`, `book_call`, `buy` với URL/offer thật. |
| Publishing kit | Metadata cho YouTube/TikTok/Facebook: title, description, hashtag, thumbnail prompt, dependencies và stale state. [C4] | Bổ sung offer, tracking, disclosure và phiên bản nội dung; mở rộng kit hiện có. |
| Xuất bản | Automation Hub có connection, asset bất biến, publish job, lịch, idempotency key, provider post ID và URL; có adapter YouTube/TikTok/Facebook. [C5] | Dùng post ID/URL làm khóa nối kết quả; không xây thêm một scheduler độc lập. |
| Đo retention | `platform_retention_datasets` có watch time, completion, rewatch, `cta_click_rate`, `conversion_rate`, nguồn manual. [C6] | Đã có chỗ nhập chỉ số; cần mẫu số, time window, nguồn dữ liệu, đơn/lead/hoa hồng và quan hệ publication/offer để diễn giải đúng. |
| Chi phí | Research giữ `cost_json`, đọc `total_cost_usd` nếu provider trả về. [C1] | Mở rộng thành tổng chi phí sản xuất thực tế gồm clip, retry, voice, công biên tập; không mặc định missing là 0. |
| Chất lượng | Có bảng report chứa rubric, điểm content/presentation, warning, evidence, dependency và override history. [C7] | Thêm kiểm tra tính nguyên bản và tính xác thực của claim; không dùng một điểm AI để tuyên bố video chắc chắn đủ điều kiện kiếm tiền. |

**Phát hiện cần ưu tiên sửa khi triển khai:** adapter YouTube hiện đặt `selfDeclaredMadeForKids: False` ngay trong payload upload, trong khi project có trường `made_for_kids`. Cần truyền lựa chọn đã được người dùng xác nhận từ project tới publication; không để mọi video, gồm hoạt hình trẻ em, bị khai báo mặc định giống nhau. Schema API chính thức có `selfDeclaredMadeForKids`, `containsSyntheticMedia` và `paidProductPlacementDetails.hasPaidProductPlacement`; việc triển khai cần kiểm tra cả endpoint/phương thức ghi tương ứng. [C8, S4, S10]

## 3. Chính sách ảnh hưởng trực tiếp đến thiết kế sản phẩm

### 3.1. YouTube: AI không tự động mất quyền kiếm tiền; sản xuất hàng loạt ít giá trị mới là vấn đề

YouTube yêu cầu nội dung nguyên bản và authentic; việc tái sử dụng nội dung cần bổ sung bình luận, thay đổi thực chất hoặc giá trị giáo dục/giải trí. Quyền sử dụng của chủ sở hữu **không tự bảo đảm** vượt qua chính sách reused content. Trang hiện hành nêu rõ ví dụ không được kiếm tiền gồm template AI chung chung, tình huống/cốt truyện lặp lại, slideshow ít giá trị, đọc lại tài liệu không tự viết và chuỗi AI clip không có logic kể chuyện. [S1]

Chính sách cũng cho phép series cùng nhân vật khi mỗi tập có câu chuyện/chủ đề khác biệt, và AI giúp thể hiện nhân vật hay câu chuyện do tác giả tạo ra. Do đó **giữ nhân vật nhất quán là tốt nhưng phải biến đổi nội dung thực chất của từng tập**. Không nên dùng “đổi giọng + thay vài hình + thêm phụ đề” làm bằng chứng nguyên bản. [S1]

Trang hiện hành có mục **AI Personas Related to Sensitive Topics**: kênh dùng persona AI tự thể hiện như chuyên gia con người để đưa lời khuyên sức khỏe, pháp luật, tài chính hoặc chính trị không được kiếm tiền. Điều này ảnh hưởng trực tiếp tới ý tưởng kênh sức khỏe/tâm lý/tài chính và prompt tạo người dẫn giả chuyên gia; không được diễn giải thành lệnh cấm mọi nội dung giáo dục hoặc mọi video AI về những chủ đề này. [S1]

**Tính năng đề xuất:** lưu nguồn gốc tài sản, brief về đóng góp riêng, evidence cho thông tin thực, kiểm tra trùng lặp trong series và cờ persona/chủ đề nhạy cảm. Các tín hiệu hỗ trợ biên tập, không dự đoán chắc chắn quyết định của YouTube.

### 3.2. Phân biệt đủ điều kiện chương trình và quyền kiếm tiền từng nội dung

| Chương trình | Điều kiện được nguồn xác nhận | Cách dùng trong sản phẩm |
|---|---|---|
| YPP mở rộng, có Việt Nam | 500 subscriber, 3 video công khai hợp lệ trong 90 ngày; cùng 3.000 giờ xem đủ điều kiện trong 12 tháng hoặc 3 triệu lượt Shorts đủ điều kiện trong 90 ngày. Đây là cửa vào sớm cho fan funding/Shopping theo điều kiện từng tính năng. [S2] | Không gắn nhãn “đã bật tiền quảng cáo” khi chỉ đạt mốc 500. |
| Chia sẻ doanh thu quảng cáo YouTube | 1.000 subscriber và 4.000 giờ xem đủ điều kiện trong 12 tháng hoặc 10 triệu lượt Shorts đủ điều kiện trong 90 ngày; giờ xem Shorts Feed không cộng vào mốc 4.000; đạt số vẫn cần xét duyệt. [S3] | Profile kênh lưu chương trình, thời điểm kiểm tra và trạng thái thực tế từ Studio. |
| YouTube Shopping affiliate | Trang chương trình có Việt Nam; yêu cầu YPP và các điều kiện kênh/địa lý, không dành cho kênh đặt made for kids hoặc có tỷ trọng đáng kể video made for kids. [S5] | Tách khỏi việc chỉ đặt link ngoài hoặc bán sản phẩm số; kiểm tra eligibility trong Studio. |
| TikTok Creator Rewards | Thông báo chính thức tháng 3/2024 nêu nội dung nguyên bản dài hơn 1 phút, 18+, 10.000 follower, 100.000 view/30 ngày, personal account ở khu vực có chương trình. Chưa xác minh toàn bộ điều kiện hiện hành hoặc Việt Nam. [S6] | Để `unknown/not_verified` cho tài khoản chưa xác minh; không dự toán thu nhập view TikTok mặc định. |
| TikTok Shop Việt Nam | Website chính thức mô tả bán hàng qua video, LIVE và hợp tác nhà sáng tạo; seller phải xác minh và vận hành theo thị trường. Trang được đọc không chứng minh điều kiện affiliate của từng creator. [S7] | Xem thương mại và commission thực tế là nhánh riêng, kiểm tra quyền Shop/affiliate ở tài khoản. |
| Facebook | Meta công bố ưu tiên nội dung gốc; ghép clip, chèn caption, đổi tốc độ hay chỉ kể lại những gì có sẵn không tạo đủ giá trị; lặp lại có thể giảm đề xuất và mất kiếm tiền. [S8] | Có bước kiểm tra original contribution; không mặc định cứ có Page/API upload là đủ điều kiện trả tiền. |

### 3.3. Khai báo AI, quảng cáo và trẻ em cần đi cùng file xuất bản

YouTube yêu cầu khai báo AI làm thay đổi đáng kể hoặc tạo nội dung chân thực, chẳng hạn sự kiện không có thật, người thật nói điều họ chưa nói; các hỗ trợ nhỏ như viết script, caption hoặc clone giọng chính mình cho voiceover được nêu trong nhóm ví dụ không cần khai báo. Nền tảng nói **khai báo AI không tự hạn chế khán giả hoặc quyền kiếm tiền**. TikTok xác nhận yêu cầu gắn nhãn AIGC chân thực và khả năng nhận Content Credentials. [S9, S11]

YouTube yêu cầu chọn paid promotion khi có quan hệ thương mại phù hợp; TikTok Direct Post yêu cầu UX cho khai báo commercial content. Nhãn AI và nhãn quảng cáo là hai quyết định khác nhau. [S12, S13]

Video made for kids bị tắt personalized ads và các tính năng như comment, notification, card/end screen, membership cùng một số tính năng thương mại. Không nên áp dụng mặc định phễu “bình luận để nhận tài liệu” hoặc Shopping vào kênh trẻ em. [S4, S5]

**Tính năng đề xuất:** một bản ghi khai báo gắn phiên bản render: `audience_classification`, `synthetic_media_disclosure`, `commercial_relationship`, nguồn/giấy phép tài sản, consent giọng và xác nhận claim. Cần trạng thái “chưa xác minh”, phạm vi dùng thương mại và ngày kiểm tra; tránh một checkbox “commercial safe” chung cho mọi model và tài sản.

### 3.4. Đăng tự động phải phù hợp cách dùng được nền tảng chấp nhận

TikTok Direct Post API chưa audit chỉ cho nội dung `SELF_ONLY` và có giới hạn người dùng. Tài liệu còn ghi công cụ chỉ phục vụ upload cho tài khoản của chính người phát triển/team là ví dụ **không chấp nhận trong intended use của Direct Post**. Vì vậy không nên hứa rằng chỉ cần xây xong adapter là tiện ích nội bộ sẽ được duyệt public posting. Đây là giới hạn của Direct Post trong tài liệu này, không tự suy ra lệnh cấm mọi workflow draft/upload khác. [S13]

Automation Hub hiện mặc định TikTok Draft/inbox và có flag riêng cho Direct Post. Giữ luồng này trong MVP; bổ sung kiểm tra capability và hướng dẫn hoàn tất việc đăng trong nền tảng. Tình trạng upload thành công, draft đã nhận, video đã public và video đủ điều kiện kiếm tiền phải là các trạng thái khác nhau. [C5, S13]

## 4. Phát triển nội dung theo hướng nào

Các lựa chọn dưới đây kế thừa bối cảnh 15 ý tưởng kênh trong [tài liệu nội bộ](y-tuong-kenh-video-ai-va-mo-hinh-kiem-tien.md), nhưng thứ tự ưu tiên là đánh giá sản phẩm ở thời điểm này, chưa phải nghiên cứu nhu cầu người mua.

| Ưu tiên thử | Dòng nội dung | Giá trị người xem nhận | Nguồn thu cần thử | Điều phải bổ sung vào nội dung |
|---|---|---|---|---|
| 1 | Công nghệ dễ hiểu / công việc cho shop hoặc văn phòng | Làm được một việc qua demo thật | Template, workshop, dịch vụ thiết lập, tài trợ phù hợp | Thao tác thật, tài liệu mẫu, kết quả có thể kiểm chứng, CTA nhận mẫu/đặt lịch |
| 2 | Video sản phẩm giải quyết vấn đề cụ thể | Biết sản phẩm hợp ai, dùng thế nào và giới hạn gì | Affiliate hoặc hợp đồng sản xuất video | Ảnh/clip sản phẩm thật được phép dùng, thông số có nguồn, offer/link xác thực; không giả trải nghiệm dùng thử bằng hình AI |
| 3 | Truyện/nhân vật gốc cho người lớn | Giải trí, cảm xúc, lý do quay lại series | Đặt hàng cá nhân hóa, tài trợ; sau đó có thể thử hội viên/IP | Mỗi tập có xung đột và kết quả khác nhau, canon/character bible, tài sản tự sở hữu hoặc có quyền |
| 4 | Giải thích kiến thức/văn hóa có nghiên cứu | Hiểu một vấn đề và có nguồn kiểm tra | Tài trợ, sản phẩm số, dịch vụ nội dung | Bình luận/phân tích riêng, phân biệt tư liệu với minh họa AI, ngày kiểm tra fact |
| Chưa ưu tiên doanh thu sớm | Hoạt hình trẻ em | Giá trị học tập/giải trí đúng lứa tuổi | Chương trình nền tảng hoặc hợp đồng nội dung khi đủ điều kiện | Thẩm định lứa tuổi, tính mạch lạc, khai báo đúng; không dùng phễu của kênh người lớn |

Với mỗi series, brief nên trả lời sáu câu: **phục vụ ai, vấn đề gì, lời hứa giá trị gì, bằng chứng gì, muốn người xem làm gì, ai trả tiền cho giá trị nào**. Một kênh có thể đăng nhiều video hữu ích không bán trực tiếp; vẫn cần biết chúng góp phần khám phá, xây niềm tin hay chuyển đổi.

Các format khởi đầu: “một lỗi → thao tác sửa → mẫu tải về”; “một nhu cầu → demo sản phẩm → ưu/nhược → link”; “một tình huống → câu chuyện riêng → lý do xem tập tiếp”. Không cần tăng số lượng template nếu chưa biết format nào giữ người xem và tạo tín hiệu kinh doanh.

## 5. Backlog có thể triển khai

### P0-A — Thử nghiệm nội dung trước

| Hạng mục | Việc cần làm | Tiêu chí hoàn thành |
|---|---|---|
| Chọn một audience và một lời hứa | Viết brief một trang, chọn một vấn đề lặp lại và một offer có thể cung cấp thật | Mỗi video trả lời được ai xem, họ nhận giá trị gì và bước tiếp theo là gì |
| Xây một series nhỏ | Làm 6–10 video cùng format; mỗi video có hook, tình huống, giá trị mới và payoff riêng | Không có hai video chỉ đổi hình/giọng; nội dung có đóng góp nguyên bản và nguồn cho claim |
| Kiểm tra chất lượng trước render | Duyệt script, source/evidence, asset rights, voice, subtitle, thumbnail và CTA | Video qua checklist; claim thiếu nguồn hoặc asset thiếu quyền bị chặn để sửa |
| Đọc phản hồi người xem | Ghi retention, câu hỏi, bình luận, lưu/chia sẻ, click/lead ở các mốc cố định | Biết người xem rơi ở đâu, hỏi gì và có hành động nào ngoài view |
| Quyết định tiếp tục | So sánh các biến thể theo cùng lời hứa; ghi giả thuyết và giới hạn dữ liệu | Chỉ nhân rộng khi có tín hiệu lặp lại ở nhiều video; nếu không thì sửa lời hứa/format |

Ở P0-A có thể dùng các màn hình và quy trình hiện có. Chưa cần thêm database doanh thu; một bảng thử nghiệm có version, giả thuyết, chi phí thời gian và kết quả là đủ để ra quyết định đầu tiên.

### P0-B — Chỉ nối doanh thu sau khi format nội dung có tín hiệu

| Hạng mục | Nội dung triển khai | Tiêu chí hoàn thành có thể kiểm tra |
|---|---|---|
| Hồ sơ kênh + mục tiêu chiến dịch | Audience, content pillars, ngôn ngữ, nền tảng, nguồn thu dự kiến, eligibility đã xác minh/ngày kiểm tra; gắn vào Research/series/project | Khi handoff sang video vẫn biết video phục vụ kênh/nhu cầu/offer nào; field chưa biết không bị AI bịa |
| Offer và brief bán hàng có bằng chứng | Offer ID, loại affiliate/sản phẩm số/dịch vụ/tài trợ, URL, audience, lợi ích, nguồn claim, giá/ngày kiểm tra, phạm vi quyền dùng tài sản | Metadata và script dùng đúng offer đã chọn; sửa offer làm artifact phụ thuộc stale |
| CTA và tracking | Thêm đích hành động kinh doanh; link/UTM hoặc mã chiến dịch, landing page/contact đích, kiểm tra URL | Xuất kit có CTA đúng ngữ cảnh và link thật; không coi comment/follow là đơn hàng |
| Khai báo từ project tới publication | Sửa hard-code made-for-kids; lưu quyết định AI/paid promotion/rights theo render revision, mapping riêng mỗi platform | Mỗi publication mang khai báo của đúng bản render; unknown yêu cầu rà soát, không tự chuyển thành false |
| Sổ kết quả và chi phí tối thiểu | Nhập CSV/manual theo publication, currency, time window; view/click/lead/order/commission pending/confirmed/refund; provider spend + retry + công | So sánh được nguồn thu xác nhận và chi phí của một chiến dịch; không đếm trùng bài đa nền tảng hoặc doanh thu |

Đây là phần nên làm đầu tiên. Có thể sử dụng landing page, form và checkout hiện có ở ngoài app; MVP chỉ quản lý link, ID và kết quả, chưa cần xây giỏ hàng/thanh toán/CRM đầy đủ.

### P1 — Học từ hiệu quả thực tế

- **Mở rộng dữ liệu retention hiện có:** thêm publication ID, thời gian lấy số, mẫu số cho tỷ lệ, definition/source, views và clicks tuyệt đối; import dữ liệu thật từ nền tảng. YouTube Analytics có watch time, average view duration, engagement và estimated revenue, nhưng quyền truy cập và report khả dụng phải kiểm tra trước khi đồng bộ. Không đồng nhất estimated revenue với số tiền đã được thanh toán. [C6, S14]
- **Thử nghiệm biến thể có version:** hook, thumbnail/title, CTA và angle; mỗi thử nghiệm nêu giả thuyết và thay đổi chính. So sánh organic là quan sát có nhiễu, không tự gọi mọi chênh lệch là quan hệ nhân quả.
- **Phản hồi vào Research:** tổng hợp câu hỏi người xem, lý do click/không mua và hiệu quả từng series để sinh ý tưởng tiếp; dùng dữ liệu được nhập/cho phép truy cập.
- **Chất lượng và nguyên bản:** so sánh nội dung trong series, lưu contribution brief, proof/claim, asset provenance. Điểm số cần giải thích được bằng bằng chứng thay vì hứa “đủ điều kiện kiếm tiền”.
- **Gói sản xuất cho khách hàng:** brief, deliverable, version, feedback, quyền sử dụng và acceptance; phù hợp nhánh bán dịch vụ nội dung.

### P2 — Chỉ mở rộng sau khi có tín hiệu doanh thu

- Đồng bộ analytics/commission bằng API khi đã có quyền và xác minh schema.
- Thư viện sản phẩm/campaign đa kênh, quản lý sponsor, báo cáo khách hàng và mức phí dựa trên chi phí thực.
- Tái sử dụng format thắng cho series/ngôn ngữ khác với biên tập phù hợp, không sản xuất hàng loạt chỉ thay từ khóa.
- Tự động hóa publishing sâu hơn trong phạm vi được nền tảng hỗ trợ và tài khoản đủ điều kiện.

**Chưa nên ưu tiên:** marketplace nội bộ, checkout/payment gateway riêng, dự báo tiền/view với RPM chung, nhiều kênh chạy đồng thời, cơ chế “viral score” không có dữ liệu kiểm chứng hoặc tự động clone/remake hàng loạt.

## 6. Dữ liệu và chỉ số để tránh tối ưu sai

Đề xuất quan hệ tối thiểu:

```text
Channel → Campaign → Offer
                    ↘ ContentProject → RenderVersion → Publication
Campaign/Offer/Publication ← MetricSnapshot, ConversionRecord, CostEntry
RenderVersion ← RightsRecord, DisclosureDecision, EvidenceReference
```

Giữ `provider_post_id`, `source_type`, `captured_at`, `period_start/end`, `currency`, `status` và mã idempotency cho import. Một video có nhiều publication; một order có thể xuất hiện trong nhiều báo cáo nên cần khóa giao dịch và quy tắc attribution rõ. Thêm `unknown` cho chi phí chưa nhập và trạng thái `pending/confirmed/reversed` cho hoa hồng.

| Câu hỏi | Chỉ số đề xuất | Lưu ý diễn giải |
|---|---|---|
| Nội dung có giữ người xem? | Retention, average watch time, completion, returning audience nếu có dữ liệu | So theo format/độ dài và cùng định nghĩa nền tảng |
| Có dẫn đến hành động? | Clicks, click rate, landing sessions, leads đủ tiêu chí | Ghi mẫu số; click/view và click/session là hai tỷ lệ khác nhau |
| Có tạo tiền? | Confirmed commission, net sales, hợp đồng đã thu, tỷ lệ chuyển đổi | GMV hoặc giá trị đơn pending không phải thu nhập của creator |
| Có đáng tiếp tục? | Contribution sau chi phí biến đổi, tổng thời gian, contribution/giờ | Tránh coi tiền công bản thân và retry là miễn phí |

Định nghĩa thử nghiệm:

```text
Contribution chiến dịch
= doanh thu thuộc về creator đã xác nhận
− hoàn trả/đảo hoa hồng chưa được trừ trong doanh thu
− phí giao dịch/phí bán hàng chưa được trừ trong doanh thu
− chi phí sản xuất, phân phối và phục vụ biến đổi
```

Nếu doanh thu đã là net sau phí/hoàn trả thì không trừ lại. Khi phân bổ thêm công biên tập, thuê bao, thiết bị và thuế mới tiến gần đến kết quả lợi nhuận đầy đủ. Không cộng doanh thu ước tính nền tảng với khoản thanh toán của chính doanh thu đó.

## 7. Thử nghiệm nhỏ trước khi mở rộng tính năng

Đề xuất một vòng **2–4 tuần**, thời lượng linh hoạt theo nguồn lực; đây là nhịp làm việc đề xuất, không phải cam kết đạt doanh thu trong thời gian đó.

1. Chọn một nhóm khán giả và một offer có thể cung cấp thật. Viết brief và giới hạn tổng ngân sách bằng tiền/thời gian.
2. Sản xuất một nhóm khoảng 6–10 video có các angle khác nhau, giữ cùng lời hứa kênh; dùng workflow sẵn có và ghi chi phí. Số lượng này chỉ để học vận hành, chưa đủ tự động kết luận thống kê.
3. Xuất bản, lưu post ID, CTA và phiên bản. Nhập kết quả theo cùng các mốc thời gian, ví dụ 48 giờ và 7 ngày; thời gian chốt commission có thể dài hơn.
4. Đọc riêng ba tầng: có người xem đúng đối tượng, có hành động có ý định, có giao dịch/lead đủ chất lượng. Xem ít nhưng có lead tốt có thể đáng thử tiếp; view nhiều không tự chứng minh khả năng bán.
5. Chỉ tăng số video/chi phí khi có tín hiệu lặp lại, offer cung cấp được và economics chấp nhận được. Đặt ngưỡng go/no-go theo giá bán, hoa hồng, công sức và ngân sách thật; không dùng một benchmark chung cho mọi ngách.

## 8. Nguồn sơ cấp và vị trí mã nguồn

Các URL ngoài dưới đây đã được đọc trực tiếp ngày 04-10-2026, trừ khi nêu rõ giới hạn. Chính sách và điều kiện có thể thay đổi; khi triển khai eligibility cần lưu ngày kiểm tra và trạng thái tài khoản thực tế.

### Nguồn nền tảng

- **S1 — YouTube channel monetization policies:** https://support.google.com/youtube/answer/1311392?hl=en — original/authentic, generic/repetitive, reused, AI persona nhạy cảm, chất lượng nội dung trẻ em.
- **S2 — Expanded YPP:** https://support.google.com/youtube/answer/13429240?hl=en — ngưỡng tham gia sớm, Việt Nam, phân biệt fan funding/Shopping và ads.
- **S3 — YPP overview & eligibility:** https://support.google.com/youtube/answer/72851?hl=en — ngưỡng ads, giờ xem Shorts Feed và xét duyệt.
- **S4 — Set your channel or video's audience:** https://support.google.com/youtube/answer/9527654?hl=en — yêu cầu audience và tính năng bị hạn chế với made for kids.
- **S5 — YouTube Shopping affiliate program overview:** https://support.google.com/youtube/answer/13376398?hl=en — Việt Nam, điều kiện kênh và Shopping affiliate.
- **S6 — TikTok, Introducing the New Creator Rewards Program, 18-03-2024:** https://newsroom.tiktok.com/en-us/introducing-the-new-creator-rewards-program — nguồn lịch sử chính thức về thiết kế và điều kiện chương trình; không xác minh eligibility tài khoản Việt Nam năm 2026.
- **S7 — TikTok Shop Việt Nam:** https://seller.tiktok.com/vn — bán hàng qua video/LIVE/creator, quy trình seller và thanh toán sau hoàn tất đơn/khung trả hàng; không dùng các case study marketing trên trang để dự báo kết quả cho dự án.
- **S8 — Meta, Rewarding Original Creators on Facebook, 13-03-2026:** https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/ — nguyên bản, thay đổi tối thiểu, reach và monetization.
- **S9 — YouTube, Disclosing use of GenAI content:** https://support.google.com/youtube/answer/14328491?hl=en — nội dung cần khai báo và ảnh hưởng của khai báo đến monetization.
- **S10 — YouTube Data API, Videos resource:** https://developers.google.com/youtube/v3/docs/videos — các trường audience, synthetic media, paid placement; cần đọc thêm phương thức ghi khi triển khai.
- **S11 — TikTok, Partnering with our industry to advance AI transparency and literacy, 09-05-2024:** https://newsroom.tiktok.com/en-us/partnering-with-our-industry-to-advance-ai-transparency-and-literacy — yêu cầu nhãn realistic AIGC và Content Credentials.
- **S12 — YouTube, Add branded content restrictions & disclosure labels:** https://support.google.com/youtube/answer/154235?hl=en — khai báo paid promotion và quan hệ thương mại.
- **S13 — TikTok Content Sharing Guidelines:** https://developers.tiktok.com/doc/content-sharing-guidelines/ — audit, SELF_ONLY, intended use, commercial disclosure và user control.
- **S14 — YouTube Analytics metrics:** https://developers.google.com/youtube/analytics/metrics — watch time, engagement, revenue ước tính và điều chỉnh cuối tháng.

### Nguồn code trong repo

- **C1:** [Research service](../../backend/services/research.py), đặc biệt `_cost_metadata` khoảng dòng 1406; [database models](../../backend/database/models.py), các class `ResearchProject`, `ResearchSource`, `ResearchRun`, `ResearchIdea`, `ResearchScript`, `ResearchScore`, `ResearchHandoff` khoảng dòng 1835–2022.
- **C2:** [Product video service](../../backend/services/product_video.py); [request models](../../backend/models.py), `ProductVideoProjectCreate` khoảng dòng 3902; [database models](../../backend/database/models.py), `ProductVideoProject` khoảng dòng 2109 với render bridge và giới hạn auto-generation/TTS.
- **C3:** [Video purpose](../../backend/services/video_purpose.py), `CTA_ACTION_VALUES`, `CTA_STYLE_PATTERN`, `sales_ad` preset.
- **C4:** [Publishing metadata](../../backend/services/video_publishing_metadata.py), `PLATFORM_PROFILES`, status và dependency handling.
- **C5:** [Automation Hub models](../../backend/database/models.py), `AutomationConnection`, `AutomationAsset`, `AutomationPublishJob` khoảng dòng 2025–2088; [tài liệu Automation Hub](../automation-hub-roxy-social-publishing.md); [publishers](../../backend/services/automation_hub/publishers/).
- **C6:** [PlatformRetentionDataset](../../backend/database/models.py), khoảng dòng 1387–1407; [API models](../../backend/models.py), các trường retention/CTA/conversion khoảng dòng 2818–2834.
- **C7:** [Quality report model](../../backend/database/models.py), khoảng dòng 1365–1385; [Video quality service](../../backend/services/video_quality.py).
- **C8:** [YouTube publisher](../../backend/services/automation_hub/publishers/youtube.py), dòng 113: `selfDeclaredMadeForKids` hard-code `False`; [project API models](../../backend/models.py), các trường `made_for_kids` khoảng dòng 1851–2027.

Các số dòng chỉ là định vị tại thời điểm kiểm tra; tên class/function là mốc đối chiếu khi code thay đổi.
