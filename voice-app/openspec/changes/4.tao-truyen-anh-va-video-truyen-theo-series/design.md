## Tổng quan thiết kế

Change này thiết kế một xưởng tạo và render sản phẩm theo series, không thiết kế website công khai cho độc giả.

```text
Tạo hoặc chọn series
      |
      v
Chọn series_mode
image_story_only / video_story_only / hybrid
      |
      +--> video_story_only
      |      |
      |      v
      |   AI Video hiện có --> MP4
      |
      +--> image_story_only hoặc hybrid
             |
             v
      Story Studio phát triển nội dung
             |
             v
      Đúng 3 hướng kịch bản
             |
             v
      Chọn/tổng hợp và duyệt Master Story
             |
             +--> Panel + prompt ảnh
             |        |
             |        v
             |    Người dùng duyệt prompt
             |        |
             |        +--> Chưa có provider: lưu/export prompt
             |        |
             |        +--> Có provider + người dùng bấm render: tạo ảnh
             |
             +--> Handoff sang AI Video --> MP4
```

Series `hybrid` dùng chung Series Bible, Hồ sơ nhân vật và memory. Khi một tập tạo cả truyện ảnh lẫn video, hai sản phẩm phải xuất phát từ cùng một Master Story Episode đã duyệt.

## Quyết định

### 1. Story Studio là workspace tạo sản phẩm, không phải website độc giả

Route `/stories` hiện phục vụ story/TTS cũ. Story Studio dùng route riêng, dự kiến `/story-studio`, để quản lý Story Episode, ba hướng kịch bản, Master Story và Image Story Adaptation.

Change này chỉ tạo hoặc render artifact nội bộ:

- prompt và ảnh panel cho truyện ảnh;
- AI Video project liên kết và MP4 do pipeline hiện có tạo.

Change này không thêm trang đọc truyện, public player, catalog, SEO hoặc mạng xã hội.

### 2. Series có ba chế độ rõ ràng

Mở rộng `VideoSeries` hiện có bằng trường:

```text
series_mode = image_story_only | video_story_only | hybrid
```

Ý nghĩa:

- `image_story_only`: Series truyện ảnh dùng Story Studio; không yêu cầu AI Video project.
- `video_story_only`: Series video tiếp tục dùng luồng AI Video hiện có; không bắt buộc tạo Story Episode trong Story Studio.
- `hybrid`: Series truyện + video tạo tập mới từ Story Studio; tập có thể xuất truyện ảnh, video hoặc cả hai, và nhánh video luôn được handoff từ Master Story đã duyệt.

`series_mode` là phạm vi của series, còn `output_intent` là mục tiêu của một Story Episode:

- series `image_story_only` chỉ chấp nhận `output_intent = truyen_anh`;
- series `video_story_only` tạo episode trực tiếp trong AI Video nên không dùng `output_intent` của Story Episode;
- series `hybrid` cho phép `truyen_anh`, `video_truyen` hoặc `ca_hai`.

Series AI Video hiện có được migration mặc định thành `video_story_only` để không thay đổi hành vi cũ. Việc cho phép đổi `series_mode` sau khi series đã có sản phẩm cần được người dùng chốt riêng trước khi implementation.

### 3. Hồ sơ nhân vật có cấu trúc dùng chung cho cả hai luồng

Không tạo một bộ nhân vật cho Story Studio và một bộ khác cho AI Video. Mỗi series có danh sách `SeriesCharacterProfile` dùng chung:

```text
SeriesCharacterProfile
  id
  series_id
  name
  role
  face_description
  hair_description
  body_description
  signature_outfit
  personality
  speech_style
  fixed_traits
  additional_notes
  sort_order
```

Trong đó:

