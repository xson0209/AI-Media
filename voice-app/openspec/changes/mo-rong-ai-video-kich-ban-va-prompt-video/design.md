## Context

AI Video Assistant phase 1 đã có project, scene, Codex CLI planning, prompt artifact, preview image, voice theo scene, subtitle SRT và ZIP nguyên liệu. Luồng hiện tại bắt đầu từ `topic` ngắn và sinh prompt ảnh cho từng scene. Người dùng mục tiêu không rành kỹ thuật, muốn nhập tiếng Việt nhưng làm video tiếng Anh, và cần copy prompt sang công cụ tạo video bên ngoài.

Phase 2 mở rộng workflow thành Script-to-Video-Prompt Studio. Thay đổi này không render MP4 trong app và không tích hợp provider video trực tiếp. Trọng tâm là biến nhiều nguồn input tiếng Việt hoặc kịch bản thô thành kịch bản video tiếng Anh hấp dẫn, chia scene thành shot ngắn, giữ continuity xuyên suốt và xuất prompt tạo video tiếng Anh chi tiết dùng chung.

## Goals / Non-Goals

**Goals:**
- Cho phép project lưu nhiều nguồn nội dung đầu vào thay vì chỉ một `topic`.
- AI tổng hợp input thành brief, phát triển câu chuyện hấp dẫn và tạo kịch bản chi tiết.
- AI duy trì continuity từ đầu đến cuối bằng story strategy, continuity bible, character bible và style bible.
- Thêm cấu trúc scene/shot: scene là phần nội dung lớn, shot là đơn vị render video ngắn khoảng 1-5 giây để tạo nhịp dựng nhanh và nhiều chuyển cảnh.
- Thay prompt ảnh bằng prompt tạo video tiếng Anh chi tiết, dạng dùng chung, không phụ thuộc provider cụ thể.
- Mỗi shot có mô tả tiếng Việt, narration tiếng Anh nếu có, transition note, video prompt, negative prompt và continuity note.
- Cho phép regenerate, lock và version từng shot/prompt để người dùng sửa cuốn chiếu.
- Cập nhật export ZIP để chứa kịch bản, shot list, continuity bible, prompt video, voice và subtitle.
- Giữ tương thích voice generation, subtitle và package readiness hiện tại.
- Áp dụng `design-taste-frontend-v1` cho UI phase 2 để giao diện local đẹp, thân thiện, dễ dùng với người không rành kỹ thuật.
- Bổ sung logging/debug local có cấu trúc cho từng bước pipeline để người dùng copy lỗi và developer truy ngược nhanh bằng `request_id`.

**Non-Goals:**
- Không render MP4 trong app.
- Không gọi trực tiếp Runway, Kling, Veo, Pika, Luma hoặc provider video khác.
- Không thêm FFmpeg, timeline editor hoặc auto-edit video.
- Không auto-publish lên mạng xã hội.
- Không thay đổi hoặc thêm TTS engine.
- Không bắt buộc prompt theo format riêng của một tool tạo video cụ thể.

## Decisions

### 1. Thêm source blocks thay vì kéo dài `topic`

Project hiện chỉ có `topic`. Phase 2 cần lưu nhiều loại input có ý nghĩa khác nhau: ý tưởng chính, ý tưởng phụ, kịch bản thô, dàn ý, ghi chú nhân vật, phong cách, audience, must-have và avoid. Các input này SHOULD được lưu thành cấu trúc có type/order/content để UI có thể thêm/xóa/sắp xếp và backend có thể đưa vào prompt planning có kiểm soát.

Phương án đã cân nhắc:
- Nhét tất cả vào một text area lớn: nhanh nhưng AI khó hiểu loại thông tin, UI khó review.
- Thêm nhiều cột cố định vào `video_projects`: dễ query nhưng cứng, khó mở rộng.

Quyết định: thêm source block model hoặc artifact JSON có schema rõ ràng. `topic` vẫn giữ làm title/summary ngắn để tương thích danh sách project.

### 2. Chạy planning theo nhiều tầng, không một prompt duy nhất

Phase 1 có thể sinh project plan trực tiếp từ topic. Phase 2 cần chất lượng nội dung cao hơn, nên pipeline nên tách thành các tầng:

```text
source blocks
  -> input synthesis
  -> story strategy + continuity bible
  -> detailed script
  -> scene breakdown
  -> shot breakdown
  -> video prompt pack
```

Tách tầng giúp validate từng artifact, retry từng phần và log lỗi chính xác hơn. Implementation có thể gom một vài tầng vào cùng một Codex call nếu cần tối ưu, nhưng schema/lưu trữ nên vẫn phản ánh các artifact riêng.

