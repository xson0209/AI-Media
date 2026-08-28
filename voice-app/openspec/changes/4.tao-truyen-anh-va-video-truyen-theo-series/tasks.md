## 1. Data Model Và Migration

- [x] 1.1 Thêm `series_mode` vào `VideoSeries` với các giá trị `image_story_only`, `video_story_only` và `hybrid`.
- [x] 1.2 Migration idempotent gán series hiện có và request cũ không gửi mode thành `video_story_only`.
- [x] 1.3 Thêm model `SeriesCharacterProfile` liên kết `series_id`, gồm name, role, face, hair, body, signature outfit, personality, speech style, fixed traits, notes và sort order.
- [x] 1.4 Giữ nguyên `VideoSeries.character_bible` cho tương thích; xác định profile có cấu trúc là nguồn ưu tiên và character bible cũ là fallback/ghi chú bổ sung.
- [x] 1.5 Thiết kế model `StoryEpisode` liên kết `series_id`, episode number/title, output intent, market/language profile, master story và approval state.
- [x] 1.6 Thiết kế model `StoryScenarioCandidate` gồm strategy type, script JSON, score JSON, strengths, risks và selected flag.
- [x] 1.7 Thiết kế model `StoryAdaptation` với kind `image_story` hoặc `video_story`, status, payload JSON và optional `linked_video_project_id`.
- [x] 1.8 Thiết kế schema panel ảnh với `prompt_status` và `render_status` tách biệt.
- [x] 1.9 Bổ sung count phù hợp cho series truyện/hybrid, tối thiểu phân biệt `story_episode_count` và `video_episode_count` mà không phá `episode_count` cũ.
- [x] 1.10 Đảm bảo episode number của Story Episode và AI Video project liên kết không bị lệch trong series hybrid.
- [x] 1.11 Nâng `series-memory.md` thành projection v2 được dựng từ database, gồm series mode, character profiles, Story Episodes đã duyệt và Video Projects.
- [x] 1.12 Chỉ cho một service chịu trách nhiệm dựng memory file; Story Studio và AI Video không append trực tiếp.
- [x] 1.13 Đảm bảo project lẻ, series video cũ và dữ liệu `character_bible` cũ vẫn hoạt động.

## 2. API Series Và Hồ Sơ Nhân Vật

- [x] 2.1 Cập nhật create series để nhận `series_mode` và cập nhật get/update/list responses để trả mode hiện tại.
- [x] 2.2 Validate `series_mode`, giữ default tương thích cho client cũ và chưa cho đổi mode sau khi tạo cho tới khi người dùng chốt policy.
- [x] 2.3 Thêm API list/create/update/delete/reorder `SeriesCharacterProfile` theo series.
- [x] 2.4 Validate name bắt buộc và giới hạn an toàn cho các trường mô tả nhân vật.
- [x] 2.5 Trả `character_profiles` trong response quản lý series, không dùng alias `characters` đang có ý nghĩa khác trong mapper cũ.
- [x] 2.6 Thêm action đề xuất chuyển `character_bible` cũ thành các profile nháp mà không ghi đè dữ liệu cũ.
- [x] 2.7 Chỉ lưu profile do AI đề xuất sau khi người dùng duyệt.
- [x] 2.8 Chặn Story Studio hoặc AI Video tạo output không được `series_mode` hỗ trợ.
- [x] 2.9 Đảm bảo thay đổi ghi chú riêng của một tập không tự sửa Hồ sơ nhân vật cấp series.

## 3. Backend API Story Studio

- [x] 3.1 Thêm endpoint list/get/create/update Story Episode theo series phù hợp với Story Studio.
- [x] 3.2 Thêm endpoint upload hoặc nhập nguồn nội dung mới cho Story Episode.
- [x] 3.3 Thêm endpoint chọn `output_intent` và kiểm tra intent phù hợp với `series_mode`.
- [x] 3.4 Thêm endpoint tạo đúng 3 scenario candidates từ Series Memory, character profiles, source input, intent, market và language.
- [x] 3.5 Thêm endpoint chấm điểm candidates theo rubric intent.
- [x] 3.6 Thêm endpoint chọn hoặc tổng hợp bản thắng thành Master Story Episode.
- [x] 3.7 Thêm endpoint approve/reject Master Story Episode.
- [x] 3.8 Khi Master Story thay đổi sau approval, huỷ approval về trạng thái chờ duyệt và đánh dấu adaptations liên quan là stale.
- [x] 3.9 Thêm endpoint đề xuất continuity/character updates và endpoint duyệt trước khi cập nhật series.
- [x] 3.10 Không cho series `video_story_only` xuất hiện như series tạo truyện trong Story Studio.

