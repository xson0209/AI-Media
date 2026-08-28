## Bối cảnh hiện tại

Lớp AI planning dùng `backend/services/ai_planning.py` để kiểm tra Codex CLI và chạy `codex exec`. Command hiện có chỉ thêm `--model settings.model` nếu settings có model, chưa có reasoning effort. `check_provider` trả message, version, request ID và error code, còn frontend card trong `AIVideoAssistant.tsx` chỉ hiển thị message/request ID.

`run_codex_exec` đã có một fallback khác cho structured output: khi `--output-schema` bị provider từ chối, hệ thống retry bằng prompt có inline JSON schema. Change này thêm một lớp fallback mới ở mức model/config, nhưng không được làm mờ fallback schema hiện có.

## Mục tiêu

- Mặc định mọi Codex AI planning dùng `gpt-5.6-sol` với `model_reasoning_effort="ultra"`.
- Không sửa global Codex config của user và không tự chọn model fallback tùy tiện.
- Khi đường ưu tiên lỗi, fallback về cấu hình Codex hiện tại của user đang chạy app/backend.
- Log và UI nói rõ model/effort thực tế đã dùng, không chỉ nói Codex CLI sẵn sàng.
- Không báo sai: nếu chỉ mới kiểm tra cấu hình mà chưa chạy thử, UI phải dùng ngôn ngữ `Cấu hình sẽ dùng`; nếu đã chạy thử hoặc đã có execution metadata thì mới dùng `Đã chạy với`/`Đang dùng`.
- Giữ tương thích với output-schema fallback và các error code hiện có.

## Không phải mục tiêu

- Không đảm bảo `gpt-5.6-sol` luôn khả dụng cho mọi tài khoản.
- Không bypass login, auth, billing, quota hoặc policy của provider.
- Không thêm provider AI planning mới ngoài Codex CLI.
- Không đổi workflow pool/concurrency.
- Không đổi model của Flow/Veo trong trình duyệt.

## Quyết định thiết kế

### 1. Resolver model/reasoning có nguồn rõ ràng

Thêm resolver tập trung cho AI planning:

```text
preferred_model = settings.model nếu user đã override rõ ràng
                hoặc VOICEBOX_CODEX_MODEL nếu env được đặt
                hoặc "gpt-5.6-sol"

preferred_reasoning_effort = settings.model_reasoning_effort nếu user đã override rõ ràng
                           hoặc VOICEBOX_CODEX_REASONING_EFFORT nếu env được đặt
                           hoặc "ultra"
```

Nếu cần phân biệt row cũ và override thủ công, migration nên giữ field nullable và resolver trả default mới ở runtime thay vì ghi đè dữ liệu cũ không rõ nguồn. Settings UI/API có thể lưu override rõ ràng khi user thay đổi.

Reasoning effort được validate theo danh sách Codex hỗ trợ tại thời điểm implementation, tối thiểu gồm `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. Giá trị invalid không được truyền vào command; hệ thống dùng default `ultra` hoặc báo lỗi validation trong Settings.

### 2. Command profile cho đường chính và fallback

Command builder tạo metadata profile trước khi chạy:

```text
primary:
  model = preferred_model
  reasoning_effort = preferred_reasoning_effort
  args include --model <model>
  args include --config model_reasoning_effort="<effort>"
  model_source = "voicebox_preferred"

fallback:
  model = cấu hình Codex hiện tại của user nếu đọc được, nếu không là "Cấu hình Codex hiện tại"
  reasoning_effort = effort hiện tại nếu đọc được, nếu không là null
  args không include app-forced --model/--config preferred
  model_source = "user_connected_codex_config"
