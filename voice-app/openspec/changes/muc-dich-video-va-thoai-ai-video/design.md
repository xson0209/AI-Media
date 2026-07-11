## Context

AI Video phase 2 đang có `target_language` để quyết định ngôn ngữ người xem nghe/đọc, và change `ngon-ngu-video-tuy-chon` đã xác định tiếng Anh/tiếng Việt phải đi xuyên suốt story, narration, voice, subtitle và export. Tuy vậy, người dùng vẫn phải tự suy luận nên chọn ngôn ngữ nào cho từng mục tiêu nội dung, chọn voice nào phù hợp, và muốn mức thoại/narration ra sao.

Hiện workflow tạo video đã có source blocks, target duration, prompt segment config, `visual_style`, `voice_profile_id`, `english_narration` tương thích cũ và auto-run tạo nguyên liệu. Change này thêm lớp cấu hình sản phẩm ở đầu workflow: người dùng chọn mục đích video, hệ thống đề xuất cấu hình và đưa mục đích đó vào AI planning để tạo thoại đúng audience.

## Goals / Non-Goals

**Goals:**
- Cho người dùng chọn `Mục đích video` trước hoặc khi tạo project AI Video phase 2.
- Preset mục đích gợi ý `target_language`, voice compatibility, dialogue mode, narration density, subtitle behavior và tone script.
- Giữ `target_language` là nguồn sự thật cuối cùng cho ngôn ngữ video; preset không được silently override lựa chọn thủ công của người dùng.
- Chuẩn hoá dữ liệu gửi Codex để purpose, target language, dialogue mode, narration density, source blocks và series context đi vào prompt theo cùng một contract ổn định.
- Chuẩn hoá dữ liệu Codex trả về để alias như `voiceover_text`, `dialogue`, `video_purpose`, `purpose`, `narration_density` được map về field chuẩn hoặc bị reject khi mâu thuẫn.
- AI planning phải tạo thoại/narration phù hợp mục đích: rõ ràng cho video giải thích, có hook/CTA cho quảng cáo, tự nhiên hơn khi cần nhân vật nói, và luôn đúng ngôn ngữ video.
- Khi đổi purpose hoặc dialogue settings trên project đã có artifact, stale đúng các phần phụ thuộc để tránh export sai script/voice/subtitle.

**Non-Goals:**
- Không thêm TTS engine mới.
- Không làm video song ngữ nhiều audio track trong cùng một project/export.
- Không làm lip-sync, multi-speaker timeline hoặc character voice casting tự động trong change này.
- Không rename `english_narration`; field này vẫn là narration/voice text tương thích theo ngôn ngữ video.
- Không tự upload/generate video clip bằng provider ngoài; change này chỉ chuẩn hóa planning, thoại, voice và export metadata.

## Decisions

### Lưu purpose trên project, không chỉ là state UI

Thêm field project-level, ví dụ `video_purpose`, để project resume, auto-run, duplicate/localize và package manifest đều biết vì sao script/thoại được tạo theo kiểu đó. Giá trị ban đầu nên là enum string ổn định:

- `vietnam_market`: audience Việt Nam, mặc định gợi ý `target_language = vi`.
- `global_short`: audience quốc tế, mặc định gợi ý `target_language = en`.
- `educational_explainer`: video giải thích/giáo dục, ưu tiên thoại rõ nghĩa và nhịp dễ nghe.
- `sales_ad`: quảng cáo/bán hàng, ưu tiên hook, lợi ích, CTA và thoại cô đọng.
- `localized_variant`: tạo bản localize từ project/source có sẵn, ưu tiên giữ ý tưởng nhưng đổi language/style theo audience mới.

Phương án khác đã cân nhắc: chỉ dùng `visual_style` hoặc source block để ghi mục đích. Cách đó không đủ máy đọc, khó stale chính xác, khó test và khó hiển thị lại trong UI.

### Preset chỉ gợi ý, `target_language` vẫn là source of truth

Khi chọn purpose mới, UI có thể đề xuất đổi `target_language`, voice profile hoặc dialogue mode, nhưng người dùng phải thấy rõ thay đổi này và có thể override. Backend không được tự đổi `target_language` ngầm chỉ vì purpose đổi.

Điều này giữ tương thích với change `ngon-ngu-video-tuy-chon`: ngôn ngữ video được quyết định bởi `target_language`, còn purpose quyết định cách viết và mức thoại trong ngôn ngữ đó.

### Chuẩn hoá outbound context trước khi gửi Codex

Thêm một helper chuẩn hoá context trước khi dựng prompt, ví dụ `normalize_phase2_codex_context(project, db)`, để tạo một object/logical payload ổn định gồm:

- `target_language`: đã normalize bằng helper AI Video language hiện có.
- `video_purpose`: enum hợp lệ hoặc fallback `custom`/default an toàn.
- `dialogue_mode`: enum hợp lệ hoặc fallback theo preset.
- `narration_density`: enum hợp lệ hoặc fallback theo preset.
- `source_blocks`: sort theo `sort_order`, strip nội dung, bỏ block rỗng, truncate an toàn nếu cần.
- `series_context`: giữ các field cốt lõi, truncate an toàn, log field thiếu/truncate như hiện tại.
- `prompt_segment_config`: segment count, clip duration, micro-scenes per prompt và target duration đã resolve.

Prompt story/shot/video-prompt vẫn có thể là text, nhưng text đó phải được build từ context đã chuẩn hoá. Như vậy test có thể kiểm tra context/prompt ổn định, và future purpose/dialogue fields không bị thêm rời rạc ở nhiều prompt.

Phương án khác đã cân nhắc: tiếp tục ghép string trực tiếp trong từng prompt. Cách đó đang hoạt động, nhưng khi thêm purpose/dialogue sẽ dễ lệch giữa story, shot breakdown và prompt pack, khó test và khó debug khi Codex trả sai.

