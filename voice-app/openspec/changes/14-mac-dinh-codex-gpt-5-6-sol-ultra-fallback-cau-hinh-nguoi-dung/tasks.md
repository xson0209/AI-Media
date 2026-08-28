## 1. Backend settings và migration

- [x] 1.1 Thêm resolver mặc định `gpt-5.6-sol` và `model_reasoning_effort="ultra"` cho AI planning.
- [x] 1.2 Thêm field `model_reasoning_effort` vào database/settings model/API nếu cần lưu override.
- [x] 1.3 Thêm env override `VOICEBOX_CODEX_REASONING_EFFORT` và validate effort hợp lệ.
- [x] 1.4 Đảm bảo migration không ghi đè cấu hình thủ công hiện có và row cũ vẫn chạy được.

## 2. Codex command và fallback

- [x] 2.1 Tách command builder thành profile đường chính và profile fallback user-connected config.
- [x] 2.2 Đường chính truyền `--model gpt-5.6-sol` và `--config model_reasoning_effort="ultra"` khi không có override.
- [x] 2.3 Đường fallback không truyền forced model/reasoning của app và để Codex CLI dùng cấu hình hiện tại của user.
- [x] 2.4 Thêm classifier lỗi model/config/reasoning để quyết định khi nào fallback.
- [x] 2.5 Giữ structured-output fallback hiện có trong từng profile và tách step name/log giữa schema fallback và model fallback.
- [x] 2.6 Không fallback sai cho lỗi missing CLI, auth/login rõ ràng, process start failure, cancel hoặc validation nội bộ.

## 3. Metadata, log và response

- [x] 3.1 Mở rộng `AIPlanningProviderCheckResponse` với requested/effective model, reasoning effort, model source, verified flag và fallback metadata.
- [x] 3.2 Ghi log start/success/error/fallback với request ID, provider, requested model/effort, effective model/effort, source và fallback reason.
- [x] 3.3 Redact provider details và không log full prompt/source/stdout/stderr dài.
- [x] 3.4 Khi fallback dùng config hiện tại nhưng không đọc được model, trả label rõ ràng `Cấu hình Codex hiện tại của người dùng` thay vì báo sai model.

## 4. Frontend AI Video panel

- [x] 4.1 Cập nhật TypeScript API type cho readiness response mới.
- [x] 4.2 Cập nhật card readiness trong `AIVideoAssistant.tsx` để hiển thị `Cấu hình sẽ dùng` hoặc `Đang dùng` kèm model/effort.
- [x] 4.3 Hiển thị fallback bằng tiếng Việt, gồm nguồn fallback và lý do rút gọn nếu có.
- [x] 4.4 Giữ request ID nhưng thêm nhãn rõ ràng và chống tràn text bằng `min-w-0`/`break-words`.

## 5. Kiểm thử và xác minh

- [x] 5.1 Thêm backend unit tests cho resolver default `gpt-5.6-sol + ultra`.
- [x] 5.2 Thêm test command args có `--model` và `--config model_reasoning_effort="ultra"`.
- [x] 5.3 Thêm test preferred failure rồi fallback về command không forced model/config.
- [x] 5.4 Thêm test schema fallback vẫn chạy sau thay đổi model fallback.
- [x] 5.5 Thêm test readiness response/log metadata không thiếu request ID và fallback fields.
- [x] 5.6 Chạy targeted backend tests liên quan AI planning.
- [x] 5.7 Chạy frontend typecheck/build tối thiểu cho app.
- [x] 5.8 Chạy `openspec validate 14-mac-dinh-codex-gpt-5-6-sol-ultra-fallback-cau-hinh-nguoi-dung --strict`.
