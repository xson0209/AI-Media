## Bối cảnh đo được (28-08-2026)

Thiết kế này dựa trên số đo thật, không phải suy đoán. Nguồn: `data/voicebox.db`.

```
30 project Cartoon International, target_language=en, dialogue_mode=character_lines
420 prompt đã lưu, tất cả prompt_status=completed / status=ready

  396/420  prompt có tín hiệu thoại
   24/420  prompt THIẾU thoại       ← 24/24 đều có speech_cues trong DB
    7/24   đã render thành clip
   17/24   còn ở tầng prompt
```

Ba kết luận khóa thiết kế:

1. **Non-determinism là gốc.** Không code nào quyết định thoại vào prompt; LLM tự quyết giữa hai instruction mâu thuẫn (`video_phase2.py:2688` yêu cầu viết thoại vs `:3795` nói voice tạo ở bước sau).
2. **Không thể phát hiện bằng probe.** 7 clip lỗi đo `mean -20.5…-23.2 dB`; đối chứng `-19.5…-22.4 dB` — trùng hoàn toàn. `has_audio=1` cho cả 126 clip. Chỉ thiếu lời, mà mức âm tổng không thấy. Nên gate **phải** ở tầng prompt, không ở tầng clip.
3. **Prompt lưu KHÔNG cấm speech.** Chuỗi trong prompt lưu là `video_phase2.py:1500` (chỉ cấm chữ trên hình). Chuỗi có `spoken audio` là `video_clip_generation.py:129-133`, chỉ nối lúc submit và không lưu. Việc 16 shot chứa `spoken audio` là câu ràng buộc ngôn ngữ hợp lệ ("Keep all viewer-facing spoken audio in natural English only"), không phải lệnh cấm.

## 1. Bốn giai đoạn và lý do thứ tự

```
A. GATE      chặn phát hành prompt thiếu thoại       → cứu 17 shot còn lại
B. BUILDER   audio contract do code sinh             → fix gốc non-determinism
C. DROPDOWN  override nguồn lời, tách khỏi ngôn ngữ  → sửa nghịch lý regex EN
D. NEWS      route /news-video parity đầy đủ         → trên nền đã vững
```

A trước vì thiệt hại đang tiếp diễn và nó rẻ nhất. D cuối vì nó là consumer của A–C, không phải nơi sửa bug.

## 2. Gate thoại (A)

`_quality_check()` (`video_phase2.py:3553-3577`) hiện không kiểm speech. Thêm điều kiện: shot có `speech_cues_json` không rỗng hoặc `english_narration` không rỗng, mà provider content không chứa thoại tương ứng → `needs_review`, chặn Copy/Download, nêu shot và lý do bằng tiếng Việt.

Gate là lưới an toàn, không phải fix. Sau khi B xong thì gate gần như không bao giờ trigger, nhưng vẫn giữ để bắt trường hợp cue bị sửa sau khi prompt đã sinh.

## 3. Builder dùng chung (B)

**Quyết định: compose lúc đọc, KHÔNG lưu provider prompt.**

```
video_shot_prompts.prompt          ← CHỈ visual (planner bị cấm viết thoại)
video_shots.speech_cues_json       ← nguồn sự thật của lời
        ↓
build_provider_prompt(visual, speech_mode, cues, negative, continuity)
        ↓
   ├─ Copy 1 shot        ├─ Download / prompt pack
   ├─ Provider automation └─ /news-video
```

Lý do không lưu cột `provider_ready_prompt`: mỗi lần sửa cue hoặc đổi `speech_mode` sẽ sinh composite cũ phải đi invalidate — chính là nguồn của toàn bộ logic stale. Compose lúc đọc thì vấn đề không tồn tại. Bỏ được một cột, một migration và phần lớn §8.

Builder trả:

```text
provider_prompt   chuỗi copy trực tiếp
negative_prompt   trường riêng
audio_contract    cấu trúc đã resolve
input_fingerprint để phát hiện stale
```

**Sửa instruction planner:** bỏ mâu thuẫn `:2688` vs `:3795`. Nói rõ field `prompt` chỉ mô tả hình ảnh, không viết lời thoại; thoại nằm ở `speech_cues`.