Phương án đã cân nhắc:
- Một Codex call tạo tất cả: nhanh nhưng output lớn, dễ invalid JSON, khó regenerate từng phần.
- Một call cho từng shot: kiểm soát tốt nhưng chậm và tốn nhiều lần gọi.

Quyết định: dùng pipeline trung gian: project-level development trước, sau đó shot/prompt generation theo scene hoặc theo batch các scene đã duyệt.

### 3. Thêm shot entity, không ép shot vào scene

Scene hiện là đơn vị voice/prompt phase 1. Với video AI, scene dài 20-30 giây cần chia thành nhiều shot 1-5 giây để tạo nhịp nhanh, nhiều chuyển cảnh và giảm cảm giác nhàm chán. Mỗi shot chỉ nên thể hiện một hành động chính hoặc một góc quay chính. Không để một scene dài chỉ có một góc quay, một bố cục hoặc một camera movement lặp lại. Shot có camera, cỡ cảnh, bố cục, motion, transition, prompt và lock state riêng, trong khi scene giữ vai trò narrative section. Narration không nên bị ép thành câu quá dài trong một shot ngắn; hệ thống cần chia narration thành cụm ngắn hoặc giữ narration ở cấp scene khi phù hợp.

Phương án đã cân nhắc:
- Dùng scene như shot: đơn giản nhưng mất khả năng nhóm nội dung và subtitle/narration theo scene.
- Lưu shot trong JSON blob của scene: ít migration nhưng khó query, khó update từng shot, khó readiness.

Quyết định: thêm `video_shots` hoặc cấu trúc tương đương với `scene_id`, `shot_order`, `duration_seconds`, `vietnamese_description`, `english_narration`, `primary_action`, `shot_type`, `camera_angle`, `framing`, `composition`, `camera_motion`, `transition_to_next`, `locked`, `status` và timestamps.

### 4. Prompt video là artifact mới, prompt ảnh trở thành legacy path

Phase 2 thay output chính từ prompt ảnh sang prompt tạo video. Không nên phá dữ liệu phase 1 bằng rename destructive ngay. Implementation nên thêm artifact prompt video mới, ví dụ `video_shot_prompts`, rồi UI/export phase 2 dùng artifact này. Các project phase 1 vẫn đọc được nếu cần.

Prompt video cần có các field rõ ràng:
- `prompt`: prompt tiếng Anh copy được ngay.
- `negative_prompt`: những thứ cần tránh.
- `duration_seconds` và `aspect_ratio`.
- `camera_motion`, `subject_motion`, `environment_motion`.
- `start_frame`, `end_frame`.
- `lighting`, `mood`, `style_notes`, `continuity_notes`.
- `quality_check` hoặc flags để biết prompt đủ chi tiết chưa.

Phương án đã cân nhắc:
- Sửa bảng `video_scene_prompts` hiện tại: ít bảng hơn nhưng trộn prompt ảnh và prompt video.
- Chỉ lưu prompt text: đơn giản nhưng khó validate/copy từng phần.

Quyết định: lưu prompt video có cấu trúc, đồng thời vẫn tạo file `.txt` copy/download thân thiện.

### 5. Ngôn ngữ tách rõ theo mục đích

Người dùng thao tác bằng tiếng Việt nhưng muốn làm video tiếng Anh. Vì vậy:
- UI, helper text, error, mô tả dễ hiểu: tiếng Việt.
- Script/narration dùng cho video: tiếng Anh theo lựa chọn project.
- Prompt video và negative prompt: tiếng Anh.
- Continuity notes có thể lưu song ngữ, nhưng bản copy cho tool video dùng tiếng Anh.

Quyết định này giảm gánh nặng cho người dùng không biết tiếng Anh nhưng vẫn tạo được đầu ra phù hợp công cụ video quốc tế.

### 6. Prompt dùng chung nhưng tối ưu chi tiết theo nội dung

Phase 2 không tạo prompt riêng cho một tool như Runway/Kling/Veo. Prompt phải dùng chung, nhưng vẫn đủ chi tiết để các tool hiểu nội dung shot. Mỗi prompt MUST không nhắc tên provider cụ thể, trừ khi tương lai có setting riêng.

Mẫu prompt copy nên có dạng tự nhiên, không phụ thuộc syntax tool:

```text
Create a 3-second vertical 9:16 cinematic video of ...
Camera movement: ...
Subject motion: ...
Environment motion: ...
Start frame: ...
End frame: ...
No text, no watermark, no distorted hands...
```

