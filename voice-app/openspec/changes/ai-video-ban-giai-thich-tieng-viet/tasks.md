## 1. Contract và dữ liệu

- [x] 1.1 Rà các luồng AI Video phase 2 đang dùng `story_strategy`, `continuity_bible`, `detailed_script`, `vietnamese_description`, `english_narration`, `VideoPromptPlan`, `VideoShotPromptResponse`, prompt download và package export.
- [x] 1.2 Chốt tên field bản giải thích tiếng Việt cho prompt video, ưu tiên `prompt_explanation_vi`, và ghi rõ field này là review/helper text chứ không phải prompt copy chính.
- [x] 1.3 Thêm field nullable cho bản giải thích tiếng Việt của prompt video ở DB/model nếu cần lưu lâu dài.
- [x] 1.4 Cập nhật migration để project/prompt cũ không có bản giải thích tiếng Việt vẫn load được.
- [x] 1.5 Cập nhật Pydantic/API types và frontend generated/manual types để phản hồi prompt video có bản giải thích tiếng Việt.

## 2. AI planning backend

- [x] 2.1 Cập nhật prompt story development để bản `_vi` luôn đủ rõ cho người dùng Việt duyệt story, continuity và kịch bản.
- [x] 2.2 Cập nhật shot/segment breakdown instruction để `vietnamese_description` giải thích timeline, micro-scene, hành động, camera, chuyển cảnh và nội dung narration khi narration không phải tiếng Việt.
- [x] 2.3 Cập nhật `VideoPromptPlan` và normalization để AI trả về prompt gốc riêng và `prompt_explanation_vi` riêng.
- [x] 2.4 Cập nhật prompt video generation để prompt gốc không bị trộn bản tiếng Việt, còn `prompt_explanation_vi` mô tả hình ảnh, hành động, camera, ánh sáng, mood, continuity và yêu cầu ngôn ngữ người xem nếu có.
- [x] 2.5 Cập nhật validation/fallback để prompt video cũ hoặc AI output thiếu `prompt_explanation_vi` không làm hỏng workflow, nhưng prompt mới phải cố gắng tạo field này.

## 3. API, download và package

- [x] 3.1 Cập nhật endpoint xem prompt video để trả về prompt gốc và bản giải thích tiếng Việt tách biệt.
- [x] 3.2 Cập nhật copy/download prompt content để copy mặc định chỉ dùng prompt gốc, còn file tải xuống có section `Bản giải thích tiếng Việt`.
- [x] 3.3 Cập nhật package phase 2 để kèm bản tiếng Việt cho story, continuity, segment list và prompt video.
- [x] 3.4 Cập nhật manifest/hướng dẫn package để giải thích bản tiếng Việt là nội dung hỗ trợ người dùng, không phải phụ đề video cuối.
- [x] 3.5 Đảm bảo readiness/stale không nhầm bản review tiếng Việt với voice, subtitle `.srt` hoặc ngôn ngữ video cuối.

## 4. Frontend AI Video Assistant

- [x] 4.1 Cập nhật copy `Ngôn ngữ video` và helper text để tách rõ ngôn ngữ video cuối với bản tiếng Việt để duyệt.
- [x] 4.2 Cập nhật phần `Story, continuity và kịch bản` để hiển thị bản tiếng Việt để duyệt rõ ràng và bản sản xuất nếu khác ngôn ngữ.
- [x] 4.3 Cập nhật phần `Prompt segment 10 giây` để nhấn mạnh mô tả tiếng Việt là bản giải thích segment, không chỉ mô tả kỹ thuật.
- [x] 4.4 Cập nhật phần `Prompt video` để hiển thị bản giải thích tiếng Việt bên cạnh/dưới prompt gốc, đồng thời nút copy chỉ copy prompt gốc.
- [x] 4.5 Bỏ các copy hardcode như `Prompt video tiếng Anh`, `narration tiếng Anh`, thay bằng nhãn động hoặc wording trung lập như `prompt gốc`, `narration theo ngôn ngữ video`.
- [x] 4.6 Đảm bảo UI không gọi bản review tiếng Việt là phụ đề video để tránh nhầm với `.srt` hoặc burn-in subtitle.

## 5. Test và xác minh

- [x] 5.1 Thêm backend test cho story development: project tiếng Anh vẫn có bản `_vi` để duyệt và bản sản xuất tiếng Anh.
- [x] 5.2 Thêm backend test cho segment breakdown: `vietnamese_description` có timeline/micro-scene và giải thích narration khi `target_language = "en"`.
- [x] 5.3 Thêm backend test cho prompt video: prompt gốc và `prompt_explanation_vi` tách biệt, copy/download không trộn sai.
- [x] 5.4 Thêm test cho prompt video cũ thiếu bản giải thích tiếng Việt vẫn đọc được và UI/API không lỗi.
- [x] 5.5 Thêm test package/export có bản tiếng Việt cho story, segment và prompt video, kèm hướng dẫn không nhầm với subtitle video.
- [x] 5.6 Chạy focused backend tests cho AI Video planning, prompt, package và subtitle/voice readiness bị ảnh hưởng.
- [x] 5.7 Chạy frontend type/build checks cho AI Video Assistant.
- [x] 5.8 Manual QA với project video English và Tiếng Việt: tạo story, segment, prompt video, copy prompt, tải prompt, export package và kiểm tra bản tiếng Việt để duyệt xuất hiện đúng chỗ.
