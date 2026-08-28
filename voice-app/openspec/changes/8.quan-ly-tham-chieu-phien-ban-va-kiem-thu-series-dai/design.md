## Tổng quan thiết kế

```text
Dữ liệu canon đã duyệt
  |
  +-- Hồ sơ nhân vật phiên bản 3
  +-- Địa điểm phiên bản 2
  +-- Style phiên bản 4
  +-- Ảnh tham chiếu phiên bản 5
  +-- Master Story phiên bản 1
  |
  v
Ảnh chụp phụ thuộc của artifact
  |
  +-- Panel 1 phụ thuộc nhân vật A, địa điểm X, style 4
  +-- Prompt video 2 phụ thuộc nhân vật B, shot 2, style 4
  +-- Voice 2 chỉ phụ thuộc narration, voice profile và ngôn ngữ
  |
  v
So sánh khi dữ liệu thay đổi
  |
  +-- Có ảnh hưởng: đánh stale đúng artifact
  +-- Không ảnh hưởng: giữ nguyên artifact
```

## Quyết định thiết kế

### 1. Ảnh tham chiếu là artifact được duyệt

Thêm mô hình khái niệm `SeriesReferenceAsset`:

```text
SeriesReferenceAsset
  id
  series_id
  entity_type
  entity_id
  reference_role
  label
  asset_path
  provider_asset_id
  mime_type
  width
  height
  checksum
  source_type
  approval_status
  revision
  active
  created_at
  updated_at
```

`entity_type` tối thiểu gồm `character` và `location`. `reference_role` tối thiểu gồm:

- nhân vật: `face_front`, `face_side`, `full_body`, `signature_outfit`, `expression`, `other`;
- địa điểm: `wide_view`, `entrance`, `interior`, `landmark_detail`, `lighting_reference`, `other`.

Một thực thể có thể có nhiều ảnh, nhưng chỉ ảnh đã duyệt và đang hoạt động mới được đưa vào gói prompt. Ảnh gốc không bị thay đổi khi tạo thumbnail hoặc bản chuyển đổi provider.

### 2. Prompt giữ tham chiếu theo mã, không nhúng dữ liệu nhạy cảm

Prompt và gói provider-neutral lưu danh sách `reference_asset_ids`, vai trò và mô tả sử dụng. Adapter provider quyết định cách gửi ảnh phù hợp khả năng provider. Không lưu cookie, token, URL đăng nhập hoặc đường dẫn hồ sơ trình duyệt.

Nếu provider chưa hỗ trợ ảnh tham chiếu, prompt vẫn giữ mô tả văn bản và ghi cảnh báo; workflow không được báo rằng ảnh đã được dùng khi thực tế chưa gửi.

### 3. Mọi dữ liệu quan trọng có phiên bản bất biến

Mỗi lần thay đổi dữ liệu đã duyệt tạo revision mới hoặc một bản ghi phiên bản. Artifact không chỉ lưu mã thực thể mà còn lưu revision đã dùng. Không chỉnh sửa lịch sử phiên bản cũ theo cách làm thay đổi ý nghĩa artifact đã tạo.

Đối tượng cần theo dõi tối thiểu:

- Hồ sơ nhân vật;
- thẻ nhớ và trạng thái hiện tại;
- ảnh tham chiếu;
- Series Bible và style;
- Master Story;
- panel và shot;
- narration và ngôn ngữ;
- prompt ảnh và prompt video.

### 4. Dấu phụ thuộc quyết định stale

Thêm `ArtifactDependencySnapshot` hoặc cấu trúc tương đương:

```text
artifact_type
artifact_id
dependency_type
dependency_id
dependency_revision
dependency_scope
created_at
```

`dependency_scope` mô tả phần bị ảnh hưởng, ví dụ `visual_identity`, `story_state`, `dialogue`, `language`, `camera_style` hoặc `reference_image`.

Khi dữ liệu thay đổi, hệ thống so sánh revision và phạm vi:

- đổi tóc nhân vật: stale panel và prompt có nhân vật đó;
- đổi địa điểm: stale artifact dùng địa điểm đó;
- đổi style toàn series: stale prompt hình ảnh và video, không tự stale voice nếu narration không đổi;
- đổi narration: stale voice, subtitle và package liên quan;
- đổi ngôn ngữ: stale narration, voice, subtitle, prompt có text người xem và package;
- đổi nhân vật không xuất hiện trong tập: không stale artifact của tập đó.

