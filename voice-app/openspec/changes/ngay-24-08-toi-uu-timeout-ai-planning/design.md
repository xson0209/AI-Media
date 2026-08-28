# Design

## Context

Mọi prompt tới Codex CLI đi qua đúng một cửa: `ai_planning.run_codex_exec` (`backend/services/ai_planning.py:739`), prompt qua stdin, schema qua `--output-schema` tempfile. Trần 600s là cứng ở 4 tầng độc lập nên hướng duy nhất là làm request nhỏ lại.

Thứ tự 3 pha là cố ý: pha 1 rẻ, không đổi kiến trúc, và **đo được ngay** — nó cho ta số liệu để biết pha 2 có cần thiết tới mức nào. Pha 3 sửa một lỗ hổng đã tồn tại chứ không phải lỗ hổng mới sinh ra.

### Số đo thật từ một lần timeout (2026-08-24)

Một lần chạy thất bại đã cung cấp số liệu, và nó phủ định hai giả định của bản design đầu tiên.

```
step             = generate_video_prompt_pack  (VIDEO_PROMPT_PACK_SCHEMA, caller duy nhất :3847)
                   → bước này ĐÃ xé lô ở VIDEO_PROMPT_BATCH_SIZE = 5
prompt_chars     =  78,063          input
stderr_chars     = 202,193          output đã stream, ~337 char/s
output_file_exists = False          last-message.txt chưa từng được ghi
stderr_tail      = "Segment 21 là khung kết..." + JSON đầy đủ
elapsed_ms       = 600,496          bị taskkill
effective_reasoning_effort = ultra
fallback_used    = False            ← đây mới là lần thử 1
```

**Kết luận 1: xé lô ở 5 là không đủ.** Bước timeout này đã được xé lô sẵn. Batch size 5 không còn là câu hỏi mở, nó là một giá trị đã được chứng minh quá to.

**Kết luận 2: chết ở decode, không ở prefill.** Model sinh 202KB và đã tới segment cuối trước khi bị kill. 600s bị đốt vào việc sinh chữ. Điều này xác nhận việc giảm *lượng output mỗi lần gọi* mới là đòn chính, giảm input chỉ là phụ.

Phân rã 78KB cho một lô 5 shot, đo từ DB (project 21 segment):

| Thành phần | Chars | |
|---|---|---|
| `micro_scenes_json` | ~22,400 | **4,480/shot** — to nhất |
| `sound_design_json` | ~2,930 | |
| `retention_json` | ~2,880 | |
| `speech_cues_json` | ~1,790 | |
| **dữ liệu theo shot** | **~30,000** | 38% |
| continuity bible | ~4,290 | |
| template tĩnh | ~4,100 | |
| `_project_context` + instructions | ~40,000 | 62%, **gửi lại mỗi lô** |

Phần cố định ~48KB trả lại nguyên vẹn cho mọi lô. Nên batch size nhỏ hơn không miễn phí: overhead cố định trên mỗi shot tăng lên. Có điểm tối ưu, không phải càng nhỏ càng tốt.

## Goals / Non-Goals

**Goals**

- Cắt thời gian chờ tệ nhất của một lời gọi logic từ 4×600s xuống 1×600s khi nguyên nhân là timeout.
- Cho từng bước tự chọn reasoning effort, thay vì `ultra` cho tất cả.
- Có số liệu định lượng (`prompt_chars`, `output_chars`, `elapsed_ms`) để so sánh trước/sau.
- Xé `generate_shots` theo lô, **kèm** commit từng lô và resume.
- Cắm dây resume cho `generate_video_prompt_pack` — chỗ đang có nguy cơ mất nửa công việc.

**Non-Goals**

- Nâng trần 600s.
- Chuyển API sang job + polling.
- Nâng concurrency của planning pool (đang chốt cứng ở 3).
- Chặn cap input cho `video_planning.py:286` và tỉa `*_history` tại `video_inspiration.py:2080`.

## Decisions

### D1. Loại timeout khỏi thang fallback

