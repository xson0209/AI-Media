## ADDED Requirements

### Requirement: Cấu hình cổng và địa chỉ runtime tập trung
Hệ thống SHALL có một contract cấu hình runtime tập trung cho backend host, backend port, frontend dev port, CORS origins, data directory, model directory và cache directory. Giá trị mặc định SHALL giữ frontend dev port là `5173` và backend port là `17493`.

#### Scenario: Chạy dev với cấu hình mặc định
- **WHEN** người phát triển chạy frontend và backend mà không đặt biến môi trường override
- **THEN** frontend SHALL chạy ở cổng `5173`
- **AND** backend SHALL chạy ở cổng `17493`
- **AND** backend SHALL cho phép CORS từ `http://localhost:5173` và `http://127.0.0.1:5173`

#### Scenario: Ghi đè cổng backend
- **WHEN** người vận hành đặt cấu hình backend port hợp lệ trước khi khởi động backend
- **THEN** backend SHALL lắng nghe trên cổng đã cấu hình
- **AND** các script hoặc bridge khởi chạy backend SHALL dùng cùng giá trị đó thay vì hardcode `17493`

#### Scenario: Cấu hình thư mục dữ liệu và model
- **WHEN** người vận hành đặt thư mục dữ liệu, model hoặc cache qua cấu hình runtime
- **THEN** backend SHALL resolve database, profile, generation, capture, model và cache path từ cùng lớp cấu hình
- **AND** các helper tương thích cũ SHALL tiếp tục trả về path đúng cho caller hiện có

### Requirement: Frontend dùng một nguồn xác định backend URL
Frontend SHALL xác định backend URL qua một helper/store thống nhất. Helper này MUST hỗ trợ cấu hình build/runtime, URL trả về từ Tauri khi chạy desktop, URL người dùng đã lưu và fallback local `http://127.0.0.1:17493`.

#### Scenario: Web dev không đặt URL tùy chỉnh
- **WHEN** frontend chạy trong môi trường web dev và không có cấu hình URL tùy chỉnh
- **THEN** frontend SHALL dùng fallback `http://127.0.0.1:17493`
- **AND** mọi API client SHALL đọc backend URL qua helper/store thống nhất

#### Scenario: Web build được phục vụ từ backend
- **WHEN** frontend production được serve cùng origin với backend
- **THEN** helper backend URL SHALL ưu tiên origin hiện tại khi origin đó là HTTP/HTTPS hợp lệ và không phải Tauri webview origin

#### Scenario: Desktop nhận URL từ Tauri
- **WHEN** Tauri khởi động hoặc phát hiện backend local thành công
- **THEN** frontend SHALL dùng URL backend do Tauri lifecycle trả về
- **AND** store SHALL không tự thay thế bằng fallback khác nếu URL đó hợp lệ

### Requirement: Backend được phân lớp theo lõi, API, tính năng và dữ liệu
Backend SHALL được tổ chức để code lõi dùng chung, định tuyến API, nghiệp vụ tính năng và truy cập dữ liệu có boundary rõ ràng. Route handler SHALL mỏng, chỉ xử lý request/response, phân quyền/validation cục bộ nếu có và gọi lớp tính năng tương ứng.

#### Scenario: Thêm route API mới
- **WHEN** cần thêm một endpoint backend mới
- **THEN** endpoint SHALL nằm trong lớp API route phù hợp
- **AND** logic nghiệp vụ chính SHALL nằm trong module tính năng hoặc service tương ứng
- **AND** route SHALL không nhúng trực tiếp pipeline dài, truy cập file phức tạp hoặc điều phối render nhiều bước nếu logic đó có thể đặt trong feature service

#### Scenario: Chia module AI Video lớn
- **WHEN** tách một phần AI Video như dự án, chạy tự động, render hoặc phụ đề/caption khỏi file lớn hiện tại
- **THEN** phần đã tách SHALL có module tính năng riêng
- **AND** import cũ SHALL có wrapper hoặc đường chuyển tiếp cho đến khi mọi caller đã chuyển sang module mới

#### Scenario: Tách lifecycle backend
- **WHEN** app FastAPI khởi động hoặc tắt
- **THEN** logic startup/shutdown SHALL được đặt trong lớp lifecycle dùng chung
- **AND** entry `backend.main:app` SHALL tiếp tục hoạt động như trước

### Requirement: Tái cấu trúc không làm đổi hành vi công khai
Thay đổi cấu trúc file/module SHALL không làm đổi public REST API, schema phản hồi, cổng mặc định, đường dẫn lưu trữ, dữ liệu dự án hoặc hành vi UI hiện có trừ khi có spec riêng cho thay đổi hành vi đó.

#### Scenario: Gọi endpoint cũ sau refactor
- **WHEN** client gọi endpoint public đã tồn tại trước refactor với payload hợp lệ
- **THEN** backend SHALL trả về status code và schema tương thích với hành vi trước refactor

#### Scenario: Mở dự án AI Video đã lưu
- **WHEN** người dùng mở dự án AI Video được tạo trước refactor
- **THEN** hệ thống SHALL resolve đúng đường dẫn media, metadata, render state và phụ đề liên quan
- **AND** hệ thống SHALL không yêu cầu migration thủ công từ người dùng

#### Scenario: Chạy script hiện có
- **WHEN** người phát triển chạy các command dev/test chính đã tồn tại
- **THEN** command SHALL tiếp tục khởi động đúng frontend/backend hoặc chạy test như trước
- **AND** nếu command dùng cấu hình mới thì giá trị mặc định SHALL tương thích với hành vi cũ

### Requirement: Kiểm thử regression cho ranh giới frontend/backend và backend layer
Hệ thống SHALL có kiểm thử hoặc kiểm chứng tự động cho cấu hình cổng/CORS, URL resolution frontend, health startup backend và route compatibility cho các vùng được refactor.

#### Scenario: Kiểm thử cấu hình backend
- **WHEN** chạy test backend liên quan cấu hình runtime
- **THEN** test SHALL xác nhận default backend port `17493`, default frontend origin `5173`, custom CORS origins và path dữ liệu/model/cache hoạt động đúng

#### Scenario: Kiểm thử URL frontend
- **WHEN** chạy test hoặc typecheck frontend sau khi đổi URL helper/API client
- **THEN** kiểm chứng SHALL xác nhận frontend không còn nhiều fallback backend URL không đồng nhất
- **AND** API client SHALL dùng server URL từ store/helper chung

#### Scenario: Kiểm thử sau khi tách feature
- **WHEN** một vùng backend được chuyển sang cấu trúc feature mới
- **THEN** test SHALL bao phủ endpoint hoặc service chính của vùng đó
- **AND** wrapper tương thích SHALL được kiểm chứng cho caller cũ nếu wrapper vẫn tồn tại
