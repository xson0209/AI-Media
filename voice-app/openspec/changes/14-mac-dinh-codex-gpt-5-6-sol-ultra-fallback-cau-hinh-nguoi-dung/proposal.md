## Vì sao

AI Video và Video Inspiration đang gọi Codex CLI qua lớp AI planning chung, nhưng cấu hình model hiện tại chỉ truyền `settings.model` nếu có và chưa truyền reasoning effort. Vì vậy người dùng không biết chính xác request đang dùng model nào, panel readiness chỉ báo Codex CLI sẵn sàng kèm request ID, còn log chưa phân biệt rõ đường chạy chính, đường fallback và model thực tế đã dùng.

Yêu cầu mới là mọi tác vụ AI planning dùng mặc định `gpt-5.6-sol` với reasoning effort cao nhất `ultra` bằng cờ `--config model_reasoning_effort="ultra"`. Nếu cấu hình ưu tiên này lỗi hoặc không khả dụng, hệ thống phải fallback về cấu hình Codex hiện tại của chính user đang kết nối, thay vì tự đoán một model khác. Người dùng cũng cần thấy rõ trong UI và log: model/effort nào được yêu cầu, model/effort nào thực sự đã chạy, có fallback hay không và vì sao.

## Thay đổi

- Đặt policy mặc định cho Codex AI planning là `gpt-5.6-sol` và reasoning effort `ultra` khi người dùng chưa cấu hình override rõ ràng trong app.
- Khi chạy `codex exec`, đường chính truyền `--model gpt-5.6-sol` và `--config model_reasoning_effort="ultra"` hoặc giá trị override hợp lệ tương ứng.
- Thêm fallback có kiểm soát: nếu đường chính thất bại vì model/reasoning/config không chạy được, retry bằng cấu hình Codex hiện tại của user đang đăng nhập/kết nối, tức không tự chọn model thay user và không ghi đè global `~/.codex/config.toml`.
- Giữ fallback structured-output hiện có: lỗi `--output-schema` vẫn có thể retry bằng inline JSON schema trong từng đường chạy, nhưng log phải phân biệt schema fallback với model/config fallback.
- Mở rộng settings/backend response để có metadata model: requested model, requested reasoning effort, effective model, effective reasoning effort, nguồn model, fallback flag, fallback reason và request ID.
- Cập nhật panel AI Video trong ảnh để hiển thị tiếng Việt dòng `Đang dùng` hoặc `Cấu hình sẽ dùng`, ví dụ `gpt-5.6-sol · ultra`, và hiển thị rõ khi đang dùng fallback.
- Ghi log/debug event có redaction cho model thực tế đã dùng, effort, nguồn cấu hình và fallback, không lưu full prompt/source dài.
- Thêm test backend và frontend type coverage để ngăn UI báo sai model so với command thực tế.

## Phạm vi

Trong phạm vi:

- Backend AI planning settings, migration và resolver cấu hình model/reasoning.
- Command builder và retry/fallback trong `run_codex_exec`.
- Readiness check response và log của Codex provider.
- Frontend API type và panel readiness/status của AI Video Assistant.
- Tests cho default `gpt-5.6-sol + ultra`, fallback về user-connected config và metadata hiển thị.

Ngoài phạm vi:

- Không sửa global Codex config của user.
- Không tự cài hoặc đổi phiên bản Codex CLI.
- Không tự tạo model fallback thứ ba ngoài cấu hình Codex hiện tại của user.
- Không đổi policy model Flow/Veo trong Chrome; change này chỉ áp dụng cho Codex CLI AI planning của app.
- Không triển khai code ứng dụng trong proposal này; phần apply sẽ làm sau.

## Ảnh hưởng

- Backend: cần thêm field hoặc resolver cho `model_reasoning_effort`, metadata fallback và logging nhất quán trong `backend/services/ai_planning.py`, `backend/models.py`, settings service và migration.
- Frontend: cần mở rộng `AIPlanningProviderCheckResponse` và UI panel để show model/effort/fallback trên cùng card readiness hiện có, không redesign.
- Data: migration phải không làm mất cấu hình hiện có. Các row cũ được resolve sang default mới nếu chưa có override, còn fallback vẫn dùng cấu hình Codex hiện tại của user.
- Vận hành: khi `gpt-5.6-sol + ultra` khả dụng, mọi planning call dùng đường này. Khi không khả dụng, user vẫn có kết quả bằng cấu hình Codex đang kết nối, đồng thời log đủ dữ liệu để debug.

## Tên change

`14-mac-dinh-codex-gpt-5-6-sol-ultra-fallback-cau-hinh-nguoi-dung`
