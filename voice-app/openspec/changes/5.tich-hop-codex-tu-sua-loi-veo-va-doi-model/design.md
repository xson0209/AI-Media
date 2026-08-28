## Bối cảnh hiện tại

AI Video đã có các phần chính:

- `VideoSeries` và `VideoProject` đã hỗ trợ `series_id`, episode metadata và Series Bible.
- `VideoProviderSession` lưu Chrome profile riêng cho Flow/Veo, không lưu credential/cookie vào database.
- `VideoClipGenerationJob` và `VideoClipGenerationItem` đã có trạng thái job/item, retry/resume/cancel, credit policy và metadata provider.
- Adapter `video_veo_chrome.submit_prompt_and_download` đã nhận `provider_project_url` và có thể mở Flow project cũ hoặc tạo project mới.
- Job runner hiện lưu Flow project URL tạm trong `step_results_json`, nhưng chưa có binding cấp project/series.
- Trong runner hiện có đoạn cố tình không reuse Flow project cho mỗi item để tránh media cũ lẫn vào shot mới. Yêu cầu mới ưu tiên consistency, nên phải thay bằng cơ chế map clip an toàn trong cùng project.

## Mục tiêu

- Một video lẻ dùng một Flow/Veo project URL xuyên suốt.
- Một series dùng một Flow/Veo project URL chung cho mọi episode.
- Chỉ tạo Flow project mới khi chưa có binding hoặc binding đã xác minh không còn tồn tại/không thể phục hồi.
- Dùng đúng model đang được chọn trong Flow UI của tài khoản hiện tại.
- Khi model đang chọn hết quota/credit hoặc bị giới hạn, pause job để người dùng tự đổi model trong Flow rồi resume.
- Cho phép Codex sửa lỗi kỹ thuật app theo vòng pause -> patch -> test -> resume.
- Không tự xử lý các rào chắn tài khoản/provider.

## Quyết định thiết kế

### 1. Lưu Flow project binding cấp project và series

Thêm binding provider với các trường tối thiểu:

```text
scope: project | series
scope_id: video_project.id hoặc video_series.id
provider: veo
provider_tool: flow
provider_project_url
provider_project_ref_hash
status: active | needs_check | invalid | rotated
last_checked_at
last_success_at
failure_reason
created_at
updated_at
```

Nếu muốn giảm migration, có thể thêm field trực tiếp vào `video_projects` và `video_series`. Tuy nhiên binding riêng dễ mở rộng hơn cho provider/model khác và dễ lưu lịch sử rotate. Implementation nên chọn cách ít rủi ro nhất sau khi audit migration hiện có.

URL thật chỉ dùng nội bộ để automation mở Flow. API/debug/package phải redaction hoặc chỉ trả hash, trừ UI vận hành nội bộ cần hiển thị link mở project cho người dùng.

### 2. Resolve URL theo scope

Khi bắt đầu job tạo clip:

```text
nếu project thuộc series:
    dùng binding active của series
    nếu chưa có -> tạo Flow project mới và lưu vào series binding
nếu project lẻ:
    dùng binding active của project
    nếu chưa có -> tạo Flow project mới và lưu vào project binding
```

Không được lấy URL từ job gần nhất làm nguồn sự thật chính nữa. `step_results_json` chỉ còn là event/audit phụ.

### 3. Không tạo project mới khi link còn phục hồi được

Trước khi tạo Flow project mới, adapter phải kiểm tra binding cũ:

- Mở URL bằng Chrome profile riêng.
- Nếu trang project load được và có prompt input hoặc workspace marker, giữ nguyên binding.
- Nếu gặp login/2FA/CAPTCHA, đánh dấu `needs_login` và yêu cầu người dùng xác minh, không tạo project mới.
- Nếu gặp application error, thử refresh/recover theo flow hiện có.
- Chỉ đánh dấu `invalid` và tạo project mới khi URL không còn là Flow project hợp lệ, project bị xóa/không tồn tại, hoặc sau các bước phục hồi vẫn không thể vào workspace.

### 4. Map clip an toàn trong cùng Flow project

Vì một project sẽ có nhiều shot/episode, runner phải map clip bằng tín hiệu mới phát sinh sau prompt:

- Chụp baseline media count/media URLs trước khi submit.
- Ghi `download_correlation_id` theo item.
- Ưu tiên URL media mới khác baseline hoặc media count tăng sau generation.
- Download vào thư mục riêng theo job/item.
- Validate file video, size ổn định và metadata trước khi import.
- Nếu có nhiều media mới mơ hồ, dừng item với lỗi retryable thay vì import nhầm shot.

Cách này thay thế lý do cũ "mở project mới để tránh nhiễu" bằng cơ chế correlation rõ hơn.

### 5. Chính sách model provider

Thêm model policy cho Flow/Veo theo hướng tôn trọng lựa chọn hiện tại trong tài khoản:

