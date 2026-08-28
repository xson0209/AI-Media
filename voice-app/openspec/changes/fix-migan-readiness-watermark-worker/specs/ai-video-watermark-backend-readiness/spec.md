## ADDED Requirements

### Requirement: Script setup worker phân giải `uv` từ dự án

Script chuẩn bị watermark worker MUST tìm `uv` theo thứ tự ưu tiên: lệnh `uv` trên `PATH` trước, sau đó `uv.exe` đi kèm venv backend trong dự án. Script MUST chỉ báo lỗi khi không tìm được `uv` ở cả hai nơi, và thông báo lỗi MUST nêu cả hai vị trí đã tìm.

#### Scenario: `uv` có trên PATH

- **WHEN** người dùng chạy script setup và `uv` có trên `PATH`
- **THEN** script dùng `uv` trên `PATH` và tiếp tục sync bình thường

#### Scenario: `uv` không có trên PATH nhưng có trong dự án

- **WHEN** người dùng chạy script setup, `uv` không có trên `PATH`, và `uv.exe` tồn tại trong venv backend của dự án
- **THEN** script dùng `uv.exe` trong dự án, không báo lỗi, và ghi rõ đang dùng `uv` từ dự án

#### Scenario: Không tìm được `uv` ở đâu cả

- **WHEN** người dùng chạy script setup và `uv` không có trên `PATH` lẫn trong venv backend của dự án
- **THEN** script dừng với thông báo nêu rõ đã tìm ở `PATH` và đường dẫn `uv.exe` trong dự án

#### Scenario: Sync extra migan

- **WHEN** người dùng chạy script setup với backend `migan`
- **THEN** script sync repo watermark kèm extra `video` và `migan`, để venv worker có `onnxruntime` và `huggingface-hub`

### Requirement: Worker báo trạng thái cache model MI-GAN

Khi kiểm tra runtime cho backend `migan`, worker MUST báo model MI-GAN đã có trong HuggingFace cache hay chưa. Việc kiểm tra MUST tra cache cục bộ và MUST NOT tải model. Trạng thái cache MUST NOT làm worker báo chưa sẵn sàng khi dependency đã đủ.

#### Scenario: Model đã cache

- **WHEN** worker chạy kiểm tra runtime cho backend `migan`, dependency đã đủ, và model MI-GAN đã có trong cache
- **THEN** worker báo sẵn sàng và báo trạng thái cache model là đã có

#### Scenario: Model chưa cache

- **WHEN** worker chạy kiểm tra runtime cho backend `migan`, dependency đã đủ, nhưng model MI-GAN chưa có trong cache
- **THEN** worker báo sẵn sàng và báo trạng thái cache model là chưa có, không tải model trong lúc kiểm tra

#### Scenario: Kiểm tra cache thất bại

- **WHEN** việc tra cache model gặp lỗi ngoài dự kiến
- **THEN** worker vẫn báo sẵn sàng theo kết quả dependency và báo trạng thái cache model là không xác định

#### Scenario: Backend cv2 không liên quan model

- **WHEN** worker chạy kiểm tra runtime cho backend `cv2`
- **THEN** worker không tra cache model MI-GAN và không báo trạng thái cache model

### Requirement: Thông báo lỗi thiếu dependency có hướng dẫn tự sửa

Khi worker không kiểm tra được runtime vì thiếu dependency, payload lỗi MUST nêu Python đang chạy worker và lệnh setup cần chạy để sửa. Yêu cầu này MUST áp dụng cho cả trường hợp thiếu dependency chung và thiếu dependency riêng của backend `migan`.

#### Scenario: Thiếu dependency riêng của MI-GAN

- **WHEN** worker kiểm tra runtime cho backend `migan` và thiếu `huggingface_hub` hoặc `onnxruntime`
- **THEN** payload lỗi nêu module còn thiếu, Python đang chạy worker, và lệnh setup kèm backend `migan`

#### Scenario: Thiếu dependency chung của worker

- **WHEN** worker kiểm tra runtime và thiếu dependency video chung
- **THEN** payload lỗi nêu nguyên nhân, Python đang chạy worker, và lệnh setup cần chạy

#### Scenario: Người dùng đọc lỗi trên UI

- **WHEN** readiness trả về lỗi thiếu dependency
- **THEN** thông báo hiển thị cho người dùng chứa hướng dẫn sửa, không chỉ nguyên văn lỗi import

### Requirement: Readiness báo trạng thái theo từng backend cleanup

Khi làm sạch watermark được bật, readiness dựng MP4 MUST báo trạng thái sẵn sàng riêng cho từng backend lấp vùng được hỗ trợ. Readiness MUST NOT spawn worker khi làm sạch watermark tắt. Điều kiện chặn dựng MP4 MUST chỉ dựa trên backend đang được chọn.

#### Scenario: Cleanup tắt

