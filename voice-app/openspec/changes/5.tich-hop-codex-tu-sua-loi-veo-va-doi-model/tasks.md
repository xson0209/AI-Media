## 1. Khảo sát và thiết kế dữ liệu

- [x] 1.1 Audit schema hiện tại của `VideoSeries`, `VideoProject`, `VideoClipGenerationJob`, `VideoClipGenerationItem` và migration idempotent liên quan.
- [x] 1.2 Chọn cách lưu Flow project binding: bảng riêng hoặc field nullable trên project/series.
- [x] 1.3 Định nghĩa trạng thái binding: `active`, `needs_check`, `invalid`, `rotated`.
- [x] 1.4 Đảm bảo project/series cũ không có binding vẫn hoạt động và chỉ tạo binding khi chạy provider job.
- [x] 1.5 Định nghĩa response/API redaction để không leak URL provider vào debug/package.

## 2. Resolve và kiểm tra Flow project URL

- [x] 2.1 Implement resolver ưu tiên series binding cho project thuộc series và project binding cho project lẻ.
- [x] 2.2 Implement check mở Flow project URL cũ bằng Chrome profile riêng.
- [x] 2.3 Phân biệt link còn dùng được, cần login, Flow application error có thể phục hồi, và link thật sự invalid.
- [x] 2.4 Chỉ tạo Flow project mới khi chưa có binding hoặc binding đã invalid sau kiểm tra.
- [x] 2.5 Khi tạo Flow project mới, lưu binding đúng scope project/series và lưu hash audit.
- [x] 2.6 Cập nhật cleanup/delete để không export Chrome profile/cookie và xử lý binding theo policy xóa project/series.

## 3. Tạo clip trong cùng Flow project

- [x] 3.1 Sửa runner để truyền `provider_project_url` đã resolve vào adapter thay vì luôn truyền `None`.
- [x] 3.2 Thay logic tránh reuse project bằng baseline media count/media URL trước khi submit prompt.
- [x] 3.3 Map media mới sau prompt bằng URL/count/correlation và download folder riêng theo item.
- [x] 3.4 Dừng item với lỗi retryable nếu media mới mơ hồ thay vì import nhầm clip.
- [x] 3.5 Lưu provider metadata đã redaction gồm model label, provider project hash, media correlation và attempt.
- [x] 3.6 Đảm bảo series chỉ có một job Veo active dùng cùng Flow project tại một thời điểm.

## 4. Chính sách dùng đúng model đang chọn trong Flow

- [x] 4.1 Thêm cấu hình provider model policy `use_current_flow_selection`.
- [x] 4.2 Đảm bảo adapter không tự click đổi model trước khi submit prompt.
- [x] 4.3 Đọc và lưu model label/cost label đang được chọn nếu UI Flow cho phép đọc an toàn.
- [x] 4.4 Khi model đang chọn hết quota/credit/billing hoặc không khả dụng, pause job với lỗi tiếng Việt để người dùng tự đổi model trong Flow.
- [x] 4.5 Khi người dùng resume sau khi đổi model thủ công trong Flow, job dùng đúng model mới đang được chọn.
- [x] 4.6 Hiển thị model đã dùng trong UI và job report, không hiển thị như một fallback tự động.

## 5. Codex auto-repair có kiểm soát

- [x] 5.1 Định nghĩa error allowlist cho lỗi kỹ thuật app có thể auto-repair.
- [x] 5.2 Định nghĩa error denylist cho login, 2FA, CAPTCHA, quota thật, billing, payment và policy block.
- [x] 5.3 Thêm trạng thái job/item `paused_for_repair` hoặc tương đương để dừng runner trước khi sửa code.
- [x] 5.4 Lưu repair context đã redaction: job id, item id, error code, step, log, screenshot path nếu có.
- [ ] 5.5 Implement Codex repair runner với file allowlist, attempt limit và timeout. _(Partial: hiện đã có allowlist, attempt limit, context và opt-in gate; chưa có runner tự patch code thật.)_
- [ ] 5.6 Chạy test/lint/smoke test bắt buộc sau patch.
- [ ] 5.7 Nếu test pass, restart/reload backend nếu cần và resume job từ item lỗi.
- [ ] 5.8 Nếu test fail, rollback hoặc giữ patch để review theo policy và job vẫn paused.
- [x] 5.9 Yêu cầu người dùng duyệt trước khi repair cần dependency mới, migration, xóa dữ liệu hoặc đổi policy cost.

## 6. UI tiếng Việt

- [x] 6.1 Hiển thị Flow project binding đang dùng: project lẻ hay series, trạng thái active/needs login/invalid.
- [x] 6.2 Hiển thị model Flow đang được chọn hoặc model đã dùng gần nhất trong panel Veo/Chrome.
- [x] 6.3 Hiển thị model thực tế đã dùng cho từng job/item.
- [x] 6.4 Hiển thị trạng thái Codex đang sửa lỗi, sửa thành công, sửa thất bại hoặc cần người dùng duyệt.
- [x] 6.5 Cung cấp action mở đúng Chrome profile và đúng Flow project URL khi cần người dùng xử lý.

## 7. Kiểm thử

- [x] 7.1 Test project lẻ tạo binding mới rồi reuse cùng URL cho nhiều shot.
- [x] 7.2 Test series reuse cùng URL cho nhiều episode và chặn job song song cùng series.
- [x] 7.3 Test link Flow cần login không tạo project mới.
- [x] 7.4 Test link Flow invalid mới tạo binding mới và đánh dấu binding cũ invalid/rotated.
- [x] 7.5 Test adapter không tự đổi model trước khi submit prompt.
- [ ] 7.6 Test job lưu model label đang được chọn khi đọc được từ UI Flow.
- [x] 7.7 Test khi model đang chọn hết quota/credit thì job pause và không tự chọn model khác.
- [x] 7.8 Test download/media correlation không import nhầm clip khi có nhiều media trong cùng Flow project.
- [x] 7.9 Test Codex auto-repair chỉ chạy với lỗi allowlist và không chạy với lỗi denylist.
- [ ] 7.10 Test repair pass thì resume job, repair fail thì giữ job paused và không mất clip đã import.

## 8. Tài liệu và vận hành

- [x] 8.1 Viết hướng dẫn tiếng Việt về luật một video một Flow project và một series một Flow project.
- [x] 8.2 Viết hướng dẫn tiếng Việt rằng app dùng đúng model đang được chọn trong Flow và người dùng tự đổi model nếu cần.
- [x] 8.3 Viết hướng dẫn tiếng Việt về giới hạn Codex auto-repair.
- [x] 8.4 Cập nhật troubleshooting cho login/2FA/CAPTCHA/quota/billing/policy block.