- `fixed_traits` chứa những điều AI không được tự thay đổi;
- trang phục, cảm xúc hoặc tình trạng riêng của từng tập có thể nằm trong Story Episode/Video Project, không ghi đè đặc điểm cố định của nhân vật;
- Story Studio dùng các profile này khi viết truyện và tạo prompt ảnh;
- AI Video dùng cùng profile khi phát triển story, scene, shot và prompt video.

`character_bible` dạng văn bản cũ vẫn được giữ để tương thích. Hệ thống có thể đề xuất tách nội dung cũ thành các thẻ nhân vật, nhưng chỉ lưu thẻ sau khi người dùng duyệt; không tự động xoá hoặc ghi đè Character Bible cũ.

`VideoSeries.character_bible` là ghi chú chung/fallback của series. `VideoProject.character_bible` chỉ là context riêng của một project video và MUST NOT được xem là nguồn chuẩn hoặc tự đồng bộ ngược để ghi đè Hồ sơ nhân vật cấp series.

AI có thể đề xuất cập nhật Hồ sơ nhân vật hoặc continuity sau một tập. Mọi thay đổi vào dữ liệu series phải được người dùng duyệt.

### 4. Database là nguồn chuẩn, series-memory.md là bản dựng

Hiện `series-memory.md` được dựng lại từ `VideoSeries` và `VideoProject`. Khi thêm Story Studio, không được để nhiều luồng append trực tiếp vào cùng file vì lần sync sau có thể ghi đè dữ liệu.

Thiết kế mới:

- database lưu Series Bible, `SeriesCharacterProfile`, Story Episode đã duyệt và Video Project;
- một service duy nhất dựng `series-memory.md`;
- memory v2 bao gồm mode của series, Hồ sơ nhân vật, episode index của Story Studio, episode index của AI Video và summary đã duyệt;
- Story Studio và AI Video chỉ yêu cầu sync thông qua service chung, không tự ghi trực tiếp vào file;
- khi file chưa tồn tại hoặc là bản v1, service có thể dựng lại từ database mà không mất dữ liệu gốc.

### 5. Chọn output intent trước khi Story Studio viết

`output_intent` là input bắt buộc của bước AI phát triển trong Story Studio:

- `truyen_anh`: ưu tiên panel rõ, khoảnh khắc hình ảnh mạnh, caption ngắn và prompt ảnh dễ render;
- `video_truyen`: ưu tiên hook, motion beat, scene/shot pacing, narration, retention, SFX và transition;
- `ca_hai`: cân bằng visual anchor cho ảnh và motion beat cho video.

Hệ thống phải kiểm tra `output_intent` có phù hợp với `series_mode` trước khi bắt đầu AI.

### 6. Story Studio tạo đúng 3 hướng kịch bản

```text
series-memory.md
+ Hồ sơ nhân vật
+ source input
+ series_mode
+ output_intent
+ market/language
  -> creative brief
  -> đúng 3 scenario candidates
  -> scoring review theo intent
  -> winner hoặc synthesis
  -> Master Story Episode
```

Ba hướng mặc định:

- hook/retention mạnh;
- cảm xúc/drama mạnh;
- visual/action mạnh.

Mỗi candidate phải có strategy, hook, logline, nội dung chính, key beats, visual moments, motion beats, strengths và risks. Rubric thay đổi theo `output_intent`.

### 7. Master Story phải được duyệt trước khi tạo adaptation

Master Story Episode có cấu trúc:

- `title`;
- `logline`;
- `hook`;
- `full_story`;
- `key_beats`;
- `character_emotions`;
- `visual_moments`;
- `motion_beats`;
- `retention_plan`;
- `market_profile`;
- `language_profile`;
- `must_have`;
- `avoid`;
- `continuity_updates`;
- `image_story_notes`;
- `video_story_notes`.

Chỉ sau khi người dùng duyệt Master Story, hệ thống mới cho tạo Image Story Adaptation hoặc handoff sang AI Video. Nếu Master Story thay đổi sau đó, approval phải bị huỷ và quay lại chờ duyệt; adaptation liên quan được đánh dấu stale. Cách giữ nhiều phiên bản và cách tạo lại sản phẩm sẽ được chốt sau.

