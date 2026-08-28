## Context

Các change trước đã hoàn tất nền quan trọng:

- `nang-cap-ai-video-retention-sound-transition` thêm retention map, transition pack, sound design plan và quality gate ở cấp project/shot/prompt.
- `render-ai-video-timeline` thêm upload clip theo shot và render MP4 bằng FFmpeg từ clip đã normalize, voice audio và phụ đề.
- Render manifest hiện đã có `retention`, `transition`, `sound_design` và `retainability_quality_check` theo shot, nhưng render readiness vẫn cảnh báo SFX/BGM chỉ là chỉ dẫn dựng nếu chưa có asset thật.

Điểm thiếu là một lớp biến metadata đó thành hành động render thật và kiểm tra lại chất lượng sau khi render.

## Goals / Non-Goals

**Goals:**

- Tạo enhanced render plan có cấu trúc từ transition/retention/sound metadata hiện có.
- Render hiệu ứng chuyển cảnh thật giữa các clip khi có thể làm bằng FFmpeg an toàn.
- Mix SFX/BGM thật theo timeline, ví dụ tiếng kính vỡ, whoosh, impact, riser, silence drop.
- Đảm bảo voice luôn rõ hơn SFX/BGM bằng mixing notes, ducking và giới hạn volume.
- Tạo AI review report tiếng Việt sau render và auto-fix/re-render giới hạn khi lỗi có thể sửa bằng render settings.
- Xuất file artifact tiếng Việt theo thứ tự `1. ...`, `2. ...`, ... để người dùng dễ đọc và chuyển sang tool dựng ngoài app.

**Non-Goals:**

- Không làm editor timeline kéo-thả nhiều track.
- Không tự tạo video clip mới, không gọi provider video mới.
- Không tự tạo voice/subtitle mới trong auto-fix.
- Không bắt buộc mọi project phải dùng enhanced render; render cơ bản vẫn hoạt động.
- Không đảm bảo mọi transition phức tạp đều render được nếu FFmpeg/runtime thiếu filter; hệ thống phải fallback có cảnh báo.

## Decisions

### 1. Thêm enhanced render plan thay vì chỉnh trực tiếp manifest cũ

Render manifest hiện là snapshot timeline. Change này thêm artifact mới, ví dụ `enhanced-render-plan.json`, chứa:

- `timeline`: danh sách shot và duration.
- `transition_actions`: transition type chuẩn hóa, start/end overlap, FFmpeg filter hoặc fallback.
- `sfx_actions`: asset id/path, cue type, start time, duration, volume, fade in/out, ducking target.
- `bgm_action`: asset id/path, loop/trim/fade, target loudness nếu có.
- `retention_actions`: hook, pattern interrupt, static span mitigation, payoff emphasis.
- `fallbacks`: lý do effect bị hạ cấp, ví dụ thiếu asset hoặc filter không khả dụng.

Manifest cũ vẫn giữ vai trò debug/readiness; plan mới là nguồn sự thật cho render nâng cao.

### 2. AI chỉ tạo plan có schema, backend mới quyết định FFmpeg command

AI được dùng để chọn loại effect, timing và lý do giữ chân người xem. Backend không chạy prose tự do; mọi output phải qua Pydantic/normalizer và enum/fallback rõ ràng.

Backend command builder chịu trách nhiệm map plan sang FFmpeg:

- Video transition: `xfade`, fade, flash, zoom/crop, frame blend hoặc fallback hard cut.
- Audio mix: `adelay`, `atrim`, `afade`, `volume`, `amix`, optional `sidechaincompress` nếu runtime hỗ trợ.
- Clip normalize vẫn dùng pipeline hiện có, nhưng concat có thể đổi từ concat demuxer sang filter graph khi cần overlap transition.

### 3. Transition effect phải bảo toàn continuity

`transition_pack.continuity_risk` là đầu vào bắt buộc. Nếu risk cao hoặc shot có continuity nhạy cảm, plan phải ưu tiên hard cut/match cut nhẹ thay vì glitch/flash mạnh. Nếu effect có thể làm mất nội dung quan trọng ở đầu/cuối clip, backend phải giảm overlap hoặc fallback.

### 4. SFX/BGM là asset thật hoặc fallback rõ ràng

SFX cue chỉ được coi là đã render thật khi có file audio hợp lệ. Asset source có thể là:

- Preset local đi kèm app nếu có license rõ.
- Upload audio asset của người dùng.
- Asset đã có trong project storage.

