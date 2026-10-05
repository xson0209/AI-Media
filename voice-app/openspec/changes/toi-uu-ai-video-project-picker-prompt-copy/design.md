## Design direction

Use the existing card, button, dialog, and muted token vocabulary. The primary hierarchy is:

1. Current project context and quick actions.
2. Workflow form/content.
3. Prompt readiness and copy actions.

### Project picker

- Dialog width `sm:max-w-2xl`, fixed header with search and filter chips.
- Search, time preset, and exact-day controls stack on narrow screens and share one compact row on larger screens.
- Time presets are based on the local calendar date of `updated_at`; selecting an exact date takes precedence over a preset.
- Project rows are compact (title, type, status, progress) and have one clear selection target.
- Long topics are reduced to a bounded single-line summary for display while the full topic remains searchable.
- Running projects use sky tone, failed projects red, and the selected project foreground inversion.
- The body is the only scroll container in the picker.

### Prompt library

- Desktop: left shot navigator and right prompt detail pane.
- Mobile: a shot selector replaces the navigator.
- Prompt detail keeps the copy button in the header and uses one scrollable text pane.
- Fresh prompts use emerald/neutral status, stale prompts amber with `Copy bản cũ`, and missing prompts a clear generate-next-step message.

### Responsive behavior

- Hide the project rail below `xl`; render a compact context bar in the main column.
- Preserve the existing rail collapse control on desktop.
- Avoid introducing a second page-level scroll region on mobile.
- Keep every picker list/grid/row track at `min-width: 0` and hide horizontal overflow in the scroll body.
