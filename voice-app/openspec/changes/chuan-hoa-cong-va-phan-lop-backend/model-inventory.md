## Kiểm kê schema/model AI Video

### Pydantic schema trong `backend/models.py`

- Source/project input: `VideoSourceBlock*`, `VideoProjectCreate`, `VideoProjectUpdate`, `VideoProjectLocalizeRequest`, `VideoSeries*`, `VideoEpisodeCreate`.
- Planning/story/shot: `VideoStory*`, `VideoScene*`, `VideoShot*`, `VideoPrompt*`, `VideoShotPrompt*`, `VideoPromptContentResponse`.
- Render: `VideoRenderSettings`, `VideoRenderReadinessResponse`, `VideoRenderJob*`, `VideoRenderTimelineShot`.
- Subtitle/caption: `VideoSubtitleCue`, `VideoSubtitleResponse`.
- Packaging/export/status: `VideoPackage*`, `VideoProjectStatusResponse`, `VideoGeneratedDataResetResponse`.
- Auto-run: `VideoAutoRunStartRequest`, `VideoAutoRunContinueRequest`, `VideoAutoRunRetryRequest`, `VideoAutoRunSummary`, `VideoAutoRunResponse`.
- Resources/cache: `Resource*`, `RenderCache*`, `SystemResource*`.

### ORM model trong `backend/database/models.py`

- Project graph: `VideoProject`, `VideoSeries`, `VideoSourceBlock`, `VideoScene`, `VideoShot`.
- Generated artifacts: `VideoScenePrompt`, `VideoShotPrompt`, `VideoSceneAsset`, `VideoShotClip`, `VideoSubtitle`, `VideoRenderJob`, `VideoPackageExport`.
- Workflow state: `VideoAutoRun`, `VideoDebugEvent`, `AIPlanningSettings`.

### Quyết định áp dụng trong change này

- Chưa di chuyển class khỏi `backend/models.py` để tránh đổi import và JSON schema trong cùng một bước.
- Tạo `backend/features/ai_video/schemas.py` làm bridge domain import cho AI Video.
- Tạo `backend/features/ai_video/repository.py` làm boundary dữ liệu bước đầu, giữ `backend.database` re-export cũ cho caller hiện có.