### 8. Prompt ảnh phải được duyệt trước khi render

Image Story Adaptation gồm danh sách panel. Mỗi panel cần:

```text
ImageStoryPanel
  order
  purpose
  caption_or_dialogue
  visual_description
  prompt
  negative_prompt
  character_consistency_notes
  style_notes
  aspect_ratio
  prompt_status
  render_status
```

Trạng thái tối thiểu:

- `prompt_status`: `draft | pending_approval | approved | stale`;
- `render_status`: `not_requested | waiting_provider | queued | rendering | completed | failed`.

Quy tắc:

- prompt chưa được duyệt không được gửi sang image provider;
- người dùng có thể duyệt từng prompt hoặc duyệt toàn bộ prompt hợp lệ;
- sửa nội dung một prompt đã duyệt phải đưa prompt đó về `pending_approval` và chặn render mới cho tới khi được duyệt lại;
- nếu chưa có provider/API key, prompt đã duyệt chuyển sang `waiting_provider`, vẫn được lưu và export;
- khi provider được cấu hình, hệ thống không tự render;
- chỉ khi người dùng bấm render, các prompt đã duyệt mới được đưa vào hàng đợi;
- UI không được báo có ảnh thành công khi mới chỉ có prompt.

Prompt mặc định là provider-neutral. Adapter provider có thể chuyển đổi prompt khi render nhưng không được làm mất các ràng buộc nhân vật và style.

### 9. Video tiếp tục dùng pipeline AI Video hiện có

Story Studio không duplicate shot breakdown, prompt video, voice, subtitle, Veo/Chrome hoặc render MP4.

Khi tạo Video Story Adaptation từ Master Story đã duyệt, hệ thống tạo hoặc mở AI Video project liên kết:

- cùng `series_id`;
- cùng episode metadata;
- reference tới `story_episode_id`;
- source blocks từ Master Story;
- Hồ sơ nhân vật dùng chung;
- target language, market profile, style, retention, sound và motion notes.

`StoryAdaptation.linked_video_project_id` cho phép quay lại đúng AI Video project. Khi pipeline hiện có render hoàn tất, Story Studio hiển thị trạng thái hoàn tất và liên kết tới MP4; Story Studio không tạo một renderer video thứ hai.

Series `video_story_only` vẫn có thể tạo episode trực tiếp trong AI Video và vẫn phải dùng Hồ sơ nhân vật chung của series.

### 10. Provider boundary

Các vai trò được tách:

- planning/content provider: viết, chấm điểm, tổng hợp và tạo prompt;
- image provider: chỉ nhận prompt ảnh đã duyệt khi người dùng chủ động render;
- video provider: tiếp tục nằm trong pipeline AI Video hiện có.

Không dùng cookie extraction làm nền tảng provider. Nếu cần browser automation, phải dùng profile/session riêng, redaction và user login thủ công theo nguyên tắc hiện có.

### 11. UI phản ánh đúng mode và trạng thái

Khi tạo series, UI hiển thị ba lựa chọn dễ hiểu:

- Series truyện ảnh;
- Series video;
- Series truyện + video.

UI chỉ hiển thị hành động phù hợp với mode. Màn Hồ sơ nhân vật phải dùng chung ở khu vực quản lý series và khả dụng từ cả Story Studio lẫn AI Video.

Với truyện ảnh, UI tách rõ:

- nội dung đã duyệt;
- panel/prompt đang chờ duyệt;
- prompt đã duyệt nhưng chưa có dịch vụ tạo ảnh;
- đang render;
- ảnh hoàn tất, stale hoặc lỗi.

Với video, UI đưa người dùng về đúng AI Video project và hiển thị khi MP4 đã hoàn tất.

## Khái niệm dữ liệu

