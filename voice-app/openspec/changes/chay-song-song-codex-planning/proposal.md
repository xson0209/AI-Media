## Why

AI Video auto-run hiện xử lý các bước Codex planning theo từng project, nên khi người dùng chuẩn bị nhiều dự án cùng lúc thì các project phải chờ nhau dù mỗi prompt pack vẫn cần một call đầy đủ để giữ continuity. Cần một cơ chế chạy song song có kiểm soát để tăng throughput mà không chia nhỏ prompt pack trong một project, tránh làm mất đồng bộ nội dung.

## What Changes

- Thêm cơ chế **Codex planning concurrency** toàn app cho các bước AI Video dùng Codex CLI, với mặc định `max_concurrency = 2`.
- Giữ nguyên nguyên tắc **mỗi project chỉ có một prompt pack generation active** và mỗi prompt pack vẫn là một full-pack Codex call để đảm bảo continuity, segment order và style nhất quán trong project.
- Các workflow manual và auto-run sẽ đưa những bước planning nặng như develop story, generate shots và generate prompt pack qua cùng một planning gate/pool thay vì chạy tự do hoặc bị khóa tuần tự theo project.
- Thêm trạng thái/observability để thấy job planning đang chờ slot, đang chạy, hoàn tất hoặc lỗi, bao gồm run/project context và thời gian chờ.
- Không thay đổi schema nội dung prompt video, không chia một project thành nhiều prompt batch, không thay đổi TTS serial queue và không tăng song song voice generation.

## Capabilities

### New Capabilities
- `ai-video-codex-planning-concurrency`: Điều phối số lượng Codex planning jobs chạy song song cho AI Video, mặc định tối đa 2 job toàn app, trong khi vẫn giữ tính nhất quán full-pack trong từng project.

### Modified Capabilities
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp. Capability mới bọc các workflow AI Video hiện có bằng planning gate/pool chung.

## Impact

- Backend: thêm planning pool/semaphore hoặc queue dùng chung cho AI Video planning calls, guard active planning theo project, trạng thái chờ slot và logging/redaction cho wait/run/failure.
- Auto-run: các bước `develop_story`, `generate_shots` và `generate_prompts` đi qua planning pool; nhiều project auto-run có thể tiến hành song song đến giới hạn 2 Codex jobs.
- Manual API: các endpoint planning/prompt hiện có sử dụng cùng giới hạn để tránh bypass pool khi người dùng bấm thủ công.
- Configuration: thêm default `max_concurrency = 2`, có thể override bằng env/settings sau khi test ổn.
- Tests: thêm coverage cho concurrency limit, per-project guard, wait state, failure release slot, auto-run multi-project throughput và việc TTS queue vẫn serial.