`_looks_like_model_config_failure` (`ai_planning.py:337-339`) mở đầu bằng:

```python
if error_code == "CODEX_EXEC_TIMEOUT":
    return True
```

Đây là lý do một prompt quá to bị chạy lại nguyên vẹn dưới profile khác. Bỏ nhánh này.

```
TRƯỚC                                    SAU
─────                                    ───
timeout 600s  (profile preferred)        timeout 600s  (profile preferred)
    ↓ coi là lỗi config model                ↓
timeout 600s  (profile fallback)         raise CODEX_EXEC_TIMEOUT
    ↓ [+ inline schema ×2]
tổng 1200-2400s → 502                    tổng 600s → 502 kèm gợi ý giảm khối lượng
```

**Đánh đổi:** một lỗi config model biểu hiện *dưới dạng* timeout sẽ mất đường fallback. Chấp nhận được, vì lỗi config thật luôn kèm text nhận diện được qua `_MODEL_CONFIG_FALLBACK_MARKERS` và các status code trong danh sách, cả hai đều còn nguyên. Không có bằng chứng nào trong code cho thấy config sai gây timeout thay vì lỗi tức thì.

Ranh giới cần giữ: nhánh HTTP status và nhánh transient marker **không** đụng tới. Chỉ bỏ đúng ba dòng của `error_code`.

### D2. Reasoning effort theo bước là MỨC TRẦN, không phải mức ưu tiên

Bản design đầu tiên đặt step effort **dưới** settings trong thứ tự ưu tiên. Số đo thật cho thấy như vậy là tự vô hiệu hoá chính tính năng này: DB thực tế có `model_reasoning_effort = 'xhigh'` được đặt tường minh, nên `settings_effort or ...` (`ai_planning.py:259`) luôn thắng, và bước cơ học vẫn chạy `xhigh`. Cần gạt bị khoá ngay tại chỗ.

Ngữ nghĩa đúng: **step khai báo mức trần**, người dùng khai báo mức mong muốn, lấy giá trị thấp hơn.

```
Thang bậc:  low < medium < high < xhigh < max < ultra

effective_effort = min( effort_người_dùng_chọn , trần_của_bước )

Ví dụ người dùng chọn xhigh:
  shot_breakdown          (không trần)  → xhigh    giữ chất lượng sáng tạo
  video_prompt_generation (trần medium) → medium   hạ được như mong muốn
  publishing_metadata     (trần medium) → medium

Người dùng chọn low:
  shot_breakdown          → low        tôn trọng lựa chọn hạ của người dùng
  video_prompt_generation → low        min(low, medium) = low
```

Lý do chọn `min` chứ không phải "step thắng": effort toàn cục thể hiện *thanh chất lượng* của người dùng cho việc sáng tạo, không phải lệnh đốt reasoning tối đa cho việc dịch shot đã có thành prompt. Đồng thời `min` bảo toàn được ý muốn hạ effort của người dùng — nếu họ chọn `low` thì không bước nào được tự nâng lên.

Trần đề xuất, dựa trên bản chất từng bước:

| Bước | Trần | Lý do |
|---|---|---|
| `video_prompt_generation` (prompt pack theo lô) | `medium` | dịch shot đã có thành prompt, cơ học. Đây là bước đang timeout |
| `publishing_metadata` | `medium` | sinh title/description theo khuôn |
| `shot_breakdown` | không trần | quyết định nhịp và continuity |
| `story_development`, story synthesis | không trần | sáng tạo, chất lượng nhạy cảm với effort |

Cần một thứ tự bậc tường minh (`CODEX_REASONING_EFFORTS` tại `:28` là `set`, không có thứ tự). Giá trị không hợp lệ vẫn bị bỏ qua im lặng qua `_normalize_reasoning_effort` (`:247`); trần không hợp lệ ⇒ coi như không có trần, không được làm lệnh Codex thất bại.

### D3. Không dùng `locked` làm mốc tiến độ

