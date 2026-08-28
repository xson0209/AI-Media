## ADDED Requirements

### Requirement: Client accepts HEIC and Live Photo inputs explicitly
The client SHALL expose a clear upload contract for HEIC/HEIF still images and iPhone Live Photo assets instead of silently treating every selected asset as an MP4 video.

#### Scenario: User selects a HEIC or HEIF still image
- **WHEN** the user selects a `.heic`, `.heif`, or matching HEIC/HEIF MIME file in a supported upload surface
- **THEN** the client SHALL either accept it for a supported still-image workflow or reject it with a Vietnamese message explaining that the current workflow needs a video component
- **AND** the client SHALL NOT submit the file to an MP4-only endpoint as if it were a video

#### Scenario: User selects an iPhone Live Photo asset without an exposed video component
- **WHEN** the platform exposes only the still-image portion of a Live Photo
- **THEN** the client SHALL explain in Vietnamese that the app cannot extract motion from that selection yet
- **AND** the client SHALL ask the user to export or upload the video component when the target workflow requires video

#### Scenario: Unsupported asset is rejected before upload artifacts are created
- **WHEN** the selected HEIC/Live Photo input is unsupported for the current workflow
- **THEN** the client SHALL stop before creating backend upload artifacts
- **AND** the user SHALL receive a clear Vietnamese reason and a suggested next action
