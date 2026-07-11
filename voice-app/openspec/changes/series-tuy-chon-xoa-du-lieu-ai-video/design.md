## Context

AI Video hiện có `video_projects` là đơn vị làm việc chính. Project chứa topic/config, source blocks, story, shots, prompts, voice, subtitles, package/render artifacts và debug events. UI “Dự án gần đây” đang hiển thị danh sách project phẳng và backend đã có một số thao tác xoá như xoá project và xoá source block, nhưng chưa expose đầy đủ trong UI và chưa có reset generated data giữ lại nguồn nhập.

Các project dài tập hiện chỉ có thể được tạo như nhiều project rời nhau. Điều này dễ làm Codex đổi nhân vật, bối cảnh, style hoặc trạng thái câu chuyện giữa tập. Tuy nhiên series không nên bắt buộc vì nhiều use case vẫn là project lẻ một video.

Một ràng buộc quan trọng là Codex output từng sai key, sai count hoặc sai cấu trúc trong các bước story/shots/prompt. Change này cần coi mapping/validation là boundary bắt buộc trước khi ghi DB, đặc biệt khi thêm Series Bible vì dữ liệu sai ở bible có thể ảnh hưởng nhiều tập sau.

## Goals / Non-Goals

**Goals:**
- Thêm series tuỳ chọn cho AI Video, không phá project lẻ hiện có.
- Cho phép series lưu nhân vật, bối cảnh, style, continuity rules, negative rules và previous episode summary.
- Cho phép tạo episode project từ series và inject Series Bible vào planning context.
- Cập nhật UI recent projects để group theo series nhưng vẫn hỗ trợ project lẻ.
- Expose thao tác xoá project, xoá source block, xoá generated data giữ source/config/series.
- Chặn hoặc yêu cầu cancel khi xoá dữ liệu trong lúc auto-run/planning/voice/render active.
- Tăng độ chặt của Codex output mapping/validation và bảo vệ dữ liệu cũ khi validation fail.

**Non-Goals:**
- Không bắt buộc mọi project phải thuộc series.
- Không merge nhiều tập vào một project khổng lồ.
- Không thêm multi-user permission model.
- Không thêm external queue, Redis hoặc service ngoài.
- Không thay đổi nguyên tắc prompt pack full-call trong một project.
- Không tự động generate ảnh reference nhân vật trong change này; chỉ giữ prompt/bible/reference text và có thể mở rộng sau.

## Decisions

### 1. Series là parent optional, project vẫn là episode/work unit

Quyết định: thêm entity `video_series` và thêm `series_id` nullable trên `video_projects`. Project không có `series_id` là standalone project như hiện tại. Project có `series_id` là một episode trong series.

Mô hình khái niệm:

```text
video_series
  id
  title
  character_bible
  world_bible
  style_bible
  continuity_rules
  negative_rules
  previous_episode_summary
  latest_episode_number
  created_at / updated_at

video_projects
  id
  series_id nullable
  episode_number nullable
  episode_title nullable
  ...existing project fields...
```

Lý do: project hiện là boundary tốt cho auto-run, prompts, voice, package, render và debug. Series nên là context kế thừa chứ không thay thế project.

Phương án khác đã cân nhắc: nhét toàn bộ series vào một project với nhiều tập bên trong. Cách đó làm project quá nặng, khó xoá từng tập, khó retry, và khiến prompt context dễ vượt giới hạn.

### 2. Series Bible inject vào planning ở boundary context, không rewrite prompt generator từng nơi

Quyết định: thêm helper tạo `series_context` cho project có series và dùng nó trong `_project_context`/planning prompt boundary của phase2 story, shots và prompt pack. Project standalone trả context rỗng.

Context inject cần có cấu trúc rõ:

```text
Series context:
- Series title
- Episode number/title
- Character bible
- World bible
- Style bible
- Continuity rules
- Negative rules
- Previous episode summary
- Non-negotiables: same character, same world, same style unless user explicitly changes the series bible
```

Lý do: giữ thay đổi tập trung và không làm logic project lẻ bị rẽ nhánh nhiều nơi.

### 3. Recent projects UI dùng grouped view mềm

Quyết định: API list projects có thể tiếp tục trả list project phẳng, nhưng frontend group theo `series_id` nếu response có series metadata. Có thể thêm endpoint `GET /ai-video/series` hoặc enrich list projects bằng minimal series summary.

UI đề xuất:

```text
Dự án gần đây

▾ Series: Người Que Làm Giàu
  Tập 01 · prompts_ready      ⋯
  Tập 02 · shots_ready        ⋯
  + Tạo tập mới

Dự án lẻ
  The Stickman World Cup Miracle  ⋯
```

Lý do: người dùng vẫn thấy project gần đây quen thuộc, nhưng series dài tập không làm list bị lộn xộn.

### 4. Deletion có 3 mức rõ ràng

Quyết định: phân biệt rõ ba thao tác:

| Operation | Giữ lại | Xoá |
|---|---|---|
| Delete source block | Project/config/artifacts khác | Một source block |
| Reset generated data | Project/source blocks/series link/config | Story/shots/prompts/voice/subtitle/package/render/debug phù hợp |
| Delete project | Không giữ project | Project, child rows, artifacts |

