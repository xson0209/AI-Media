## Context

AI Video phase 2 hiện đã có các mảnh chính:

- Auto-run tạo story, shot, prompt video, voice và `.srt`.
- Render timeline có thể dựng MP4 khi mỗi shot có clip active trong `video_shot_clips`.
- UI đã có panel upload clip thủ công và nút render MP4.
- `video_shot_clips` đã có sẵn `source`, `provider`, `provider_asset_id` và `provider_metadata`, phù hợp để lưu clip từ provider ngoài.

Khoảng trống hiện tại nằm giữa prompt và clip: người dùng phải tự mở Veo/Gemini/Flow trong Chrome, chọn đúng tài khoản Google, paste prompt, chờ tạo clip, download file và upload lại vào Voicebox. Với tài khoản Google/Veo, cố gắng login tự động hoặc dùng profile tạm sẽ làm người dùng bị hỏi đăng nhập nhiều lần, dễ gặp 2FA/CAPTCHA và có rủi ro bảo mật. Thiết kế cần coi phiên Chrome đã đăng nhập là tài sản local do người dùng quản lý.

## Goals / Non-Goals

**Goals:**
- Dùng Chrome profile riêng, bền vững, để người dùng đăng nhập Google/Veo thủ công một lần và dùng lại session đó.
- Tự chạy prompt video theo shot qua Veo bằng browser thật có UI, không yêu cầu người dùng copy/paste từng prompt.
- Tải clip về thư mục tạm theo job, map đúng clip về đúng shot và import vào `video_shot_clips`.
- Chạy resume/retry idempotent: shot đã có clip provider hợp lệ thì không tạo lại trừ khi user bật force.
- Dừng rõ ràng khi cần đăng nhập lại, hết quota, download fail hoặc provider UI thay đổi.
- Cho phép tự kích hoạt render MP4 sau khi mọi clip bắt buộc đã sẵn sàng và render readiness pass.
- UI tiếng Việt, rõ phiên tài khoản nào đang dùng và bước nào cần người dùng can thiệp.

**Non-Goals:**
- Không tự động đăng nhập Google bằng email/password.
- Không bypass CAPTCHA, 2FA, quota, paywall hoặc policy của Google/Veo.
- Không trích xuất cookie/token từ Chrome profile cá nhân mặc định.
- Không hỗ trợ nhiều provider trong MVP ngoài adapter Veo, nhưng thiết kế để thêm adapter sau.
- Không chạy nhiều browser automation job song song cùng một provider account.
- Không thay thế upload clip thủ công; upload thủ công vẫn là fallback.

## Decisions

### 1. Dùng Chrome profile riêng của Voicebox thay vì profile Chrome mặc định

Quyết định: tạo và quản lý một profile directory riêng, ví dụ trong app data:

```text
ai-video/browser-profiles/veo-chrome/
ai-video/provider-downloads/<job_id>/
```

Khi người dùng bấm “Mở Chrome đăng nhập Veo”, app launch Chrome bằng profile này. Người dùng chọn đúng Google account và hoàn tất login trong browser thật. Các lần sau job dùng lại cùng profile, nên cookie/session Google còn nguyên nếu chưa hết hạn.

Không lưu mật khẩu, token hay cookie vào database. Database chỉ lưu metadata:

- `provider`: `veo`
- `chrome_profile_path`
- `status`: `not_configured|needs_login|ready|invalid|checking`
- `verified_account_hint`: email đã mask hoặc display text đã redaction nếu đọc được từ UI
- `last_checked_at`, `failure_reason`, `created_at`, `updated_at`

Phương án khác đã cân nhắc: attach vào Chrome cá nhân đang mở. Cách đó tiện nhưng profile có thể bị lock, download bị lẫn với download cá nhân, remote debugging trên profile chính là bề mặt rủi ro lớn. Profile riêng an toàn và dễ debug hơn.

### 2. Browser automation dùng browser thật có UI, không dùng headless login

Quyết định: automation launch Chrome thật với `--user-data-dir` riêng và một remote debugging port/job hoặc dùng Playwright persistent context với Chrome channel nếu dependency được thêm. Dù implementation chọn CDP trực tiếp hay Playwright, contract là:

- browser phải có UI để người dùng xử lý login/2FA/CAPTCHA khi provider yêu cầu;
- job phải pause với `status = "needs_login"` thay vì cố vượt qua màn xác minh;
- app không nhập credential thay người dùng;
- chỉ một active automation session/provider để tránh tranh profile.

