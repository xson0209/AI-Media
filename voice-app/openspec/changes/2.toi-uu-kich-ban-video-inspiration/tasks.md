## 1. Schema Và Lưu Trữ

- [x] 1.1 Mở rộng schema rewrite để có `hook_3_5s`, `viewer_question`, `curiosity_gap`, `retention_plan`, `sound_design_plan`, `audio_direction` và `ai_video_source_blocks`.
- [x] 1.2 Lưu candidate drafts, điểm đánh giá và bản tổng hợp cuối trong `analysis_json` hoặc cấu trúc tương thích hiện có.
- [x] 1.3 Đảm bảo bản cuối vẫn điền được các field hiện tại: title, big idea, hook, script, segments, visual suggestions và originality note.

## 2. Pipeline Tối Ưu Kịch Bản

- [x] 2.1 Tạo bước creative brief ngắn từ transcript, visual summary, analysis và định hướng người dùng.
- [x] 2.2 Tạo 2-3 candidate kịch bản khác hướng, mỗi candidate có đủ hook 3-5s, retention và sound design.
- [x] 2.3 Tạo bước chấm điểm candidate theo rubric tiếng Việt.
- [x] 2.4 Tạo bước tổng hợp bản cuối tốt nhất từ candidate và đánh giá.
- [x] 2.5 Nếu AI trả thiếu trường bắt buộc, hiển thị lỗi tiếng Việt và không ghi đè bản script cũ đã hợp lệ.

## 3. Handoff Sang AI Video

- [x] 3.1 Cập nhật draft handoff để source blocks có đủ retention, sound design, audio direction và hook 3-5s.
- [x] 3.2 Giữ `visualStyle` là bản tóm tắt ngắn dưới giới hạn backend; dữ liệu dài nằm trong source blocks.
- [x] 3.3 Không tự ghi đè thị trường, ngôn ngữ final, thời lượng, tỷ lệ, voice hoặc cách chạy.

## 4. UI Tiếng Việt

- [x] 4.1 Thêm hoặc đổi nút thành `Viết kịch bản tối ưu`.
- [x] 4.2 Hiển thị progress tiếng Việt: tạo bản nháp, chấm điểm, tổng hợp bản cuối.
- [x] 4.3 Hiển thị bản cuối với các mục dễ hiểu: Hook 3-5 giây, Kịch bản, Nhịp giữ chân, Âm thanh, Gợi ý hình ảnh.
- [x] 4.4 Nếu hiển thị candidate, dùng tiếng Việt như `Bản nháp 1`, `Bản nháp 2`, `Lý do chọn`.

## 5. Kiểm Thử

- [x] 5.1 Test rewrite tối ưu tạo đủ trường AI Video cần dùng.
- [x] 5.2 Test hook 3-5s không rỗng và được đưa vào source block `idea` hoặc `must_have`.
- [x] 5.3 Test retention và sound design được đưa sang `style_notes`.
- [x] 5.4 Test dữ liệu dài không làm `/ai-video/projects` trả 422.
- [x] 5.5 Test lỗi AI thiếu field không ghi đè script cũ.
