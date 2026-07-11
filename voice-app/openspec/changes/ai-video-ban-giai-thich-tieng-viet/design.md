## Context

AI Video phase 2 hiện có luồng tạo story, continuity, detailed script, shot/segment, prompt video, voice, subtitle và package. Change `ngon-ngu-video-tuy-chon` đang tách `target_language` thành ngôn ngữ video cuối, nhưng người dùng còn cần một lớp tiếng Việt trong app để hiểu nội dung AI đang tạo, đặc biệt khi prompt video hoặc narration sản xuất dùng tiếng Anh.

Code hiện tại đã có một số hướng đi đúng cho story song ngữ: `story_strategy_vi`, `continuity_bible_vi`, `detailed_script_vi` trong planning, còn field tương thích `english_narration` được hiểu là narration theo ngôn ngữ video. Phần thiếu rõ nhất là prompt video: model `VideoPromptPlan` và bảng `video_shot_prompts` đang lưu prompt gốc, negative prompt và metadata kỹ thuật, nhưng chưa có bản giải thích tiếng Việt riêng để người dùng đọc duyệt.

## Goals / Non-Goals

**Goals:**

- Luôn có bản tiếng Việt để người dùng hiểu, duyệt và chỉnh nội dung AI Video phase 2.
- Tách bản review tiếng Việt khỏi ngôn ngữ video cuối: bản review không quyết định voice, phụ đề `.srt`, narration hoặc prompt copy chính.
- Hiển thị rõ bản sản xuất và bản tiếng Việt ở Story, Prompt segment 10 giây và Prompt video.
- Đưa bản tiếng Việt vào package/download để người dùng tiếp tục làm việc ngoài Voicebox.
- Giữ tương thích với project/prompt cũ bằng fallback an toàn.

**Non-Goals:**

- Không thêm chế độ video song ngữ nhiều audio/subtitle track.
- Không đổi ngôn ngữ UI Voicebox sang đa ngôn ngữ; UI vẫn tiếng Việt trong workflow này.
- Không đổi tên field `english_narration` trong change này.
- Không bắt buộc prompt gốc phải viết bằng tiếng Việt; prompt gốc có thể dùng tiếng Anh kỹ thuật nếu tốt hơn cho tool tạo video.
- Không thay TTS engine, voice profile hoặc logic subtitle timing.

## Decisions

### Bản review tiếng Việt là lớp hỗ trợ người dùng, không phải ngôn ngữ video

Mọi nội dung review tiếng Việt phải được xem là helper text để người dùng hiểu workflow. Nguồn sự thật cho ngôn ngữ video cuối vẫn là `project.target_language`.

Phương án khác đã cân nhắc: dùng bản tiếng Việt review làm fallback narration/subtitle khi video là tiếng Anh. Cách đó dễ làm sai video cuối và trộn hai khái niệm, nên không chọn.

### Story tiếp tục dùng cấu trúc song ngữ hiện có

Story development nên tiếp tục tạo các field `_vi` cho người dùng đọc duyệt và field sản xuất theo `target_language`. UI có thể hiển thị bản tiếng Việt trước, rồi bản sản xuất nếu khác tiếng Việt.

Phương án khác đã cân nhắc: chỉ dịch toàn bộ `detailed_script` sau khi tạo. Cách đó đơn giản hơn nhưng làm mất cấu trúc review ở story strategy và continuity bible, đồng thời khó test được từng phần.

### Segment dùng `vietnamese_description` làm bản review chính

Prompt segment 10 giây đã có `vietnamese_description`; field này nên trở thành bản review tiếng Việt chính cho timeline, micro-scene, hành động, camera và chuyển cảnh. Khi narration sản xuất không phải tiếng Việt, segment cần thêm hoặc mở rộng mô tả tiếng Việt để người dùng hiểu nội dung narration đang nói gì.

