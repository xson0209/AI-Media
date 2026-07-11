## ADDED Requirements

### Requirement: Theo dõi trạng thái tài nguyên AI Video
Hệ thống MUST cung cấp trạng thái tài nguyên local liên quan đến AI Video, bao gồm model đang loaded, loại backend, lần sử dụng gần nhất, trạng thái job đang chạy, memory pressure của máy, GPU/MLX cache nếu có, và kích thước các cache liên quan.

#### Scenario: Xem trạng thái khi có model đang loaded
- **WHEN** người dùng mở màn hình quản lý model hoặc resource panel khi một model TTS/STT/LLM đang loaded
- **THEN** hệ thống hiển thị model đó là loaded, loại backend, model size nếu có, lần sử dụng gần nhất và trạng thái memory hiện tại

#### Scenario: Xem trạng thái khi không có model đang loaded
- **WHEN** không có model local nào đang loaded
- **THEN** hệ thống hiển thị trạng thái tài nguyên rảnh và không báo memory pressure giả

### Requirement: Tự unload model idle
Hệ thống MUST tự unload model local đã idle quá thời gian cấu hình, miễn là model đó không có job đang chạy hoặc đang được queue sử dụng.

#### Scenario: Model idle quá timeout
- **WHEN** một model đã loaded nhưng không được dùng quá thời gian idle-unload đã cấu hình
- **THEN** hệ thống unload model đó và cập nhật trạng thái resource/model thành unloaded

#### Scenario: Model đang có job active
- **WHEN** một model đã vượt idle timeout nhưng vẫn có generation, transcription, LLM request hoặc AI Video voice job đang active
- **THEN** hệ thống không unload model cho đến khi job active kết thúc

### Requirement: Giới hạn số model nặng loaded đồng thời
Hệ thống MUST áp dụng giới hạn số model nặng được giữ loaded cùng lúc và unload model ít dùng gần đây nhất trước khi load thêm model nặng khác nếu vượt giới hạn.

#### Scenario: Load model nặng mới khi đã đạt giới hạn
- **WHEN** số model nặng loaded đã đạt giới hạn và người dùng yêu cầu load một model nặng khác
- **THEN** hệ thống unload model nặng ít dùng gần đây nhất không active trước khi load model mới

#### Scenario: Tất cả model nặng đều đang active
- **WHEN** số model nặng loaded đã đạt giới hạn nhưng mọi model nặng hiện tại đều đang active
- **THEN** hệ thống giữ nguyên các model active và chờ theo queue hoặc báo trạng thái bận thay vì unload cưỡng bức

### Requirement: Cache voice prompt có giới hạn
Hệ thống MUST giới hạn memory cache của voice prompt theo số lượng, dung lượng ước tính hoặc TTL, đồng thời vẫn giữ disk cache để tái sử dụng sau khi entry bị đẩy khỏi RAM.

#### Scenario: Memory cache vượt giới hạn
- **WHEN** voice prompt memory cache vượt giới hạn đã cấu hình
- **THEN** hệ thống loại bỏ các entry ít dùng gần đây nhất khỏi RAM mà không xóa disk cache tương ứng

#### Scenario: Dùng lại prompt từ disk cache
- **WHEN** voice prompt không còn trong memory cache nhưng vẫn còn disk cache hợp lệ
- **THEN** hệ thống load prompt từ disk cache, đưa lại vào memory cache nếu còn quota và không tạo prompt mới

### Requirement: Quản lý MLX cache trên Apple Silicon
Hệ thống MUST phát hiện backend MLX trên Apple Silicon và áp dụng giới hạn hoặc cleanup cache MLX khi queue đã idle hoặc khi memory pressure vượt ngưỡng cấu hình.

#### Scenario: MLX cache cao khi queue idle
- **WHEN** backend MLX đang dùng, queue generation đã idle và MLX cache vượt ngưỡng cấu hình
- **THEN** hệ thống clear hoặc giảm MLX cache và ghi nhận sự kiện cleanup trong resource status/log

#### Scenario: MLX cache trong lúc generation đang chạy
- **WHEN** một generation MLX đang chạy
- **THEN** hệ thống không clear MLX cache giữa chừng để tránh ảnh hưởng inference đang active

### Requirement: Cache render intermediate
Hệ thống MUST tái sử dụng render intermediate hợp lệ cho các bước normalize clip và stage video/audio khi source media, timing và render settings liên quan không đổi.

#### Scenario: Render lại chỉ đổi phụ đề
- **WHEN** người dùng render lại cùng project với cùng clip, timing, resolution, fps, fit mode và duration mode nhưng chỉ đổi subtitle mode hoặc subtitle style
- **THEN** hệ thống tái sử dụng normalized video intermediates thay vì chạy normalize clip lại từ đầu

#### Scenario: Source clip thay đổi
- **WHEN** source clip của một shot bị thay, xóa hoặc metadata liên quan thay đổi
- **THEN** hệ thống bỏ qua intermediate cũ của shot đó và tạo intermediate mới

#### Scenario: Render settings thay đổi
- **WHEN** resolution, fps, fit mode, background color hoặc duration mode thay đổi
- **THEN** hệ thống không dùng lại intermediate được tạo từ settings cũ

### Requirement: Cleanup thủ công an toàn
Hệ thống MUST cung cấp thao tác thủ công để unload model idle, clear memory cache, clear MLX cache khi an toàn và dọn render intermediate cache theo project hoặc toàn cục.

#### Scenario: Người dùng bấm giải phóng RAM/GPU
- **WHEN** người dùng yêu cầu giải phóng RAM/GPU
- **THEN** hệ thống unload các model idle, clear memory cache có thể xóa an toàn và trả về danh sách hành động đã thực hiện

#### Scenario: Cleanup thủ công khi có job active
- **WHEN** người dùng yêu cầu cleanup trong lúc có job active
- **THEN** hệ thống chỉ cleanup các tài nguyên không active và báo rõ tài nguyên nào được giữ lại vì đang chạy

### Requirement: Cấu hình bảo thủ mặc định
Hệ thống MUST có cấu hình mặc định bảo thủ để giảm rủi ro: không unload trong lúc job active, không xóa disk cache quan trọng nếu chưa được yêu cầu, và ưu tiên giảm memory cache trước khi unload model.

#### Scenario: Chạy với cấu hình mặc định
- **WHEN** người dùng không cấu hình resource policy riêng
- **THEN** hệ thống dùng timeout, giới hạn cache và ngưỡng memory mặc định phù hợp cho máy local 16GB mà không làm gián đoạn workflow AI Video

#### Scenario: Người dùng chỉnh cấu hình
- **WHEN** người dùng hoặc môi trường runtime cấu hình timeout/ngưỡng/giới hạn cache khác
- **THEN** hệ thống áp dụng cấu hình mới và phản ánh các giá trị đó trong resource status