**Xoá regex viết lại prose:** `FLOW_PROVIDER_POST_RENDER_CUE_REPLACEMENTS[2]` (`video_clip_generation.py:138-140`) và `_strip_provider_spoken_audio_blockers` (`:262-272`). Cái thứ hai đã là no-op — hai regex của nó không match chuỗi `:1500` lẫn prompt thật. Cái thứ nhất là thứ đang xoá câu voiceover của project EN, tạo prompt tự mâu thuẫn (nó chỉ ăn tới dấu chấm đầu, nên `"Pogo says, I have a plan!"` vẫn sống sót cạnh lệnh cấm `spoken audio`).

## 4. Năm mode nguồn lời (C)

`uses_veo_native_speech()` (`video_speech.py:34-39`) hiện là switch hardcode theo ngôn ngữ. Toàn hệ thống đã gọi nó nhất quán ở 15 chỗ và mỗi chỗ đã xử lý đúng hai nhánh — nên đổi **một hàm** là đủ, không phải wire 15 chỗ:

| Chỗ gọi | Veo tự đọc | Voice project |
|---|---|---|
| `video_voice.py:551` | chặn TTS | tạo TTS |
| `video_clip_generation.py:979` | nối speech section | không nối |
| `video_auto_runs.py:1095` | bỏ bước voice | chạy bước voice |
| `video_rendering.py:877` | timing theo clip | timing theo `audio_duration` |
| `video_rendering.py:3145` | bed `SKIP_NATIVE_SPEECH` | bed ducked |
| `video_subtitles.py:218,328` | subtitle theo clip | subtitle theo TTS |
| `video_packages.py:223,595` | check clip audio | check narration |
| `video_phase2.py:3279` | dặn planner viết thoại | cue chỉ là metadata |

**Cảnh báo:** `video_packages.py:284,328,411` gọi `speech_source_for_language` **trực tiếp**, không qua `uses_veo_native_speech`. Phải sửa cả ba, nếu không manifest ghi nguồn lời sai — loại lỗi âm thầm không ai thấy tới lúc render xong.

### Ma trận và derive

| `speech_mode` | Lời trong prompt | → `dialogue_mode` | → `clip_audio_mode` | canonical |
|---|---|---|---|---|
| `veo_narration` | instruction, off-screen | `voiceover` | `clip_only` | `veo_native` |
| `veo_dialogue` | instruction, visible, lip-sync | `character_lines` | `clip_only` | `veo_native` |
| `voicebox_co_context` | context-only (cấm đọc) | giữ hiện có | `drop` | `project_audio` |
| `voicebox_khong_context` | absent | `voiceover` | `drop` | `project_audio` |
| `none` | absent | giữ hiện có | `drop` | `project_audio` |

`speech_mode` là **input duy nhất**; hai field kia dẫn xuất. Nhờ vậy double voice (Voicebox + prompt yêu cầu Veo đọc) và Veo-đọc-mà-prompt-không-có-lời trở thành **không biểu diễn được**, khỏi cần test.

Điều này cũng giữ nguyên non-goal của change `ngay-23-08-am-thanh-3-muc`: ta **suy ra** mức âm, không **đổi default** toàn cục.

Phân biệt hai mode Voicebox là khác biệt thật: `co_context` cho shot presenter đang giải thích (muốn Veo biết nội dung để tay/miệng/nhịp khớp); `khong_context` cho b-roll (nói nội dung cho Veo là rủi ro — nó có thể tự thêm người đang nói).

`voicebox_co_context` là mode dễ vỡ nhất: đưa lời rồi bảo đừng đọc thì Veo vẫn có thể đọc. Bắt buộc mute clip mặc định + probe `has_audio` cảnh báo.

### Resolver

Thứ tự: shot override → project override → `speech_source_for_language()` (legacy). Response trả cả `speech_mode` và `effective_speech_source`. Project không có override thì mọi hành vi cũ giữ nguyên, nên test `test_veo_native_vietnamese_speech.py:122-126` vẫn pass.

Không để `target_language == "vi"` tự ép native khi project đã có override tường minh.

## 5. Parity với `/ai-video` (D)

`/news-video` **dùng lại đúng máy móc của `/ai-video`**, không phát minh stepper riêng.

Auto-run dùng nguyên `STEP_ORDER` (`video_auto_runs.py:73-91`):