- **WHEN** người dùng chưa bật làm sạch watermark
- **THEN** readiness không spawn worker, không probe backend nào, và thiếu worker không chặn dựng MP4

#### Scenario: Cleanup bật, cả hai backend sẵn sàng

- **WHEN** người dùng bật làm sạch watermark và cả `cv2` lẫn `migan` đều sẵn sàng
- **THEN** readiness báo cả hai backend sẵn sàng và không chặn dựng MP4

#### Scenario: Cleanup bật, chọn cv2 trong khi migan chưa sẵn sàng

- **WHEN** người dùng bật làm sạch watermark, chọn backend `cv2` đã sẵn sàng, còn `migan` chưa sẵn sàng
- **THEN** readiness cho phép dựng MP4, báo `cv2` sẵn sàng và `migan` chưa sẵn sàng kèm lý do

#### Scenario: Cleanup bật, chọn migan chưa sẵn sàng

- **WHEN** người dùng bật làm sạch watermark và chọn backend `migan` chưa sẵn sàng
- **THEN** readiness chặn dựng MP4 và nêu lý do backend đang chọn chưa sẵn sàng

### Requirement: Cảnh báo model chưa cache trước khi dựng

Khi backend đang chọn là `migan`, dependency đã đủ nhưng model chưa cache, readiness MUST cho phép dựng MP4 và MUST phát cảnh báo nêu rõ lần dựng đầu cần mạng và dung lượng tải xấp xỉ. Trạng thái model chưa cache MUST NOT bị trình bày như lỗi.

#### Scenario: Chọn MI-GAN khi model chưa cache

- **WHEN** người dùng bật làm sạch watermark, chọn `migan`, dependency đủ và model chưa cache
- **THEN** readiness cho phép dựng MP4 và trả cảnh báo rằng lần dựng đầu cần mạng để tải model khoảng 28 MB

#### Scenario: Chọn MI-GAN khi model đã cache

- **WHEN** người dùng bật làm sạch watermark, chọn `migan`, dependency đủ và model đã cache
- **THEN** readiness cho phép dựng MP4 và không phát cảnh báo về tải model

#### Scenario: Chọn cv2 không phát cảnh báo model

- **WHEN** người dùng bật làm sạch watermark và chọn `cv2`
- **THEN** readiness không phát cảnh báo về tải model MI-GAN

### Requirement: UI đánh dấu cách lấp vùng chưa sẵn sàng

Trong bảng dựng nhanh MP4, mỗi lựa chọn cách lấp vùng MUST hiển thị được trạng thái chưa sẵn sàng. Lựa chọn chưa sẵn sàng MUST bị vô hiệu hoá để người dùng không chọn được, và giao diện MUST nêu lý do chưa dùng được. Khi readiness chưa có dữ liệu, giao diện MUST NOT vô hiệu hoá lựa chọn nào.

#### Scenario: MI-GAN chưa sẵn sàng

- **WHEN** người dùng bật làm sạch watermark và readiness báo `migan` chưa sẵn sàng
- **THEN** lựa chọn MI-GAN bị vô hiệu hoá kèm nhãn cho biết chưa sẵn sàng, và giao diện nêu lý do

#### Scenario: Cả hai backend sẵn sàng

- **WHEN** readiness báo cả `cv2` và `migan` đều sẵn sàng
- **THEN** cả hai lựa chọn đều chọn được và không có nhãn chưa sẵn sàng

#### Scenario: Readiness đang tải

- **WHEN** người dùng vừa bật làm sạch watermark và readiness chưa trả kết quả
- **THEN** giao diện không vô hiệu hoá lựa chọn nào và cho biết đang kiểm tra

#### Scenario: Model chưa cache vẫn chọn được

- **WHEN** readiness báo `migan` sẵn sàng nhưng model chưa cache
- **THEN** lựa chọn MI-GAN vẫn chọn được và giao diện nêu cảnh báo lần dựng đầu cần mạng

### Requirement: Giữ nguyên phạm vi làm sạch watermark

Change này MUST NOT mở rộng phạm vi làm sạch watermark. Việc làm sạch MUST tiếp tục chỉ xử lý dấu AI nhìn thấy được hỗ trợ và metadata đã xác minh. Tài liệu MUST tiếp tục nêu rõ watermark ẩn không bị xử lý.

#### Scenario: Watermark ẩn không được xử lý

- **WHEN** người dùng chạy làm sạch watermark với bất kỳ backend nào
- **THEN** hệ thống không xử lý watermark ẩn hay SynthID, và tài liệu nêu rõ giới hạn này

#### Scenario: Chất lượng lấp vùng không đổi kết quả phát hiện

- **WHEN** người dùng đổi cách lấp vùng giữa `cv2` và `migan`
- **THEN** phạm vi dấu AI được phát hiện không đổi, chỉ chất lượng vùng được lấp thay đổi
