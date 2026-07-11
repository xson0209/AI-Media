## ADDED Requirements

### Requirement: Tạo retention map có cấu trúc cho AI Video phase 2
Hệ thống SHALL tạo retention map có cấu trúc cho AI Video phase 2 để xác định hook, curiosity gap, nhịp beat, pattern interrupt, payoff và rủi ro người xem rời video.

#### Scenario: Tạo retention map sau khi phát triển story
- **WHEN** AI phát triển story cho một project phase 2
- **THEN** hệ thống lưu retention map gồm hook trong 0-2 giây đầu, viewer question, curiosity gap, beat curve, pattern interrupts, payoff plan và drop-off risks

#### Scenario: Retention map theo thời lượng video
- **WHEN** project có `target_duration_seconds`
- **THEN** retention map SHALL chia beat theo timeline của video và không tạo beat vượt quá thời lượng mục tiêu

#### Scenario: Retention map cho project không có thời lượng mục tiêu
- **WHEN** project chưa có `target_duration_seconds`
- **THEN** hệ thống SHALL tạo retention map theo thứ tự scene hoặc shot dự kiến và ghi rõ thời lượng là auto

#### Scenario: Bản review tiếng Việt của retention map
- **WHEN** hệ thống hiển thị hoặc export retention map
- **THEN** người dùng SHALL thấy bản tiếng Việt tự nhiên giải thích hook, nhịp giữ chân, pattern interrupt và payoff

### Requirement: Shot breakdown kế thừa retention role và camera grammar
Hệ thống SHALL mở rộng shot hoặc segment breakdown để mỗi shot có vai trò giữ chân người xem, lý do cắt dựng, visual surprise và camera grammar chống lặp.

#### Scenario: Shot có retention role
- **WHEN** AI tạo shot breakdown từ story đã duyệt
- **THEN** mỗi shot hoặc segment SHALL có retention role như cold open, setup, build-up, reveal, pattern interrupt, climax, payoff hoặc CTA

#### Scenario: Shot có cut reason
- **WHEN** một shot có shot tiếp theo
- **THEN** hệ thống SHALL lưu cut reason mô tả vì sao cần chuyển cảnh tại điểm đó, ví dụ theo hành động, cảm xúc, âm thanh, reveal hoặc nhịp narration

#### Scenario: Camera grammar chống lặp
- **WHEN** một scene hoặc chuỗi segment có nhiều hơn một shot
- **THEN** hệ thống SHALL kiểm tra shot type, camera angle, framing, composition và camera motion để tránh lặp cùng một bố cục hoặc góc máy quá nhiều

#### Scenario: Pattern interrupt trong đoạn dài
- **WHEN** một đoạn video dài hơn 8 giây hoặc một segment 10 giây được tạo
- **THEN** shot breakdown SHALL có ít nhất một pattern interrupt hoặc visual surprise phù hợp nội dung để giảm rủi ro người xem rời video

#### Scenario: Shot locked không bị regenerate
- **WHEN** người dùng regenerate shot breakdown theo batch
- **THEN** hệ thống MUST giữ nguyên retention role, camera grammar, transition và sound design của các shot đã khóa

### Requirement: Tạo transition pack có cấu trúc
Hệ thống SHALL tạo transition pack cho shot hoặc segment để mô tả loại chuyển cảnh, trigger, timing, lý do dựng, SFX đi kèm và rủi ro continuity.

#### Scenario: Transition pack cho shot có shot tiếp theo
- **WHEN** shot không phải shot cuối cùng của video
- **THEN** hệ thống SHALL tạo transition pack gồm transition type, transition trigger, timing, edit reason, transition SFX và continuity risk

#### Scenario: Transition cuối video
- **WHEN** shot là shot cuối cùng của video
- **THEN** transition pack SHALL mô tả final hold, payoff frame, CTA hoặc kết thúc âm thanh thay vì yêu cầu chuyển sang shot tiếp theo

#### Scenario: Transition không phá continuity
- **WHEN** hệ thống tạo transition pack
- **THEN** transition pack MUST không thay đổi nhân vật, trang phục, bối cảnh, story state hoặc phong cách đã khóa trong continuity bible

#### Scenario: Transition gắn với narration hoặc sound cue
- **WHEN** transition được kích hoạt bởi lời đọc hoặc âm thanh
- **THEN** transition pack SHALL ghi rõ trigger theo từ khóa narration, beat âm thanh, silence drop, riser, impact hoặc hành động visual

### Requirement: Tạo sound design plan cho project và shot
Hệ thống SHALL tạo sound design plan để mô tả nhạc nền, ambience, SFX, silence drop, impact/riser/whoosh và mixing notes cho AI Video phase 2.

