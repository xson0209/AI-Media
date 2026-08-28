## Why

Khi người dùng làm nhiều video, AI Video đã có thể chạy nền nhưng Video Inspiration vẫn giữ yêu cầu chờ trong nhiều phút. Trạng thái hàng đợi voice cũng chưa rõ: người dùng không biết giọng nào đang tạo thật, giọng nào đang chờ, và việc hủy dự án chưa dọn các voice đang xếp hàng.

Ứng dụng cần một cơ chế điều phối chung, dễ hiểu với người không biết kỹ thuật: tối đa 3 dự án được xử lý cùng lúc, toàn ứng dụng chỉ tạo tối đa 2 giọng cùng lúc, phần vượt giới hạn tự động chờ và tự tiếp tục khi có chỗ trống.

## What Changes

- Thêm bộ điều phối workflow dùng chung cho AI Video và Video Inspiration, mặc định tối đa 3 dự án đang xử lý trong một backend local.
- Dự án thứ tư không bị lỗi; dự án chuyển sang trạng thái chờ và tự tiếp tục theo thứ tự khi một trong ba dự án trước kết thúc, bị hủy hoặc dừng để chờ người dùng duyệt.
- Chuyển Video Inspiration analyze/rewrite sang background job: API trả nhanh, ứng dụng tiếp tục phản hồi và frontend theo dõi tiến độ bằng polling.
- Đưa các lần gọi Codex của AI Video và Video Inspiration qua planning pool dùng chung, mặc định tối đa 3 tác vụ planning, đồng thời chặn chạy trùng trên cùng project/job.
- Giữ prompt pack AI Video là một full-pack call cho toàn project để không làm mất continuity.
- Đặt giới hạn cứng tối đa 2 tác vụ tạo voice trên toàn ứng dụng, bao gồm cả generation queue và đường tạo voice streaming.
- Phân biệt rõ trạng thái voice `queued`, `loading_model`, `generating` và trạng thái kết thúc; hủy dự án sẽ hủy các voice còn đang chờ của dự án đó.
- Giới hạn phần nhận dạng lời nói của Video Inspiration ở mức 1 tác vụ mặc định để tránh ba video cùng tranh RAM/GPU; render tiếp tục dùng khóa toàn cục hiện có.
- Hiển thị UI hoàn toàn bằng tiếng Việt: số dự án đang chạy/chờ, `Tạo giọng: x/2`, số giọng đang chờ và trạng thái từng dự án.
- Giảm polling dư thừa: chỉ theo dõi chi tiết các dự án cần thiết, còn danh sách dùng dữ liệu tổng hợp.
- Thêm xử lý restart/interrupted, retry và cancel để không để job treo vô hạn.

## Capabilities

### New Capabilities

- `ai-media-workflow-concurrency`: Điều phối tối đa 3 workflow AI Video/Video Inspiration, tối đa 3 Codex planning jobs, tối đa 2 voice generations và 1 STT job trong ứng dụng local single-process, kèm trạng thái hàng đợi tiếng Việt, cancel và phục hồi sau restart.

### Modified Capabilities

- Không sửa trực tiếp capability đã archive. Change này mở rộng change planning hiện có để phản ánh đúng implementation hiện tại và yêu cầu mới trên toàn ứng dụng.

## Impact

- Backend: workflow pool, planning pool dùng chung, background runner cho Video Inspiration, hard cap voice, STT gate, trạng thái tài nguyên và cancel propagation.
- AI Video: auto-run tham gia workflow pool, giữ tối đa 3 project active, hủy run dọn voice đang chờ, vẫn giữ full-pack prompt generation.
- Video Inspiration: analyze/rewrite trả về ngay sau khi xếp lịch, chạy nền, có cancel/retry và không khóa toàn workspace.
- Frontend: nhãn/trạng thái tiếng Việt, theo dõi nhiều project/job, hiển thị số slot và hàng đợi, bỏ `busy` toàn trang ở Video Inspiration.
- Configuration: các giới hạn mặc định là workflow `3`, planning `3`, voice `2`, STT `1`; voice không được cấu hình cao hơn `2` trong phạm vi change này.
- Storage/deployment: không thêm Redis và không hỗ trợ nhiều backend worker/replica trong change này; cơ chế giới hạn là toàn cục trong một process local.
- Tests: concurrency, background responsiveness, cancel/retry, restart, voice hard cap kể cả streaming, UI types/build và manual smoke test với voice engine thật.
