# Thiết kế: Sửa ổn định schema, fallback và voice cho AI Video Phase 2

## 1. Nguyên tắc thiết kế

### 1.1 Tách ba loại dữ liệu

Pipeline phải phân biệt rõ:

```text
Provenance / audit metadata
    -> job ID, URL, path, checksum, source package, block type

Review / explanation content
    -> tiếng Việt, mô tả cho người dùng, lý do fallback, cảnh báo

Production content
    -> narration, speech cue, subtitle, prompt video, text người xem nghe/đọc
```

Chỉ loại thứ ba được truyền vào TTS, subtitle production và prompt generation. Provenance có thể được đính kèm dưới dạng metadata hoặc evidence reference nhưng không được nội suy thành narration.

### 1.2 Schema output phải khai báo được toàn bộ contract

Thay các field tự do bằng model cụ thể:

- `related_characters`: model `RelatedCharacterPlan`.
- `visible_characters`: model `VisibleCharacterPlan`.
- `quality_check`: model `QualityCheckPlan` với các flag/ghi chú cần thiết.

Nếu một object thật sự cần mở rộng tùy ý, object đó không được gửi qua strict structured output; phải dùng field chuỗi/JSON text được validate ở tầng ứng dụng hoặc dùng một contract key-value đã định nghĩa trước.

Sanitizer phải kiểm tra đệ quy:

- object có `properties` thì `required` phải đúng bằng tập property;
- object không có `properties` không được âm thầm biến thành object strict rỗng;
- `$ref`, `$defs`, `items`, `anyOf`, `oneOf`, `allOf` đều phải được kiểm tra;
- union nullable phải giữ đúng contract provider hỗ trợ;
- unsupported keyword phải được loại bỏ hoặc báo lỗi trước khi gọi provider.

### 1.3 Fallback có cùng contract ngôn ngữ với đường chính

Fallback story/shot/prompt phải nhận `target_language` làm nguồn sự thật. Với `en`, mọi `english_narration` phải là tiếng Anh; tiếng Việt chỉ được đặt trong `vietnamese_description`, review hoặc technical note.

Fallback không được lấy `project.topic` nguyên khối nếu topic có handoff metadata. Source compiler cần trả các trường tách biệt, ví dụ:

```text
creative_source_text
source_provenance
source_constraints
source_style_notes
```

Nếu chưa thể tách ở lớp compiler, `_fallback_source_snippets()` phải lọc tối thiểu các marker:

- `Provenance nguồn Video Inspiration`;
- `Video Inspiration job ID`;
- `Loại nguồn`, `Tên file nguồn`, `Link nguồn`;
- `Đường dẫn file nguồn`, `Gói phân tích`;
- URL, path nội bộ, checksum, JSON/MP4 artifact reference.

Lọc marker chỉ là lớp phòng thủ; nguồn đúng vẫn phải được tách cấu trúc ở upstream.

### 1.4 Không tạo artifact downstream từ narration chưa được kiểm tra

Trước khi enqueue TTS, tạo subtitle hoặc đánh dấu render-ready, chạy `validate_production_narration()`:

- text không rỗng và không phải metadata;
- không chứa provenance/job ID/URL/path marker;
- ngôn ngữ phù hợp với `target_language` theo policy nhẹ, có thể dùng heuristic + cờ review thay vì khẳng định ngôn ngữ tuyệt đối;
- độ dài phù hợp duration;
- speech cue và narration không xung đột.

Nếu không đạt, shot chuyển sang `needs_review` hoặc `voice_blocked`, không tạo generation.

### 1.5 Chế độ “Chỉ câu lệnh video” và native audio của Veo 3

`material_target=prompts_only` chỉ có nghĩa là không chạy pipeline TTS/SRT riêng và không tự tạo audio file bên ngoài. Nó không có nghĩa là prompt video được phép bỏ qua âm thanh.

Mỗi prompt trong chế độ này phải có một khối audio production rõ ràng, gồm:

- thoại nguyên văn theo `target_language`, không phải tóm tắt nội dung thoại;
- `speaker_name`, `speaker_role`, `voice_description`, `delivery`, `emotion`, `context` và `lip_sync_required` cho từng câu thoại;
- chỉ dẫn thoại trong khung hình hay voice-over ngoài khung hình;
- ambience/room tone và âm thanh môi trường theo bối cảnh;
- SFX theo hành động và timestamp/beat khi có thể;
- music mood, energy curve, điểm vào/ra và mức trộn;
- quy tắc mix để thoại rõ, không bị nhạc/SFX che;
- chỉ dẫn cho Veo 3 render native audio trong chính clip.