```text
model_selection_mode = "use_current_flow_selection"
allow_automatic_model_change = false
observed_model_label = label đọc được từ UI Flow
observed_model_cost_label = cost/credit label đã sanitize nếu đọc được
```

Trước khi submit prompt, adapter chỉ cần đọc model/cost label hiện tại nếu UI cho phép đọc an toàn:

1. Không tự click đổi model trước khi gửi prompt.
2. Nếu đọc được label model đang chọn, lưu vào metadata/report đã redaction.
3. Nếu model đang chọn báo hết quota, hết credit, billing hoặc không khả dụng, pause job với lỗi tiếng Việt.
4. Người dùng có thể tự đổi model trong Flow UI, sau đó bấm resume; lần resume dùng đúng model mới đang được chọn.

Không hard-code `Omni Flash` hoặc bất kỳ model miễn phí nào làm mặc định. Hệ thống không tự chọn model có phí hoặc miễn phí; người dùng quyết định model trong Flow.

### 6. Phân loại lỗi auto-repair

Lỗi được chia ba nhóm.

Nhóm auto-repair được:

- Selector Flow đổi.
- Không tìm thấy nút/model dropdown nhưng screenshot/log có đủ context.
- Download watcher timeout/stalled do bug app.
- Map media/download mơ hồ do logic correlation.
- Parse trạng thái provider sai.
- Test adapter/service fail do code app.

Nhóm cần người dùng duyệt trước:

- Thêm dependency mới.
- Migration database.
- Thay đổi logic xóa dữ liệu.
- Thay đổi policy credit/model có thể phát sinh cost.
- Sửa nhiều module ngoài provider/job boundary.

Nhóm không auto-repair:

- Login, 2FA, CAPTCHA.
- Billing/payment.
- Quota thật đã hết và người dùng chưa chọn model khác có thể chạy được trong Flow.
- Policy block của Google/Veo.
- Tài khoản bị giới hạn.

### 7. Vòng Codex repair

Khi gặp lỗi kỹ thuật thuộc allowlist:

```text
pause job
lưu repair context: job id, item id, project id, error_code, step, log redacted, screenshot path nếu có
khởi chạy Codex repair task
Codex tạo patch trong repo
chạy tests bắt buộc
nếu pass: restart/reload service nếu cần, resume job từ item lỗi
nếu fail: rollback patch do attempt đó tạo hoặc giữ patch để review, job vẫn paused
```

Giới hạn:

- Tối đa 1 repair active trong toàn app hoặc tối đa 1 repair cho cùng provider boundary.
- Tối đa số attempt cấu hình, mặc định 1-2 lần cho cùng lỗi.
- Không sửa file ngoài allowlist nếu không có duyệt.
- Không commit/push tự động.
- Không làm mất clip/prompt/voice/subtitle đã có.

### 8. Observability và báo cáo tiếng Việt

Mỗi repair attempt lưu:

- error_code, repair_status, files_changed, tests_run, test_result, resume_result.
- lý do tiếng Việt nếu không tự sửa.
- technical details đã redaction.

UI hiển thị:

- Flow project đang dùng cho video/series.
- Model Flow đang chọn hoặc model đã dùng gần nhất.
- Job đang chạy, paused vì người dùng, paused vì Codex repair, repair pass/fail.
- Nút mở Chrome đúng project, retry/resume và xem báo cáo.

## Rủi ro và giảm thiểu

- Flow UI đổi thường xuyên: cô lập selector/model logic trong adapter và test bằng snapshot/fixture.
- Dùng chung Flow project có thể làm media cũ lẫn media mới: bắt buộc baseline/correlation và dừng khi mơ hồ.
- Model/cost thay đổi theo tài khoản: chỉ ghi nhận model đang được chọn và pause nếu provider báo giới hạn, không hard-code hoặc tự đổi model.
- Codex sửa quá rộng: allowlist file, test bắt buộc, attempt limit và duyệt thủ công cho thay đổi lớn.
- Migration ảnh hưởng dữ liệu cũ: binding nullable, project cũ vẫn chạy; chỉ tạo binding khi bắt đầu job provider.
- URL provider nhạy cảm: không đưa URL thật vào package/debug export; log hash/redacted.

## Rollback

- Có thể tắt phần đọc model label và vẫn dùng Flow theo lựa chọn hiện tại của tài khoản.
- Có thể tắt Codex auto-repair, job sẽ pause và báo lỗi như trước.
- Có thể quay về upload clip thủ công và render timeline hiện có.
- Binding Flow project không làm mất clip đã import; nếu binding lỗi có thể invalidate thủ công và tạo binding mới.

## Câu hỏi mở

- Có cần lưu lịch sử model người dùng đã chọn theo job để thống kê chất lượng/chi phí không?
- Codex repair nên chạy bằng CLI local hay thông qua một job worker riêng của app?
- Với series rất dài, có cần giới hạn số asset trong một Flow project và đề xuất rotate có kiểm soát sau khi người dùng đồng ý không?