Nếu cue như `glass_break` không có asset, render không được báo sai rằng MP4 đã có tiếng kính vỡ. Plan/report phải ghi fallback, ví dụ "thiếu asset glass_break nên chỉ giữ silence drop/impact nhẹ nếu có".

### 5. Voice ducking là mặc định khi có narration

Khi shot có narration, SFX/BGM mặc định phải thấp hơn voice. Plan phải có volume/fade ngắn và ducking notes. Backend nên bắt đầu với rule an toàn:

- SFX ngắn dưới voice, không chồng lên từ khóa quan trọng nếu cue không phải transition impact.
- BGM thấp hơn voice và fade vào/ra ở đầu/cuối video.
- Silence drop không được cắt mất voice; chỉ dùng ở khoảng không lời hoặc trước/giữa transition hợp lệ.

### 6. AI review sau render là vòng kiểm tra có giới hạn

Sau render nâng cao, backend tạo review input gồm:

- enhanced render plan.
- timeline manifest.
- render-cache summary.
- output metadata từ FFprobe.
- keyframe thumbnails hoặc frame sample nếu khả dụng.
- audio summary cơ bản, ví dụ duration, stream count, loudness estimate nếu implement được.

AI review trả JSON có:

- `passed`.
- `findings`.
- `fixable_actions`.
- `requires_user_action`.
- `review_vi`.

Nếu `fixable_actions` chỉ liên quan timing/volume/effect fallback, hệ thống có thể auto-fix và re-render tối đa 1-2 lần theo setting. Nếu cần clip/voice mới, hệ thống dừng và báo người dùng.

### 7. File export tiếng Việt theo thứ tự là contract user-facing

Các artifact đọc được bởi người dùng phải dùng tên tiếng Việt có số thứ tự ở đầu để sắp xếp ổn định:

1. `1. Kịch bản và nhịp giữ chân.md`
2. `2. Shot list và chuyển cảnh.csv`
3. `3. Prompt video và chỉ dẫn hiệu ứng.md`
4. `4. Âm thanh SFX và mixing notes.md`
5. `5. Báo cáo AI review sau render.md`
6. `6. Timeline manifest dựng MP4.json`

Tên file phải được sanitize bằng helper hiện có để chạy được trên Windows/macOS nhưng vẫn giữ tiếng Việt khi có thể.

## Risks / Trade-offs

- FFmpeg filter graph phức tạp dễ lỗi theo runtime -> tách command builder, test filter generation và fallback về render cơ bản/hard cut.
- SFX quá to hoặc lệch voice -> mặc định ducking/volume thấp, review report bắt audio clutter risk.
- Asset licensing không rõ -> chỉ dùng preset có nguồn hợp lệ hoặc upload của người dùng; không tự tải asset internet.
- AI review có thể nhận xét sai nếu chỉ có metadata -> review phải nói rõ nguồn đã phân tích; không được khẳng định đã nghe/xem chi tiết nếu chỉ dùng metadata.
- Re-render nhiều vòng tốn thời gian -> giới hạn vòng fix, lưu report từng attempt và cho phép tắt enhanced review.
- UI có thể quá rối -> hiển thị chế độ đơn giản trước: bật/tắt enhanced render, danh sách cue/effect, warning, report; không làm timeline editor.

## Migration Plan

1. Thêm nullable fields hoặc bảng phụ cho enhanced render plan/report trên render job.
2. Thêm subfolder artifact cho enhanced render plans, SFX assets và review reports.
3. Mở rộng render settings với enhanced render, SFX/BGM enabled, AI review enabled và max fix attempts.
4. Implement plan generation/normalization/validation, không ghi plan nếu invalid.
5. Implement FFmpeg command builders cho transition/video effects và audio mix.
6. Implement review report và auto-fix loop giới hạn.
7. Cập nhật UI tiếng Việt và export artifacts theo tên file có số thứ tự.
8. Rollback an toàn: tắt enhanced render, giữ render cơ bản hiện có, dữ liệu mới là nullable/artifact riêng.

## Open Questions

- Có nên bundle sẵn một bộ SFX nhỏ có license rõ trong repo/app hay chỉ cho upload asset trước?
- Có cần BGM ngay trong phase đầu hay chỉ SFX transition trước?
- AI review nên bắt buộc trước download hay chỉ là bước tùy chọn với warning nếu chưa chạy?
- Nên giới hạn transition overlap mặc định bao nhiêu, ví dụ 0.25-0.6 giây, để tránh ăn mất nội dung clip AI?
