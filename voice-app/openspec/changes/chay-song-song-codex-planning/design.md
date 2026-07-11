## Context

AI Video phase 2 hiện có nhiều bước dùng Codex CLI qua `ai_planning.run_codex_exec`: phát triển story, tạo shot breakdown và tạo prompt video pack. Auto-run đã điều phối các bước này theo từng project, nhưng khi nhiều project cùng chạy thì throughput chưa tối ưu vì mỗi bước planning nặng thường giữ một project chờ trong nhiều phút.

Prompt video pack có yêu cầu continuity cao. Một project cần giữ một full-pack Codex call để AI nhìn toàn bộ shot list, segment order, continuity bible, transition và target language cùng lúc. Vì vậy tối ưu đúng ở đây không phải chia một project thành nhiều prompt call song song, mà là cho nhiều project khác nhau chạy planning song song với giới hạn an toàn.

Code hiện có các ràng buộc quan trọng:
- Codex execution là subprocess blocking, có timeout/retry và structured output schema.
- Auto-run chạy trong background task và đã có state machine riêng cho project.
- TTS generation dùng serial queue riêng để tránh tranh GPU; change này không được đụng vào cơ chế đó.
- App là local desktop/server single-process trong thực tế hiện tại, SQLite local và artifact storage local.

## Goals / Non-Goals

**Goals:**
- Cho phép tối đa 2 Codex planning jobs chạy song song toàn app theo mặc định.
- Giữ mỗi project chỉ có một planning operation active tại một thời điểm.
- Giữ `generate_video_prompt_pack` là một full-pack call trong một project, không tách batch theo shot.
- Áp dụng cùng giới hạn cho auto-run và manual AI Video planning endpoints.
- Hiển thị/log được trạng thái chờ slot, thời gian chờ, job đang chạy và lỗi.
- Release slot chắc chắn khi planning success, validation fail, Codex timeout, exception hoặc auto-run dừng.

**Non-Goals:**
- Không chia prompt pack của một project thành nhiều Codex call.
- Không tăng song song voice/TTS generation.
- Không thêm distributed queue, Redis hoặc worker process ngoài.
- Không thay đổi output schema của prompt video, shot breakdown hoặc story development.
- Không cố giải quyết multi-process server deployment trong change này.

## Decisions

### 1. Dùng global planning pool mặc định 2 slot

Quyết định: thêm service nhỏ cho AI Video planning concurrency, ví dụ `video_planning_pool`, quản lý một global semaphore/pool với `max_concurrency = 2` theo mặc định. Giá trị có thể override bằng env hoặc setting sau khi test, nhưng default implementation phải an toàn và không vượt 2 nếu chưa cấu hình rõ.

Phương án khác đã cân nhắc: giữ tuần tự một job toàn app. Cách này an toàn nhưng không tận dụng được thời gian chờ network/API khi có nhiều project. Chạy không giới hạn thì dễ tạo nhiều subprocess Codex, tăng timeout/rate-limit và làm UI khó hiểu.

### 2. Giữ per-project planning lock độc lập với global slot

Quyết định: trước khi một planning job xin global slot, service kiểm tra project đó có planning operation active chưa. Nếu có, request cùng project phải dừng rõ ràng bằng lỗi tiếng Việt hoặc trạng thái waiting/active đã biết, và không tạo thêm Codex call trùng.

Lý do: prompt/story/shot writes đang cập nhật artifact và status theo project. Hai planning operations cùng project có thể ghi đè prompt, stale state hoặc package readiness sai. Per-project lock bảo vệ dữ liệu; global pool chỉ bảo vệ throughput.

### 3. Bọc planning call ở boundary chung, không rewrite từng prompt generator

Quyết định: mọi đường gọi Codex trong AI Video phase 2 phải đi qua một boundary chung, ví dụ wrapper quanh `_run_structured_codex` hoặc `ai_planning.run_codex_exec` khi có `project_id`/`step_name`. Boundary này chịu trách nhiệm acquire/release slot, log wait/run, và giữ retry behavior hiện có bên trong planning step.

Phương án khác đã cân nhắc: thêm semaphore riêng ở từng route/service method. Cách đó dễ bỏ sót path manual hoặc auto-run, và sau này thêm step planning mới sẽ dễ bypass giới hạn.

