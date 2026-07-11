## ADDED Requirements

### Requirement: Người dùng chọn mục đích video cho AI Video project
Hệ thống SHALL cho phép người dùng chọn một mục đích video ổn định cho AI Video phase 2 project để hệ thống gợi ý cấu hình phù hợp với audience và use case.

#### Scenario: Tạo project với mục đích thị trường Việt Nam
- **WHEN** người dùng tạo AI Video project với mục đích `Thị trường Việt Nam`
- **THEN** hệ thống lưu purpose tương ứng và gợi ý video language, voice, subtitle và thoại phù hợp với audience Việt Nam

#### Scenario: Tạo project với mục đích global short
- **WHEN** người dùng tạo AI Video project với mục đích `Global / English short`
- **THEN** hệ thống lưu purpose tương ứng và gợi ý video language, voice, subtitle và thoại phù hợp với audience quốc tế

#### Scenario: UI giải thích tác động của mục đích video
- **WHEN** người dùng nhìn thấy control `Mục đích video`
- **THEN** UI giải thích bằng tiếng Việt rằng lựa chọn này ảnh hưởng tới ngôn ngữ gợi ý, giọng đọc, thoại/narration, phụ đề và phong cách script

### Requirement: Preset mục đích gợi ý cấu hình nhưng không thay thế nguồn sự thật ngôn ngữ
Hệ thống SHALL dùng purpose preset để gợi ý cấu hình ban đầu, nhưng `target_language` SHALL vẫn là nguồn sự thật quyết định ngôn ngữ người xem nghe và đọc trong video cuối.

#### Scenario: Preset gợi ý tiếng Việt nhưng người dùng override sang tiếng Anh
- **WHEN** người dùng chọn purpose gợi ý tiếng Việt nhưng đặt `target_language = "en"`
- **THEN** hệ thống tạo story, thoại, voice, phụ đề và export bằng tiếng Anh theo `target_language`

#### Scenario: Preset gợi ý tiếng Anh nhưng người dùng override sang tiếng Việt
- **WHEN** người dùng chọn purpose gợi ý tiếng Anh nhưng đặt `target_language = "vi"`
- **THEN** hệ thống tạo story, thoại, voice, phụ đề và export bằng tiếng Việt theo `target_language`

#### Scenario: Backend không tự đổi ngôn ngữ video ngầm
- **WHEN** API update purpose của project mà không gửi `target_language`
- **THEN** hệ thống giữ nguyên `target_language` hiện tại của project

### Requirement: AI planning tạo thoại và narration theo mục đích video
Hệ thống SHALL đưa purpose, dialogue mode, narration density và `target_language` vào AI planning để tạo thoại/narration phù hợp mục đích video.

#### Scenario: Video giải thích dùng thoại rõ nghĩa
- **WHEN** AI planning phát triển story hoặc shot cho project có purpose `educational_explainer`
- **THEN** prompt yêu cầu thoại/narration rõ nghĩa, dễ nghe, đủ ngữ cảnh và đúng ngôn ngữ video

#### Scenario: Video quảng cáo dùng hook và CTA
- **WHEN** AI planning phát triển story hoặc shot cho project có purpose `sales_ad`
- **THEN** prompt yêu cầu thoại/narration có hook, lợi ích chính, nhịp cô đọng và CTA phù hợp, đồng thời đúng ngôn ngữ video

#### Scenario: Video cần câu thoại nhân vật
- **WHEN** project dùng dialogue mode `character_lines` hoặc `mixed`
- **THEN** AI planning tạo câu thoại tự nhiên cho nhân vật hoặc người nói trong giới hạn scope một voice track hiện có

#### Scenario: Project voiceover-only không tạo thoại nhân vật ngoài ý muốn
- **WHEN** project dùng dialogue mode `voiceover`
- **THEN** AI planning ưu tiên narration/voiceover và không bắt buộc tạo các câu thoại nhân vật riêng

### Requirement: Chuẩn hoá context gửi Codex cho purpose và thoại
Hệ thống SHALL chuẩn hoá AI Video project context trước khi gửi Codex để story development, shot breakdown và video prompt generation dùng cùng một contract về purpose, ngôn ngữ video và thoại/narration.

#### Scenario: Context gửi Codex có field purpose và dialogue chuẩn
- **WHEN** hệ thống gọi Codex cho story, shot hoặc prompt của AI Video project có purpose và dialogue settings
- **THEN** prompt context chứa purpose, `target_language`, dialogue mode và narration density ở dạng đã normalize

#### Scenario: Source blocks gửi Codex được chuẩn hoá
- **WHEN** project có nhiều source blocks trước khi gọi Codex
- **THEN** hệ thống gửi source blocks theo thứ tự ổn định, bỏ nội dung rỗng, trim text và không làm mất block type

#### Scenario: Series context gửi Codex được chuẩn hoá an toàn
- **WHEN** project thuộc series có Series Bible dài hoặc thiếu field
- **THEN** hệ thống gửi series context đã truncate/log an toàn và vẫn giữ các field cốt lõi có sẵn cho Codex

#### Scenario: Purpose preset không làm prompt mâu thuẫn target language
- **WHEN** purpose gợi ý một ngôn ngữ nhưng project có `target_language` khác do người dùng override
- **THEN** context gửi Codex MUST ưu tiên `target_language` và không yêu cầu viewer-facing speech/subtitle bằng ngôn ngữ khác

