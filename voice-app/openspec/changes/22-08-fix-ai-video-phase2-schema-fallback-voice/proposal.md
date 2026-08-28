# Đề xuất: Sửa ổn định schema, fallback và voice cho AI Video Phase 2

**Ngày:** 22-08-2026  
**Ngôn ngữ artifact:** Tiếng Việt  
**Tên change:** `22-08-fix-ai-video-phase2-schema-fallback-voice`

## Why

Các lỗi xảy ra ở nhiều lớp nhưng có chung một đường đi: schema không đủ chặt làm provider từ chối, fallback lấy nhầm metadata làm nội dung sản xuất, rồi downstream tạo voice từ text sai ngôn ngữ. Gộp trong một change giúp sửa contract từ nguồn đến artifact cuối, giữ audit có thể truy nguyên và tránh tình trạng sửa riêng lỗi 400 nhưng vẫn tạo audio sai hoặc timeout lặp lại.

## What Changes

- Chuẩn hóa toàn bộ schema structured output của AI Video Phase 2 và loại bỏ object tự do.
- Sửa fallback context, fallback narration, batching/timeout và kiểm soát provenance.
- Thêm validation ngôn ngữ/nội dung trước TTS, subtitle, package và render.
- Điều chỉnh chế độ **Chỉ câu lệnh video**: không tạo TTS/SRT riêng nhưng prompt Veo phải chứa đầy đủ thoại, speaker/delivery/lip-sync và chỉ dẫn ambience, nhạc nền, SFX, mix để Veo 3 render native audio cùng clip.
- Bổ sung audit provider error, truncation, retry, fallback và cơ chế repair artifact voice sai.

## Bối cảnh

Trong lần chạy project `Wrong Note, Right Way` ngày 22-08-2026, AI Video Phase 2 phát sinh một chuỗi lỗi liên quan với nhau:

- Codex/OpenAI từ chối `response_format` vì schema strict có `required` nhưng thiếu property tương ứng, lần lượt với `related_characters` và `quality_check`.
- Các object tự do từ `dict[str, Any]`/`dict` bị sanitizer biến thành object strict không có `properties`; `visible_characters` cũng có cùng rủi ro.
- Ba bước `story_development`, `shot_breakdown` và `video_prompt_generation` timeout sau khi retry bằng inline schema. Prompt lớn nhất khoảng 278.731 ký tự.
- Source context bị truncate nhưng chưa phân biệt rõ phần nội dung sáng tạo và metadata handoff/provenance.
- Fallback nội bộ lấy `project.topic` và source block có provenance làm nội dung sáng tạo. Vì vậy `video_scenes.dialogue` và `video_shots.english_narration` chứa URL, job ID, đường dẫn file và câu tiếng Việt mô tả metadata.
- Project có `target_language=en`, nhưng TTS nhận chuỗi tiếng Việt/metadata với language code `en` và đã tạo audio sai cho shot 1, đồng thời bắt đầu tạo shot 2.
- Chế độ `prompts_only` hiện được mô tả là bỏ qua giọng/SRT, nhưng contract chưa bắt buộc prompt phải mang thoại và audio direction để Veo 3 tự render thoại cùng hiệu ứng âm thanh.
- Audit log chỉ giữ lỗi cuối `CODEX_EXEC_TIMEOUT`, làm mất nguyên văn provider error 400 của lần `--output-schema` trước khi fallback.

Các lỗi này không chỉ là lỗi giao diện. Chúng làm giảm độ tin cậy của structured output, làm fallback tạo nội dung không dùng được và có thể phát sinh audio/subtitle/render từ dữ liệu sai.

## Mục tiêu

- Đảm bảo mọi schema gửi tới Codex/OpenAI Structured Outputs hợp lệ theo strict subset: object có property cụ thể, `required` khớp chính xác với `properties`, `additionalProperties=false` và nested schema hợp lệ.
- Loại bỏ object tự do khỏi các output contract của Phase 2 hoặc thay bằng model có field rõ ràng.
- Giữ nguyên provider error trước khi retry, phân biệt schema fallback, model/config fallback và fallback nội bộ.
- Giảm kích thước context/prompt, tránh gửi toàn bộ source hoặc toàn bộ 18 segment vào một request, đồng thời ghi rõ phần nào bị truncate.
- Làm fallback nội bộ an toàn: không dùng provenance, URL, path, job ID hoặc metadata handoff làm narration/production field.
- Bảo đảm `english_narration` thực sự dùng ngôn ngữ video đã chọn; với project `en`, narration phải là tiếng Anh tự nhiên.
- Bảo đảm **Chỉ câu lệnh video** vẫn tạo prompt Veo 3 có nguyên văn thoại và sound design đầy đủ; chỉ bỏ artifact TTS/SRT bên ngoài.
- Chặn TTS/subtitle/render nếu narration còn chứa metadata hoặc sai ngôn ngữ; đánh dấu cần review thay vì tạo audio sai.
- Có cơ chế làm stale/xóa artifact voice cũ sau khi narration được sửa và cho phép tạo lại toàn bộ voice một cách rõ ràng.
- Bổ sung audit, regression test và kiểm tra dữ liệu cho lỗi đã quan sát trong project ngày 22-08.

## Phạm vi

Trong phạm vi:

- `backend/services/ai_planning.py` và sanitizer/output-schema fallback.
- Các schema và fallback trong `backend/services/video_phase2.py`.
- Tách context/provenance khỏi nội dung sáng tạo trong source compiler/handoff dùng cho AI Video.
- Validation narration, TTS, subtitle readiness, package/render readiness và stale propagation.
- Audit/debug events, provider detail redaction và request/step correlation.
- Migration hoặc script một lần để đánh dấu artifact voice sai của project bị ảnh hưởng.
- Backend tests, schema contract tests, fallback tests, language/content guard tests và kiểm tra audit.

Ngoài phạm vi:

- Thay đổi engine/model TTS hoặc giọng `Thoại3 English - Tham Hiem`.
- Thay đổi thuật toán Veo/Chrome provider.
- Thiết kế lại giao diện AI Video; chỉ thêm trạng thái/cảnh báo cần thiết nếu contract hiện tại chưa đủ.
- Sửa nội dung nguồn Video Inspiration gốc hoặc xóa file media nguồn.
- Tự động phát hành video đã tạo trước khi người dùng duyệt lại narration và voice.

## Kết quả mong muốn

Một lần chạy Phase 2 có thể gặp provider 400/timeout nhưng vẫn đạt một trong hai trạng thái an toàn:

1. Provider trả output hợp lệ và pipeline tiếp tục với nội dung đúng ngôn ngữ; hoặc
2. Fallback nội bộ tạo nội dung có cấu trúc, không chứa metadata, có cờ `fallback_used`, có audit đầy đủ và yêu cầu review nếu không đủ dữ liệu.

Không có request nào được phép tạo voice từ text chứa provenance, URL, file path, job ID hoặc narration không khớp `target_language`.
