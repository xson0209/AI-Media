## Requirements

### Requirement: Project switching stays discoverable

The AI Video workspace MUST expose the current project and a direct action to change it on narrow layouts without rendering the full project rail inline.

#### Scenario: Mobile project context

- **WHEN** the viewport is narrower than the desktop rail breakpoint
- **THEN** the workflow is shown before the project list
- **AND** the current project name and `Đổi dự án` action are visible.

### Requirement: Bulk copy is safe by default

The prompt library MUST copy only fresh, non-empty prompts through its default bulk action and MUST display the number of prompts being copied.

#### Scenario: Mixed prompt statuses

- **WHEN** a project has fresh, stale, and missing prompts
- **THEN** the bulk action excludes stale and missing prompts
- **AND** the UI reports the eligible count.
