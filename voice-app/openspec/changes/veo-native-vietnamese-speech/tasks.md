## 1. Contract và migration

- [x] 1.1 Thêm helper resolve speech source theo target language.
- [x] 1.2 Thêm `speech_cues_json` vào VideoShot model/migration và API schemas.
- [x] 1.3 Thêm normalization/fallback cho speech cues từ narration/dialogue mode/visible characters.
- [x] 1.4 Đảm bảo thay speech cues làm stale prompt, clip, subtitle, render và package phù hợp.

## 2. Character voice và prompt generation

- [x] 2.1 Đưa `speech_style`, personality và voice context vào episode cast prompt text.
- [x] 2.2 Yêu cầu shot planner tạo speech cues có speaker/exact text/context.
- [x] 2.3 Tạo helper build Veo-native speech section từ shot, profiles, guests và scene context.
- [x] 2.4 Giữ nguyên visual prompt hiện tại và nối native speech section sau provider compaction.
- [x] 2.5 Giữ hành vi cấm spoken audio cho project không phải tiếng Việt.

## 3. Clip, subtitle và render

- [x] 3.1 Readiness tiếng Việt yêu cầu clip có audio thay vì TTS.
- [x] 3.2 Duration resolver tiếng Việt dùng clip duration cho shot có lời.
- [x] 3.3 Subtitle tiếng Việt dùng speech cue text/narration và clip duration.
- [x] 3.4 Audio segment builder extract audio từ clip Veo cho tiếng Việt, TTS cho ngôn ngữ khác.
- [x] 3.5 Final render không chồng Veo audio và TTS.
- [x] 3.6 Package readiness/manifest nhận biết Veo-native speech.

## 4. Auto-run và UI

- [x] 4.1 Auto-run tiếng Việt bỏ qua generate/wait voice nhưng vẫn tạo clip, subtitle và render.
- [x] 4.2 UI project/voice panel giải thích tiếng Việt dùng audio Veo 3 và không yêu cầu voice profile.
- [x] 4.3 UI shot hiển thị speech cues, speaker, voice description và context để review.
- [x] 4.4 Cập nhật API client/types và các label summary liên quan.

## 5. Verification

- [x] 5.1 Thêm migration/model/API tests cho speech cues.
- [x] 5.2 Thêm provider prompt tests cho tiếng Việt và regression tiếng Anh.
- [x] 5.3 Thêm readiness/render command tests cho Veo audio và TTS regression.
- [x] 5.4 Thêm subtitle/auto-run/package tests cho tiếng Việt không có voice profile.
- [x] 5.5 Chạy focused backend tests.
- [x] 5.6 Chạy frontend typecheck/lint/build.
- [x] 5.7 Chạy OpenSpec validation và cập nhật toàn bộ checklist.

Ghi chú xác minh: lint các file frontend thay đổi đã pass; lint toàn bộ `app/src` vẫn có lỗi accessibility/hook tồn tại sẵn ở `ComicSeriesAnalysis.tsx` và `SeriesDialogs.tsx`, ngoài phạm vi change này.
