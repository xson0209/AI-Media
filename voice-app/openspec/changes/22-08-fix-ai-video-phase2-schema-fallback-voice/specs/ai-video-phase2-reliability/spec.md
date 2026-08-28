# Đặc tả: Độ tin cậy AI Video Phase 2

## ADDED Requirements

### Requirement: Schema structured output phải hợp lệ

Mọi schema gửi tới Codex/OpenAI Structured Outputs MUST là strict JSON Schema hợp lệ.

#### Scenario: Object có required và properties không khớp

- **WHEN** schema được tạo hoặc chuẩn hóa
- **THEN** `required` MUST là mảng chứa đúng mọi key trong `properties` và không có key dư
- **AND** provider request MUST bị chặn ở local nếu invariant này không đạt
- **AND** audit MUST ghi path schema và lý do validation

#### Scenario: Object tự do không có properties

- **WHEN** output model chứa `dict`, `dict[str, Any]` hoặc object không khai báo field
- **THEN** hệ thống MUST không gửi object đó như strict structured output
- **AND** MUST yêu cầu model có contract cụ thể hoặc chuyển sang fallback text có validation

### Requirement: Fallback không được đưa metadata vào production content

Fallback MUST phân biệt provenance/audit metadata với narration, dialogue, subtitle và prompt production.

#### Scenario: Source có provenance handoff

- **WHEN** source block hoặc project topic chứa job ID, URL, path, checksum, tên gói phân tích hoặc marker provenance
- **THEN** các giá trị đó MUST NOT được dùng làm `english_narration`, speech cue text, subtitle text hoặc production dialogue
- **AND** provenance MUST chỉ được giữ trong metadata/evidence/audit

#### Scenario: Provider timeout và dùng fallback nội bộ

- **WHEN** story, shot hoặc prompt pack chuyển sang fallback
- **THEN** fallback MUST tạo nội dung có cấu trúc và gắn `fallback_used`
- **AND** fallback MUST lọc metadata trước khi ghi DB
- **AND** nếu không tạo được production content hợp lệ, trạng thái MUST là `needs_review`, không được giả vờ thành công

### Requirement: Production narration phải đúng ngôn ngữ video

`target_language` MUST là nguồn sự thật cho narration, speech cue, subtitle và TTS.

#### Scenario: Project chọn tiếng Anh

- **WHEN** `target_language=en`
- **THEN** `english_narration` MUST là narration tiếng Anh tự nhiên
- **AND** tiếng Việt chỉ được xuất hiện trong field review/explanation hoặc `vietnamese_description`
- **AND** text tiếng Việt rõ ràng hoặc metadata MUST bị chặn trước TTS

#### Scenario: Narration không hợp lệ trước TTS

- **WHEN** narration chứa provenance marker, URL/path/job ID hoặc không đạt kiểm tra ngôn ngữ
- **THEN** hệ thống MUST không tạo generation/audio
- **AND** shot MUST chuyển sang `needs_review` hoặc `voice_blocked`
- **AND** audit MUST ghi `VIDEO_VOICE_NARRATION_INVALID` cùng shot order và lý do đã redaction

### Requirement: Chế độ chỉ câu lệnh video phải chứa native audio intent

Khi `material_target=prompts_only`, hệ thống MUST bỏ qua TTS/SRT riêng nhưng MUST giữ đầy đủ audio intent trong prompt Veo để Veo 3 có thể render thoại và hiệu ứng âm thanh trong clip.

#### Scenario: Prompt-only có thoại nhân vật

- **WHEN** shot có thoại hoặc voice-over và material target là `prompts_only`
- **THEN** prompt MUST chứa nguyên văn câu thoại theo `target_language`
- **AND** MUST có speaker, vai trò, cách đọc, cảm xúc, bối cảnh và `lip_sync_required`
- **AND** prompt MUST phân biệt thoại on-screen với voice-over off-screen
- **AND** hệ thống MUST không tạo TTS/SRT riêng cho shot đó

#### Scenario: Prompt-only có hiệu ứng âm thanh

- **WHEN** shot có hành động, ambience, nhạc nền hoặc SFX cần render
- **THEN** prompt MUST có khối `SOUND DESIGN` hoặc tương đương với ambience, music, SFX, timing/beat và mixing notes
- **AND** MUST chỉ dẫn Veo 3 render native audio trong chính clip
- **AND** mixing notes MUST yêu cầu thoại rõ hơn nhạc/SFX khi hai nguồn chồng nhau

#### Scenario: Prompt-only thiếu audio intent