### Chuẩn hoá inbound Codex output trước khi validate/ghi DB

Mở rộng pattern `_normalize_*_payload` hiện có cho các field mới. Các alias cần map về field chuẩn gồm tối thiểu:

- Purpose: `video_purpose`, `purpose`, `project_purpose`, `audience_purpose`, `use_case`.
- Dialogue mode: `dialogue_mode`, `voice_mode`, `speech_mode`, `narration_mode`.
- Narration density: `narration_density`, `voiceover_density`, `speech_density`, `talk_density`.
- CTA style: `call_to_action_style`, `cta_style`, `cta`, `sales_cta`.
- Narration text: tiếp tục map `english_narration`, `narration`, `voiceover`, `voiceover_text`, `dialogue`, `spoken_narration` về field tương thích hiện có.

Nếu nhiều alias cùng xuất hiện nhưng nội dung khác nhau, hệ thống phải reject bằng lỗi mapping rõ ràng thay vì đoán. Nếu Codex trả thiếu field core cho purpose/dialogue contract, lỗi validation phải ghi được raw/normalized field types giống các bước phase 2 hiện tại.

Phương án khác đã cân nhắc: để Pydantic schema tự reject mọi alias lạ. Cách đó chặt hơn nhưng làm Codex output dễ fail vì LLM thường dùng tên field gần đúng; normalize alias giúp workflow bền hơn mà vẫn reject khi có mâu thuẫn.

### Tách dialogue guidance khỏi TTS implementation

Change này cần “thoại” ở mức script/voice text, không mở rộng sang nhiều speaker hoặc lip-sync. Nên thêm planning contract, có thể là các field cấu hình nhẹ:

- `dialogue_mode`: `voiceover`, `character_lines`, hoặc `mixed`.
- `narration_density`: `light`, `balanced`, hoặc `dense`.
- `call_to_action_style`: optional cho `sales_ad`.

Các field này đi vào prompt story/shot generation để AI tạo `scene.dialogue` và `shot.english_narration` đúng mục đích. TTS vẫn tạo audio từ text đã có bằng voice profile hiện tại.

Phương án khác đã cân nhắc: tạo luôn multi-speaker dialogue. Cách đó cần data model speaker/voice mapping, timeline alignment, render/subtitle thay đổi lớn và chưa cần cho mục tiêu hiện tại.

### Voice compatibility là cảnh báo sớm, không silent fallback

Frontend nên dùng bảng hỗ trợ engine/language hiện có để cảnh báo khi purpose đề xuất tiếng Việt nhưng voice/engine hiện tại không hỗ trợ. Backend vẫn phải validate ở request tạo voice để không silent fallback sang tiếng Anh hoặc voice sai ngôn ngữ.

### Localize bằng duplicate project, không song ngữ trong một project

Nếu người dùng muốn cả bản tiếng Việt và tiếng Anh, workflow nên tạo bản sao/localized variant từ source/project hiện có. Mỗi project có một `target_language`, một purpose snapshot và artifact riêng. Cách này đơn giản cho stale, package, voice và subtitle.

## Risks / Trade-offs

- Purpose enum quá cứng, sau này muốn thêm use case mới phải sửa code -> Giảm rủi ro bằng helper preset map tập trung và label/config frontend dùng chung type.
- Preset tự đổi quá nhiều cấu hình làm người dùng mất kiểm soát -> UI phải preview “sẽ đổi gì” và chỉ apply rõ ràng khi người dùng chọn.
- AI vẫn sinh thoại lệch purpose hoặc lệch language -> Prompt phải đưa `purpose`, `target_language`, `dialogue_mode`, `narration_density` vào cùng context và test prompt/stub phải kiểm tra các instruction này.
- Chuẩn hoá outbound/inbound không đồng bộ giữa story, shot và prompt pack -> Dùng helper context chung và alias map tập trung; test cả ba bước Codex với cùng purpose/dialogue settings.
- Alias quá rộng có thể map nhầm ý nghĩa -> Chỉ alias các field đã biết, reject conflict khi nhiều alias có nội dung khác nhau, và log raw/normalized field types khi fail.
- Voice tiếng Việt phụ thuộc engine/profile -> Hiển thị warning sớm ở UI và backend trả lỗi tiếng Việt rõ ràng, không fallback im lặng.
- Đổi purpose có thể stale nhiều artifact -> Chỉ stale story/shot/prompt/voice/subtitle/package khi purpose hoặc dialogue settings đã dùng để tạo artifact thay đổi; không stale chỉ vì đổi label UI không tác động output.

## Migration Plan

- Thêm cột nullable/default cho `video_purpose` và các setting dialogue nếu quyết định lưu riêng. Project cũ fallback `global_short` hoặc `custom` nhưng không đổi `target_language` hiện có.
- Backfill project cũ theo hướng an toàn: nếu không có purpose, UI hiển thị `Tùy chỉnh` hoặc purpose mặc định không ép regenerate.
- Package manifest ghi purpose nếu có; nếu thiếu thì ghi `custom`/empty để tương thích.
- Rollback đơn giản nếu chỉ thêm nullable/default columns: code cũ bỏ qua các cột mới, dữ liệu project vẫn còn `target_language`, narration và voice artifacts cũ.

## Open Questions

- Có cần purpose `custom` ngay từ đầu để người dùng tự chỉnh ngoài preset không, hay chỉ dùng preset enum và cho override từng field?
- `localized_variant` nên là purpose trong cùng form hay một action riêng `Tạo bản localize` từ project hiện tại?
- Có cần lưu `dialogue_mode` và `narration_density` thành cột riêng ngay, hay chỉ lưu trong một JSON config để dễ mở rộng preset?
