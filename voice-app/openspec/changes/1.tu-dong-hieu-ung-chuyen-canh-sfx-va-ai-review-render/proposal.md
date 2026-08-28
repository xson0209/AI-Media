## Why

AI Video phase 2 đã có retention map, transition pack, sound design plan và render MP4 từ clip + voice + phụ đề. Tuy nhiên render hiện tại mới dùng các chỉ dẫn đó như metadata trong manifest; MP4 cuối chưa tự tạo hiệu ứng chuyển cảnh thật, chưa mix SFX/BGM thật như tiếng kính vỡ, whoosh, impact, silence drop, và chưa có bước AI phân tích lại bản render để sửa nhịp trước khi trả kết quả.

Người dùng cần một bước dựng thông minh hơn: AI dùng creative direction đã có để biến transition/sound cue thành hành động render thật, sau đó tự kiểm tra chất lượng giữ chân người xem và sửa lại trong giới hạn an toàn trước khi hoàn tất.

## What Changes

- Thêm render plan có cấu trúc để chuyển `transition_pack`, `retention_json`, `sound_design_json` và `retainability_quality_check` thành hiệu ứng dựng thật trên timeline.
- Hỗ trợ các hiệu ứng chuyển cảnh có thể render bằng FFmpeg như hard cut có chủ đích, match cut, crossfade, dip to black/white, whip-like blur, glitch flash, punch zoom và speed ramp nhẹ khi phù hợp.
- Thêm SFX/BGM asset workflow tối thiểu: thư viện preset local và/hoặc upload asset audio theo cue, mapping alias như `glass_break`, `whoosh`, `impact`, `riser`, `silence_drop`.
- Mix voice, SFX và BGM bằng FFmpeg với volume, fade, delay theo timeline và ducking/mixing notes để voice không bị che.
- Thêm AI render review sau khi có output: phân tích manifest, render plan, keyframe/metadata/audio summary và phát hiện hook yếu, đoạn quá tĩnh, transition lệch nhịp, SFX quá to/thiếu cue hoặc continuity risk.
- Cho phép auto-fix và re-render giới hạn 1-2 vòng khi lỗi có thể sửa bằng timing/volume/effect settings mà không cần tạo lại clip hoặc voice.
- Xuất các file báo cáo tiếng Việt bắt đầu bằng số thứ tự, ví dụ `1. Kịch bản và nhịp giữ chân.md`, `2. Shot list và chuyển cảnh.csv`, `3. Prompt video và chỉ dẫn hiệu ứng.md`, `4. Âm thanh SFX và mixing notes.md`, `5. Báo cáo AI review sau render.md`, `6. Timeline manifest dựng MP4.json`.

## Capabilities

### New Capabilities

- `ai-video-render-hieu-ung-giu-chan`: Render hiệu ứng chuyển cảnh, SFX/BGM thật và AI review/re-render cho AI Video phase 2 nhằm cải thiện nhịp dựng và khả năng giữ chân người xem.

### Modified Capabilities

- None.

## Impact

- Backend render pipeline trong `backend/services/video_rendering.py`: thêm render plan, command builders cho transition/effect/audio mix, review loop và artifact output.
- AI planning/validation trong `backend/services/video_phase2.py` hoặc service mới để tạo/normalize/validate render enhancement plan từ metadata creative direction đã có.
- Database/API models cho render job cần lưu enhanced render settings, review report, fix attempts, asset references và output file/report paths.
- Storage/package export cần thêm artifact tiếng Việt có tên bắt đầu bằng `1.`, `2.`, ... và giữ filename an toàn cho Windows/macOS.
- Frontend AI Video Assistant cần UI tiếng Việt để bật/tắt enhanced render, xem SFX/transition mapping, xem AI review report và tải output.
- Tests backend cho command builders, SFX timing/mix, ducking, review retry limit, stale behavior, package/export filenames và fallback khi thiếu asset.

## Out of Scope

- Không tích hợp provider video mới trong change này.
- Không tạo timeline editor kéo-thả nhiều track.
- Không tự sinh asset âm thanh bằng dịch vụ bên ngoài nếu người dùng chưa cấu hình rõ.
- Không thay thế workflow render MP4 cơ bản; enhanced render là lớp bổ sung có thể tắt.
- Không tạo lại clip video hoặc voice trong auto-fix; chỉ sửa render plan, transition parameters, SFX timing, volume/fade/ducking và re-render.
