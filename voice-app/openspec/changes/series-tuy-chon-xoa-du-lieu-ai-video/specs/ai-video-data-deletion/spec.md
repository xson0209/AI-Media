## ADDED Requirements

### Requirement: Xoá project từ danh sách dự án gần đây
Hệ thống SHALL cho phép người dùng xoá AI Video project từ UI danh sách dự án gần đây bằng thao tác có xác nhận rõ ràng.

#### Scenario: Xoá project thành công
- **WHEN** người dùng chọn xoá một project và xác nhận
- **THEN** hệ thống SHALL xoá project khỏi database, xoá artifacts liên quan trên disk và loại project khỏi danh sách dự án gần đây sau khi refetch

#### Scenario: Huỷ confirm xoá project
- **WHEN** người dùng mở confirm xoá project nhưng bấm huỷ
- **THEN** hệ thống MUST NOT xoá database row hoặc artifact file nào của project

### Requirement: Xoá từng đoạn nguồn nội dung/source block
Hệ thống SHALL cho phép xoá từng đoạn nguồn nội dung đã nhập trong AI Video project, tương ứng với source block hiện có.

#### Scenario: Xoá source block trong project
- **WHEN** người dùng xoá một source block của project
- **THEN** hệ thống SHALL xoá đúng source block đó và giữ các source block còn lại theo thứ tự ổn định

#### Scenario: Xoá source block làm project stale
- **WHEN** source block bị xoá sau khi project đã có story, shots hoặc prompts
- **THEN** hệ thống SHALL đánh dấu planning/artifacts liên quan là stale để người dùng biết cần regenerate trước khi dùng tiếp

#### Scenario: Xoá source block cuối cùng
- **WHEN** người dùng cố xoá source block cuối cùng của project
- **THEN** hệ thống SHALL yêu cầu confirm rõ hoặc chặn thao tác nếu project sẽ không còn input hợp lệ để auto-run

### Requirement: Xoá generated data nhưng giữ project và nguồn nhập
Hệ thống SHALL hỗ trợ xoá dữ liệu đã generate của một project mà không xoá project, source blocks, series link hoặc cấu hình project.

#### Scenario: Reset generated data
- **WHEN** người dùng chọn xoá dữ liệu đã tạo nhưng giữ nguồn nhập
- **THEN** hệ thống SHALL xoá story/shots/prompts/voice/subtitles/packages/render outputs/debug events phù hợp và giữ topic, source blocks, series id, Series Bible link, target language, voice profile và prompt config

#### Scenario: Reset project thuộc series
- **WHEN** project thuộc series được reset generated data
- **THEN** hệ thống SHALL giữ liên kết series và MUST NOT xoá hoặc sửa Series Bible

### Requirement: Xoá dữ liệu không được phá active jobs
Hệ thống SHALL xử lý an toàn khi project đang có auto-run, planning job, voice generation hoặc render job active.

#### Scenario: Project đang auto-run hoặc planning
- **WHEN** người dùng yêu cầu xoá project hoặc reset generated data trong lúc project đang auto-run/planning active
- **THEN** hệ thống SHALL chặn thao tác hoặc yêu cầu cancel job trước, và SHALL trả thông báo tiếng Việt rõ ràng thay vì xoá giữa chừng

#### Scenario: Project đang voice/render job active
- **WHEN** project có voice generation hoặc render job đang active
- **THEN** hệ thống SHALL không xoá artifact đang được ghi và SHALL báo trạng thái cần dừng/chờ job trước khi xoá

### Requirement: Xoá series có bảo vệ episode projects
Hệ thống SHALL không xoá nhầm toàn bộ episode projects khi người dùng chỉ muốn xoá series metadata.

#### Scenario: Xoá series còn episodes
- **WHEN** người dùng chọn xoá series còn episode projects
- **THEN** hệ thống SHALL hiển thị lựa chọn rõ ràng giữa detach episodes khỏi series hoặc xoá cả series cùng toàn bộ episodes, và MUST require confirm mạnh nếu xoá cả episodes

#### Scenario: Detach episodes khỏi series
- **WHEN** người dùng chọn xoá series nhưng giữ episodes
- **THEN** hệ thống SHALL xoá series metadata, set episode projects thành project lẻ và giữ artifacts của từng project

### Requirement: Deletion observability
Hệ thống SHALL ghi log/debug event cho thao tác xoá dữ liệu quan trọng để developer biết đã xoá gì và lỗi ở đâu nếu fail.

#### Scenario: Xoá artifact lỗi
- **WHEN** hệ thống không xoá được một artifact file trên disk
- **THEN** hệ thống SHALL log project id, operation, artifact type, path đã redact nếu cần, error class và SHALL trả lỗi thân thiện hoặc warning phù hợp

#### Scenario: Xoá thành công
- **WHEN** thao tác xoá project, reset generated data hoặc xoá source block thành công
- **THEN** hệ thống SHALL log operation summary an toàn gồm số row/artifact đã xoá và MUST NOT log full source content hoặc prompt content dài