Phương án khác đã cân nhắc: headless browser đăng nhập tự động. Cách đó dễ bị Google chặn, làm người dùng đăng nhập lại nhiều hơn và khiến app phải giữ credential, nên loại khỏi scope.

### 3. Tách provider adapter khỏi job orchestration

Quyết định: thêm service orchestrator chung, ví dụ `video_clip_generation.py`, và adapter provider, ví dụ `providers/veo_chrome.py`.

Adapter chịu trách nhiệm:

- mở URL provider;
- xác minh session đang vào được trang tạo video;
- tìm input prompt, submit prompt và chọn setting tối thiểu nếu cần;
- chờ trạng thái provider chuyển sang completed hoặc lỗi;
- bắt download event hoặc phát hiện file mới trong download dir;
- trả về file path, provider asset id nếu có và metadata đã redaction.

Orchestrator chịu trách nhiệm:

- chọn shot cần tạo clip;
- lấy prompt video đã passed/completed;
- tạo item/job state;
- gọi adapter;
- import file vào `video_shot_clips`;
- retry/cancel/resume;
- gọi render job khi đủ điều kiện và user bật auto-render.

Lý do: UI Veo có thể thay đổi thường xuyên. Tách adapter giúp sửa selector/flow provider mà không làm hỏng state machine, DB, import clip hoặc render handoff.

### 4. Job theo shot, idempotent và resume được

Quyết định: thêm persistence cho clip generation:

```text
video_provider_sessions
  id, provider, status, chrome_profile_path, verified_account_hint,
  last_checked_at, failure_reason, created_at, updated_at

video_clip_generation_jobs
  id, project_id, provider, session_id, status, current_step, progress,
  force, auto_render, render_job_id, download_dir, failure_reason,
  error_code, step_results_json, started_at, completed_at, created_at, updated_at

video_clip_generation_items
  id, job_id, project_id, shot_id, prompt_id, status, attempt_count,
  provider_asset_id, downloaded_file_path, clip_id, failure_reason,
  started_at, completed_at, created_at, updated_at
```

Nếu muốn MVP nhỏ hơn, `items` có thể nằm trong JSON ở job, nhưng bảng riêng dễ poll UI, retry từng shot và test hơn. Mỗi item có trạng thái:

```text
pending -> opening_provider -> submitting_prompt -> waiting_generation
        -> downloading -> importing -> completed
        -> needs_login | failed | cancelled
```

Runner luôn đọc trạng thái thật trước khi chạy:

- shot đã có clip active `source = provider`, `provider = veo`, file tồn tại và không stale thì skip;
- item đã completed và clip còn hợp lệ thì skip;
- retry chỉ chạy lại item failed/missing/stale;
- force mới tạo lại clip đã có.

### 5. Download watcher phải map file về đúng shot bằng thư mục theo job/item

Quyết định: mỗi item dùng download directory riêng hoặc file marker riêng:

```text
provider-downloads/<job_id>/<shot_order>-<item_id>/
```

Runner chỉ nhận file hoàn tất khi:

- file không còn extension tạm như `.crdownload`;
- size ổn định qua ít nhất hai lần kiểm tra;
- MIME/extension thuộc nhóm video hỗ trợ;
- FFprobe đọc được metadata hoặc import service đánh lỗi rõ ràng.

Sau khi import thành công qua helper dùng chung với upload clip, file tạm có thể xóa hoặc giữ đến khi job terminal theo policy cleanup. `video_shot_clips.provider_metadata` chỉ lưu id/status/count/URL đã rút gọn, không lưu full DOM, cookie, token hoặc prompt dài.

Phương án khác đã cân nhắc: dùng thư mục Downloads mặc định của Chrome rồi đoán file mới nhất. Cách đó dễ map nhầm file cá nhân và khó retry, nên không phù hợp.

### 6. Render handoff dùng render readiness/job hiện có

Quyết định: sau khi mọi required shot có clip active ready, job gọi `get_render_readiness`. Nếu readiness pass và `auto_render = true`, tạo render job bằng service hiện có với settings mặc định hoặc settings từ request. Nếu readiness fail, clip generation job hoàn tất ở trạng thái `completed_with_render_blocked` hoặc `needs_input` với missing reasons tiếng Việt.

Không duplicate logic FFmpeg/render. Clip generation chỉ chịu trách nhiệm tạo/import clip.

### 7. UI có hai panel rõ: phiên Chrome và job clip

UI trong `AIVideoAssistant` nên tách component con, ví dụ `AIVideoVeoChromePanel`.