`generate_shots` xóa mọi shot chưa khóa khi vào lại (`video_phase2.py:3201-3203`). Nếu suy tiến độ từ `locked`, resume sẽ phải khóa hộ shot do máy sinh, làm ô nhiễm một cột thuộc về hành vi người dùng — và người dùng sẽ thấy shot tự khóa mà họ không bấm.

Chọn: thêm một cột JSON trên `video_projects` lưu tiến độ lô. Theo tiền lệ `step_state_json` của comic analysis, và migration theo khuôn `_add_column` (`database/migrations.py:62`, danh sách cột `video_projects` tại `:1130`).

```
shot_batch_state_json = {
  "run_key":         "<fingerprint input>",   # đổi input ⇒ tiến độ cũ vô hiệu
  "target_count":    40,
  "locked_count":    0,
  "batch_size":      5,
  "completed":       [1, 2, 3],               # batch_index đã ghi bền
  "batch_keys":      {"1": "<uuid5>", ...},   # idempotency key đã hoàn tất
  "updated_at":      "..."
}
```

`run_key` là chốt an toàn quan trọng nhất: nó ngăn việc trộn kết quả của hai lần chạy khác input. Tính từ những gì thực sự chi phối output — script/scene đã duyệt, `target_duration_seconds`, `prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt`, `dialogue_mode`, `target_language`, style/character bible, `locked_count`.

Luồng vào lại:

```
generate_shots()
   │
   ├─ đọc shot_batch_state_json
   │
   ├─ run_key khớp VÀ completed không rỗng?
   │     ├─ CÓ  → giữ shot của các lô trong completed,
   │     │        xóa shot chưa khóa NGOÀI phạm vi đó,
   │     │        chỉ chạy các lô còn thiếu
   │     └─ KHÔNG → hành vi hiện tại: xóa hết shot chưa khóa,
   │                xóa state, chạy từ lô 1
   │
   └─ mỗi lô: gọi Codex → validate → db.add → db.commit
              → cập nhật completed + batch_keys → db.commit
```

Điểm dễ sai: bước "xóa shot chưa khóa" hiện là vô điều kiện. Nó phải trở thành có điều kiện, nếu không resume sẽ tự xóa đúng thứ nó vừa lưu.

### D3b. Giảm batch size và cắt output dư — đòn trực tiếp vào bước đang timeout

Số đo cho thấy `generate_video_prompt_pack` timeout dù đã xé lô ở 5. Hai cần gạt độc lập:

**Giảm batch size.** 5 → 2 hoặc 3 cho prompt pack. Nhưng phần cố định ~48KB trả lại mỗi lô, nên lô nhỏ hơn làm tổng prefill tăng:

```
21 shot, phần cố định 48KB/lô:
  batch 5 →  5 lô → 240KB overhead, ~30KB shot-data/lô, ~40KB output/lô  ← đang timeout
  batch 3 →  7 lô → 336KB overhead, ~18KB shot-data/lô, ~24KB output/lô
  batch 2 → 11 lô → 528KB overhead, ~12KB shot-data/lô, ~16KB output/lô
```

Overhead tăng là prefill (nhanh), output giảm là decode (chậm). Đánh đổi có lợi, nhưng không vô hạn — dưới 2 thì overhead cố định áp đảo. Để batch size thành hằng riêng cấu hình được, không dùng chung với shot breakdown.

**Cắt input dư mà không mất thông tin.** `micro_scenes_json` là 4,480 char/shot, phần lớn nhất của dữ liệu theo shot, và nó được `generate_shots` sinh ra rồi `generate_video_prompt_pack` gửi lại nguyên JSON thô (`_video_prompt_shot_lines:3703`). Cân nhắc gửi dạng gọn thay vì `json.dumps` đầy đủ. Đây là việc giảm prefill nên hiệu quả thấp hơn hai cần gạt trên — làm sau, và chỉ khi số đo cho thấy cần.

### D4. Xé `generate_shots` bằng hạ tầng đã có, không viết mới

Ba mảnh cần thiết đều đã tồn tại:

- `_prompt_pack_batches` (`:3669`) — cắt list giữ nguyên thứ tự, nhận `batch_size` tham số.
- `_validate_shot_order_output` (`:945`) — đã nhận `expected_count` và `first_shot_order`, và đã chấp nhận cả dải cục bộ `1..N` (`:961-963`). Dùng được cho từng lô **không cần sửa**.
- `_run_structured_codex` (`:2733`) — đã nhận `max_attempts` và `technical_context`.

Khuôn prompt theo lô: dùng lại đúng thủ pháp placeholder của `generate_video_prompt_pack` (`:3835-3838`) — dựng prompt một lần với token, rồi `.replace()` cho từng lô. Rẻ và đã được chứng minh trong repo.

`segment_instruction` (`:3208-3215`) hiện nói "Tạo đúng {segments_to_generate} prompt segment mới". Theo lô, câu này thành số của lô, kèm dải order tuyệt đối trên tổng số segment toàn video để model không mất định vị.

Retry mỗi lô: theo `VIDEO_PROMPT_BATCH_MAX_ATTEMPTS = 2` (`:51`) với `max_attempts=1` ở lời gọi trong (`:3849`), giống prompt pack. Kết hợp D1, một lô timeout tốn 600s và dừng, không nhân lên.

### D5. Continuity carry-over — cái giá của việc xé lô

Một lời gọi duy nhất đang cho sự mạch lạc toàn cục miễn phí. Xé lô làm mất tính chất đó, và đây là rủi ro chất lượng thật của change này, không phải chi tiết phụ.

Mỗi lô N>1 nhận một khối carry-over gọn từ shot cuối của lô N-1, đọc **từ DB** (đã commit) chứ không từ biến trong RAM — như vậy resume sau khi tiến trình chết vẫn có carry-over đúng:

- `transition_to_next` của shot cuối
- character appearance / wardrobe, setting và lighting của shot cuối
- `shot_order` cuối và dải order lô này phải sinh, trên tổng `target_segment_count`

Continuity bible và style bible truyền cho **mọi** lô, không chỉ lô đầu.

**Rủi ro còn lại:** không giải quyết được vấn đề nhịp toàn cục (arc của video). Một lời gọi thấy toàn cảnh mà lô thì không. Giảm thiểu bằng cách vẫn đưa toàn bộ `scene_lines` vào mọi lô — scene là dàn ý cấp trên của shot, và đây là dữ liệu input nên chỉ tốn prefill (nhanh), không tốn decode.

### D6. Vì sao commit từng lô là bắt buộc chứ không phải tùy chọn

Đây là lý do pha 2 và pha 3 không được tách rời khỏi việc xé lô.

```
Job 10 lô, mỗi lô fail độc lập 5%:
  P(mất toàn bộ, không resume) = 1 - 0.95^10 ≈ 40%
  P(fail one-shot)             ≈ 5-15%
⇒ xé lô mà không resume làm TỆ HƠN
Có resume: mỗi lần chạy lại chỉ tốn phần còn thiếu ⇒ hội tụ
```

`generate_video_prompt_pack` đang chính xác ở trạng thái xấu này: đã xé lô (`:3812`) nhưng tích lũy trong RAM (`:3809-3810`) và `db.commit()` một lần ở `:4140`.

Còn `_prompt_pack_batch_idempotency_key` (`:3679`) đã tính uuid5 ổn định từ `shot.id:revision:shot_order` — đúng thứ cần cho resume — nhưng chỉ được truyền vào log (`:3821`). Chỉ cần lưu và tra, không cần thiết kế lại.

### D7. Không che output bị cắt

`_safe_json_output` (`ai_planning.py:1228`) biến output không parse được thành `{"text": raw}`. Với batching, output bị cắt là dạng lỗi phổ biến nhất, và nó phải nhìn thấy được.

Điều kiện tách theo việc **có truyền schema hay không**, vì `research.py:1455/:2314` gọi không schema và chờ text thuần:

