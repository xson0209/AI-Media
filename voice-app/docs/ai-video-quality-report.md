# Báo cáo chất lượng nội dung, retention và đầu ra AI Video

Tài liệu này mô tả lớp kiểm tra chất lượng được thêm cho Video Inspiration và AI Video. Mục tiêu là cho người dùng biết nội dung có đủ sức giữ chân không, có copy sát nguồn không, prompt có bám đúng beat không, voice/subtitle có khớp bản cuối không, và dữ liệu retention thật nếu có đang tương quan với đoạn nào.

## Rubric mặc định 75/25

Báo cáo dùng thang 100 điểm nhưng không dùng tổng điểm để che lỗi chặn.

- 75 điểm nội dung: khách hàng mục tiêu, vấn đề, hook, lời hứa, câu hỏi trung tâm, logic tiến triển, thông tin mới, cảm xúc/stakes/bằng chứng, micro-payoff, payoff và CTA.
- 25 điểm cách thể hiện: hình ảnh hỗ trợ nội dung, voice/cách nói, chữ/subtitle, dựng và âm thanh.

Hệ thống không cho trọng số nội dung thấp hơn 60% nếu chưa có xác nhận cấu hình đặc biệt. Ngay cả khi tổng điểm cao, báo cáo vẫn bị `blocked` hoặc `needs_review` nếu có lỗi canon, hook-payoff, originality, narration, prompt, voice hoặc subtitle nghiêm trọng.

## Các trạng thái

- `not_checked`: chưa chạy kiểm tra hoặc section chưa áp dụng được.
- `checking`: đang kiểm tra.
- `passed`: đạt.
- `needs_review`: cần người dùng xem lại trước khi tiếp tục.
- `blocked`: có lỗi chặn.
- `stale`: artifact đầu vào đổi sau lần kiểm tra gần nhất.

Khi project, handoff, timeline, shot, prompt, voice, subtitle hoặc retention dataset đổi sau lần kiểm tra gần nhất, báo cáo mới nhất được đánh dấu `stale` thay vì hiển thị như còn hợp lệ.

## Các lớp kiểm tra

Báo cáo gồm 12 section:

- `input_analysis_quality`
- `handoff_quality`
- `project_memory_quality`
- `candidate_quality`
- `content_retention_quality`
- `originality_quality`
- `story_quality`
- `shot_quality`
- `prompt_quality`
- `voice_quality`
- `subtitle_quality`
- `cross_stage_consistency`

Mỗi section có trạng thái, điểm, tóm tắt tiếng Việt, bằng chứng, lỗi chặn, cảnh báo và hành động sửa đề xuất.

## Retention analytics thực tế

Người dùng có thể nhập dữ liệu retention dạng manual/CSV/JSON/platform export qua API:

- `POST /ai-video/projects/{project_id}/retention-datasets`
- `GET /ai-video/projects/{project_id}/retention-datasets`
- `POST /video-inspiration/jobs/{job_id}/retention-datasets`

Dữ liệu điểm timeline được chuẩn hóa theo timestamp và phần trăm duration. Khi có mốc tụt hoặc xem lại, hệ thống căn với target beat tương ứng và dùng ngôn ngữ tương quan như “có khả năng liên quan” hoặc “cần kiểm chứng”. Báo cáo không khẳng định một yếu tố là nguyên nhân chắc chắn nếu không có thử nghiệm kiểm soát.

## API báo cáo

AI Video project:

- `POST /ai-video/projects/{project_id}/quality/reports`
- `GET /ai-video/projects/{project_id}/quality/reports/latest`
- `GET /ai-video/projects/{project_id}/quality/reports`
- `POST /ai-video/quality/reports/{report_id}/override`

Video Inspiration job:

- `POST /video-inspiration/jobs/{job_id}/quality/reports`
- `GET /video-inspiration/jobs/{job_id}/quality/reports/latest`

Override bắt buộc có lý do và không xóa lỗi cũ. Lịch sử override lưu trạng thái trước/sau, người ghi đè, lý do và danh sách blocking errors tại thời điểm ghi đè.

## Kiểm thử không gọi Veo

Test `backend/tests/test_video_quality.py` tạo fixture project có analysis package, handoff, Project Memory, target timeline, prompt, voice và subtitle bằng dữ liệu cố định. Test xác nhận:

- Prompt đẹp về camera nhưng thiếu nội dung beat bị chặn.
- Report chuyển `stale` khi input revision đổi.
- Retention dataset được chuẩn hóa và chỉ dùng ngôn ngữ tương quan.
- Nội dung đích copy sát nguồn bị chặn originality.
- Override giữ lại lịch sử lỗi.
- Bộ kiểm tra không tạo `video_clip_generation_items` hoặc `video_shot_clips`, không submit prompt, không tạo clip provider và không tiêu credit.
