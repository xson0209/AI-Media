## Ngày ghi nhận
08-09-2026

## Thiết kế
Độ dài dùng format_profile hiện có: long_form kích hoạt lập kế hoạch theo chương. Cách kể bổ sung vào cấu hình dự án độc lập với thể loại. Dàn ý, trạng thái duyệt và kết quả chương lưu trong retention_plan_json.longform để tận dụng lưu trữ hiện tại.

Luồng dài: tạo dàn ý → duyệt dàn ý → viết các chương theo thứ tự → kiểm tra toàn bài → duyệt kịch bản → tạo cảnh/clip. Mỗi lần gọi AI chỉ viết một chương theo mục tiêu và ngân sách thời lượng; nhận dàn ý tổng, trạng thái và phần kết chương trước. Kịch bản cuối dùng các scene và narration đã tạo, không yêu cầu AI viết lại toàn bộ.

Không dùng fallback kịch bản ngắn khi bước lập kế hoạch dài thất bại. Giữ dữ liệu để thử lại. Nội dung dàn ý thay đổi phải được duyệt lại. Kiểm tra AI hỗ trợ biên tập, không bảo đảm tính đúng đắn thực tế của dẫn chứng.

## Chi tiết triển khai 09-09-2026
- `retention_plan_json.longform` lưu revision, outline, outline_approved, chapters, editorial_review, status và error. Dàn ý/chương luôn được trả lại qua API dự án để khôi phục sau reload.
- Gọi AI riêng cho dàn ý, từng chương và biên tập. JSON schema phải mô tả đầy đủ các trường. Chương có cảnh và narration sản xuất; ghép trực tiếp vào StoryDevelopmentPlan sau khi review đạt, không yêu cầu AI viết lại.
- Mỗi chương hợp lệ được commit trước khi gọi chương tiếp theo. Retry sử dụng tiền tố chương đã lưu; tạo dàn ý mới hoặc sửa dàn ý phải xóa approval/review và kết quả phụ thuộc của bản nháp.
- Dàn ý dùng revision để ngăn thao tác duyệt/sửa từ trang cũ. Snapshot đầu vào ngăn kết quả AI ghi đè cấu hình vừa thay đổi.
- Auto-run có bước review_outline và story_quality_gate. Duyệt dàn ý là quyết định người dùng kể cả full_auto. Story approval, generate_shots và generate_prompts đều kiểm tra trạng thái nội dung dài để tránh bypass qua API.
- Kiểm tra cục bộ phát hiện thiếu nội dung, thời lượng không hợp lệ, chương lặp; biên tập AI kiểm tra ý nghĩa hook/payoff, tính tiến triển, continuity và hướng dẫn thể loại. Lỗi provider hoặc review sai cấu trúc phải dừng, không giả lập kết quả đạt.
- Timeline từ tham khảo không sử dụng modulo để lặp lại các beat nguồn; phần vượt nguồn phải thể hiện cần phát triển nội dung mới.

## Tương thích
Giữ tên các artifact OpenSpec theo quy ước công cụ; nội dung tài liệu tiếng Việt. Không sửa change 15 cũ hoặc thay đổi các chỉnh sửa có sẵn của người dùng.