## 4. AI Planning Và Continuity

- [x] 4.1 Tạo creative brief/schema Story Studio đọc Series Bible, character profiles và `series-memory.md`.
- [x] 4.2 Khi character profiles có dữ liệu, dùng chúng làm nguồn nhân vật ưu tiên; chỉ fallback về `character_bible` khi cần.
- [x] 4.3 Cập nhật planning context AI Video để series video/hybrid cũng đọc cùng character profiles.
- [x] 4.4 Tạo đúng 3 candidates mặc định: hook/retention mạnh, cảm xúc/drama mạnh và visual/action mạnh.
- [x] 4.5 Thay đổi trọng số candidate theo `output_intent`.
- [x] 4.6 Tạo scoring rubric riêng cho `truyen_anh`, `video_truyen` và `ca_hai`.
- [x] 4.7 Tạo bước synthesis thành Master Story nhất quán với fixed traits và continuity.
- [x] 4.8 Validate AI output trước khi lưu; nếu thiếu trường bắt buộc thì giữ dữ liệu cũ và trả lỗi tiếng Việt.
- [x] 4.9 AI MUST NOT tự thay đổi fixed traits hoặc lưu profile/continuity update chưa được người dùng duyệt.
- [x] 4.10 Log request_id, step_name, series mode, intent, candidate count và lỗi đã redaction.
- [x] 4.11 Cập nhật validation AI Video để character profiles hợp lệ có thể thay cho chuỗi `character_bible` bắt buộc, đồng thời không sync `VideoProject.character_bible` ngược để ghi đè profile cấp series.

## 5. Image Story Adaptation Và Render Ảnh

- [x] 5.1 Tạo endpoint sinh Image Story Adaptation từ Master Story đã duyệt.
- [x] 5.2 Chia Master Story thành panel theo thứ tự, mỗi panel có mục đích, caption/lời thoại và mô tả hình ảnh.
- [x] 5.3 Tạo prompt ảnh, negative prompt, style notes và character consistency notes cho từng panel.
- [x] 5.4 Đưa face, hair, body, signature outfit và fixed traits phù hợp vào prompt nhân vật.
- [x] 5.5 Thêm endpoint duyệt/reject prompt từng panel, action duyệt toàn bộ prompt hợp lệ và reset approval khi nội dung prompt đã duyệt bị sửa.
- [x] 5.6 Chặn image provider nếu prompt chưa ở trạng thái approved.
- [x] 5.7 Khi chưa có provider/API key, giữ prompt đã duyệt ở `waiting_provider` và vẫn cho lưu/export prompt.
- [x] 5.8 Khi provider được cấu hình, không tự render; yêu cầu người dùng bấm action render.
- [x] 5.9 Thêm render request/job chỉ nhận các panel đã duyệt và cập nhật queued/rendering/completed/failed.
- [x] 5.10 Không báo ảnh thành công khi mới chỉ có prompt hoặc render request.
- [x] 5.11 Lưu ảnh render và metadata provider theo adapter đã cấu hình; không bắt buộc provider cụ thể trong contract Story Studio.

## 6. Video Story Handoff Và MP4

- [x] 6.1 Tạo endpoint sinh Video Story Adaptation từ Master Story đã duyệt.
- [x] 6.2 Tạo hoặc mở AI Video project cùng `series_id`, episode metadata và source blocks từ Master Story.
- [x] 6.3 Đưa character profiles, hook, full story, key beats, visual/motion moments, retention, sound notes, must-have và avoid vào handoff.
- [x] 6.4 Lưu `story_episode_id` và `linked_video_project_id` để quay lại đúng hai phía.
- [x] 6.5 Giữ đúng episode number khi handoff trong series hybrid.
- [x] 6.6 Không duplicate shot breakdown, prompt video, voice, subtitle, Veo/Chrome hoặc render logic trong Story Studio.
- [x] 6.7 Hiển thị trạng thái AI Video project liên kết và liên kết tới MP4 khi render job hiện có hoàn tất.
- [x] 6.8 Đảm bảo series `video_story_only` tiếp tục tạo episode trực tiếp trong AI Video và dùng character profiles chung.

