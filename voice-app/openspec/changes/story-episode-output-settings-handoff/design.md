## Approach

Store Story Episode production preferences in a single `output_settings_json` column. This avoids a wide migration and keeps the contract extensible for image/story/video options that may grow.

The backend normalizes settings at create/update/response time:

- `image.panel_mode`: `auto` or `manual`
- `image.panel_count`: optional manual panel count
- `image.aspect_ratio`, `image.width`, `image.height`
- `video.aspect_ratio`, `video.target_language`, `video.dialogue_mode`, `video.narration_density`, `video.video_purpose`
- `video.prompt_segment_count`, `video.prompt_segment_duration_seconds`, `video.micro_scenes_per_prompt`
- `video.handoff_only`: defaults to `true`

Image panel generation chooses panel count as follows:

1. If manual panel count is set, use that count.
2. If a linked AI Video project already has shots and micro-scenes, use the number of micro-scenes.
3. If a linked AI Video project has shots but no micro-scenes, use shot count.
4. Otherwise derive from Master Story beats/visual/motion moments.

Video handoff uses Story Episode video settings when creating the linked AI Video project. The handoff creates the project and source blocks only; it does not start story development, shot generation, prompts, clips, voice, subtitle or render.

## Tradeoffs

- A JSON settings column is less queryable than separate columns, but it is safer for this fast-moving single-user workflow and avoids repeated schema churn.
- Manual panel count can create more prompts than the Master Story has beats. The backend maps available story rows cyclically with panel numbering, so users can intentionally request long scroll episodes.
- Full micro-scene image generation from video shots depends on creating the video adaptation and generating shots first. If shots do not exist yet, Story Studio still produces a complete configurable image adaptation from Master Story.