Prompt phải phân biệt rõ phần `DIALOGUE` và `SOUND DESIGN`, nhưng vẫn nằm trong một prompt Veo duy nhất. Không được đưa provenance, URL, path, job ID hoặc ghi chú review tiếng Việt vào khối thoại/audio production.

Khi `prompts_only` được chọn:

- không enqueue `create_shot_narration()`;
- không tạo SRT riêng;
- không coi thiếu `audio_path`/SRT riêng là lỗi readiness;
- readiness phải kiểm tra prompt có dialogue/audio direction nếu shot có lời hoặc có yêu cầu âm thanh;
- nếu prompt thiếu thoại/SFX bắt buộc, shot phải `needs_review`, không được coi là prompt hoàn chỉnh.

### 1.6 Fallback và batching để giảm timeout

Giữ fallback inline JSON hiện tại nhưng bổ sung:

- lưu provider stderr/status của attempt đầu;
- giới hạn prompt theo budget từng bước;
- chỉ gửi summary/chunks cần thiết cho từng bước;
- chia prompt pack thành batch nhỏ theo segment, có stable shot order và idempotency;
- với `video_prompt_generation`, mặc định chia tối đa 5 shot/batch; mỗi batch dùng nguyên schema và nguyên quality instruction hiện tại, chỉ thay danh sách shot đầu vào;
- mỗi batch có đúng 2 attempts tối đa (lần đầu + 1 retry). Batch lỗi sau retry làm fail toàn pack và không dùng fallback prompt nội bộ để ghi thay;
- chỉ merge/persist sau khi mọi batch đã pass validation; batch metadata được ghi bằng idempotency key ổn định và không ghi nội dung prompt đầy đủ vào audit;
- không gửi lặp lại toàn bộ story, source và 18 shot trong từng request;
- ghi `prompt_chars`, `source_chars`, `truncated_block_ids`, `batch_index`, `batch_count` trong audit.

Nếu vượt budget, pipeline phải báo `context_compacted` hoặc `needs_review`, không im lặng cắt phần có ý nghĩa.

## 2. Luồng xử lý dự kiến

```text
Source handoff
  -> chuẩn hóa creative text / provenance / constraints riêng
  -> compile context theo budget
  -> tạo schema strict hợp lệ
  -> Codex structured output
       | thành công
       v
    validate schema + language + production content
       | thất bại provider/timeout
       v
    lưu provider detail + retry inline schema có giới hạn
       | vẫn thất bại
       v
    fallback nội bộ an toàn, có language/content validation
  -> validate scene/shot/prompt contract
  -> persist với fallback metadata
  -> nếu prompts_only: validate dialogue/audio block -> prompt sẵn sàng gửi Veo 3
  -> nếu full_materials: validate narration -> enqueue voice/subtitle
  -> render chỉ khi nguồn audio tương ứng đã hợp lệ
```

## 3. Audit và khôi phục dữ liệu

Mỗi AI attempt cần event liên kết cùng `request_id`, `project_id`, `step_name`, `attempt`, `fallback_kind` và các budget count. Event failure phải giữ cả:

- `provider_status_code`;
- `provider_message_redacted`;
- `schema_path`/schema issue nếu có;
- `retry_reason`;
- kết quả cuối cùng (`fallback_used`, `fallback_kind`).

Project đã bị ảnh hưởng cần được xử lý như một data repair:

- đánh stale/xóa generation và audio sai;
- đánh stale subtitle/package/render;
- không tự động phát lại audio cũ;
- tạo lại story/shot narration sau khi fallback được sửa;
- yêu cầu người dùng duyệt narration trước khi enqueue TTS lại.

## 4. Tương thích ngược

- Giữ tên field API `english_narration` vì frontend và DB hiện dùng field này, nhưng semantics là “narration theo ngôn ngữ video đã chọn”, không mặc định tiếng Anh.
- Các row cũ chứa JSON object tự do được normalize về model mới; key không biết phải đưa vào `additional_notes`/review metadata hoặc đánh `needs_review`, không silently drop.
- Project đã có audio hợp lệ không bị tạo lại nếu narration hash không đổi và validation vẫn pass.

## 5. Tiêu chí không chấp nhận

- Không dùng `dict`/`dict[str, Any]` làm item object trong schema gửi Structured Outputs.
- Không coi `required` là hợp lệ nếu có key không nằm trong `properties`.
- Không enqueue TTS với text chứa provenance marker hoặc target-language mismatch rõ ràng.
- Không coi fallback là thành công nếu chỉ tạo được row nhưng production content không dùng được.
