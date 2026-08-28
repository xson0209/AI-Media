# Browser QA `/news-video` — 28-08-2026

- Vite dev server chạy tại `http://127.0.0.1:4000`.
- Backend chạy tại `http://127.0.0.1:17493`.
- Playwright snapshot đã kiểm tra viewport 375×800, 390×844, 1280×900 và 1440×1000.
- Route hiển thị đúng Sidebar, form nguồn tin, 5 speech modes, khung hình, shot/prompt flow, render panel và publishing metadata panel.
- Label/select có accessible name; nút project có `type="button"`.
- Clipboard/upload cần clip thật nên không tự động hoàn tất với project không có shot/MP4; flow manual được hiển thị rõ trong UI.
