## Why

### Status 2026-07-12

Core implementation is already present in the repository: provider session persistence, CDP-based Chrome launch/check, Veo/Flow adapter, clip generation orchestrator, API routes/client types, and the AI Video Veo3 panel. This OpenSpec change now tracks the remaining hardening, test, QA, documentation, and cleanup work needed before the feature should be considered complete.

AI Video hiện đã tạo được prompt, voice, phụ đề và render MP4 nếu người dùng upload clip theo từng shot, nhưng đoạn tạo clip bằng Veo/Chrome vẫn thủ công: copy prompt, chọn đúng tài khoản Google, chờ generate, tải file rồi upload lại vào project. Cần một workflow tự động hoá có kiểm soát để dùng lại Chrome session đã đăng nhập đúng tài khoản, tránh đăng nhập Veo nhiều lần và nối thẳng clip tải về vào render trong Voicebox.

## What Changes

- Thêm workflow **Tạo clip bằng Veo qua Chrome** cho AI Video phase 2, chạy sau khi project đã có prompt video theo shot.
- Thêm quản lý phiên Chrome/Veo bằng Chrome profile riêng của Voicebox, để người dùng đăng nhập Google/Veo thủ công một lần rồi app dùng lại profile đó cho các lần sau.
- Không lưu mật khẩu Google, token, cookie hoặc dữ liệu đăng nhập nhạy cảm vào database; hệ thống chỉ lưu metadata session tối thiểu như profile path, provider, trạng thái kiểm tra và thời điểm xác minh gần nhất.
- Thêm job tạo clip ngoài: lấy prompt theo shot, mở hoặc dùng Chrome profile đã cấu hình, đưa prompt vào Veo, theo dõi trạng thái tạo clip, bắt file tải về và map về đúng shot.
- Lưu clip tải về bằng model `video_shot_clips` hiện có với `source = "provider"`, `provider = "veo"` và metadata đã redaction, sau đó dùng render timeline hiện có để dựng MP4.
- Hỗ trợ pause/resume/retry/cancel khi Veo yêu cầu đăng nhập lại, bị quota, lỗi download, clip thiếu hoặc người dùng đóng Chrome.
- UI AI Video thêm khu **Phiên Veo/Chrome** và **Tạo clip tự động** bằng tiếng Việt: mở Chrome đăng nhập, kiểm tra session, chạy theo shot, theo dõi tiến độ, retry shot lỗi và tự chuyển sang render khi đủ clip.
- Không tự động đăng nhập Google bằng username/password, không vượt qua CAPTCHA/2FA, không gom cookie từ Chrome cá nhân mặc định và không chạy nhiều phiên song song cùng một provider account.

## Capabilities

### New Capabilities
- `ai-video-veo-chrome-clip-generation`: Quản lý Chrome profile đã đăng nhập Veo, tự gửi prompt video theo shot, tải clip về project, import clip vào `video_shot_clips` và kích hoạt render MP4 khi đủ điều kiện.

### Modified Capabilities
- Không có capability đã archive cần sửa trực tiếp. Capability mới dùng output của auto-run prompt/voice/SRT và render timeline hiện có.

## Impact

- Backend: thêm service/job cho external clip generation, persistence session/job, download watcher, import clip từ file provider vào `video_shot_clips`, guard active job và lỗi tiếng Việt.
- Browser automation/runtime: cần cơ chế launch Chrome profile riêng hoặc attach profile đã cấu hình; ưu tiên browser thật có UI, không headless login Google.
- Storage: thêm thư mục profile/session cấu hình ở app data, thư mục download tạm theo job/run, cleanup file tạm sau khi import clip thành artifact project.
- API: endpoint cấu hình Chrome/Veo session, kiểm tra session, start/status/cancel/retry clip generation job và optional auto-render khi đủ clip.
- Frontend: mở rộng AI Video Assistant với panel cấu hình phiên Veo/Chrome, trạng thái đăng nhập, danh sách shot cần tạo clip, progress download/import/render và action mở Chrome đăng nhập lại.
- Security/privacy: không persist credential/cookie trong DB, redaction log, cảnh báo người dùng dùng Chrome profile riêng cho Voicebox thay vì profile cá nhân chính.
- Tests/QA: thêm backend tests cho state machine, download watcher/import clip, session invalid/re-auth, retry idempotent, render handoff; manual QA với Chrome profile thật và tài khoản Veo đã đăng nhập.