### 4. Full prompt pack vẫn là đơn vị atomic trong một project

Quyết định: `generate_video_prompt_pack` vẫn build prompt từ toàn bộ shot cần tạo, gọi Codex một lần và validate/ghi kết quả như hiện tại. Concurrency chỉ xảy ra giữa project khác nhau, ví dụ project A và project B cùng tạo prompt pack.

Lý do: người dùng đã lo đúng về việc gọi Codex riêng có thể làm dữ liệu không đồng bộ. Full-pack call giữ cùng continuity bible, language instruction, target segment count và transition plan trong một response.

### 5. Auto-run có waiting planning state, manual API dùng cùng pool

Auto-run khi không lấy được slot ngay phải chuyển sang trạng thái dễ hiểu như `waiting_planning` hoặc giữ `running` với `current_step` mô tả đang chờ slot Codex. Khi có slot, auto-run tiếp tục step hiện tại.

Manual endpoints vẫn có thể trả response đồng bộ như hiện tại, nhưng không được bypass pool. Nếu project đang có planning job khác active, manual endpoint trả lỗi tiếng Việt rõ ràng thay vì chờ mơ hồ hoặc tạo job trùng. Nếu chỉ thiếu global slot nhưng project không trùng, endpoint có thể chờ trong giới hạn timeout hiện có và log wait duration.

### 6. Pool là in-memory cho MVP, không thêm migration

Quyết định: dùng in-memory semaphore/registry trong process cho MVP. App hiện chạy local single process; auto-run interruption đã có hướng xử lý khi app restart. Không cần thêm bảng DB nếu chỉ cần giới hạn concurrent Codex subprocess trong runtime.

Phương án khác đã cân nhắc: persisted planning_jobs table. Cách này giúp inspect sâu và multi-process hơn, nhưng làm scope lớn hơn nhiều. Nếu sau này cần queue/history UI chi tiết, có thể nâng cấp từ pool in-memory sang persisted job model.

### 7. TTS serial queue không bị thay đổi

Planning pool mới không được dùng `task_queue.enqueue_generation` vì queue đó cố ý serialize TTS inference. Auto-run vẫn enqueue nhiều voice shot như hiện tại, nhưng voice worker vẫn xử lý một generation tại một thời điểm.

## Risks / Trade-offs

- Codex/API rate-limit khi chạy 2 job lớn cùng lúc -> Giữ default 2, log timeout/rate error và cho phép hạ về 1 bằng config.
- Manual endpoint chờ slot có thể làm request lâu hơn -> Log wait state rõ ràng; nếu cần ở phase sau có thể chuyển manual planning sang job/poll endpoint.
- In-memory pool không giữ trạng thái qua restart -> Running auto-run đã có cơ chế sync interrupted; sau restart pool bắt đầu trống và các run cũ phải được đánh failed/retry rõ ràng.
- Per-project lock rò rỉ nếu exception không release -> Dùng context manager/finally và test exception path.
- SQLite write contention nếu hai project hoàn tất Codex cùng lúc -> Mỗi project ghi DB trong transaction riêng, giữ critical section ngắn, không giữ DB session trong lúc chờ slot/Codex nếu có thể.
- Tăng throughput có thể làm máy người dùng chậm khi Codex subprocess chạy song song -> Default 2, có setting/env để giảm và observability để thấy queue/wait.

## Migration Plan

- Không cần migration database cho MVP.
- Thêm planning pool service và cấu hình default 2.
- Bọc các AI Video planning calls hiện có bằng pool chung.
- Cập nhật auto-run summary/status để hiển thị chờ slot planning.
- Rollback an toàn bằng cách đặt `max_concurrency = 1` hoặc bypass pool về behavior tuần tự hiện tại.

## Open Questions

- Có cần expose setting `max_concurrency` trong UI Settings ngay trong change này không, hay chỉ env/config internal trước?
- Manual endpoint khi thiếu global slot nên chờ tới timeout hay trả lỗi 429/409 để UI retry/poll sau?
- Có cần lưu lịch sử planning wait/run riêng trong debug panel, hay debug event hiện tại đủ cho MVP?