- **WHEN** shot yêu cầu thoại hoặc âm thanh nhưng prompt không có dialogue/audio block hợp lệ
- **THEN** shot MUST chuyển sang `needs_review`
- **AND** material run MUST NOT coi prompt là hoàn chỉnh hoặc gửi sang render tự động

### Requirement: Readiness phải phân biệt native audio và audio ngoài

Readiness MUST dùng `material_target` và nguồn speech để quyết định artifact bắt buộc.

#### Scenario: Prompt-only không có audio file ngoài

- **WHEN** `material_target=prompts_only` và prompt đã có dialogue/audio intent hợp lệ
- **THEN** thiếu `audio_path` hoặc SRT riêng MUST NOT là blocking error
- **AND** audit MUST ghi external TTS/SRT đã được bỏ qua có chủ đích

#### Scenario: Full materials cần audio ngoài

- **WHEN** material target yêu cầu project audio và không dùng native speech
- **THEN** readiness MUST tiếp tục yêu cầu voice/subtitle artifact theo contract hiện tại

### Requirement: Retry, timeout và audit phải truy nguyên được

Mọi attempt của AI planning MUST được liên kết bằng request ID và lưu kết quả từng lớp fallback.

#### Scenario: Provider từ chối response_format

- **WHEN** `--output-schema` trả lỗi 400
- **THEN** audit MUST giữ provider status/message đã redaction trước khi retry
- **AND** event MUST phân biệt schema fallback với model/config fallback và fallback nội bộ

#### Scenario: Prompt vượt budget hoặc bị truncate

- **WHEN** source context bị cắt hoặc prompt được batch
- **THEN** audit MUST ghi `source_chars`, `prompt_chars`, danh sách block bị truncate, batch index/count và lý do
- **AND** pipeline MUST không im lặng coi nội dung bị cắt là đầy đủ

### Requirement: Prompt pack phải được batch mà không hạ contract chất lượng

Prompt pack Phase 2 MUST được chia thành các batch tuần tự, mặc định tối đa 5 shot mỗi batch. Mỗi batch MUST giữ nguyên schema, quality instructions, continuity context, target language và toàn bộ các trường dữ liệu đầu vào của shot; chỉ được giảm số shot nằm trong request.

#### Scenario: Batch giữ nguyên chất lượng và stable order

- **WHEN** project có nhiều hơn 5 shot cần tạo prompt
- **THEN** hệ thống MUST gửi các batch theo thứ tự shot tăng dần, mỗi batch tối đa 5 shot
- **AND** prompt của batch MUST chỉ chứa shot được gán cho batch đó
- **AND** output MUST được validate bằng cùng contract quality hiện tại trước khi merge
- **AND** kết quả cuối MUST được merge deterministic theo `shot_order`, không trùng và không thiếu shot
- **AND** audit MUST ghi `batch_index`, `batch_count`, `batch_start_order`, `batch_end_order`, `batch_shot_orders`, `batch_prompt_chars` và stable idempotency key

#### Scenario: Batch lỗi được retry đúng một lần

- **WHEN** một batch lỗi do provider, timeout, parse hoặc validation
- **THEN** hệ thống MUST retry đúng một lần cho chính batch đó
- **AND** MUST không retry lại các batch đã thành công
- **AND** nếu retry vẫn lỗi, toàn bộ prompt-pack generation MUST thất bại
- **AND** hệ thống MUST không dùng fallback prompt nội bộ để ghi thay cho batch lỗi

#### Scenario: Không ghi partial prompt pack

- **WHEN** một batch bất kỳ thất bại sau lần retry duy nhất
- **THEN** hệ thống MUST không ghi prompt của các batch trước đó
- **AND** prompt pack cũ của project MUST được giữ nguyên
- **AND** chỉ sau khi toàn bộ batch pass và full-pack validation pass hệ thống mới được persist prompt rows/files

### Requirement: Khôi phục artifact downstream khi narration thay đổi

Thay đổi narration hoặc phát hiện narration invalid MUST làm stale các artifact phụ thuộc.

#### Scenario: Phát hiện audio đã tạo từ narration sai

- **WHEN** repair phát hiện generation/audio chứa metadata hoặc sai ngôn ngữ
- **THEN** generation, audio, subtitle, package và render phụ thuộc MUST được đánh stale/xóa theo policy khôi phục
- **AND** source media gốc MUST được giữ nguyên
- **AND** voice chỉ được tạo lại sau khi narration được validate và người dùng duyệt khi cần