```
có output_schema  → không parse được ⇒ raise, kèm output_chars
không có schema   → giữ nguyên {"text": raw}
```

## Risks / Trade-offs

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Xé lô làm mất mạch truyện | **cao** — rủi ro chính | D5 carry-over đọc từ DB; giữ `scene_lines` đầy đủ ở mọi lô; so sánh chất lượng thủ công trên một project thật trước khi mở rộng |
| Tổng thời gian *tăng* vì lô chạy tuần tự | trung bình | Đánh đổi có ý thức: đổi latency lấy tỉ lệ thành công. Không nâng concurrency (chốt cứng ở 3). Đây là lý do đo trước ở pha 1 |
| Resume giữ lại shot cũ khi lẽ ra phải tạo lại | trung bình | `run_key` fingerprint; khác input ⇒ hủy state, chạy từ đầu |
| Hạ effort làm giảm chất lượng bước cơ học | thấp-trung bình | Chỉ hạ prompt pack + publishing metadata; settings của người dùng vẫn thắng; có thể lùi bằng cách sửa một hằng |
| Bỏ fallback cho timeout che mất một lỗi config thật | thấp | Nhánh status code và marker text còn nguyên |
| Migration cột mới trên `video_projects` | thấp | `_add_column` idempotent (`migrations.py:62`); cột nullable, project cũ đọc ra `None` = chưa có tiến độ |
| Người dùng vẫn thấy UI treo | tồn đọng, **không** giải quyết ở change này | Vẫn đồng bộ trong một POST; xé lô làm mỗi lô ngắn hơn nhưng không có progress channel. Ghi nhận là việc tiếp theo |

## Migration Plan

Ba pha triển khai và kiểm chứng độc lập. Pha 1 đứng một mình được và nên deploy trước để lấy số liệu.

```
Pha 1  D1 + D2 + metrics + D7 + sửa thông báo lỗi
       không schema DB, không đổi hành vi thành công
       ⇒ đo elapsed_ms / prompt_chars / output_chars theo step_name
       ⇒ quyết định pha 2 dựa trên số liệu thật, không dựa trên suy đoán
              │
Pha 2  migration cột + xé lô generate_shots + commit từng lô + resume
       shot ≤ 1 lô ⇒ đúng 1 lời gọi, tương đương hành vi cũ
              │
Pha 3  commit từng lô + tra idempotency cho generate_video_prompt_pack
       dùng lại persistence của pha 2
```

Rollback: pha 1 lùi bằng revert thuần. Pha 2/3 lùi được mà giữ cột — cột nullable, bỏ qua thì trở lại hành vi one-shot.

## Open Questions

- **Đã trả lời:** batch size cho prompt pack. 5 là quá to, đo được. Chuyển thành D3b.
- Batch size mới cho prompt pack nên là 2 hay 3? Cần đo `elapsed_ms` ở cả hai trên project 21 segment. Bắt đầu từ 3, hạ xuống 2 nếu vẫn tiến gần trần.
- Kích thước lô cho `generate_shots` chưa có số đo. Shot breakdown nặng hơn prompt pack mỗi phần tử (22 field, lồng sâu 4), nên có thể phải nhỏ hơn cả prompt pack. Đo ở pha 1 trước khi chốt; dùng hằng riêng.
- Có nên bỏ trạng thái tiến độ dở sau một thời gian (ví dụ 24 giờ) để tránh resume vào một lần chạy đã quá cũ?
- `output_file_exists = False` khi timeout nghĩa là output đã stream ra stderr nhưng chưa flush vào `last-message.txt`. Có thể thu hồi output dở từ stderr để cứu một phần công việc thay vì bỏ hết? Đáng khảo sát nhưng rủi ro cao (output cắt giữa JSON), không đưa vào change này.
- Sau pha 1, bước nào còn tiến gần trần 600s? Nếu `story_studio.synthesize_master_story` (ngân sách chỉ **300s**, không phải 600) vẫn timeout thì nó cần một change riêng, vì đơn vị xé ở đó là act/beat chứ không phải segment.
