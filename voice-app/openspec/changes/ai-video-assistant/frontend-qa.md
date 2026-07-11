## AI Video Assistant Frontend QA

Ngày kiểm tra: 2026-06-29

## Lệnh đã chạy

- `cd app && bun run typecheck` → pass
- `cd app && bunx biome lint src/components/AIVideoAssistant/AIVideoAssistant.tsx src/lib/api/client.ts src/lib/api/types.ts src/router.tsx src/components/Sidebar.tsx` → pass
- `backend/venv/bin/python -m pytest backend/tests/test_ai_video_backend.py -q` → pass, 13 tests
- `openspec validate ai-video-assistant --strict` → pass
- Vite dev server: `http://127.0.0.1:5173/`
- Route check: `curl -I http://127.0.0.1:5173/ai-video` → HTTP 200

## Visual QA Checklist

- Desktop layout: AI Video page uses split/asymmetric layout with main workflow column and right status/download/debug rail.
- Mobile layout: workflow grid collapses to one column via Tailwind responsive grid classes; no `h-screen` is used in the new page.
- Palette: neutral Voicebox base with existing muted amber accent; no neon glow, no purple/blue AI gradient treatment.
- Copy: primary wizard copy is Vietnamese-first.
- Icons: uses existing `lucide-react`; no new icon dependency was added.
- Loading state: project list/scene/status regions use skeleton rows.
- Empty state: project, scene, prompt, voice and package sections show inline empty states.
- Error state: mutation/API errors render inline in Vietnamese-friendly flow; backend also returns `error_code` and `request_id`.
- Advanced debug: debug details are hidden behind a collapsed disclosure and omit raw file paths.
- Text overlap: fixed-format controls use grid/flex wrapping and do not depend on viewport-width font scaling.

## Notes

- Playwright is not installed in this project, so no automated screenshot artifact was produced. I did not add Playwright as a new dependency for this OpenSpec change.
