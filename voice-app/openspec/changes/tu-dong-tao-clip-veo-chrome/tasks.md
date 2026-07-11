## 1. Schema, Storage Và Dependency Decision

- [ ] 1.1 Chọn hướng automation cụ thể cho MVP: Playwright persistent Chrome channel hoặc CDP trực tiếp với installed Chrome; ghi lại lý do và tác động packaging.
- [ ] 1.2 Nếu dùng dependency mới, cập nhật dependency backend/build tương ứng và xác nhận không tải Chromium riêng khi dùng Chrome đã cài.
- [ ] 1.3 Thêm ORM model `VideoProviderSession` với provider, status, chrome profile path, account hint đã mask, last checked, failure reason và timestamps.
- [ ] 1.4 Thêm ORM model `VideoClipGenerationJob` với project id, provider, session id, status, current step, progress, force, auto render, render job id, download dir, failure reason, error code, step results JSON và timestamps.
- [ ] 1.5 Thêm ORM model `VideoClipGenerationItem` với job id, project id, shot id, prompt id, status, attempt count, provider asset id, downloaded path, clip id, failure reason và timestamps.
- [ ] 1.6 Thêm migration idempotent cho các bảng mới và index theo provider/status/project/job/shot.
- [ ] 1.7 Thêm helper storage cho Chrome profile riêng, download tạm theo job/item và cleanup an toàn khi job terminal hoặc project bị xóa.
- [ ] 1.8 Đảm bảo ZIP package/debug export không bao gồm Chrome profile, cookie hoặc thư mục provider downloads tạm.

## 2. Browser Session Manager

- [ ] 2.1 Implement service phát hiện Chrome executable trên macOS/Windows/Linux và cho phép cấu hình path nếu auto-detect fail.
- [ ] 2.2 Implement launch Chrome bằng profile riêng của Voicebox, URL Veo cấu hình được, UI thật và download directory riêng.
- [ ] 2.3 Implement API/service mở Chrome để người dùng đăng nhập Veo thủ công, tạo session record nếu chưa có.
- [ ] 2.4 Implement check session: xác minh vào được trang tạo video, phát hiện login/2FA/CAPTCHA/consent và cập nhật `ready` hoặc `needs_login`.
- [ ] 2.5 Implement guard chỉ một active Chrome automation session/provider, detect profile lock hoặc Chrome process cũ.
- [ ] 2.6 Redact account hint, URL và technical details; không đọc hoặc ghi cookie/token/local storage vào DB.
- [ ] 2.7 Implement invalidate/reconnect session khi Chrome bị đóng, profile lỗi hoặc provider yêu cầu đăng nhập lại.

## 3. Veo Provider Adapter

- [ ] 3.1 Tạo interface provider adapter chung: check session, submit prompt, wait generation, download clip, normalize provider error.
- [ ] 3.2 Implement `veo_chrome` adapter tối thiểu cho surface Veo đã chọn, với selector/URL đặt ở một module cấu hình dễ sửa.
- [ ] 3.3 Implement submit prompt cho một shot, dùng prompt video completed/passed mới nhất và không log full prompt dài.
- [ ] 3.4 Implement wait generation với timeout, polling hợp lý và trạng thái tiếng Việt cho UI.
- [ ] 3.5 Implement phát hiện lỗi provider: needs login, quota/billing, policy block, UI changed, download unavailable và unknown.
- [ ] 3.6 Implement download capture vào folder item riêng; không dùng Downloads mặc định của user để đoán file.
- [ ] 3.7 Implement file completion check: bỏ qua `.crdownload`, size ổn định, extension/MIME video hợp lệ và timeout rõ ràng.
- [ ] 3.8 Implement adapter result metadata đã redaction gồm provider asset id nếu có, filename sanitize, duration/size sau probe và attempt count.

## 4. Clip Generation Orchestrator

- [ ] 4.1 Implement service tạo job từ project: validate phase 2, session ready, shot tồn tại và prompt video hợp lệ.
- [ ] 4.2 Implement active job guard trên cùng project/provider để không chạy song song gây trùng download hoặc clip.
- [ ] 4.3 Implement chọn item cần chạy: skip shot đã có clip provider hợp lệ nếu không force; retry chỉ item missing/failed/stale.
- [ ] 4.4 Implement state machine item: pending, opening provider, submitting prompt, waiting generation, downloading, importing, completed, needs_login, failed, cancelled.
- [ ] 4.5 Implement runner background tuần tự theo shot để tránh quota/session conflict.
- [ ] 4.6 Implement import clip provider bằng helper chung với upload clip, tạo `video_shot_clips` source provider và deactivate clip active cũ.
- [ ] 4.7 Implement failure handling và retryable error codes tiếng Việt cho login, quota, download timeout, invalid video, UI changed và user cancelled.
- [ ] 4.8 Implement cancel job: ngừng submit/download item tiếp theo, giữ clip đã import và cleanup file tạm phù hợp.
- [ ] 4.9 Implement resume sau `needs_login` từ item chưa hoàn tất, không tạo lại item completed nếu không force.
- [ ] 4.10 Implement startup sync cho job đang active từ phiên app trước sang failed/needs_retry với thông báo tiếng Việt.
- [ ] 4.11 Implement auto-render handoff: gọi render readiness và tạo render job hiện có khi mọi clip ready và request bật auto render.
- [ ] 4.12 Implement trạng thái render blocked khi clip ready nhưng thiếu voice/subtitle/FFmpeg/timer; trả missing reasons cho frontend.

## 5. API Backend Và Types

