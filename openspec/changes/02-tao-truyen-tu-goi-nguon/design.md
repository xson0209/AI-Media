# Thiết kế: Story Studio tạo truyện từ Gói nguồn

## Hiện trạng

Story Studio hiện có một seam `_compile_episode_source_payload()` để lấy nguồn đã duyệt cho candidate prompt. Seams liên quan:

- `comic_series_analysis.source_context.compile_context()`
- `creative_brief["structured_source"]`
- `dependency_fingerprint` trên `StoryScenarioCandidate`
- `generate_candidates()` / `select_master_story()` / `synthesize_master_story()`

Nhưng source payload hiện tại vẫn là một payload riêng của Story Studio, không phải Gói nguồn chuẩn dùng chung.

## Hướng triển khai

### 1. Story Studio đọc Gói nguồn chuẩn

Thay vì tự dựng payload nguồn riêng, `_compile_episode_source_payload()` sẽ:

- gọi `comic_source_context.compile_source_package()`;
- lấy `SourcePackage` trả về;
- biến package đó thành payload phù hợp cho Story Studio candidate generation;
- giữ một bản text ngắn gọn để nhét vào memory/prompt giới hạn độ dài.

### 2. Structured source của candidate phải nói rõ package

`creative_brief["structured_source"]` sẽ mang thông tin như:

- `schema_version`
- `source_kind`
- `source_ref_id`
- `source_revision`
- `title`
- `summary`
- `coverage_metrics`
- `limitations`
- `provenance`
- `fingerprint`
- `blocks`

Nếu cần bản text rút gọn cho prompt, Story Studio có thể tạo thêm trường phụ như `prompt_text` hoặc `prompt_chunks`, nhưng phải xuất phát từ package chứ không dựng lại song song một payload khác.

### 3. Candidate rows vẫn tương thích DB hiện tại

Không thêm cột mới.

Story Studio tiếp tục dùng:

- `source_document_id`
- `source_document_revision`
- `development_mode`
- `dependency_fingerprint`

Nhưng `dependency_fingerprint` sẽ là fingerprint của Gói nguồn chuẩn.

### 4. Giữ hành vi người dùng

Người dùng vẫn thấy:

- đúng 3 candidate;
- candidate khác nhau theo chiến lược;
- master story được chọn/synthesize như cũ;
- giao diện app vẫn dùng tiếng Việt để người dùng đọc;
- ngôn ngữ nội dung truyện/video là lựa chọn riêng qua `target_language`;
- shape chính của API không đổi.

### 5. Tách UI language và content language

Trong change này, “ngôn ngữ giao diện” và “ngôn ngữ nội dung” được xem là hai khái niệm khác nhau:

- `ui_language`: ngôn ngữ chữ hiển thị trong app cho người dùng đọc. Hiện tại giữ mặc định/cố định là tiếng Việt.
- `target_language` hoặc `language_profile`: ngôn ngữ nội dung được sinh ra cho người xem, gồm title, hook, full story, narration, thoại, phụ đề, chữ trên màn hình và CTA.

Hệ thống không được dùng `target_language` để đổi label UI sang tiếng Anh/Nhật/Hàn..., và cũng không được dùng việc UI là tiếng Việt để ép output truyện/video phải là tiếng Việt.

Ở các prompt AI:

- các field phục vụ người xem phải bám `target_language`;
- các field giải thích/duyệt cho app như `reason_vi`, `review_vi`, `*_vi` vẫn viết tiếng Việt để người dùng hiểu.

Ở UI:

- label, hint, trạng thái, lỗi và mô tả thao tác vẫn là tiếng Việt;
- dropdown ngôn ngữ nội dung hiển thị tên ngôn ngữ bằng tiếng Việt;
- lựa chọn nội dung không còn chỉ giới hạn `vi/en`.

## Rủi ro

- Nếu package summary text quá dài, prompt có thể vượt budget.
- Nếu structured_source đổi shape quá mạnh, một số test snapshot/prompt có thể fail.
- Nếu fingerprint tính thiếu block/provenance, stale sau này có thể kém chính xác.
- Nếu prompt vẫn còn câu cũ kiểu “viết bằng tiếng Việt” cho field phục vụ người xem, nội dung có thể bị ép sai ngôn ngữ dù UI đã chọn ngôn ngữ khác.

## Kiểm soát

- Giữ `_compile_episode_source_payload()` là seam hẹp, không kéo refactor lan ra toàn bộ Story Studio.
- Giữ fallback hiện có cho memory/prompt nếu package không tạo được.
- Không đổi schema candidate/master trong bước này.
- Dùng helper ngôn ngữ chung cho video/story để tránh hard-code `vi/en` rải rác.
- Dùng test để bảo đảm candidate output vẫn tương thích.