### Requirement: Chuẩn hoá output Codex cho purpose, thoại và alias tương thích
Hệ thống SHALL chuẩn hoá dữ liệu Codex trả về trước khi validate hoặc ghi DB, bao gồm alias purpose/dialogue/narration và conflict detection rõ ràng.

#### Scenario: Codex trả alias purpose
- **WHEN** Codex trả purpose bằng alias như `purpose`, `project_purpose`, `audience_purpose` hoặc `use_case`
- **THEN** hệ thống map giá trị đó về field purpose chuẩn nếu không có mâu thuẫn

#### Scenario: Codex trả alias dialogue mode hoặc narration density
- **WHEN** Codex trả dialogue mode hoặc narration density bằng alias như `voice_mode`, `speech_mode`, `narration_mode`, `voiceover_density` hoặc `talk_density`
- **THEN** hệ thống map giá trị đó về field chuẩn trước khi validate

#### Scenario: Codex trả alias narration text
- **WHEN** Codex trả thoại/narration bằng alias như `narration`, `voiceover`, `voiceover_text`, `dialogue` hoặc `spoken_narration`
- **THEN** hệ thống map text đó vào narration field tương thích theo ngôn ngữ video đã chọn

#### Scenario: Codex trả alias mâu thuẫn
- **WHEN** Codex trả nhiều alias cùng nghĩa nhưng nội dung khác nhau cho purpose, dialogue mode, narration density hoặc narration text
- **THEN** hệ thống từ chối output bằng lỗi mapping rõ ràng và không ghi artifact mới vào DB

#### Scenario: Log raw và normalized output khi validation fail
- **WHEN** output Codex không validate sau bước normalize
- **THEN** hệ thống ghi thông tin debug gồm raw field types, normalized field types và validation errors đã redaction phù hợp

### Requirement: Tạo voice dùng thoại đúng ngôn ngữ và cảnh báo voice không phù hợp
Hệ thống SHALL tạo voice từ thoại/narration đã sinh theo `target_language`, và MUST cảnh báo hoặc từ chối rõ ràng nếu voice profile, engine hoặc model không hỗ trợ ngôn ngữ video.

#### Scenario: Purpose tiếng Việt với voice không hỗ trợ tiếng Việt
- **WHEN** project có `target_language = "vi"` nhưng voice profile hoặc engine đã chọn không hỗ trợ tiếng Việt
- **THEN** UI hoặc backend báo lỗi tiếng Việt rõ ràng trước hoặc trong bước tạo voice, và không fallback sang tiếng Anh

#### Scenario: Purpose tiếng Anh với voice hỗ trợ tiếng Anh
- **WHEN** project có `target_language = "en"` và voice profile hoặc engine hỗ trợ tiếng Anh
- **THEN** hệ thống gửi thoại/narration tiếng Anh vào TTS pipeline với language `en`

#### Scenario: Đổi voice không làm đổi purpose hoặc target language
- **WHEN** người dùng đổi voice profile của project
- **THEN** hệ thống không tự đổi purpose hoặc `target_language`, nhưng SHALL cập nhật cảnh báo compatibility nếu voice mới không phù hợp

### Requirement: Đổi mục đích hoặc cấu hình thoại làm stale artifact phụ thuộc
Hệ thống SHALL đánh dấu artifact phụ thuộc là stale khi purpose, dialogue mode hoặc narration density thay đổi theo cách ảnh hưởng tới story, thoại, prompt, voice, subtitle hoặc package.

#### Scenario: Đổi purpose sau khi đã có story và voice
- **WHEN** project đã có story, shot narration, voice hoặc subtitle và người dùng đổi purpose sang giá trị khác
- **THEN** hệ thống đánh dấu các artifact phụ thuộc là stale hoặc cần tạo lại trước khi export

#### Scenario: Đổi dialogue mode sau khi đã có shot narration
- **WHEN** project đã có shot narration và người dùng đổi dialogue mode
- **THEN** hệ thống đánh dấu shot narration, prompt video, voice, subtitle và package là stale hoặc cần tạo lại

#### Scenario: Không stale khi người dùng chỉ mở preview preset
- **WHEN** người dùng xem preview tác động của một purpose nhưng chưa apply thay đổi vào project
- **THEN** hệ thống không đánh dấu artifact nào là stale

### Requirement: Localize project tạo bản riêng cho từng ngôn ngữ video
Hệ thống SHALL hỗ trợ workflow tạo bản localize hoặc duplicate project để người dùng có cả bản tiếng Việt và tiếng Anh mà không trộn artifact song ngữ trong cùng một project.

#### Scenario: Tạo bản tiếng Anh từ project tiếng Việt
- **WHEN** người dùng tạo bản localize tiếng Anh từ project có `target_language = "vi"`
- **THEN** hệ thống tạo project mới hoặc bản sao có `target_language = "en"`, purpose/sources phù hợp và artifact cần regenerate riêng

#### Scenario: Tạo bản tiếng Việt từ project tiếng Anh
- **WHEN** người dùng tạo bản localize tiếng Việt từ project có `target_language = "en"`
- **THEN** hệ thống tạo project mới hoặc bản sao có `target_language = "vi"`, purpose/sources phù hợp và artifact cần regenerate riêng

#### Scenario: Export package chỉ chứa một ngôn ngữ video
- **WHEN** người dùng export package của một AI Video project
- **THEN** package manifest, voice, subtitle và script SHALL phản ánh một `target_language` duy nhất của project đó