- [ ] 5.1 Thêm Pydantic models cho provider session, session check/open request, clip generation job, item summary, start/retry/cancel/resume request và response.
- [ ] 5.2 Thêm routes lấy/cấu hình session Veo, mở Chrome đăng nhập, check session và invalidate/reconnect session.
- [ ] 5.3 Thêm routes start/latest/get clip generation job theo project.
- [ ] 5.4 Thêm routes resume, retry và cancel job với lỗi tiếng Việt nhất quán qua `video_errors`.
- [ ] 5.5 Cập nhật `apiClient` và frontend TypeScript types cho provider session/job/item/render handoff.
- [ ] 5.6 Cập nhật debug endpoint AI Video để hiển thị session/job summary đã redaction, không trả profile path nhạy cảm nếu không cần.
- [ ] 5.7 Đảm bảo endpoints từ chối thao tác khi project đang delete/reset, auto-run hoặc render active nếu gây race nguy hiểm.

## 6. Frontend AI Video UI

- [ ] 6.1 Tách component `AIVideoVeoChromePanel` hoặc tương đương để không làm `AIVideoAssistant.tsx` phình thêm quá mức.
- [ ] 6.2 Thêm panel trạng thái phiên Veo/Chrome: chưa cấu hình, cần đăng nhập, checking, ready, invalid/error.
- [ ] 6.3 Thêm action "Mở Chrome đăng nhập Veo", "Kiểm tra phiên", "Đăng nhập lại" và "Dùng phiên này" bằng tiếng Việt.
- [ ] 6.4 Thêm danh sách shot với trạng thái prompt/clip/provider item: thiếu prompt, đã có clip, chờ tạo, đang tải, đã import, lỗi, cần đăng nhập.
- [ ] 6.5 Thêm start form với `force` và `Tự render MP4 khi đủ clip`, disable đúng khi thiếu session hoặc thiếu prompt.
- [ ] 6.6 Thêm progress panel theo job/item, mô tả dễ hiểu cho người không code và không hiển thị raw status làm nhãn chính.
- [ ] 6.7 Thêm retry/cancel/resume actions, giữ upload clip thủ công và render panel hiện có làm fallback.
- [ ] 6.8 Khi job `needs_login`, UI đưa người dùng tới action mở đúng Chrome profile và resume sau khi check session pass.
- [ ] 6.9 Sau khi auto-render tạo render job, UI invalidate render queries và hiển thị tiến độ render MP4 hiện có.
- [ ] 6.10 Kiểm tra responsive layout, text không overlap, không dùng emoji, không thêm dependency UI mới khi chưa kiểm tra `app/package.json`.

## 7. Backend Tests

- [ ] 7.1 Test migration tạo bảng session/job/item và indexes.
- [ ] 7.2 Test session manager không lưu cookie/token vào DB/log và dùng profile path riêng.
- [ ] 7.3 Test check session chuyển `ready`, `needs_login` và lỗi Chrome missing/profile lock.
- [ ] 7.4 Test start job hợp lệ, project không tồn tại, thiếu prompt, session chưa ready và active job trùng.
- [ ] 7.5 Test item selection skip clip provider hợp lệ và force tạo lại clip.
- [ ] 7.6 Test download watcher nhận file hoàn tất, bỏ qua `.crdownload`, timeout và invalid video.
- [ ] 7.7 Test import clip provider tạo `video_shot_clips` đúng source/provider/metadata và deactivate clip cũ.
- [ ] 7.8 Test retry/resume/cancel không chạy lại item completed và giữ clip đã import.
- [ ] 7.9 Test app restart sync job active sang failed/needs_retry.
- [ ] 7.10 Test auto-render gọi render service khi readiness pass và render blocked khi readiness fail.
- [ ] 7.11 Test debug redaction không chứa full prompt dài, cookie, token, DOM hoặc credential.

## 8. Frontend Tests Và Type Checks

- [ ] 8.1 Thêm type/build coverage cho API client methods và TypeScript types mới.
- [ ] 8.2 Thêm component-level test hoặc targeted verification cho session panel: not configured, needs login, ready và error.
- [ ] 8.3 Thêm check UI cho job progress: pending, submitting, waiting, downloading, importing, completed, failed và needs login.
- [ ] 8.4 Thêm check action retry/cancel/resume và auto-render handoff invalidate render query.
- [ ] 8.5 Chạy frontend typecheck/build liên quan đến AI Video Assistant.

## 9. Manual QA Và Documentation

- [ ] 9.1 Manual QA lần đầu: mở Chrome profile riêng, đăng nhập đúng Google/Veo, check session ready.
- [ ] 9.2 Manual QA chạy một shot: gửi prompt sang Veo, tải clip, import vào đúng shot và render readiness cập nhật.
- [ ] 9.3 Manual QA chạy nhiều shot tuần tự, resume khi user đóng Chrome giữa chừng.
- [ ] 9.4 Manual QA needs-login: xóa/expire session, job dừng cần đăng nhập, user đăng nhập lại và resume từ shot chưa xong.
- [ ] 9.5 Manual QA quota/provider error/download timeout và retry sau khi xử lý.
- [ ] 9.6 Manual QA auto-render: đủ clip/voice/SRT thì tự tạo render job và tải MP4 hoàn chỉnh.
- [ ] 9.7 Manual QA bảo mật: ZIP/debug export không chứa Chrome profile, cookie/token hoặc full prompt dài.
- [ ] 9.8 Cập nhật docs AI Video bằng tiếng Việt: cách dùng Chrome profile riêng, vì sao không login tự động, cách giảm đăng nhập lại và fallback upload clip thủ công.