Phương án khác đã cân nhắc: thêm field `narration_translation_vi` riêng cho shot. Field riêng rõ hơn nhưng tăng migration và UI surface. Có thể thêm sau nếu `vietnamese_description` không đủ biểu đạt; phase đầu nên tận dụng field hiện có và test prompt yêu cầu mô tả rõ narration.

### Prompt video cần field giải thích tiếng Việt riêng

Thêm một field lưu bản giải thích tiếng Việt cho prompt video, ví dụ `prompt_explanation_vi`, trên planning schema, DB/API response và file export. Prompt gốc vẫn là field copy chính để đưa sang tool tạo video.

Phương án khác đã cân nhắc: nhúng bản dịch tiếng Việt vào cuối prompt gốc. Cách đó làm prompt copy bị nhiễu, có thể ảnh hưởng tool tạo video, và khiến người dùng khó copy riêng phần cần dùng.

### Download/package phải tách prompt gốc và bản giải thích

File prompt tải xuống nên có cấu trúc rõ: prompt gốc, negative prompt nếu có, và phần `Bản giải thích tiếng Việt`. Package nên có file hoặc section tiếng Việt cho từng segment để người dùng đọc lại khi copy prompt sang công cụ ngoài.

Phương án khác đã cân nhắc: chỉ hiển thị tiếng Việt trong UI. Cách đó không đủ vì workflow hiện tại phụ thuộc export/download để làm việc ngoài Voicebox.

### Copy UI phải dùng nhãn động, không hardcode English

Các câu như "Prompt video tiếng Anh" hoặc "narration tiếng Anh" phải đổi thành ngôn ngữ động hoặc wording trung lập: "prompt gốc", "narration theo ngôn ngữ video", "bản tiếng Việt để duyệt".

Phương án khác đã cân nhắc: chỉ sửa copy cho tiếng Việt. Cách đó không giải quyết trường hợp project tiếng Anh và project tiếng Việt cùng tồn tại.

## Risks / Trade-offs

- Prompt AI có thể tạo bản giải thích tiếng Việt quá ngắn -> Thêm instruction rõ độ chi tiết và test kiểm tra field không rỗng, có timeline/visual/narration khi cần.
- Thêm field DB cho prompt video cần migration -> Dùng nullable field, fallback rỗng cho prompt cũ và không phá download cũ.
- UI có thể bị rối vì hiển thị cả prompt gốc và bản tiếng Việt -> Dùng nhãn rõ và thứ tự ổn định: bản tiếng Việt để đọc duyệt, prompt gốc để copy.
- Prompt gốc có thể bị lẫn tiếng Việt nếu instruction mơ hồ -> Prompt planning phải nói rõ prompt gốc là nội dung copy sang tool; bản tiếng Việt nằm ở field riêng.
- Tăng chi phí output AI vì sinh thêm bản tiếng Việt -> Chỉ áp dụng cho phase 2 AI Video artifacts cần người dùng duyệt; không dịch log/debug hoặc metadata phụ.

## Migration Plan

- Thêm nullable field cho bản giải thích tiếng Việt của prompt video nếu implementation chọn lưu DB.
- Project/prompt cũ không có bản giải thích tiếng Việt vẫn load được; UI hiển thị trạng thái thiếu bản review và cho phép tạo lại prompt.
- Khi tạo lại prompt video, hệ thống điền bản giải thích tiếng Việt và đánh prompt/package là phiên bản mới.
- Rollback: bỏ UI hiển thị field mới và bỏ generation field mới; dữ liệu nullable vẫn không ảnh hưởng prompt gốc.

## Open Questions

- Tên field cuối cùng nên là `prompt_explanation_vi`, `prompt_review_vi` hay `prompt_translation_vi`? Khuyến nghị `prompt_explanation_vi` vì mục tiêu là giúp hiểu, không nhất thiết dịch từng chữ.
- Segment có cần field riêng cho bản dịch narration tiếng Việt không, hay `vietnamese_description` đủ? Khuyến nghị bắt đầu bằng `vietnamese_description`, chỉ thêm field riêng nếu QA cho thấy người dùng vẫn khó hiểu narration.