Panel phiên Chrome:

- Trạng thái: chưa cấu hình, cần đăng nhập, đã sẵn sàng, lỗi.
- Nút “Mở Chrome đăng nhập Veo”.
- Nút “Kiểm tra phiên”.
- Account hint đã mask nếu có.
- Cảnh báo dùng profile riêng, không dùng Chrome cá nhân chính.

Panel tạo clip:

- Danh sách shot/prompt/clip status.
- Nút “Tạo clip bằng Veo”.
- Tùy chọn `force` và `Tự render MP4 khi đủ clip`.
- Progress theo shot: đang gửi prompt, đang chờ Veo, đang tải, đã import, lỗi, cần đăng nhập.
- Action pause/resume/retry/cancel.
- Khi `needs_login`, đưa người dùng bấm mở Chrome, đăng nhập lại rồi resume.

Không dùng text kỹ thuật như raw status làm nội dung chính; status kỹ thuật chỉ nằm trong debug.

### 8. Observability và redaction là bắt buộc

Log event cần có:

- job id, item id, project id, shot id;
- provider, step, status, duration, error code;
- account hint đã mask;
- download filename đã sanitize;
- technical details đã truncate/redact.

Không log:

- cookie, token, local storage, credential;
- full prompt dài;
- full source/story/narration;
- full provider DOM.

## Risks / Trade-offs

- [Risk] Veo UI thay đổi selector hoặc flow upload/generate/download -> Tách provider adapter, thêm error code `VIDEO_PROVIDER_UI_CHANGED`, cho fallback mở Chrome để người dùng làm tay và vẫn upload clip thủ công.
- [Risk] Google/Veo yêu cầu đăng nhập lại hoặc 2FA -> Job chuyển `needs_login`, UI mở đúng Chrome profile và resume sau khi user xác minh.
- [Risk] Chrome profile bị lock do người dùng đang mở cùng profile -> Chỉ cho một session active, detect lock/process, hiển thị lỗi yêu cầu đóng cửa sổ Voicebox Chrome hoặc bấm reconnect.
- [Risk] Download file map nhầm shot -> Dùng download dir riêng theo job/item, không dùng Downloads mặc định.
- [Risk] Provider quota hoặc giới hạn tài khoản -> Dừng `needs_input`/`failed` với reason tiếng Việt, không retry vòng lặp vô hạn.
- [Risk] Automation có thể bị coi là vi phạm policy provider nếu lạm dụng -> Không bypass login/quota/CAPTCHA, chỉ automation thao tác người dùng có quyền làm trong browser thật; docs cần nhắc người dùng tuân thủ điều khoản provider.
- [Risk] Playwright/CDP dependency làm packaging phức tạp -> Ưu tiên dùng installed Chrome channel và không tải Chromium riêng; nếu dependency mới được thêm, task implementation phải cập nhật build/frozen verification.
- [Risk] Profile riêng vẫn chứa cookie trên filesystem -> Không đưa profile vào ZIP/debug export, không đọc cookie vào app, cảnh báo người dùng đây là dữ liệu đăng nhập local.

## Migration Plan

1. Thêm model/migration idempotent cho provider session, clip generation job và item.
2. Thêm storage subdir cho Chrome profile metadata/download tạm, hoặc helper dùng app data path ngoài project khi phù hợp.
3. Implement service session manager: open Chrome login, check session, invalidate session.
4. Implement Veo adapter tối thiểu và job runner theo shot.
5. Reuse/import clip vào `video_shot_clips` bằng helper chung với upload clip.
6. Thêm API start/status/cancel/retry/check-session/open-login.
7. Thêm UI panel tiếng Việt và docs hướng dẫn đăng nhập một lần bằng Chrome profile riêng.
8. Rollback an toàn: ẩn UI/API provider generation; clip đã import vẫn là `video_shot_clips` bình thường và render/upload thủ công tiếp tục hoạt động.

## Open Questions

- Veo URL/UI cụ thể trong tài khoản người dùng là Gemini, Flow hay một surface khác, và selector/download flow có khác nhau không?
- MVP có cần hỗ trợ batch mọi shot tự động hoàn toàn, hay nên bắt đầu bằng chạy từng shot có xác nhận để giảm rủi ro quota?
- Có cần cho người dùng chọn Chrome executable/path thủ công trên Windows/Linux/macOS không?
- Có cần lưu nhiều Chrome profile/provider account hay MVP chỉ một profile Veo duy nhất?