#### Scenario: Sound design plan toàn project
- **WHEN** AI tạo creative direction cho project phase 2
- **THEN** hệ thống SHALL lưu project-level sound design gồm music mood, energy curve, ambience bed, peak moments và nguyên tắc mix dưới voice

#### Scenario: Sound cue theo shot
- **WHEN** AI tạo shot hoặc segment có hành động, reveal, transition hoặc payoff
- **THEN** shot SHALL có sound cues phù hợp như whoosh, riser, impact hit, crowd swell, room tone, glitch, silence drop hoặc ambience change

#### Scenario: Sound design không che narration
- **WHEN** shot có narration hoặc dialogue
- **THEN** sound design plan MUST có mixing notes yêu cầu voice rõ hơn music/SFX và tránh cue dày trong lúc có lời quan trọng

#### Scenario: Shot không lời dùng âm thanh để giữ nhịp
- **WHEN** shot không có narration
- **THEN** sound design plan SHALL mô tả ambience, SFX hoặc music movement giúp shot không bị cảm giác trống nếu phù hợp nội dung

#### Scenario: Render chưa có asset SFX thật
- **WHEN** hệ thống chưa có file BGM hoặc SFX để mix vào MP4
- **THEN** sound design plan SHALL được hiển thị và export như chỉ dẫn dựng, không được báo sai rằng MP4 đã có SFX/BGM thật

### Requirement: Prompt video phản ánh retention, transition và sound design
Hệ thống SHALL đưa creative direction đã duyệt vào prompt video và bản giải thích tiếng Việt mà không làm nhiễu prompt copy chính.

#### Scenario: Prompt video có creative direction
- **WHEN** hệ thống tạo prompt video cho một shot hoặc segment
- **THEN** prompt SHALL bao gồm chỉ dẫn phù hợp về retention role, visual surprise, camera grammar, transition intent và sound design cue nếu các yếu tố đó liên quan tới tool video hoặc editor

#### Scenario: Prompt gốc không trộn bản dịch tiếng Việt
- **WHEN** hệ thống lưu field prompt gốc để copy sang công cụ tạo video
- **THEN** field prompt MUST NOT trộn bản giải thích tiếng Việt hoặc nội dung review tiếng Việt vào prompt gốc

#### Scenario: Bản giải thích tiếng Việt đầy đủ
- **WHEN** hệ thống tạo `prompt_explanation_vi`
- **THEN** bản giải thích SHALL mô tả nội dung visual, camera, transition, sound cue, retention purpose và ngôn ngữ người xem nếu có

#### Scenario: Negative prompt tránh lỗi làm giảm retention
- **WHEN** hệ thống tạo negative prompt
- **THEN** negative prompt SHALL tránh text overlay không mong muốn, subtitle sai, watermark, logo, mặt/tay méo, flicker, camera shake bất thường, extra people và lỗi visual có thể làm người xem mất tập trung

### Requirement: Kiểm tra retainability quality gate
Hệ thống SHALL kiểm tra chất lượng giữ chân người xem trước khi coi shot hoặc prompt video là sẵn sàng.

#### Scenario: Hook yếu trong đầu video
- **WHEN** retention map hoặc prompt đầu tiên không có hook rõ trong 0-2 giây đầu
- **THEN** quality gate SHALL đánh dấu lỗi hoặc cảnh báo hook yếu và yêu cầu regenerate hoặc chỉnh thủ công trước khi export được coi là đạt

#### Scenario: Đoạn quá tĩnh
- **WHEN** một segment dài hơn ngưỡng cấu hình mà không có thay đổi camera, visual surprise, transition hoặc sound cue
- **THEN** quality gate SHALL đánh dấu rủi ro static span để người dùng regenerate hoặc bổ sung nhịp dựng

#### Scenario: Lặp camera quá nhiều
- **WHEN** nhiều shot liên tiếp dùng cùng shot type, camera angle, framing và camera motion
- **THEN** quality gate SHALL đánh dấu repeated camera risk và không coi variation là đạt nếu vượt ngưỡng hard-fail

#### Scenario: Âm thanh quá dày
- **WHEN** sound design cue chồng lên narration quan trọng hoặc thiếu mixing notes
- **THEN** quality gate SHALL đánh dấu audio clutter risk và yêu cầu bổ sung mixing notes hoặc giảm cue

#### Scenario: Quality check được trả về API
- **WHEN** frontend tải project, shot hoặc prompt detail
- **THEN** API SHALL trả retainability quality check để UI hiển thị checklist tiếng Việt chỉ rõ thiếu hook, camera, transition, sound hoặc payoff