### 5. Stale phải có lý do và mức lan truyền

Mỗi lần đánh stale lưu sự kiện gồm dữ liệu nguồn thay đổi, phiên bản cũ/mới, artifact bị ảnh hưởng và quy tắc lan truyền. UI hiển thị lý do bằng tiếng Việt và cho phép tạo lại đúng phạm vi.

Không tự xóa artifact cũ. Artifact stale vẫn xem và so sánh được nhưng không được dùng làm đầu ra mới mà không có cảnh báo hoặc ghi đè.

### 6. Bộ kiểm thử series dài dùng dữ liệu giả lập có chủ đích

Tạo bộ dữ liệu kiểm thử tối thiểu gồm:

- ít nhất 30 tập cho kiểm thử thường xuyên;
- tùy chọn 100 tập cho kiểm thử tải dài;
- nhiều nhân vật, quan hệ, địa điểm, đạo cụ và mạch truyện;
- sự kiện cũ được nhắc lại sau nhiều tập;
- thay đổi canon đã duyệt và đề xuất chưa duyệt;
- bí mật chỉ được tiết lộ từ một tập xác định;
- thay đổi chỉ ảnh hưởng một nhóm artifact.

Bộ kiểm thử chạy tới:

```text
Chọn ký ức
-> tạo ba candidate
-> đánh giá và tổng hợp
-> Master Story
-> panel hoặc shot
-> prompt
-> kiểm tra và tự sửa
-> voice giả lập
-> subtitle thật từ narration/timing giả lập
```

Không chạy bước submit Veo, tạo clip hoặc render phụ thuộc clip provider.

### 7. Chỉ số chất lượng có thể đo

Bộ kiểm thử báo tối thiểu:

- tỷ lệ lấy đúng thẻ bắt buộc;
- tỷ lệ không lấy thẻ gây nhiễu;
- số lỗi canon phát hiện được;
- số lỗi canon bị bỏ sót trong bộ dữ liệu chuẩn;
- tỷ lệ candidate khác nhau đạt yêu cầu;
- tỷ lệ prompt đạt sau sửa;
- số artifact bị stale đúng;
- số artifact bị stale thừa;
- số lần gọi AI và tổng dung lượng ngữ cảnh;
- xác nhận không có lời gọi provider video.

### 8. Dữ liệu kiểm thử phải tái lập

Các bài kiểm thử tự động dùng AI giả lập hoặc câu trả lời cố định để kết quả ổn định. Có thể có bộ đánh giá AI tùy chọn, nhưng không được là điều kiện duy nhất để kiểm thử chính vượt qua.

## Bảo mật và lưu trữ

- Chỉ chấp nhận loại ảnh và dung lượng được cấu hình.
- Tên tệp được làm sạch; đường dẫn lưu trữ nằm trong thư mục artifact của ứng dụng.
- Package và debug export không chứa credential, cookie hoặc đường dẫn hồ sơ trình duyệt.
- Nếu ảnh tham chiếu không được phép đưa vào package, hệ thống chỉ xuất mã và metadata an toàn.

## Rủi ro và giảm thiểu

- Quá nhiều phiên bản: giữ metadata và chính sách dọn dẹp riêng, không xóa phiên bản đang được artifact tham chiếu.
- Đánh stale quá rộng: dùng dependency scope và bài kiểm thử stale thừa.
- Provider không hỗ trợ ảnh tham chiếu: adapter báo rõ fallback văn bản.
- Bộ kiểm thử AI không ổn định: kiểm thử chính dùng dữ liệu cố định, đánh giá AI chỉ là lớp bổ sung.
- Series 100 tập làm kiểm thử chậm: tách bộ 30 tập chạy thường xuyên và bộ 100 tập chạy theo lịch hoặc thủ công.

## Khả năng quay lui

Có thể tắt việc đưa ảnh tham chiếu vào gói provider và quay về mô tả văn bản. Dependency snapshot và phiên bản chỉ bổ sung dữ liệu; có thể tạm quay về stale cấp project nếu cần, nhưng không xóa lịch sử lý do stale đã lưu.