```
validate → develop_story → waiting_planning → review_character_proposals
→ review_story → generate_shots → generate_prompts → generate_publishing_metadata
→ review_prompts → generate_clips → waiting_clips → generate_voice → waiting_voice
→ generate_subtitle → generate_render → waiting_render → completed
```

Dùng nguyên `material_target` (`video_auto_runs.py:59-62`): `full_materials`, `prompts_only`, `publishing_kit`, `video_clips`, cùng các tập `*_SKIPPED_STEPS` (`:112-115`).

UI parity gồm **dựng MP4 tại chỗ**: tái dùng `AIVideoRenderPanel.tsx`, `AIVideoPublishingMetadataPanel.tsx` và luồng upload clip. Route đăng ký như các route hiện có (`router.tsx:200-204`, component import trực tiếp — **không** lazy, khớp pattern thật của repo) và thêm `/news-video` vào `isWideWorkspace` (`router.tsx:83-89`).

Khác `/ai-video` đúng ba chỗ: nhập tin tức thay nhập truyện, dropdown năm mode nguồn lời, và editorial gate.

### Luồng bảy bước

```
① NGUỒN TIN          dán URL (ghi chú) + nội dung bài/transcript/ý tưởng
       ↓
② SINH PROMPT        AI sinh visual prompt theo shot; audio contract do code ghép
       ↓
③ COPY               người dùng tự dán lên Veo 3, tự render
       ↓
④ UPLOAD             tự tải MP4 về, upload vào shot đã chọn explicit
       ↓
⑤ ÂM THANH           theo mode: nghe duyệt native / tạo TTS Voicebox / bỏ qua
       ↓
⑥ DỰNG MP4           AIVideoRenderPanel: xoá logo, subtitle, ghép audio, encode
       ↓
⑦ TẢI VỀ             MP4 hoàn chỉnh
```

Bước ⑥ **không viết mới**. `AIVideoRenderPanel.tsx` đã có toggle xoá watermark (`:536`), chọn backend (`:542`), trạng thái worker và cảnh báo model chưa cache (`:587`). Tái dùng panel là có nguyên cụm.

**Lưu ý hiệu năng:** theo số đo trước đó, xoá watermark là nút thắt của quá trình dựng — chậm hơn encode. Lần đầu còn phải tải model. UI phải nói rõ để người dùng không tưởng là treo.

Bước ① chỉ **lưu** URL làm ghi chú nguồn. Hệ thống không fetch. Người dùng phải dán nội dung bài. Đây là ranh giới MVP quan trọng: crawler tự đọc URL thuộc phase 2.

## 6. Dữ liệu và migration

```text
video_projects.speech_source            nullable   NULL = hành vi cũ
video_shots.speech_source_override      nullable   NULL = theo project
news_video_workflows                    1 dòng/project, FK video_projects.id
  visual_format, source_note, default_speech_source
```

Tái dùng `video_projects`, `video_shots`, `video_shot_prompts`, `video_shot_clips`. Không tạo `NewsProject`, kho clip hay FFmpeg pipeline song song.

**Không** thêm `video_shot_prompts.provider_ready_prompt` (xem §3). **Không** thêm `workflow_kind` — bảng `news_video_workflows` là discriminator duy nhất; có row nghĩa là News project.

Migration là SQLite hand-rolled idempotent, không Alembic (`backend/database/migrations.py:1-19`). Cột mới thêm vào dict `project_column_defaults` (~`:1104`) và `shot_column_defaults` (`:1140`). Double-run an toàn; row legacy `NULL` đi fallback cũ.

Lưu ý: `video_projects` có **cả** `language` và `target_language`. News project set `target_language="vi"` và phải set `language` tường minh, không để trống.

## 7. Cấu hình News Video

```text
target_language = "vi"
aspect_ratio    = "9:16"
prompt_segment_duration_seconds = 8        # cho phép 4/6/8/10
visual_format   = tech_explainer | newsroom_presenter | cinematic_broll
                  | data_motion_graphics | hyperframes_hybrid
default_speech_source = một trong năm mode  # mặc định voicebox_khong_context
```

`visual_format` là preset mô tả đặc tính hình ảnh, không phải tên để sao chép phong cách độc quyền.

