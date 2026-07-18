# Issue tracker: GitHub

Issue và PRD của repo này được quản lý bằng GitHub Issues. Khi máy có `gh` CLI thì dùng `gh` cho các thao tác với tracker.

## Quy ước thao tác

- Tạo issue: `gh issue create --title "..." --body "..."`.
- Đọc issue: `gh issue view <number> --comments`.
- Liệt kê issue: `gh issue list`.
- Comment vào issue: `gh issue comment <number> --body "..."`.
- Thêm hoặc gỡ nhãn: `gh issue edit <number> --add-label "..."` và `--remove-label "..."`.
- Đóng issue: `gh issue close <number> --comment "..."`.

Repo được suy ra từ `git remote -v`; khi chạy trong clone thì `gh` tự nhận repo.

## Pull request có được xem là yêu cầu triage không?

Không. Repo này chưa coi PR là một nguồn yêu cầu riêng để triage.

- Đọc PR: `gh pr view <number> --comments` và `gh pr diff <number>`.
- Comment hoặc gắn nhãn PR: dùng các lệnh tương ứng của `gh pr`.

GitHub dùng chung dãy số cho issue và PR. Vì vậy `#42` có thể là issue hoặc PR. Khi cần, thử `gh pr view 42` trước, nếu không có thì dùng `gh issue view 42`.

## Khi một skill nói "publish to the issue tracker"

Tạo một GitHub Issue.

## Khi một skill nói "fetch the relevant ticket"

Chạy `gh issue view <number> --comments`.

## Lưu ý hiện tại

Nếu máy chưa cài `gh` CLI hoặc chưa đăng nhập GitHub, hãy tạo bản nháp trong repo trước, rồi publish lên GitHub sau.