```

Fallback không được ghi vào global config. Nó chỉ bỏ override ưu tiên của app để Codex CLI tự dùng profile/session/config hiện tại của user.

### 3. Thứ tự retry

`run_codex_exec` nên dùng helper chạy một attempt cho một command profile:

1. Chạy profile với `--output-schema` nếu request có schema.
2. Nếu lỗi thuộc nhóm schema/structured-output, retry cùng profile bằng inline schema.
3. Nếu profile chính vẫn thất bại vì model/config/reasoning/provider không dùng được, chạy profile fallback.
4. Fallback cũng được dùng schema fallback theo cùng quy tắc.
5. Nếu fallback thành công, trả output của fallback và ghi metadata `fallback_used=true`.
6. Nếu cả hai đều fail, trả lỗi có request ID và chi tiết đã redaction cho cả lỗi chính và fallback.

Không fallback model/config khi lỗi là không tìm thấy Codex CLI, không chạy được process, chưa login/auth rõ ràng, request bị hủy chủ động hoặc lỗi validation nội bộ trước khi gọi CLI. Các lỗi này cần báo thẳng vì fallback cùng CLI không giải quyết được.

Nhóm lỗi nên fallback gồm:

- model không tồn tại/không hỗ trợ/không có quyền;
- reasoning effort hoặc `--config` bị từ chối;
- provider trả lỗi do model/config preferred không khả dụng;
- timeout hoặc lỗi tạm thời của preferred model khi fallback user config có thể vẫn chạy.

### 4. Metadata trả về và lưu log

Thêm metadata chung:

```text
requested_model
requested_reasoning_effort
effective_model
effective_reasoning_effort
model_source
model_verified
fallback_used
fallback_reason
fallback_error_code
request_id
```

`effective_model` là model profile thực sự tạo output thành công. Với đường chính, đây là `gpt-5.6-sol` hoặc override đã truyền bằng cờ. Với fallback, nếu đọc được config hiện tại của Codex thì ghi model đó; nếu không đọc được thì ghi label tiếng Việt `Cấu hình Codex hiện tại của người dùng` và đặt `model_source=user_connected_codex_config`.

Log bắt buộc có các field trên ở cả start, success, fallback start, fallback success và error. Không log full prompt, full source, full stdout/stderr dài hoặc secret. Chi tiết provider tiếp tục dùng redaction hiện có.

### 5. Readiness check và UI panel

`AIPlanningProviderCheckResponse` cần mở rộng cùng metadata model. Khi `check_exec=false`, response chỉ xác nhận CLI/path/login và cấu hình dự kiến, nên `model_verified=false`. Khi `check_exec=true` hoặc sau một execution thật, metadata có thể là verified.

Frontend card trong AI Video Assistant giữ layout hiện tại nhưng thêm dòng ngắn:

```text
Cấu hình sẽ dùng: gpt-5.6-sol · ultra
```

Khi fallback đã xảy ra hoặc readiness exec xác nhận fallback:

```text
Đang dùng fallback: Cấu hình Codex hiện tại của người dùng
Lý do: <fallback_reason đã rút gọn>
```

Request ID vẫn hiển thị, nhưng nên có nhãn `Request ID:` để dễ đọc. Text container cần `min-w-0` và `break-words` để model label dài không tràn panel.

### 6. Settings và migration

Thêm field `model_reasoning_effort` cho `AIPlanningSettings` nếu implementation chọn lưu trong database. Migration phải thêm column nullable để row cũ không vỡ. Settings response/update/type frontend cần nhận field này.

Default resolver có thể không ghi `gpt-5.6-sol` trực tiếp vào row cũ; như vậy user vẫn có fallback profile riêng và có thể phân biệt default runtime với override thủ công. Nếu implementation ghi default vào row mới, vẫn phải giữ fallback bằng cách chạy command fallback không truyền override.

### 7. Kiểm thử

Test backend cần cover:

- Settings mới hoặc row trống resolve ra `gpt-5.6-sol` và `ultra`.
- Command chính có `--model gpt-5.6-sol` và `--config model_reasoning_effort="ultra"`.
- Lỗi model/config của command chính chạy retry fallback không có cờ preferred.
- Schema fallback vẫn hoạt động trong từng profile.
- Log/response có `effective_model`, `fallback_used`, `fallback_reason` và request ID.
- Auth/missing CLI không kích hoạt fallback sai.

Frontend test/typecheck cần đảm bảo response mới được type đúng và panel render được các trạng thái default, verified, fallback và unknown fallback.

## Rủi ro và giảm thiểu

- `gpt-5.6-sol` hoặc `ultra` có thể không khả dụng với một tài khoản: fallback về cấu hình Codex hiện tại của user và log rõ lý do.
- Không phải lúc nào cũng đọc được model thực tế khi dùng fallback CLI default: UI phải nói rõ `Cấu hình Codex hiện tại của người dùng` thay vì bịa model.
- Retry nhiều tầng có thể làm timeout dài hơn: tổng timeout mỗi attempt vẫn bị giới hạn theo settings; log elapsed riêng cho từng attempt.
- Dễ nhầm schema fallback với model fallback: metadata và step name phải tách `codex_exec_schema_fallback` khỏi `codex_exec_model_fallback`.
- Nếu settings cũ có model thủ công, default mới có thể bị hiểu nhầm: UI nên hiển thị nguồn model để user biết đang dùng default app hay override.

## Rollback

- Có thể tắt preferred override bằng env/config để chỉ dùng cấu hình Codex hiện tại của user.
- Có thể giữ field `model_reasoning_effort` nullable và bỏ truyền `--config` nếu Codex CLI thay đổi cú pháp.
- Nếu UI metadata gây lỗi type/build, backend vẫn có thể trả các field optional và frontend hiển thị message/request ID như trước.