### 7. Continuity bible và story strategy là nguồn sự thật xuyên suốt

AI phải tạo `story_strategy` và `continuity_bible` trước khi tạo shot/prompt. Các prompt shot phải tham chiếu lại continuity bible để giữ nhân vật, trang phục, đạo cụ, bối cảnh, tone màu, mood và style camera ổn định.

Story strategy cần mô tả hook, xung đột, emotional arc, payoff và nhịp dựng. Đây là phần biến input thô thành nội dung hấp dẫn, không chỉ chia cảnh máy móc.

### 8. Lock và regenerate là thao tác theo shot

Người dùng cần sửa từng shot mà không làm mất phần đã duyệt. Shot có `locked=true` MUST không bị AI update trong các lần regenerate batch, trừ khi người dùng unlock rõ ràng. Regenerate có thể áp dụng cho một shot, một scene hoặc tất cả shot chưa locked.

Khi regenerate shot, hệ thống MUST đánh stale prompt, voice/subtitle/package liên quan nếu narration hoặc timing thay đổi.

### 9. Export phase 2 theo cấu trúc video prompt

ZIP phase 2 cần đặt tên tiếng Việt và có cấu trúc dễ kéo vào quy trình dựng:

```text
Bộ nguyên liệu - Ten du an/
  00 - Huong dan su dung.txt
  01 - Kich ban/
    Kich ban tieng Anh.txt
    Mo ta tieng Viet.txt
    Continuity bible.txt
    Shot list.csv
  02 - Prompt video/
    Scene 01 - Shot 01 - Prompt video.txt
  03 - Giong doc/
  04 - Phu de/
  Manifest.json
```

Preview image hiện có là tùy chọn và không còn là trung tâm của phase 2.

## Risks / Trade-offs

- Prompt quá dài hoặc quá nhiều shot -> Giới hạn max source length, max scenes/shots và chia batch khi gọi Codex.
- Codex output invalid JSON -> Validate từng schema, không lưu artifact hỏng, log validation errors và cho retry từng bước.
- AI phát triển nội dung lệch ý người dùng -> UI phải cho review source synthesis, story strategy và script trước khi tạo shot/prompt.
- Nhân vật vẫn không nhất quán ở tool video ngoài -> Prompt mỗi shot phải nhắc continuity notes, nhưng cần nói rõ đây là best-effort vì app không điều khiển renderer ngoài.
- Thêm shot entity làm package/readiness phức tạp hơn -> Tách readiness theo scene và shot, chỉ chặn export khi thiếu prompt video hoặc voice/subtitle bắt buộc.
- Regenerate có thể làm mất nội dung đã duyệt -> Lock state và version history phải được tôn trọng.
- Prompt dùng chung có thể chưa tối ưu hoàn hảo cho một provider cụ thể -> Giữ generic ở phase 2, để provider-specific prompt profiles cho phase sau.
- Migration có thể ảnh hưởng project phase 1 -> Thêm bảng/cột mới theo hướng backward-compatible, không rename/drop destructive trong phase 2.
- UI phase 2 có thể trở thành màn phức tạp vì nhiều bước -> Dùng workflow-first layout, copy tiếng Việt ngắn gọn, empty/loading/error states và mobile-first responsive để người dùng không bị lạc.
- Logging có thể lộ dữ liệu người dùng hoặc token nếu làm ẩu -> Redact secret, truncate nội dung dài, không log full binary/audio và chỉ hiển thị technical details trong debug panel.

## Migration Plan

1. Thêm migration cho source blocks, shot rows, video prompt artifacts và project-level story/continuity fields theo pattern `_migrate_*` hiện có.
2. Giữ các bảng phase 1 như `video_projects`, `video_scenes`, `video_scene_prompts` để tránh phá dữ liệu cũ.
3. Thêm API mới hoặc mở rộng API hiện có cho source blocks, develop script, generate shots, generate video prompts, lock/unlock và regenerate shot.
4. Cập nhật service Codex planning theo pipeline nhiều tầng, validate từng output schema.
5. Thêm structured logger/debug context cho các bước source, story, shot, prompt, voice, subtitle và export.
6. Cập nhật UI AI Video Assistant: tab/khu nhập nguồn nội dung, review story strategy, scene/shot editor, prompt video panel, debug panel và export phase 2.
7. Cập nhật package service để xuất prompt video và shot list thay vì prompt ảnh.
8. Cập nhật tests backend/frontend cho schema, stale state, lock/regenerate, readiness, logging/debug và export.
9. Rollback an toàn bằng cách ẩn UI phase 2 và giữ data mới không ảnh hưởng voice/profile/story hiện có.

