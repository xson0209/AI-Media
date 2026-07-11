## ADDED Requirements

### Requirement: Lựa chọn ngôn ngữ video điều khiển nội dung người xem nghe và đọc
Hệ thống SHALL cho phép người dùng chọn tiếng Anh hoặc tiếng Việt làm ngôn ngữ video của AI Video project, và lựa chọn đó SHALL điều khiển ngôn ngữ người xem nghe hoặc đọc trong video cuối.

#### Scenario: Người dùng tạo project video tiếng Anh
- **WHEN** người dùng tạo AI Video phase 2 project với ngôn ngữ video `English`
- **THEN** hệ thống lưu `target_language = "en"` và coi project đó là video tiếng Anh

#### Scenario: Người dùng tạo project video tiếng Việt
- **WHEN** người dùng tạo AI Video phase 2 project với ngôn ngữ video `Tiếng Việt`
- **THEN** hệ thống lưu `target_language = "vi"` và coi project đó là video tiếng Việt

#### Scenario: UI giải thích lựa chọn ngôn ngữ video
- **WHEN** người dùng nhìn thấy control `Ngôn ngữ video` trong AI Video Assistant
- **THEN** UI giải thích bằng tiếng Việt rằng lựa chọn này điều khiển narration, voice và phụ đề mà người xem sẽ nghe hoặc đọc

### Requirement: Kịch bản và narration theo ngôn ngữ video đã chọn
Hệ thống SHALL tạo story script, scene dialogue và shot narration bằng ngôn ngữ video đã chọn cho project.

#### Scenario: Tạo story cho video tiếng Anh
- **WHEN** AI planning phát triển story cho project có `target_language = "en"`
- **THEN** detailed script, scene dialogue và shot narration dành cho người xem được tạo bằng tiếng Anh

#### Scenario: Tạo story cho video tiếng Việt
- **WHEN** AI planning phát triển story cho project có `target_language = "vi"`
- **THEN** detailed script, scene dialogue và shot narration dành cho người xem được tạo bằng tiếng Việt

#### Scenario: Project tiếng Việt không yêu cầu narration tiếng Anh
- **WHEN** AI planning xây prompt cho story development, shot breakdown hoặc prompt video generation của project có `target_language = "vi"`
- **THEN** planning instruction không yêu cầu English narration cho script, scene dialogue hoặc shot narration dành cho video

#### Scenario: Giải thích trong UI vẫn là tiếng Việt
- **WHEN** hệ thống hiển thị label, helper text, lỗi, trạng thái hoặc giải thích shot trong AI Video UI
- **THEN** các nội dung UI đó vẫn là tiếng Việt dù ngôn ngữ video của project là tiếng Anh hay tiếng Việt

### Requirement: Tạo voice theo ngôn ngữ video đã chọn
Hệ thống SHALL tạo narration audio của AI Video bằng ngôn ngữ video đã chọn, trừ khi API request có override ngôn ngữ rõ ràng.

#### Scenario: Request tạo voice cho video tiếng Anh
- **WHEN** người dùng tạo voice cho scene hoặc shot trong project có `target_language = "en"`
- **THEN** request tạo voice của AI Video dùng language `en` và gửi narration tiếng Anh vào TTS generation pipeline

#### Scenario: Request tạo voice cho video tiếng Việt
- **WHEN** người dùng tạo voice cho scene hoặc shot trong project có `target_language = "vi"`
- **THEN** request tạo voice của AI Video dùng language `vi` và gửi narration tiếng Việt vào TTS generation pipeline

#### Scenario: Voice không hỗ trợ ngôn ngữ video thì báo lỗi rõ
- **WHEN** voice profile, engine, model hoặc experimental gate đã chọn không tạo được ngôn ngữ video của project
- **THEN** hệ thống từ chối request tạo voice bằng lỗi tiếng Việt rõ ràng và không tự fallback sang ngôn ngữ khác

#### Scenario: Tạo voice tiếng Việt bằng TADA 3B ở chế độ test
- **WHEN** project có `target_language = "vi"` và voice profile dùng engine `tada`
- **AND** hệ thống bật local test bypass cho TADA 3B Vietnamese
- **THEN** request tạo voice của AI Video dùng `language = "vi"` và `model_size = "3B"` để người dùng nghe thử trực tiếp trong app
- **AND** hệ thống vẫn coi kết quả là thử nghiệm, không coi TADA Vietnamese là support chính thức và không fallback sang tiếng Anh

