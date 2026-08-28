# Implementation notes — Story Studio handoff/source visibility and schema sanitizer

Date: 2026-07-15

## Completed in this fix

- Story Studio now consumes `/story-studio?seriesId=...&episodeId=...` and applies the deep-link once per URL, so Comic Analysis handoff opens the intended Series and Story Episode instead of falling back to the first item.
- Story Episode API responses now include `current_source_document_id` and `source_summary`.
- `source_summary` includes source document id, source revision, source kind, Comic Analysis job id, analysis revision, chunk/page/panel/dialogue counts, coverage metrics, limitations, and whether a structured source exists.
- Story Studio now renders a Comic Analysis source badge with revision, chunk/page/panel/dialogue counts, source document id, limitations, and a link back to the Comic Analysis job.
- Comic Analysis handoff settings now use clearer Vietnamese UX labels: market is a dropdown, language is explicitly `Ngôn ngữ truyện/video`, CTA options are localized, and video prompt segmentation shows a computed summary.
- Story image defaults are now `720x1280` for vertical `9:16` output across frontend defaults, Story Studio backend defaults, and Comic handoff normalization.
- Comic handoff creates new Story Studio series with an anime/manga/webtoon comic-story style bible, and Story Studio falls back to the same style guidance for image/video prompts when the source document is `comic_analysis` and the series has no explicit style bible.
- `ai_planning.run_codex_exec()` now sanitizes `response_format` / `output_schema` JSON schemas before passing them to Codex/OpenAI structured output:
  - every object schema gets `additionalProperties: false`;
  - object branches inside `type` unions are normalized through `anyOf`;
  - nested schemas under `properties`, `items`, `$defs`, `definitions`, `anyOf`, `oneOf`, and `allOf` are normalized recursively.
- Phân tích truyện tranh hiện dùng trải nghiệm tiến trình cùng kiểu với AI Video:
  - lần phân tích đang chọn hiển thị khung tiến trình đầy đủ với nhãn trạng thái, tóm tắt bước hiện tại, hướng dẫn bước tiếp theo, phần trăm lớn, thanh tiến trình có chuyển động và các ô mốc theo chặng;
  - danh sách lần phân tích hiển thị thanh tiến trình nhỏ và phần trăm cho từng lần phân tích;
  - các nút hành động cập nhật giao diện tức thì khi lấy nguồn, phân tích, viết kịch bản tối ưu và đưa vào Story Studio;
  - bước viết lại kịch bản phía máy chủ đánh dấu `current_step=rewrite_story` với tiến độ cao trong lúc Codex viết kịch bản tối ưu, rồi khôi phục trạng thái trước đó nếu bước viết lại lỗi.

## OpenSpec task mapping

- Completes task 9.7 behavior in implementation: `/story-studio` reads `seriesId` and `episodeId` deep-links.
- Completes task 9.8 behavior in implementation: Story Studio displays Comic Analysis source badge, revision, page/panel/dialogue counts, and a link back to the analysis screen.
- Hoàn tất hành vi của task 7.14: máy chủ ghi điểm kiểm tra `rewrite_story` bền vững trong lúc tạo kịch bản tối ưu.
- Hoàn tất hành vi của task 10.15: giao diện tiến trình Phân tích truyện tranh đi theo mẫu khung tiến trình của AI Video.
- Hoàn tất xác minh của task 12.23: giao diện tiến trình và điểm kiểm tra viết lại kịch bản đã vượt qua kiểm tra kiểu frontend, biên dịch backend và kiểm thử hồi quy route truyện tranh.
- Adds regression coverage for the upstream 400 schema failure:

```text
Invalid schema for response_format 'codex_output_schema':
... evidence_refs.items.type.0 ... 'additionalProperties' is required to be supplied and to be false
```

## Verification run

```powershell
.\.codex-temp\pytest-venv\Scripts\python.exe -m pytest backend/tests/test_comic_handoff.py::test_commit_creates_full_source_document backend/tests/test_ai_planning_schema.py::test_codex_exec_sanitizes_output_schema_for_openai_response_format -q
.\.codex-temp\pytest-venv\Scripts\python.exe -m pytest backend/tests/test_comic_source_context.py::test_source_summary -q
npm run typecheck
.\.codex-temp\pytest-venv\Scripts\python.exe -m pytest backend/tests/test_comic_handoff.py::test_commit_creates_full_source_document backend/tests/test_comic_handoff.py::test_comic_handoff_image_prompt_keeps_anime_manga_webtoon_style backend/tests/test_story_studio.py::test_image_adaptation_manual_panel_count_and_image_size -q
bun x tsc -p app/tsconfig.json --noEmit
.\backend\venv\Scripts\python.exe -m py_compile backend\routes\comic_series_analysis.py
.\backend\venv\Scripts\python.exe -m pytest backend\tests\test_comic_routes.py -q
```