## Open Questions

- Trong khoảng 1-5 giây, UI nên dùng default cụ thể là 3 giây hay chế độ Auto để AI tự chọn theo nhịp nội dung?
- Có cần migration chuyển project phase 1 prompt ảnh sang prompt video không, hay chỉ áp dụng phase 2 cho project mới?
- Có cần export thêm `.csv` shot list ngay trong phase 2 hay để sau?
- Có cần preset content type như storytelling, documentary, educational, ad, motivational ngay từ phase 2 không?

## Resolved Decisions

### 1. Default shot duration: 3 giây, cho phép chọn Auto

**Quyết định:** UI dùng default **3 giây** cho mỗi shot. Người dùng có thể chọn chế độ **Auto** để AI tự quyết định duration theo nhịp nội dung.

**Lý do:**
- 3 giây là thời lượng an toàn cho hầu hết video AI tools (Runway, Kling, Veo)
- Cho phép AI tự điều chỉnh giúp video có nhịp tự nhiên hơn
- Người dùng không rành kỹ thuật dễ chọn default, người dùng nâng cao có thể chọn Auto

### 2. Không migration project phase 1 sang phase 2

**Quyết định:** Chỉ áp dụng phase 2 cho **project mới**. Project phase 1 vẫn hoạt động bình thường với prompt ảnh.

**Lý do:**
- Tránh rủi ro phá dữ liệu cũ
- Prompt ảnh và prompt video có cấu trúc khác nhau, migration không đơn giản
- Người dùng có thể tạo project mới nếu muốn dùng phase 2

### 3. Export shot list dạng CSV

**Quyết định:** Phase 2 **có export shot list dạng .csv** trong ZIP package.

**Lý do:**
- Editor video cần bảng shot list để import vào Premiere/Resolve
- CSV dễ mở trong Excel/Google Sheets
- Format: scene_order, shot_order, duration, vietnamese_description, english_narration, shot_type, camera_angle, transition

### 4. Preset content type để sau

**Quyết định:** **Không thêm preset content type** trong phase 2. Có thể thêm ở phase sau nếu cần.

**Lý do:**
- Phase 2 đã đủ lớn với nhiều tính năng mới
- Người dùng có thể mô tả content type trong source blocks
- Giữ UI đơn giản cho người dùng không rành kỹ thuật

### 5. Story review workflow trước khi tạo shot

**Quyết định:** Người dùng **phải review và approve** story strategy, continuity bible và detailed script trước khi AI tạo shot breakdown.

**Workflow:**
```
Source blocks → [Sinh story] → Review story → [Approve] → Shot breakdown → Prompts
                                    │
                                    └── [Reject] → Regenerate story (giữ source)
```

**UI:**
- Màn hình review hiển thị story strategy, continuity bible và script
- Nút "Duyệt kịch bản" để approve
- Nút "Viết lại" để regenerate (không mất source blocks)
- Không cho phép tạo shot khi chưa approve story

**Lý do:**
- Tránh AI tạo shot từ kịch bản sai lệch ý người dùng
- Người dùng có cơ hội sửa trước khi invest vào shot/prompt
- Giảm waste khi phải regenerate toàn bộ

### 6. Error handling và retry policy cho Codex

**Quyết định:** Hệ thống có retry logic và error messages tiếng Việt thân thiện.

**Retry policy:**
- Mỗi bước Codex call: tối đa **3 lần retry**
- Giữa các lần retry: đợi 2 giây
- Nếu 3 lần đều fail: dừng pipeline, hiển thị lỗi tiếng Việt

**Error messages tiếng Việt:**
| Lỗi kỹ thuật | Thông báo người dùng |
|--------------|---------------------|
| Codex CLI not found | "Chưa cài đặt Codex CLI. Vào Settings để cấu hình." |
| Timeout | "AI xử lý quá lâu. Thử lại hoặc rút ngắn nội dung." |
| Invalid JSON | "AI trả về dữ liệu không đúng định dạng. Thử lại." |
| Validation error | "Nội dung AI tạo thiếu thông tin. Thử lại hoặc sửa source." |

**Logging:**
- Mỗi lỗi log với request_id, step_name, error_type
- User-facing message không chứa technical jargon
- Debug panel hiển thị technical details cho troubleshooting

### 7. Mobile layout approach

**Quyết định:** UI phase 2 dùng **mobile-first responsive layout**.

**Layout strategy:**
- Desktop (≥1024px): 2 cột (main content + sidebar)
- Tablet (768-1023px): 1 cột, sidebar chuyển xuống dưới
- Mobile (<768px): 1 cột, stack vertically, không có sidebar cố định

