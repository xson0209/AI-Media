## Vì sao

Luồng AI Video hiện đã có nền tảng tạo prompt, điều khiển Flow/Veo qua Chrome, tải clip về shot và render MP4. Tuy nhiên để tạo sản phẩm dài hơi ổn định hơn, hệ thống cần thêm ba ràng buộc vận hành:

- Mỗi video lẻ phải dùng đúng một Flow/Veo project để giữ asset, nhân vật, cảnh và style nhất quán.
- Mỗi series dài tập phải dùng chung một Flow/Veo project cho toàn bộ episode, chỉ tạo project mới khi link cũ thật sự không còn dùng được.
- Khi job gặp lỗi kỹ thuật của app, Codex được phép sửa code có kiểm soát, chạy test và resume job; nhưng không được tự xử lý login, 2FA, CAPTCHA, billing, quota thật hoặc policy block.

Người dùng muốn hệ thống tôn trọng model đang được chọn trong tài khoản Flow hiện tại. Nếu tài khoản đó đang chọn model nào thì job dùng đúng model đó, không tự đặt mặc định `Omni Flash`, không tự quét fallback và không tự đổi model thay người dùng.

## Thay đổi

- Thêm contract lưu `provider_project_url` cấp project video lẻ và cấp series.
- Thêm logic resolve Flow project URL theo thứ tự: series URL nếu project thuộc series, project URL nếu project lẻ, sau đó chỉ tạo project mới khi chưa có URL hoặc URL đã xác minh là không còn dùng được.
- Đổi tư duy tạo clip từ "mỗi shot có thể mở project mới để tránh nhiễu" sang "cùng project nhưng map clip bằng baseline media/download correlation an toàn".
- Thêm provider model policy: dùng đúng model đang được chọn trong Flow UI, chỉ đọc và ghi nhận model label/cost label đã sanitize, không tự đổi model.
- Thêm vòng Codex auto-repair cho lỗi kỹ thuật: pause job, chụp context/log, tạo patch, chạy test, restart/resume nếu pass, hoặc giữ job paused nếu fail.
- Phân loại lỗi rõ: lỗi kỹ thuật app có thể auto-repair; lỗi tài khoản/provider phải dừng và yêu cầu người dùng thao tác trong Chrome.
- Toàn bộ UI, lỗi, báo cáo và OpenSpec của change này dùng tiếng Việt.

## Phạm vi

Trong phạm vi:

- Database/API/model response cho Flow project binding cấp project và series.
- Service resolve, validate, invalidate và rotate Flow project URL.
- Veo/Flow adapter chọn model theo policy trước khi submit prompt.
- Job state machine cho pause/resume sau auto-repair.
- Codex repair runner có allowlist lỗi, giới hạn patch, test bắt buộc và báo cáo tiếng Việt.
- UI hiển thị model Flow đang được chọn, trạng thái Flow project binding và trạng thái Codex repair.
- Tests cho reuse project, dùng đúng model đang chọn, phân loại lỗi và resume sau repair.

Ngoài phạm vi:

- Không bypass login Google, 2FA, CAPTCHA, quota, billing, paywall hoặc policy của Google/Veo.
- Không tự mua credit hoặc thay đổi gói tài khoản.
- Không đọc/copy cookie từ Chrome cá nhân.
- Không gọi provider HTTP trực tiếp bằng cookie.
- Không tạo hệ thống agent tự sửa vô hạn hoặc tự commit/push code.

## Ảnh hưởng

- Backend: thêm field/bảng hoặc artifact metadata cho Flow project binding, model đang được chọn, repair attempt và error classification.
- Browser automation: adapter phải mở đúng Flow project URL, chọn model trước khi submit prompt và không tạo project mới nếu URL hiện tại còn dùng được.
- Storage/log: lưu URL ở dạng cần dùng cho automation nhưng log/debug/package chỉ lưu hash hoặc bản redacted.
- Frontend: thêm trạng thái "Project Flow đang dùng", model Flow đang chọn, và báo cáo Codex sửa lỗi.
- Testing: thêm coverage cho project lẻ, series, dùng đúng selected model, link hỏng, lỗi kỹ thuật và lỗi cần người dùng.

## Tên change

`5.tich-hop-codex-tu-sua-loi-veo-va-doi-model`