#### Scenario: API override ngôn ngữ vẫn được hỗ trợ
- **WHEN** API client gửi rõ một `language` được hỗ trợ trong AI Video narration request
- **THEN** hệ thống dùng language trong request đó cho generation và vẫn giữ đúng behavior readiness/status của project

### Requirement: Phụ đề dùng narration theo ngôn ngữ video đã chọn
Hệ thống SHALL tạo file phụ đề AI Video từ narration text của ngôn ngữ video đã chọn và timing thật của audio.

#### Scenario: Tạo phụ đề cho video tiếng Anh
- **WHEN** toàn bộ voice audio bắt buộc đã hoàn tất cho project có `target_language = "en"`
- **THEN** các cue trong file `.srt` chứa narration tiếng Anh theo thứ tự scene hoặc shot

#### Scenario: Tạo phụ đề cho video tiếng Việt
- **WHEN** toàn bộ voice audio bắt buộc đã hoàn tất cho project có `target_language = "vi"`
- **THEN** các cue trong file `.srt` chứa narration tiếng Việt theo thứ tự scene hoặc shot

#### Scenario: Readiness phụ đề theo artifact đúng ngôn ngữ
- **WHEN** narration text hoặc `target_language` của project thay đổi sau khi đã tạo phụ đề
- **THEN** hệ thống đánh dấu subtitle và package liên quan là stale trước khi export

### Requirement: Prompt video và metadata export phản ánh ngôn ngữ video đã chọn
Hệ thống SHALL đảm bảo prompt video và metadata trong package không mâu thuẫn với ngôn ngữ video đã chọn.

#### Scenario: Tạo prompt video cho project tiếng Anh
- **WHEN** hệ thống tạo prompt video cho project có `target_language = "en"`
- **THEN** prompt chỉ dẫn video render dùng tiếng Anh ở narration, speech, subtitle hoặc on-screen language khi các yếu tố này xuất hiện

#### Scenario: Tạo prompt video cho project tiếng Việt
- **WHEN** hệ thống tạo prompt video cho project có `target_language = "vi"`
- **THEN** prompt chỉ dẫn video render dùng tiếng Việt ở narration, speech, subtitle hoặc on-screen language khi các yếu tố này xuất hiện

#### Scenario: Ngôn ngữ kỹ thuật trong prompt có thể dùng cách viết dễ hiểu cho provider
- **WHEN** prompt video có chi tiết về camera, lighting, motion, style hoặc negative prompt
- **THEN** các chi tiết kỹ thuật đó có thể dùng wording dễ hiểu cho provider, nhưng MUST NOT chỉ dẫn video dùng viewer-facing language khác với `target_language`

#### Scenario: Manifest package ghi rõ ngôn ngữ video
- **WHEN** người dùng export AI Video package
- **THEN** manifest và hướng dẫn trong package ghi rõ video language là tiếng Anh hay tiếng Việt, đồng thời kèm script, voice và subtitle tương ứng

### Requirement: Đổi ngôn ngữ video làm stale các artifact phụ thuộc
Hệ thống SHALL đánh dấu các artifact đã tạo là stale khi ngôn ngữ video của project đổi sau khi đã có story, shot, voice, subtitle, prompt hoặc package.

#### Scenario: Người dùng đổi project tiếng Anh sang tiếng Việt
- **WHEN** project đổi từ `target_language = "en"` sang `target_language = "vi"`
- **THEN** hệ thống đánh dấu story/script, shot narration, prompt video, voice, subtitle và package readiness là stale hoặc cần tạo lại

#### Scenario: Người dùng đổi project tiếng Việt sang tiếng Anh
- **WHEN** project đổi từ `target_language = "vi"` sang `target_language = "en"`
- **THEN** hệ thống đánh dấu story/script, shot narration, prompt video, voice, subtitle và package readiness là stale hoặc cần tạo lại

#### Scenario: Project tiếng Anh cũ vẫn tương thích
- **WHEN** một AI Video phase 2 project cũ không có lựa chọn ngôn ngữ tiếng Việt rõ ràng
- **THEN** hệ thống giữ hành vi video tiếng Anh hiện tại bằng cách default `target_language` về `en`
