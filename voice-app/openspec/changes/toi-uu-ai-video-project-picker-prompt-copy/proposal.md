## Why

The AI Video workspace currently spends too much vertical space on the project sidebar and prompt cards. On mobile, the full project list appears before the workflow, and users must open a disclosure and scroll through long prompt blocks before they can copy a prompt. This makes switching projects and handing prompts to a video tool unnecessarily slow.

## What Changes

- Add a compact project context bar and a searchable project picker dialog for mobile and narrow layouts.
- Keep the desktop project rail, but show a bounded recent list and route the full list through the picker dialog.
- Surface quick actions for switching projects, opening the prompt library, and copying ready prompts.
- Rework the prompt library dialog into a shot navigator with one focused prompt viewport, explicit fresh/stale/missing states, and copy actions next to the prompt.
- Make bulk copy labels include the number of eligible prompts and keep stale prompts out of the default bulk action.
- Add compact time presets plus an exact-day date picker using each project's `updated_at` value.
- Constrain project rows and summaries so long source topics cannot create horizontal overflow on narrow viewports.

## Scope

Frontend-only change in `AIVideoAssistant.tsx`; existing API contracts, auto-run behavior, project actions, and prompt status semantics remain unchanged.

## Acceptance Criteria

- Mobile first render shows the workflow and current project context without an inline project list.
- Project picker supports search and filters for all, standalone, series, running, and failed projects; selecting a project closes the dialog.
- Project picker supports time presets (today, yesterday, last 7 days, last 30 days, older) and an exact calendar-day filter; type/status and date filters can be combined.
- Desktop sidebar still exposes running/failed projects and recent projects, with a full-list affordance.
- Prompt library copy actions are visible without opening a disclosure; default bulk copy copies only fresh prompts and reports `x/y` counts.
- Project rows remain inside the dialog width even when a project topic is thousands of characters long.
- Prompt dialog has a single primary scroll area and remains keyboard accessible at 367px, 390px, 1280px, and 1440px widths.