### Requirement: Validate và normalize output Codex trước khi lưu
Hệ thống SHALL parse, normalize và validate output Codex cho retention, shot, transition, sound và prompt trước khi lưu bất kỳ artifact mới nào.

#### Scenario: Codex trả JSON đúng schema
- **WHEN** Codex trả JSON object hợp lệ theo output schema
- **THEN** hệ thống SHALL validate bằng Pydantic, chạy quality gate và chỉ commit dữ liệu sau khi tất cả bước bắt buộc pass

#### Scenario: Codex trả alias phổ biến
- **WHEN** Codex trả field alias như `beat_curve`, `retention_beats`, `sfx`, `sound_cues`, `transition`, `edit_transition` hoặc `camera_movement`
- **THEN** hệ thống SHALL normalize alias đó về field chính trước khi validate schema

#### Scenario: Codex trả JSON sai định dạng
- **WHEN** Codex trả markdown, prose, JSON không parse được hoặc object thiếu list bắt buộc
- **THEN** hệ thống MUST không lưu artifact mới, MUST trả lỗi tiếng Việt rõ ràng và MUST log debug event có raw field types, normalized field types nếu có, validation errors và step name

#### Scenario: Codex trả thiếu field bắt buộc
- **WHEN** Codex trả output parse được nhưng thiếu hook, retention beat, transition pack, sound cue, prompt field hoặc quality field bắt buộc
- **THEN** hệ thống MUST fail validation, không xóa artifact cũ đã completed và không đánh project là ready sai

#### Scenario: Retry không làm hỏng dữ liệu cũ
- **WHEN** bước Codex retry nhiều lần nhưng cuối cùng vẫn fail validation
- **THEN** hệ thống SHALL giữ nguyên story, shot, prompt, voice, subtitle, package và render artifact cũ đang hợp lệ

### Requirement: Export creative direction trong package và render manifest
Hệ thống SHALL đưa retention, transition và sound design vào package/export hoặc render manifest để người dùng tiếp tục dựng video ngoài Voicebox.

#### Scenario: Package phase 2 có creative direction
- **WHEN** người dùng export ZIP phase 2 cho project có retention/sound direction
- **THEN** package SHALL chứa retention map, shot list có transition pack, sound design cues, quality notes và bản giải thích tiếng Việt

#### Scenario: Prompt download có section rõ ràng
- **WHEN** người dùng tải prompt cho một shot hoặc segment
- **THEN** file prompt SHALL tách rõ prompt gốc, negative prompt, retention notes, transition notes, sound design notes và bản giải thích tiếng Việt

#### Scenario: Render manifest có metadata dựng
- **WHEN** hệ thống tạo render timeline manifest cho project có creative direction
- **THEN** manifest SHALL bao gồm retention role, transition pack và sound design cue theo shot để hỗ trợ debug hoặc workflow render nâng cao sau này

#### Scenario: Project cũ không có creative direction
- **WHEN** người dùng export hoặc render project phase 2 cũ chưa có retention/sound direction
- **THEN** hệ thống SHALL không crash và SHALL hiển thị trạng thái thiếu creative direction như warning hoặc action regenerate thay vì lỗi dữ liệu

### Requirement: Stale behavior khi creative direction thay đổi
Hệ thống SHALL đánh dấu stale các artifact phụ thuộc khi retention, transition hoặc sound design thay đổi.

#### Scenario: Đổi retention map project
- **WHEN** retention map hoặc beat curve của project thay đổi sau khi đã có shot hoặc prompt
- **THEN** hệ thống SHALL đánh dấu shot chưa khóa, prompt video, package và render output là stale

#### Scenario: Đổi transition hoặc sound design của shot
- **WHEN** transition pack hoặc sound design plan của một shot thay đổi
- **THEN** hệ thống SHALL đánh dấu prompt của shot đó, package và render output là stale

#### Scenario: Đổi sound design không đổi narration
- **WHEN** sound design thay đổi nhưng narration text và duration không đổi
- **THEN** hệ thống SHALL không bắt buộc tạo lại voice hoặc subtitle, nhưng SHALL đánh dấu package/render metadata là stale

#### Scenario: Đổi narration vẫn ảnh hưởng audio workflow
- **WHEN** regenerate creative direction làm thay đổi narration hoặc duration của shot
- **THEN** hệ thống SHALL giữ behavior hiện có là đánh dấu voice, subtitle, prompt, package và render output cần tạo lại hoặc kiểm tra lại
