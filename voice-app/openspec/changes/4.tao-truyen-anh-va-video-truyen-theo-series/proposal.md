## Bối cảnh

AI Video hiện đã có series tuỳ chọn, Series Bible, `series-memory.md`, pipeline phát triển kịch bản video, tạo clip và render MP4. Tuy nhiên series hiện thiên về video, Character Bible chủ yếu là văn bản tự do và chưa có workflow riêng để phát triển truyện ảnh từ một nội dung đã duyệt.

Người dùng cần một xưởng sản xuất nội dung theo series, trong đó mỗi series có thể được tạo với một trong ba chế độ:

- `image_story_only`: Series truyện ảnh, chỉ phát triển và render truyện ảnh;
- `video_story_only`: Series video, chỉ dùng luồng AI Video và render MP4;
- `hybrid`: Series truyện + video, dùng chung nhân vật, thế giới và mạch truyện cho cả hai đầu ra.

Với series `hybrid`, truyện ảnh và video của cùng một tập phải xuất phát từ cùng một Master Story Episode đã được người dùng duyệt. Với series `video_story_only`, luồng AI Video hiện tại vẫn hoạt động độc lập nhưng phải dùng chung Hồ sơ nhân vật có cấu trúc của series.

Renderer ảnh hiện có thể chưa được cấu hình hoặc chưa có API key. Vì vậy Story Studio phải hoạt động theo hướng prompt-first: tạo panel và prompt, chờ người dùng duyệt, sau đó chỉ render khi provider ảnh đã sẵn sàng và người dùng chủ động bắt đầu.

## Mục tiêu

- Thêm route/workspace tiếng Việt cho **Story Studio**, dự kiến `/story-studio`, không dùng lại route `/stories` đang phục vụ story/TTS cũ.
- Mở rộng series hiện có bằng `series_mode` gồm `image_story_only`, `video_story_only` và `hybrid`.
- Cho phép series cũ tiếp tục hoạt động như series video bằng migration mặc định sang `video_story_only`.
- Dùng chung một `series_id`, Series Bible, Hồ sơ nhân vật và `series-memory.md` giữa Story Studio và AI Video.
- Thêm Hồ sơ nhân vật có cấu trúc cho mỗi nhân vật, tối thiểu gồm:
  - tên và vai trò;
  - khuôn mặt;
  - tóc;
  - vóc dáng;
  - trang phục đặc trưng;
  - tính cách;
  - cách nói chuyện;
  - những điều không được thay đổi.
- Cho phép AI đề xuất Hồ sơ nhân vật hoặc cập nhật continuity, nhưng chỉ lưu thay đổi sau khi người dùng duyệt.
- Cho phép người dùng chọn mục tiêu đầu ra của từng Story Episode phù hợp với chế độ series:
  - `truyen_anh`;
  - `video_truyen`;
  - `ca_hai`.
- AI đọc Series Memory, Hồ sơ nhân vật, nguồn nhập mới và market/language profile để tạo đúng 3 hướng kịch bản khác nhau.
- AI chấm điểm từng hướng theo mục tiêu đầu ra, sau đó chọn hoặc tổng hợp bản tốt nhất.
- Lưu bản thắng thành **Master Story Episode** và yêu cầu người dùng duyệt trước khi tạo sản phẩm.
- Từ Master Story Episode đã duyệt:
  - tạo **Image Story Adaptation** gồm panel, caption/lời thoại, prompt ảnh, negative prompt và consistency notes;
  - chỉ gửi prompt ảnh đã được người dùng duyệt sang renderer;
  - nếu chưa có image provider/API key, vẫn lưu và export prompt, đồng thời hiển thị trạng thái đang chờ provider;
  - khi provider sẵn sàng, chỉ render sau khi người dùng chủ động bấm render;
  - tạo **Video Story Adaptation** bằng cách handoff sang AI Video hiện có và nhận sản phẩm MP4 từ pipeline đó.
- Dùng database làm nguồn dữ liệu chính; `series-memory.md` là file được một service duy nhất dựng lại từ series, Hồ sơ nhân vật và các tập đã duyệt.
- UI, trạng thái, lỗi, rubric và tài liệu trong change này dùng tiếng Việt.

## Ngoài phạm vi

- Không xây dựng website công khai để độc giả đọc truyện hoặc xem video.
- Không xây dựng catalog, tìm kiếm, bookmark, lịch sử đọc/xem, SEO, sitemap hoặc public player.
- Không tự động đăng lên TikTok, YouTube hoặc Facebook; việc này thuộc một OpenSpec riêng trong tương lai.
- Không thay thế pipeline `/ai-video` hiện có cho shot breakdown, prompt video, voice, subtitle, Veo/Chrome hoặc render MP4.
- Không dùng route `/stories` hiện tại cho Story Studio.
- Không bắt buộc mọi series hoặc mọi tập phải tạo cả truyện ảnh và video.
- Không tự động render ảnh chỉ vì người dùng vừa cấu hình provider/API key.
- Không tích hợp trực tiếp cookie automation hoặc trích cookie web cho provider ảnh/video.
- Chưa chốt trong change này chính sách giữ bao nhiêu phiên bản cũ, tự dọn ảnh thử hoặc cách render lại từng panel; các quyết định đó cần được người dùng xác nhận riêng trước khi áp dụng.

## Kết quả mong muốn

Khi tạo series, người dùng chọn rõ Series truyện ảnh, Series video hoặc Series truyện + video. Series video cũ vẫn tiếp tục hoạt động. Mỗi series có Hồ sơ nhân vật dùng chung để cả Story Studio và AI Video giữ đúng ngoại hình, tính cách, cách nói chuyện và các đặc điểm không được thay đổi.

Với Series truyện ảnh hoặc Series truyện + video, người dùng mở Story Studio, tạo một tập, nhập nội dung hoặc yêu cầu AI phát triển tiếp, chọn đầu ra phù hợp và nhận đúng 3 hướng kịch bản. Sau khi chọn và duyệt Master Story, hệ thống chia panel, tạo prompt ảnh và chờ người dùng duyệt prompt. Nếu chưa có image provider, người dùng vẫn có thể lưu hoặc export prompt. Khi provider đã sẵn sàng, người dùng chủ động bắt đầu render.

Với đầu ra video, Story Studio không dựng lại video. Hệ thống tạo hoặc mở AI Video project liên kết cùng series và tập, sau đó pipeline AI Video hiện có tiếp tục cho tới sản phẩm MP4.

## Tên change

`4.tao-truyen-anh-va-video-truyen-theo-series`

Change giữ tên hiện có để nhất quán với các change đánh số trong repository. Nội dung proposal, design, tasks và spec dùng tiếng Việt.
