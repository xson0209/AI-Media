## Ghi nhận ngày

22-07-2026

## Bối cảnh

Dự án đã có nhiều nền tảng tốt cho chất lượng nội dung: Series Brain và context compiler của change 6, ba candidate và critic của change 7, dependency/stale của change 8, Project Memory và target timeline của change 10, cùng quality report của change 11. Tuy nhiên các khả năng này chưa được nối thành đường chạy bắt buộc của AI Video phase 2.

Luồng chính hiện vẫn có thể tạo một kịch bản trong một lần, sau đó phân scene, shot và prompt từ các khối văn bản. Project Memory, target timeline, context snapshot theo nhiệm vụ và quality report tồn tại nhưng chưa luôn là nguồn chuẩn bắt buộc cho `develop_story`, `generate_shots`, `generate_video_prompt_pack`, voice và subtitle. Vì vậy nội dung có thể đúng schema nhưng vẫn lặp ý, thiếu thông tin mới, đổi trạng thái đột ngột hoặc không trả đúng lời hứa của hook.

## Mục tiêu

- Tạo một `Narrative Contract` có phiên bản và trạng thái duyệt làm nguồn chuẩn nội dung cho từng video.
- Dùng đúng ba candidate độc lập, cùng context snapshot, critic tách biệt và bước tổng hợp có nguồn cho AI Video.
- Biểu diễn câu chuyện thành các beat có mã ổn định, vai trò, thông tin mới, thay đổi trạng thái, open loop, micro-payoff và payoff.
- Bắt buộc scene, shot, prompt, narration, voice và subtitle ánh xạ tới `beat_id` và `narrative_revision` tương ứng.
- Biên dịch Series Memory và Project Memory theo đúng nhiệm vụ `story`, `shot`, `prompt`, `voice` hoặc `subtitle` thay vì dùng một context chung cho mọi bước.
- Theo dõi `state_in` và `state_out` của nhân vật, địa điểm, đạo cụ, kiến thức, cảm xúc và open loop để kiểm tra continuity giữa các đoạn.
- Đưa quality report thành quality gate trong auto-run, chặn lỗi hook-payoff, content stagnation, originality, canon và cross-stage consistency.
- Tự sửa có giới hạn đúng beat hoặc artifact bị lỗi, không tự đổi hook, payoff hoặc narration đã duyệt.
- Tạo một release snapshot đã duyệt để các luồng xuất bản sau này chỉ đọc, không ghi ngược vào story, shot, prompt, voice, subtitle hoặc render.

## Ngoài phạm vi

- Không đăng tự động lên TikTok, Instagram, YouTube hoặc Facebook trong change này.
- Không triển khai OAuth, token, upload session, lịch đăng hoặc retry của nền tảng xã hội.
- Không thay thế change `1.tu-dong-hieu-ung-chuyen-canh-sfx-va-ai-review-render`; change này tập trung vào nội dung trước render.
- Không thay thế change `13-phan-tich-truyen-tranh-tu-lien-ket-va-tao-series`; nguồn truyện tranh chỉ là một nguồn đầu vào.
- Không tự duyệt candidate tổng hợp, Narrative Contract hoặc quality override thay người dùng.
- Không cho vòng repair chạy vô hạn hoặc tạo lại toàn bộ video khi chỉ một beat/shot bị lỗi.

## Khả năng mới

- `hop-dong-noi-dung-xuyen-suot-ai-video`: quản lý Narrative Contract, beat graph, continuity state, context snapshot theo nhiệm vụ, quality gate và targeted repair xuyên suốt AI Video.

## Phụ thuộc

- Dùng Series Brain và task context từ change `6.toi-uu-bo-nao-series-va-truy-xuat-ky-uc`.
- Tái sử dụng candidate, critic, synthesis và prompt repair từ change `7.nang-cap-sang-tao-kich-ban-va-tu-sua-prompt`.
- Dùng dependency snapshot, revision và stale propagation từ change `8.quan-ly-tham-chieu-phien-ban-va-kiem-thu-series-dai`.
- Dùng structured handoff, Project Memory và target timeline từ change `10.chuan-hoa-handoff-va-bo-nho-du-an-ai-video`.
- Dùng rubric và quality report từ change `11.danh-gia-chat-luong-noi-dung-giu-chan-va-dau-ra-ai-video`.
- Tích hợp với auto-run hiện có nhưng không nhập luồng social publishing vào cùng workflow.

## Kết quả mong muốn

Mỗi video có một trục nội dung đã duyệt và có thể truy vết. Mỗi beat phải chứng minh người xem biết thêm điều gì, trạng thái câu chuyện thay đổi ra sao và lý do xem tiếp là gì. Mỗi scene, shot, prompt, narration, voice và subtitle chỉ được coi là sẵn sàng khi bám đúng beat và revision.

Auto-run phải dừng ở cổng review hoặc lỗi chặn thay vì tự động đẩy nội dung yếu xuống clip/render. Khi một artifact thay đổi, hệ thống chỉ stale và tạo lại phần phụ thuộc. Luồng đăng mạng xã hội sau này chỉ nhận release snapshot bất biến hoặc có version, không được sửa ngược dữ liệu sản xuất.

## Tên change

`15.ket-noi-hop-dong-noi-dung-xuyen-suot-ai-video`
