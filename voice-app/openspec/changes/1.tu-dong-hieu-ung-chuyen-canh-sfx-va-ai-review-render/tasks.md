## 1. Schema và Storage

- [x] 1.1 Rà `VideoRenderSettings`, `VideoRenderJob`, render manifest hiện có và chọn cách lưu enhanced render plan/report backward-compatible.
- [x] 1.2 Thêm field hoặc bảng phụ cho enhanced render settings, enhanced plan path, review report path, fix attempt count và final review status.
- [x] 1.3 Thêm storage subfolders cho enhanced plans, SFX/BGM assets, review reports và export artifacts tiếng Việt.
- [x] 1.4 Thêm migration idempotent để project/render job cũ vẫn mở và render cơ bản bình thường.
- [x] 1.5 Cập nhật Pydantic/TypeScript response models cho settings, plan summary, review report và artifact filenames.

## 2. Enhanced Render Plan

- [x] 2.1 Thêm Pydantic schema cho transition action, SFX action, BGM action, retention action, fallback và review-fix action.
- [x] 2.2 Tạo service build enhanced render plan từ timeline manifest, `retention_json`, `transition_json`, `sound_design_json` và quality check.
- [x] 2.3 Normalize alias SFX/transition phổ biến như `glass_break`, `broken_glass`, `whoosh`, `impact`, `riser`, `silence_drop`, `match_cut`, `whip_pan`, `glitch`.
- [x] 2.4 Validate plan: timing nằm trong timeline, overlap không âm, asset required có file nếu cue phải render thật, volume/fade trong ngưỡng an toàn.
- [ ] 2.5 Log lỗi tiếng Việt và debug details khi AI plan invalid; không commit plan bán hỏng.

## 3. SFX/BGM Asset Workflow

- [x] 3.1 Thêm model/API tối thiểu để upload hoặc chọn asset SFX/BGM cho project.
- [x] 3.2 Probe audio asset bằng FFprobe, giới hạn size/duration/format và trả lỗi tiếng Việt khi không hợp lệ.
- [x] 3.3 Map cue như tiếng kính vỡ sang asset thật; nếu thiếu asset thì tạo fallback rõ trong plan/report.
- [ ] 3.4 Đảm bảo asset không bị xóa nhầm khi render job cũ còn cần debug/report.
- [x] 3.5 Thêm tests cho upload/probe asset và missing-asset fallback.

## 4. FFmpeg Video Effects

- [x] 4.1 Thêm command builder cho transition graph khi timeline có overlap/effect.
- [ ] 4.2 Hỗ trợ ít nhất hard cut, crossfade, dip to black/white, flash, punch zoom nhẹ và glitch/whip fallback an toàn.
- [x] 4.3 Fallback về hard cut hoặc render cơ bản khi FFmpeg thiếu filter hoặc plan không thể render an toàn.
- [x] 4.4 Giữ duration cuối khớp timeline/voice/subtitle sau khi thêm transition overlap.
- [x] 4.5 Thêm unit tests cho command builder và duration math.

## 5. FFmpeg Audio Mix

- [x] 5.1 Thêm audio mix graph cho voice, SFX và BGM bằng delay/trim/fade/volume/amix.
- [x] 5.2 Implement ducking hoặc volume policy mặc định để voice rõ hơn SFX/BGM khi có narration.
- [x] 5.3 Hỗ trợ silence drop chỉ ở khoảng hợp lệ, không cắt mất voice.
- [ ] 5.4 Thêm loudness/volume warning cơ bản nếu audio mix có nguy cơ quá dày.
- [x] 5.5 Thêm tests cho SFX timing, glass break cue, fade, ducking và missing voice/silence shot.

## 6. AI Review và Auto-Fix

- [x] 6.1 Tạo review input từ enhanced plan, timeline manifest, FFprobe output, keyframe samples nếu có và render metadata.
- [x] 6.2 Thêm AI review schema trả `passed`, `findings`, `fixable_actions`, `requires_user_action`, `review_vi`.
- [ ] 6.3 Chỉ auto-fix các lỗi render-plan như timing, volume, fade, fallback effect; không tạo lại clip/voice/subtitle.
- [ ] 6.4 Giới hạn re-render 1-2 vòng theo settings và lưu report từng attempt.
- [x] 6.5 Nếu review cần user action, dừng và hiển thị báo cáo tiếng Việt thay vì lặp vô hạn.
- [ ] 6.6 Thêm tests cho review pass, fixable action, requires-user-action và retry limit.

## 7. Export File Tiếng Việt Có Số Thứ Tự

- [x] 7.1 Thêm export artifact `1. Kịch bản và nhịp giữ chân.md`.
- [x] 7.2 Thêm export artifact `2. Shot list và chuyển cảnh.csv`.
- [x] 7.3 Thêm export artifact `3. Prompt video và chỉ dẫn hiệu ứng.md`.
- [x] 7.4 Thêm export artifact `4. Âm thanh SFX và mixing notes.md`.
- [x] 7.5 Thêm export artifact `5. Báo cáo AI review sau render.md`.
- [x] 7.6 Thêm export artifact `6. Timeline manifest dựng MP4.json`.
- [x] 7.7 Đảm bảo helper sanitize filename vẫn giữ tiếng Việt khi có thể và an toàn trên Windows/macOS.
- [x] 7.8 Thêm tests cho filename bắt đầu bằng số thứ tự và nội dung tiếng Việt.

## 8. API và UI

- [x] 8.1 Mở rộng render readiness/job API để nhận enhanced render settings và trả review/enhanced status.
- [x] 8.2 Thêm API upload/list/delete SFX/BGM asset nếu chưa có.
- [x] 8.3 Cập nhật `apiClient` và TypeScript types.
- [x] 8.4 Cập nhật AI Video render panel bằng tiếng Việt: bật enhanced render, asset status, effect/SFX summary, review status và download report.
- [x] 8.5 UI phải giữ workflow gọn, không biến thành timeline editor kéo-thả.
- [x] 8.6 Hiển thị rõ khi SFX chỉ là fallback/metadata và chưa được mix thật.

## 9. Verification

- [x] 9.1 Chạy OpenSpec validation cho change.
- [x] 9.2 Chạy focused backend tests cho render timeline, command builders, SFX mix, review loop và export filenames.
- [x] 9.3 Chạy frontend typecheck/build phù hợp nếu UI/API types thay đổi.
- [ ] 9.4 Manual QA một project có transition + tiếng kính vỡ: render MP4, xem review report, xác nhận voice không bị che.
- [ ] 9.5 Manual QA fallback thiếu asset: app không nói sai rằng MP4 đã có SFX thật.

## 10. Documentation

- [ ] 10.1 Cập nhật docs AI Video giải thích enhanced render, transition effect, SFX/BGM asset và AI review.
- [ ] 10.2 Ghi rõ enhanced render có thể fallback về hard cut/render cơ bản nếu thiếu filter/asset.
- [ ] 10.3 Cập nhật changelog/release notes nếu repo yêu cầu.

