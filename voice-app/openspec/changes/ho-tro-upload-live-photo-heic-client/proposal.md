## Context

Some users capture short inspiration moments as iPhone Live Photos or HEIC/HEIF stills instead of MP4 files. The current upload flows focus on MP4/video sources, so these assets need a clear client-side contract before implementation.

## Goals

- Define client support for selecting HEIC/HEIF image files and iPhone Live Photo assets where the platform exposes them.
- Keep validation and user-facing errors clear in Vietnamese.
- Avoid pretending a still image is a complete video source unless the app can extract a usable motion/video component.

## Non-Goals

- Do not implement server-side HEIC decoding in this change.
- Do not bypass OS photo-library permissions or platform media restrictions.
- Do not generate MP4 output from a still image without an explicit later workflow.
