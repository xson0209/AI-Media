## ADDED Requirements

### Requirement: Giới hạn số Codex planning jobs chạy song song
Hệ thống SHALL điều phối các AI Video planning jobs dùng Codex CLI qua một global planning pool với mặc định tối đa 2 job chạy cùng lúc toàn app.

#### Scenario: Hai project chạy planning cùng lúc
- **WHEN** hai AI Video projects khác nhau cùng yêu cầu bước planning dùng Codex CLI và không project nào đang có planning job active
- **THEN** hệ thống SHALL cho phép cả hai job lấy slot và chạy song song nếu `max_concurrency = 2`

#### Scenario: Project thứ ba phải chờ slot
- **WHEN** hai Codex planning jobs đang chạy và một project thứ ba yêu cầu planning
- **THEN** hệ thống SHALL không khởi chạy Codex subprocess thứ ba trước khi một slot được release

#### Scenario: Cấu hình concurrency mặc định
- **WHEN** người dùng không cấu hình giới hạn planning concurrency
- **THEN** hệ thống SHALL dùng `max_concurrency = 2`

#### Scenario: Giảm concurrency bằng cấu hình
- **WHEN** runtime config hoặc env đặt giới hạn planning concurrency hợp lệ là `1`
- **THEN** hệ thống SHALL chỉ cho một Codex planning job chạy cùng lúc và các job khác phải chờ slot hoặc trả trạng thái chờ phù hợp

### Requirement: Không chạy song song nhiều planning jobs trên cùng project
Hệ thống SHALL đảm bảo mỗi AI Video project chỉ có một planning operation active tại một thời điểm, dù request đến từ auto-run hay endpoint thủ công.

#### Scenario: Chặn planning trùng project
- **WHEN** một project đang chạy hoặc đang chờ một Codex planning job và client yêu cầu planning job thứ hai cho cùng project
- **THEN** hệ thống SHALL từ chối hoặc trả trạng thái active bằng thông báo tiếng Việt rõ ràng và MUST NOT tạo Codex subprocess trùng cho project đó

#### Scenario: Project khác vẫn được chạy
- **WHEN** project A đang có planning job active và project B yêu cầu planning
- **THEN** hệ thống SHALL cho project B dùng global planning pool bình thường nếu còn slot trống

#### Scenario: Release project lock sau lỗi
- **WHEN** planning job của project fail do timeout, invalid output, validation error hoặc exception
- **THEN** hệ thống SHALL release project lock để người dùng có thể retry sau khi lỗi được ghi nhận

### Requirement: Giữ prompt pack là full-pack call trong từng project
Hệ thống SHALL giữ việc tạo prompt video pack của một project là một Codex call đầy đủ cho toàn bộ shot cần prompt, không chia nhỏ theo shot hoặc batch trong change này.

#### Scenario: Tạo prompt pack cho một project
- **WHEN** project cần tạo prompt video cho nhiều shot hoặc segment
- **THEN** hệ thống SHALL gửi toàn bộ shot/segment cần tạo vào một Codex planning request cho project đó

#### Scenario: Không chia prompt theo shot
- **WHEN** project có nhiều shot cần prompt và global planning pool còn slot
- **THEN** hệ thống MUST NOT tạo nhiều Codex calls song song cho các shot riêng lẻ của cùng project

#### Scenario: Validation full pack vẫn giữ nguyên
- **WHEN** Codex trả prompt video pack cho một project
- **THEN** hệ thống SHALL validate prompt count, shot order, required prompt fields, continuity fields, retention notes, transition notes và sound design notes trước khi ghi artifact như luồng hiện có

### Requirement: Auto-run dùng planning pool chung
Hệ thống SHALL đưa các bước planning trong AI Video auto-run qua planning pool chung để nhiều project auto-run có thể tiến hành song song trong giới hạn cấu hình.

#### Scenario: Hai auto-run cùng tạo prompt
- **WHEN** hai project auto-run khác nhau cùng đến bước `generate_prompts`
- **THEN** hệ thống SHALL cho tối đa hai prompt pack Codex calls chạy song song khi `max_concurrency = 2`

#### Scenario: Auto-run chờ slot planning
- **WHEN** auto-run cần chạy Codex planning nhưng global pool đã đầy
- **THEN** auto-run SHALL hiển thị hoặc lưu trạng thái đang chờ slot planning, gồm current step dễ hiểu cho frontend poll

#### Scenario: Auto-run tiếp tục sau khi có slot
- **WHEN** một planning slot được release và auto-run đang chờ slot
- **THEN** auto-run SHALL tiếp tục đúng planning step đang chờ mà không skip validation hoặc tạo artifact giả

### Requirement: Endpoint thủ công không bypass planning pool
Hệ thống SHALL áp dụng cùng planning concurrency limit cho các endpoint thủ công của AI Video dùng Codex CLI.

#### Scenario: Manual generate prompt dùng pool
- **WHEN** người dùng bấm tạo prompt video thủ công trên một project
- **THEN** request SHALL acquire planning slot trước khi gọi Codex CLI và MUST release slot sau khi hoàn tất hoặc lỗi

#### Scenario: Manual story hoặc shot generation dùng pool
- **WHEN** người dùng bấm phát triển story hoặc tạo shot breakdown thủ công
- **THEN** request SHALL sử dụng cùng planning pool thay vì gọi Codex CLI trực tiếp ngoài giới hạn

#### Scenario: Manual request trùng project đang auto-run
- **WHEN** project đang có auto-run planning active và người dùng bấm manual planning cho cùng project
- **THEN** hệ thống SHALL không tạo planning job trùng và SHALL trả lỗi hoặc trạng thái tiếng Việt giải thích project đang xử lý

### Requirement: Observability cho planning concurrency
Hệ thống SHALL ghi debug event và summary đủ để developer biết planning job nào đang chờ, chạy, hoàn tất hoặc lỗi mà không lộ nội dung prompt đầy đủ.

#### Scenario: Log khi chờ slot
- **WHEN** planning job phải chờ vì global pool đã đầy
- **THEN** hệ thống SHALL ghi debug event gồm project id, step name, wait start hoặc wait duration, max concurrency và thông tin đã redaction

#### Scenario: Log khi acquire và release slot
- **WHEN** planning job lấy hoặc release slot
- **THEN** hệ thống SHALL ghi event có project id, step name, active count hoặc queue position nếu có, duration và status

#### Scenario: Không log full prompt
- **WHEN** hệ thống ghi technical details cho planning concurrency
- **THEN** technical details MUST NOT chứa toàn bộ source text, full prompt video hoặc narration dài; chỉ lưu count, ids, độ dài text hoặc preview đã rút gọn

### Requirement: Không thay đổi TTS serial queue
Hệ thống SHALL giữ TTS generation queue hoạt động tuần tự như hiện tại, độc lập với Codex planning pool.

#### Scenario: Nhiều auto-run enqueue voice
- **WHEN** nhiều project auto-run hoàn tất prompt và enqueue voice cho các shot
- **THEN** hệ thống SHALL vẫn xử lý TTS generation theo serial queue hiện có và MUST NOT chạy nhiều inference TTS song song vì planning concurrency

#### Scenario: Planning pool không dùng generation queue
- **WHEN** Codex planning jobs được schedule
- **THEN** hệ thống SHALL dùng planning pool riêng và MUST NOT enqueue planning jobs vào TTS generation queue