## 7. Frontend Series Và Story Studio

- [x] 7.1 Thêm route `/story-studio` và giữ `/stories` hiện tại cho story/TTS cũ.
- [x] 7.2 Khi tạo series, hiển thị ba lựa chọn tiếng Việt: Series truyện ảnh, Series video, Series truyện + video.
- [x] 7.3 Filter series và hành động theo `series_mode` trong Story Studio và AI Video.
- [x] 7.4 Thêm màn quản lý Hồ sơ nhân vật dùng chung từ khu vực series.
- [x] 7.5 Form nhân vật có tên/vai trò, khuôn mặt, tóc, vóc dáng, trang phục đặc trưng, tính cách, cách nói chuyện, điều không được thay đổi và ghi chú.
- [x] 7.6 Hiển thị đề xuất chuyển Character Bible cũ hoặc cập nhật profile để người dùng duyệt/reject.
- [x] 7.7 UI Story Studio cho nhập nguồn, chọn intent hợp lệ và tạo candidates.
- [x] 7.8 UI hiển thị đúng 3 candidates, điểm, lý do chọn, điểm mạnh, rủi ro và nút duyệt.
- [x] 7.9 UI hiển thị trạng thái duyệt của Master Story và cảnh báo các adaptations đang stale.
- [x] 7.10 UI panel ảnh tách rõ prompt nháp, chờ duyệt, đã duyệt, chờ provider, đang render, hoàn tất, stale và lỗi.
- [x] 7.11 UI không tự bắt đầu render sau khi người dùng thêm API key/provider.
- [x] 7.12 UI Video Story đưa người dùng tới đúng AI Video project và cho mở/tải MP4 khi hoàn tất.
- [x] 7.13 UI dùng tiếng Việt tự nhiên và không dùng raw status làm nội dung chính.

## 8. Tests Và Verification

- [x] 8.1 Test migration series cũ mặc định `video_story_only` và project cũ không bị ảnh hưởng.
- [x] 8.2 Test tạo series ở cả ba mode.
- [x] 8.3 Test Story Studio chỉ nhận series `image_story_only` hoặc `hybrid`.
- [x] 8.4 Test AI Video chỉ tạo episode trực tiếp trong series `video_story_only`; video của series `hybrid` phải đi qua handoff từ Story Studio.
- [x] 8.5 Test intent bị chặn khi không phù hợp với series mode.
- [x] 8.6 Test CRUD và reorder character profiles.
- [x] 8.7 Test Story Studio và AI Video nhận cùng một character profile.
- [x] 8.8 Test fixed traits xuất hiện trong planning/prompt và AI suggestion không tự ghi đè profile.
- [x] 8.9 Test `character_bible` cũ vẫn là fallback khi chưa có profiles.
- [x] 8.10 Test memory v2 chứa character profiles, Story Episodes và Video Projects mà không mất dữ liệu sau sync lại.
- [x] 8.11 Test Story Studio tạo đúng 3 candidates và scoring thay đổi theo intent.
- [x] 8.12 Test chưa duyệt Master Story thì không tạo adaptation.
- [x] 8.13 Test prompt chưa duyệt thì không thể render.
- [x] 8.14 Test thiếu provider vẫn lưu/export prompt và dùng trạng thái `waiting_provider`.
- [x] 8.15 Test cấu hình provider không tự render; chỉ action người dùng mới tạo render request.
- [x] 8.16 Test render ảnh thành công/thất bại cập nhật đúng trạng thái, không báo thành công giả.
- [x] 8.17 Test video handoff giữ `series_id`, episode number, character profiles và liên kết project.
- [x] 8.18 Test Story Studio không duplicate video renderer và hiển thị MP4 từ render job hiện có.
- [x] 8.19 Test sửa Master Story huỷ approval và làm adaptations stale.
- [x] 8.20 Test sửa prompt đã duyệt đưa prompt về chờ duyệt và chặn render.
- [x] 8.21 Chạy backend tests liên quan và frontend typecheck sau implementation.
- [x] 8.22 Chạy `openspec validate 4.tao-truyen-anh-va-video-truyen-theo-series --strict`.