Source block deletion sẽ mark stale khi project đã có generated data. Reset generated data không xoá Series Bible. Delete project thuộc series không xoá series trừ khi người dùng chọn thao tác xoá cả series.

Lý do: người dùng có nhu cầu dọn từng đoạn nhập và cũng có nhu cầu reset project nhưng không muốn nhập lại toàn bộ brief.

### 5. Chặn deletion khi job active

Quyết định: trước khi delete/reset, service kiểm tra active auto-run, planning pool/project active, voice jobs và render jobs. Nếu active, trả lỗi tiếng Việt yêu cầu cancel/chờ hoàn tất.

Lý do: tránh xoá DB/file khi background task đang ghi artifact, gây orphan rows hoặc file missing khó debug.

### 6. Strict Codex mapping là service boundary dùng chung

Quyết định: gom mapping/validation vào helper rõ ràng theo từng payload type, ví dụ:

```text
map_story_payload(raw) -> normalized dict
map_shot_breakdown_payload(raw, expected_scenes/config) -> normalized dict
map_prompt_pack_payload(raw, expected_shots/project/series) -> normalized dict
map_series_bible_payload(raw) -> normalized dict
```

Mỗi mapper thực hiện:
- whitelist alias keys;
- reject alias conflict;
- type summary;
- expected count/order/id checks;
- required fields checks;
- deterministic normalization only;
- validation error with machine-readable code.

Lý do: mapping rải rác trong từng generator làm khó kiểm soát và dễ tạo fallback quá rộng. User đã gặp sai dữ liệu nhiều lần nên boundary này phải fail-fast thay vì đoán bừa.

### 7. Ghi DB sau khi toàn bộ payload pass validation

Quyết định: validate toàn bộ normalized payload trước khi xoá/ghi rows và file mới. Với prompt pack, chỉ xoá prompt cũ sau khi pack mới pass count/order/required fields. Với shots, chỉ replace non-locked shots sau khi toàn bộ shot plan hợp lệ.

Lý do: tránh mất dữ liệu tốt khi Codex trả invalid. Đây quan trọng hơn việc cố salvage một phần output.

### 8. Observability bắt buộc cho mapping và deletion

Quyết định: thêm debug events cho deletion operation và mapping failure. Technical details chỉ lưu ids/counts/key names/type summary/preview ngắn, không lưu full source/prompt/narration.

Lý do: khi lỗi xảy ra, developer cần biết fail ở source block nào, expected/actual count ra sao, key nào thiếu, nhưng không nên lưu nội dung dài hoặc secret.

## Risks / Trade-offs

- [Risk] Series Bible quá dài làm prompt nặng hoặc vượt giới hạn → Mitigation: giới hạn length từng bible field, truncate previous episode summary trước, không truncate character/world/style cốt lõi nếu có thể.
- [Risk] User chỉnh Series Bible sau khi đã có nhiều tập làm tập cũ và tập mới lệch nhau → Mitigation: series bible update chỉ ảnh hưởng planning mới; UI ghi rõ tập cũ không tự regenerate.
- [Risk] Delete/reset làm mất dữ liệu ngoài ý muốn → Mitigation: confirm rõ theo operation, menu tách “xoá project” và “xoá dữ liệu đã tạo”, block khi job active.
- [Risk] Mapping quá strict khiến Codex output hợp lý nhưng không đúng key bị reject nhiều hơn → Mitigation: whitelist alias phổ biến, log received keys/type summary, retry existing Codex flow khi có thể.
- [Risk] Migration thêm nullable columns/table ảnh hưởng dữ liệu cũ → Mitigation: nullable `series_id`, project cũ mặc định standalone, không backfill bắt buộc.
- [Risk] Grouped UI phức tạp hơn sidebar hiện tại → Mitigation: giữ project lẻ render đơn giản; chỉ group khi có `series_id`.

## Migration Plan

1. Thêm migration idempotent cho `video_series` và nullable `series_id`, `episode_number`, `episode_title` trên `video_projects`.
2. Không backfill project cũ; tất cả project cũ là standalone.
3. Thêm backend models/responses cho series và enrich project response bằng optional series metadata.
4. Thêm service/API CRUD series, create episode, delete/reset operations.
5. Thêm mapper/validator boundary và chuyển story/shots/prompt pack/series bible qua boundary này trước khi ghi.
6. Cập nhật UI recent projects grouped view, project menu, confirm dialogs và source block delete controls.
7. Thêm tests trước khi bật UI flow hoàn chỉnh.

Rollback an toàn: nếu cần tắt series UI, project cũ vẫn chạy độc lập vì `series_id` nullable. Delete/reset APIs nên giữ riêng và có thể ẩn UI nếu cần.

## Open Questions

- Có cần cho phép “duplicate tập trước” để clone cấu hình/tone của tập gần nhất không, hay chỉ tạo tập mới từ Series Bible?
- Khi xoá series còn episodes, default nên là detach episodes hay chặn cho tới khi user xoá từng tập?
- Series summary nên được cập nhật thủ công sau review, hay có nút “cập nhật từ tập này” để tránh Codex tự ghi summary ngoài ý muốn?
