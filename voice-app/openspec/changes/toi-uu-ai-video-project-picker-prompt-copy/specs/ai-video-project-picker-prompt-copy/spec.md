## MODIFIED Requirements

### Requirement: Project switching stays discoverable

The AI Video workspace MUST expose the current project and a direct action to change it on narrow layouts without rendering the full project rail inline.

#### Scenario: Mobile project context

- **WHEN** the viewport is narrower than the desktop rail breakpoint
- **THEN** the workflow is shown before the project list
- **AND** the current project name and `Đổi dự án` action are visible.

### Requirement: Project picker remains within the viewport

The project picker MUST keep its list, rows, and summaries constrained to the dialog width, including when a project contains a very long topic.

#### Scenario: Long project topic on a narrow viewport

- **WHEN** the picker is opened at a viewport width of 367px or 390px
- **AND** a project topic is thousands of characters long
- **THEN** the row remains no wider than the picker body
- **AND** the body has no horizontal overflow

## ADDED Requirements

### Requirement: Project picker supports time filtering

The project picker MUST provide both relative time presets and an exact calendar-day filter based on the project's `updated_at` value. Time filtering MUST compose with search, type, and status filters.

#### Scenario: Filter by exact updated day

- **WHEN** the user selects a calendar date
- **THEN** only projects updated on that local calendar day are shown
- **AND** the result count and selected date are visible

#### Scenario: Filter by relative time preset

- **WHEN** the user selects `Hôm nay`, `Hôm qua`, `7 ngày qua`, `30 ngày qua`, or `Cũ hơn 30 ngày`
- **THEN** projects are filtered by their local updated calendar date
- **AND** the user can still combine the preset with an existing type/status filter

### Requirement: Bulk copy is safe by default

The prompt library MUST copy only fresh, non-empty prompts through its default bulk action and MUST display the number of prompts being copied.

#### Scenario: Mixed prompt statuses

- **WHEN** a project has fresh, stale, and missing prompts
- **THEN** the bulk action excludes stale and missing prompts
- **AND** the UI reports the eligible count.
