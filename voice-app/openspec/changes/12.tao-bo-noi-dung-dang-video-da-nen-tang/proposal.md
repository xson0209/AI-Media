## Bối cảnh

AI Video hiện đã có luồng tạo story, segment, prompt video, voice, phụ đề và render. Tuy nhiên sau khi prompt video hoàn tất, người dùng vẫn phải tự viết nội dung đăng video cho từng nền tảng. Hệ thống chưa tạo tiêu đề video, mô tả, hashtag hoặc prompt ảnh bìa/thumbnail; cũng chưa có vị trí rõ ràng để copy từng trường.

YouTube, TikTok và Facebook có cách trình bày, hành vi khám phá nội dung và vùng ảnh bìa khác nhau. Dùng chung một bản tiêu đề, mô tả, hashtag và prompt ảnh bìa cho cả ba nền tảng làm giảm chất lượng đầu ra và khiến người dùng phải chỉnh sửa thủ công nhiều lần.

Luồng voice và phụ đề đã tồn tại nhưng còn hai điểm cần củng cố để chuỗi mới đáng tin cậy: phụ đề phải giữ đúng khoảng thời gian của segment không lời, và tạo lại voice phải làm stale artifact phụ đề cấp project trước khi người dùng tải hoặc render.

## Mục tiêu

- Sau khi toàn bộ prompt video hợp lệ được tạo, dùng Codex tạo tiếp một bộ nội dung đăng video cấp project.
- Tạo biến thể riêng cho YouTube, TikTok và Facebook.
- Mỗi nền tảng có bốn trường bắt buộc: Tiêu đề video, Mô tả, Hashtag và Prompt tạo ảnh bìa/thumbnail bằng AI.
- Hiển thị mỗi trường trong một ô riêng có hành động copy riêng.
- Cho phép tạo lại riêng nền tảng đang chọn hoặc tạo lại toàn bộ ba nền tảng.
- Đặt phần Nội dung đăng video ngay sau phần Prompt video và trước phần Voice và phụ đề.
- Tích hợp bước tạo bộ nội dung đăng video vào auto-run có trạng thái, tiến độ, retry và resume.
- Dùng target_language, mục đích video, CTA, story, narration, retention plan và prompt cuối làm nguồn sự thật.
- Giữ nguyên pipeline TTS và SRT hiện có, chỉ nối thêm bước mới trước voice/phụ đề.
- Đảm bảo phụ đề cuối không lệch timeline khi có segment không lời và không còn hợp lệ sau khi voice thay đổi.

## Ngoài phạm vi

- Không tự đăng video hoặc tự truy cập tài khoản YouTube, TikTok, Facebook hay nền tảng khác.
- Không cam kết thứ hạng tìm kiếm, lượt xem, tỷ lệ nhấp hoặc hiệu quả thương mại.
- Không lấy keyword trend, search volume hoặc analytics tài khoản nếu người dùng không cung cấp.
- Không sinh file ảnh thumbnail thật trong change này; hệ thống chỉ sinh prompt văn bản để người dùng copy sang công cụ tạo ảnh.
- Không thêm Messenger như một nền tảng SEO. Nội dung chia sẻ Messenger, nếu cần, sẽ là một capability hoặc trường share_message riêng.
- Không thay đổi engine TTS, hard cap hàng đợi voice, thuật toán render clip hoặc provider tạo video.
- Không triển khai tự động A/B test tiêu đề hoặc thumbnail.

## Khả năng mới

- bo-noi-dung-dang-video-da-nen-tang: tạo, lưu, đọc, làm stale, retry và copy bộ nội dung đăng video riêng cho YouTube, TikTok và Facebook.

## Khả năng thay đổi

- ai-video-auto-material-run: thêm bước generate_publishing_metadata sau prompt và trước gate duyệt prompt/voice; thêm target publishing_kit nhưng giữ nguyên nghĩa prompts_only.
- ai-video-video-prompt-studio: thêm section Nội dung đăng video với ba tab nền tảng và bốn ô copy cho mỗi tab.
- ai-video-codex-output-mapping: mở rộng mapping deterministic và validation atomic cho structured output của bộ nội dung đăng video.
- Luồng voice/subtitle: bảo đảm voice mới làm stale subtitle project và subtitle giữ đúng offset qua segment không lời.

## Luồng mong muốn

    Story và segment
        -> Prompt video
        -> Bộ nội dung đăng video đa nền tảng
        -> Duyệt prompt và nội dung đăng
        -> Voice
        -> Chờ voice
        -> Phụ đề SRT
        -> Clip/render nếu được chọn

Ở chế độ review_gated, hệ thống tạo prompt và bộ nội dung đăng video trước khi dừng ở review_stage = prompts. Người dùng duyệt cả hai nhóm đầu ra trong cùng một chặng. Ở chế độ full_auto, hệ thống vẫn validate đầy đủ rồi mới tiếp tục sang voice và phụ đề.

## Tương thích material target

- prompts_only giữ nguyên ý nghĩa hiện tại: chỉ tạo prompt video.
- publishing_kit là target mới: tạo prompt video và bộ nội dung đăng video, sau đó dừng trước voice/phụ đề.
- full_materials tạo prompt, bộ nội dung đăng video, voice và phụ đề.
- video_clips tạo prompt, bộ nội dung đăng video, clip, voice, phụ đề và render theo luồng hiện có.

## Phụ thuộc

- Phụ thuộc luồng auto-run của change auto-chay-ai-video-nguyen-lieu.
- Phụ thuộc planning pool dùng chung của change chay-song-song-codex-planning.
- Phụ thuộc target_language của change ngon-ngu-video-tuy-chon.
- Phụ thuộc mapping/validation không ghi partial data của change series-tuy-chon-xoa-du-lieu-ai-video.
- Tái sử dụng project memory, retention plan, prompt pack, voice và subtitle hiện có.

## Kết quả mong muốn

Người dùng tạo prompt video xong sẽ nhận ngay một phần Nội dung đăng video. Họ chọn YouTube, TikTok hoặc Facebook, sau đó copy riêng Tiêu đề video, Mô tả, Hashtag hoặc Prompt tạo ảnh bìa; khi cần có thể tạo lại riêng tab đang chọn hoặc tạo lại toàn bộ. Auto-run có thể tiếp tục từ đầu ra này sang voice và phụ đề mà không tạo lại artifact hợp lệ khi retry. Mọi trạng thái lỗi, thiếu dữ liệu hoặc stale đều hiển thị bằng tiếng Việt và không yêu cầu người dùng đọc JSON kỹ thuật.

## Tên change

12.tao-bo-noi-dung-dang-video-da-nen-tang
