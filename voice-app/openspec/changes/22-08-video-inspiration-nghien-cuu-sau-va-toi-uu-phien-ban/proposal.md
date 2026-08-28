## Ngày đề xuất

22-08-2026

## Why

Video Inspiration hiện đã có hai nền tảng liên quan nhưng tách rời:

- Route `/video-inspiration` có thể phân tích video theo chế độ `quick` hoặc `high_quality`, sau đó người dùng tự thực hiện các bước tiếp theo.
- Pipeline tối ưu kịch bản đã tạo nhiều candidate, chấm điểm và tổng hợp thành bản cuối, nhưng toàn bộ pipeline chạy cố định và chưa cho người dùng chọn candidate, chạy lại từng stage hoặc tạo nhiều bản tối ưu có kiểm soát.

Người dùng cần một luồng liền mạch hơn: bắt đầu một lần bằng nghiên cứu sâu, chờ xử lý nền, rồi tự động mở form AI Video để cấu hình. Khi cần phát triển nhiều hướng kịch bản, người dùng cần chọn candidate, chấm điểm theo batch và tạo một hoặc nhiều phiên bản tối ưu mà không phải chạy lại các stage đã có kết quả.

## What Changes

- Thêm hành động `Nghiên cứu sâu → Cấu hình Video AI` cho Video Inspiration.
- Dùng chất lượng phân tích sâu (`high_quality` hoặc profile tương đương có công bố coverage), nhưng không bắt người dùng đi qua nhiều màn hình trung gian.
- Sau khi nghiên cứu sâu thành công, tự dựng draft analysis-only và mở `/ai-video?draft=video-inspiration`.
- Không tạo AI Video project, không auto-run planning/generation và không ghi đè lựa chọn cấu hình cuối của người dùng.
- Cho phép tạo 2–3 candidate trong một batch, chọn candidate bằng checkbox và chấm điểm nhiều candidate trong một AI call.
- Cho phép tạo một hoặc nhiều bản tổng hợp tối ưu từ candidate/điểm đã chọn.
- Lưu revision, fingerprint, trạng thái từng stage và cache để chạy lại đúng stage bị lỗi hoặc bị stale.
- Giữ provenance, limitation và cảnh báo originality khi handoff.

## Impact

- Frontend Video Inspiration có thêm hành động nghiên cứu sâu, pending intent, candidate selection, batch scoring và multi-version synthesis.
- AI Video cần chuẩn hóa việc nhận draft: chỉ nạp dữ liệu để cấu hình, không tự tạo project hoặc chọn chế độ chạy cuối.
- Backend mở rộng contract cho stage/revision/fingerprint, batch scoring, multi-version synthesis, cache và retry theo stage.
- Database/storage cần lưu candidate, score, final version và quan hệ provenance theo revision mà không phá dữ liệu cũ.
- Workflow/planning pool tiếp tục là giới hạn concurrency dùng chung; stage dài cần heartbeat để tránh stale giả.
- API và hành vi Video Inspiration hiện có phải giữ tương thích ngược.

## Phạm vi

### Bao gồm

- UI action và trạng thái pending cho nghiên cứu sâu → handoff cấu hình.
- Draft AI Video không bắt buộc có `rewritten_script`; có thể dùng transcript, analysis package và source blocks làm seed.
- Candidate selection, batch scoring, multi-version synthesis.
- Cache theo analysis revision, ngôn ngữ, định hướng, số candidate, rubric và model.
- Bounded concurrency, retry theo stage, partial failure và progress tiếng Việt.
- Regression tests cho Video Inspiration và AI Video handoff.

### Không bao gồm

- Không tự tạo project AI Video sau khi handoff draft.
- Không tự chạy story planning, prompt, voice, subtitle, render, Veo hoặc publishing.
- Không thay đổi pipeline STT/vision nền ngoài các tham số cần để chọn profile nghiên cứu sâu.
- Không tạo vô hạn candidate hoặc vô hạn request song song.
- Không xóa hoặc ghi đè candidate, điểm số hay revision cũ.

## Tiêu chí thành công

- Một thao tác có thể khởi động nghiên cứu sâu và tự mở form AI Video sau khi job hoàn tất.
- Form AI Video nhận đủ transcript, analysis, visual evidence, limitations, direction và provenance để tiếp tục cấu hình.
- Handoff không chọn `full_materials`, không auto-run và không ghi đè market, ngôn ngữ cuối, thời lượng, tỷ lệ, voice hoặc run mode.
- Candidate được tạo và chấm điểm theo batch; tạo lại không gọi lại các stage có fingerprint giống nhau.
- Người dùng có thể chọn bản cuối để handoff và truy vết được nguồn candidate/score tương ứng.