**Chưa kiểm:** hiện chưa rõ có gì validate range của `prompt_segment_duration_seconds`. Word-budget (2,5–3,0 từ/giây, buffer 15% → ~20-24 từ ở 8 giây) chưa đối chiếu timing TTS tiếng Việt thật. Cần spike trước khi khóa câu lỗi yêu cầu người dùng chia shot.

## 8. Speech cue

Model hiện tại là Pydantic `VideoShotSpeechCue` (`backend/models.py:469-485`), lưu ở JSON column `video_shots.speech_cues_json`, không có bảng riêng. Field hiện có: `text`, `speaker_role`, `speaker_name`, `voice_description`, `delivery`, `emotion`, `start_seconds`, `end_seconds`, `lip_sync_required`, `character_profile_id`, `context`.

`pronunciation_notes` **chưa tồn tại** — phải thêm mới.

`speaker_role` hiện chỉ nhận bốn giá trị (`models.py:474-477`): `visible_character`, `offscreen_narrator`, `episode_guest`, `unknown`. Alias API `visible_presenter`/`character` phải normalize về `visible_character`; `text_vi` normalize về `text`.

Canonical speech source hiện chỉ có hai hằng (`video_speech.py:17-18`): `veo_native`, `project_audio`. **Không có `none`** — `none` là mode News, map về `project_audio` + không tạo TTS.

## 9. Stale và rollback

Dùng fingerprint hiện hành và trạng thái `draft`, `review_required`, `ready`, `stale`, `blocked`. Đổi source/narration/visual/negative làm stale prompt và clip compatibility; đổi `speech_mode` làm stale voice, subtitle và render. `video_phase2.py:3517` đã có logic stale theo field ảnh hưởng prompt — `speech_source` phải vào danh sách đó.

Rollback bằng feature flag/ẩn route và ngừng action mới; không xóa clip, credential, Chrome profile hay project cũ.

## 10. Phạm vi dữ liệu cũ

**Quyết định: không migrate.** Change này chỉ đảm bảo prompt sinh ra **từ nay** là đúng.

Hệ quả phải chấp nhận, ghi ra để không ai bất ngờ:

- 24 shot thiếu thoại trong 30 project cartoon **vẫn thiếu**; 7 clip đã mất lời **vẫn mất**.
- Muốn dùng lại project cũ nào thì sinh lại prompt cho project đó thủ công.
- **Không** thêm cột phân loại prompt (`visual_only` hoặc tương đương). Phương án đó chỉ cần khi muốn prompt cũ và mới sống chung — ở đây không cần.
- Không regenerate hàng loạt, không strip thoại legacy bằng regex.

Đánh đổi: đơn giản hơn nhiều (bỏ một cột, một migration, logic đọc cờ ở ba consumer, và test hai loại prompt sống chung), nhưng prompt cũ không được cứu.

## 11. Rủi ro

- **Ba chỗ `speech_source_for_language` trực tiếp** (`video_packages.py:284,328,411`) nếu bỏ sót sẽ ghi manifest sai âm thầm.
- **Xoá watermark là nút thắt hiệu năng** ở bước dựng MP4, chậm hơn encode, lần đầu phải tải model. Cần trạng thái tiến trình rõ ràng, không để người dùng tưởng treo.
- **URL không tự đọc.** Nếu UI không nói rõ, người dùng dán link rồi tưởng hệ thống đã đọc bài → narration rỗng hoặc AI tự bịa. Phải có helper text tường minh.
- **Mode `hon_hop` phase 2 phụ thuộc code chưa chạy thật.** Đường `CLIP_AUDIO_MODE_BED` (`video_rendering.py:2429`) chưa từng execute trên render thật dù test pass: `mute_clip_audio` default `True` (`:2993-2995`), panel không persist, auto-run dựng `VideoRenderSettings()` mặc định. Thêm nữa `clip_audio_bed_decision` (`:3016-3018`) có guard chặn đúng ca này để tránh comb-filter. Phải chứng minh đường bed sống trước khi hứa mode 6.
- **`voicebox_co_context` có thể bị Veo đọc.** Mute mặc định + cảnh báo probe.
- **Regex cũ xoá voiceover.** Sau khi bỏ `:138-140`, cần regression test provider automation cho cả EN và VI.