```text
VideoSeries
  id
  title
  series_mode
  character_bible legacy
  world_bible
  style_bible
  continuity_rules
  negative_rules
  previous_episode_summary

SeriesCharacterProfile
  id
  series_id
  structured character fields

StoryEpisode
  id
  series_id
  episode_number
  title
  output_intent
  market_profile
  language_profile
  source_digest
  master_story_json
  approval_status
  approved_at

StoryScenarioCandidate
  id
  story_episode_id
  strategy_type
  script_json
  score_json
  strengths
  risks
  selected

StoryAdaptation
  id
  story_episode_id
  kind = image_story | video_story
  status
  payload_json
  linked_video_project_id nullable
```

Core identity, relationship, approval và status nên được lưu bằng bảng có foreign key. Structured creative documents và provider-specific payload có thể nằm trong JSON đã validate.

## Rủi ro và giảm thiểu

- Rủi ro: mode mới làm hỏng series video cũ. Giảm thiểu: migration series cũ thành `video_story_only` và giữ API cũ hoạt động.
- Rủi ro: Story Studio và AI Video tạo hai hồ sơ nhân vật khác nhau. Giảm thiểu: một danh sách `SeriesCharacterProfile` dùng chung theo `series_id`.
- Rủi ro: Character Bible cũ bị mất khi chuyển sang thẻ nhân vật. Giảm thiểu: giữ nguyên dữ liệu cũ; chuyển đổi chỉ tạo bản đề xuất cần người dùng duyệt.
- Rủi ro: AI tự sửa nhân vật hoặc continuity. Giảm thiểu: AI chỉ đề xuất; người dùng duyệt trước khi lưu vào series.
- Rủi ro: nhiều service ghi đè `series-memory.md`. Giảm thiểu: database là nguồn chuẩn và chỉ một service dựng memory.
- Rủi ro: phát sinh chi phí ảnh ngoài ý muốn. Giảm thiểu: bắt buộc duyệt prompt và bấm render thủ công.
- Rủi ro: UI báo nhầm đã render ảnh. Giảm thiểu: tách `prompt_status` và `render_status`.
- Rủi ro: Story Studio trùng pipeline video. Giảm thiểu: chỉ handoff và liên kết MP4 từ AI Video.

## Migration plan

1. Thêm `series_mode` vào series; gán series hiện có thành `video_story_only`.
2. Thêm storage/API cho `SeriesCharacterProfile`, giữ nguyên `character_bible` cũ.
3. Thêm model cho Story Episode, Scenario Candidate, Story Adaptation và trạng thái panel/prompt.
4. Nâng service `series-memory.md` lên projection v2 từ database, bao gồm cả Story Studio và AI Video.
5. Thêm API chọn mode khi tạo series, quản lý Hồ sơ nhân vật, Story Episode, candidate, approval, prompt approval và image render request.
6. Thêm route `/story-studio` và màn quản lý Hồ sơ nhân vật dùng chung.
7. Thêm handoff sang AI Video và liên kết trạng thái/kết quả MP4.
8. Thêm tests cho migration series cũ, ba mode, Hồ sơ nhân vật, memory, prompt approval, thiếu provider và video handoff.

## Điểm cần người dùng chốt tiếp

- Có cho phép đổi `series_mode` sau khi series đã có tập hoặc sản phẩm hay không.
- Khi ảnh chưa đạt, có cho render lại riêng từng panel và giữ nhiều ảnh để chọn hay không.
- Khi Master Story thay đổi, tạo phiên bản mới hay chỉ dùng cảnh báo stale và tạo lại thủ công.
- Khi video đã có MP4 nhưng truyện thay đổi, cập nhật project cũ hay tạo video project mới.
- Chính sách giữ/xoá prompt, ảnh thử, MP4 và các sản phẩm cũ.
- Có thêm ảnh tham chiếu cố định cho từng nhân vật trong Hồ sơ nhân vật hay không.
