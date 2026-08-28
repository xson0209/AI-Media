# Video Inspiration: nghiên cứu sâu và tối ưu nhiều phiên bản

Tài liệu này mô tả hai hành động mới tại `/video-inspiration`. Cả hai đều chạy nền và dùng chung giới hạn tài nguyên của các workflow video; trình duyệt không phải giữ một HTTP request mở trong suốt quá trình.

## Nghiên cứu sâu → Cấu hình Video AI

Nút `Nghiên cứu sâu → Cấu hình Video AI` luôn yêu cầu profile `high_quality`. Từ “nhanh” trong trải nghiệm chỉ có nghĩa là thao tác một lần, không phải giảm chất lượng nghiên cứu.

Khi phân tích hoàn tất, ứng dụng tự mở `/ai-video?draft=video-inspiration` và nạp transcript, gói phân tích, bằng chứng hình ảnh, limitations, provenance và định hướng người dùng. Draft có thể chưa có kịch bản viết lại. AI Video chỉ mở form ở chế độ cấu hình thủ công: không tạo project, không chạy planning/generation và không tự chọn `full_materials`, market, ngôn ngữ cuối, thời lượng, tỷ lệ khung hình, voice hay run mode.

Pending intent được giữ trong session để tiếp tục sau reload. Intent chỉ redirect khi đúng job đã hoàn tất `high_quality`; job lỗi, bị hủy hoặc stale sẽ xóa intent và giữ người dùng tại Video Inspiration để retry.

## Tạo, chấm điểm và tổng hợp nhiều phiên bản

Quy trình gồm ba stage độc lập:

1. `Tạo nhiều bản nháp` tạo 2–3 candidate trong một structured AI call.
2. Chọn candidate bằng checkbox, sau đó chấm các bản đã chọn hoặc chấm tất cả trong một batch call.
3. Chọn chiến lược và số lượng 1–3 bản cuối, rồi tổng hợp trong một batch call. Người dùng chọn rõ một bản cuối trước khi handoff.

Scoring dùng rubric có version, gồm hook, clarity, originality, retention, production feasibility, sound design và alignment. Candidate, score và final version lưu fingerprint, revision, provenance cùng lịch sử revision cũ để đối chiếu.

Cache bỏ qua AI call khi fingerprint không đổi. Fingerprint bao gồm analysis revision, ngôn ngữ, định hướng, số lượng candidate, candidate đã chọn, rubric và provider/model. Khi input đổi, chỉ stage tương ứng và downstream chạy lại.

## Hiệu năng, heartbeat và vận hành

- Các stage chạy qua workflow/planning pool hiện có; một job không thể xếp trùng hai stage biến thể.
- Backend cập nhật heartbeat 30 giây trong các tác vụ dài để UI không báo stale giả.
- `VOICEBOX_VIDEO_INSPIRATION_STALE_SECONDS` cấu hình ngưỡng stale từ 5 phút đến 4 giờ; mặc định 900 giây. Heartbeat mới là lớp bảo vệ chính, tăng ngưỡng chỉ là dự phòng cho môi trường chậm.
- Metadata stage chỉ lưu thời điểm, latency, số ký tự prompt, token đầu vào ước tính, số output và model. Không ghi transcript/script đầy đủ vào metadata vận hành.
- Đặt `VOICEBOX_FEATURE_VIDEO_INSPIRATION_VARIANTS=false` để tắt candidate/scoring/synthesis mà không ảnh hưởng phân tích sâu và pipeline viết lại cũ.

## Phân biệt ba khái niệm

- Nghiên cứu sâu: thu thập và phân tích nguồn ở chất lượng cao.
- Candidate scoring: so sánh nhiều hướng kịch bản bằng cùng một rubric; chưa tạo video.
- AI Video generation: planning và sản xuất media sau khi người dùng đã tự cấu hình form AI Video. Deep handoff không tự khởi chạy bước này.