**Mobile-specific:**
- Form inputs full width
- Buttons stack vertically
- Scene/shot cards collapsible
- Bottom sheet cho shot details thay vì sidebar
- Không dùng horizontal scroll

**CSS approach:**
- Dùng Tailwind responsive classes (sm:, md:, lg:)
- Test trên viewport 375px (iPhone SE) và 768px (iPad)
- Task 6.10 validation đảm bảo không có horizontal scroll

### 8. Shot variation validation

**Quyết định:** Backend validate shot variation để đảm bảo không có scene với tất cả shot giống nhau.

**Validation rules:**
- Trong một scene có nhiều shot: ít nhất 2 trong số (camera_angle, framing, composition, camera_motion) phải khác nhau
- Nếu AI trả về shot giống nhau: reject và yêu cầu regenerate
- Log warning khi phát hiện duplicate shots

**Implementation:**
- Thêm function `validate_shot_variation(shots: list[ShotPlan]) -> bool`
- Gọi trong `_run_structured_codex` sau khi parse shot breakdown
- Return friendly error nếu validation fail

### 9. UI quality theo design-taste-frontend-v1

**Quyết định:** UI phase 2 áp dụng baseline `design-taste-frontend-v1`: DESIGN_VARIANCE 8, MOTION_INTENSITY 6, VISUAL_DENSITY 4, nhưng vẫn ưu tiên workflow rõ ràng cho người dùng local không rành kỹ thuật.

**UI direction:**
- First screen là workspace tạo video thật, không làm landing/hero marketing
- Ngôn ngữ UI, helper text, lỗi và checklist dùng tiếng Việt rõ nghĩa
- Form dùng label phía trên, helper/error phía dưới, input block có spacing ổn định
- Loading dùng skeleton theo layout, không chỉ spinner chung chung
- Empty state chỉ rõ bước tiếp theo như thêm ý tưởng, duyệt kịch bản hoặc tạo prompt
- Inline error state luôn có hành động thực tế: thử lại, copy request_id, mở debug
- Mobile collapse về một cột, không horizontal scroll, không text overlap, không `h-screen`

**Visual constraints:**
- Không dùng emoji trong UI copy, alt text hoặc code
- Tránh neon/glow và palette tím/xanh kiểu AI; dùng nền neutral với tối đa một accent color saturation dưới 80%
- Không lồng card trong card; chỉ dùng card khi nó thực sự phân nhóm thao tác hoặc artifact
- Motion chỉ animate transform/opacity; animation lặp phải tách component nhỏ để tránh re-render nặng

**Dependency check đã xác nhận:**
- `app/package.json` đang dùng Tailwind v4 qua `@tailwindcss/vite`
- `framer-motion` đã có, có thể dùng cho motion UI nếu tách component đúng cách
- `lucide-react` đã có, nhưng skill v1 yêu cầu `@phosphor-icons/react` hoặc `@radix-ui/react-icons` nếu import icon mới theo chuẩn skill
- `@phosphor-icons/react` và `@radix-ui/react-icons` chưa có; implementation phải thêm dependency trước khi import, hoặc ghi rõ quyết định dùng icon system hiện có của app nếu project muốn giữ nhất quán

### 10. Local-first logging và debug

**Quyết định:** Phase 2 ghi structured logs local cho pipeline AI Video và cho phép người dùng copy thông tin lỗi từ debug panel.

**Log event fields:**
- `request_id`, `project_id`, `scene_id`, `shot_id`
- `step_name`, `provider`, `model`, `status`, `duration_ms`, `retry_count`
- `error_code`, exception class, technical message, validation errors
- path/file metadata đã redaction khi liên quan export, voice, subtitle hoặc uploaded content

**Local debug behavior:**
- Backend tạo `request_id` cho mỗi action pipeline và trả về cùng response/error
- Debug/status endpoint trả trạng thái artifact, lỗi gần nhất theo step và `request_id`
- UI debug panel ẩn mặc định, hiển thị technical details đã redaction khi người dùng mở
- Nút copy debug info tạo payload ngắn gồm friendly message, `request_id`, step, error code và technical details đã redaction

**Redaction rules:**
- Không log secret token, API key, bearer token hoặc full environment value
- Không log full uploaded binary/audio hoặc toàn bộ nội dung source quá dài
- Truncate user text dài và đánh dấu rõ nội dung đã bị rút gọn
- Không đưa technical stack trace vào user-facing toast; chỉ hiển thị trong debug panel
