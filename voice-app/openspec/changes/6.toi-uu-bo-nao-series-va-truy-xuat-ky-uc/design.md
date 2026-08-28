## Tổng quan thiết kế

Change này thay bộ nhớ dạng một khối văn bản bằng kiến trúc nhiều tầng:

```text
Cơ sở dữ liệu chuẩn
  |
  +-- Series Bible và Hồ sơ nhân vật hiện có
  +-- Thẻ nhớ có cấu trúc
  +-- Trạng thái hiện tại của series
  +-- Tóm tắt từng tập và từng chặng
  |
  v
Bộ chọn ký ức theo nhiệm vụ
  |
  v
Bộ phân bổ dung lượng theo nhóm
  |
  v
Gói ngữ cảnh có dấu vết nguồn
  |
  v
AI tạo nội dung
  |
  v
Kiểm tra mâu thuẫn canon
```

## Quyết định thiết kế

### 1. Cơ sở dữ liệu là nguồn chuẩn duy nhất

Không dùng nhiều tệp Markdown làm các nguồn sự thật độc lập. `series-memory.md` và các tệp bộ nhớ theo nhóm được dựng lại từ cơ sở dữ liệu. Việc sửa canon phải đi qua API và trạng thái duyệt, tránh cùng một dữ liệu có hai bản mâu thuẫn.

### 2. Thẻ nhớ là đơn vị truy xuất nhỏ

Thêm mô hình khái niệm `SeriesMemoryCard`:

```text
SeriesMemoryCard
  id
  series_id
  card_type
  title
  content_json
  tags
  entity_refs
  importance
  status
  effective_from_episode
  effective_to_episode
  source_type
  source_id
  revision
  approved_at
  created_at
  updated_at
```

`card_type` tối thiểu gồm:

- `series_identity`;
- `relationship`;
- `location`;
- `prop`;
- `story_thread`;
- `canon_rule`;
- `visual_style`;
- `episode_summary`;
- `arc_summary`;
- `series_summary`;
- `reviewed_note`.

Hồ sơ nhân vật hiện có vẫn là nguồn chuẩn cho danh tính nhân vật. Bộ chọn ký ức chuyển Hồ sơ nhân vật thành thẻ ngữ cảnh khi cần, không sao chép thành một bản nhân vật thứ hai.

### 3. Trạng thái hiện tại là ảnh chụp sau tập đã duyệt

Thêm mô hình khái niệm `SeriesCurrentState`:

```text
SeriesCurrentState
  id
  series_id
  based_on_episode_number
  character_states_json
  relationship_states_json
  location_states_json
  prop_states_json
  open_threads_json
  unresolved_conflicts_json
  revision
  approval_status
  approved_at
  created_at
  updated_at
```

AI chỉ đề xuất bản thay đổi trạng thái. Người dùng phải duyệt trước khi bản đó trở thành trạng thái hiện tại. Bản cũ được giữ để truy vết, chưa bị ghi đè không thể phục hồi.

### 4. Tóm tắt toàn series dùng cấu trúc phân tầng

Hệ thống lưu:

- tóm tắt riêng từng tập;
- tóm tắt từng chặng, ví dụ mỗi 10 tập hoặc theo mạch truyện;
- tóm tắt tổng quát toàn series;
- trạng thái hiện tại;
- danh sách mạch truyện đang mở.

Khi cần tìm sự kiện cũ, bộ chọn đọc mục lục rồi lấy đúng tóm tắt tập hoặc chặng liên quan. Không bắt AI đọc tuần tự toàn bộ tệp qua nhiều yêu cầu.

### 5. Bộ chọn ký ức hoạt động theo nhiệm vụ

Thêm dịch vụ khái niệm `SeriesContextCompiler`. Đầu vào gồm series, số tập, loại nhiệm vụ, nguồn người dùng, Master Story hoặc shot hiện tại và các mã thực thể đã biết.

Loại nhiệm vụ tối thiểu:

- `story_candidate`;
- `master_story`;
- `image_panel_prompt`;
- `video_story_development`;
- `shot_breakdown`;
- `video_prompt`;
- `voice`;
- `subtitle`.

Mỗi kết quả trả về:

- nội dung ngữ cảnh đã biên dịch;
- danh sách thẻ và phiên bản đã dùng;
- nhóm dữ liệu và dung lượng đã dùng;
- dữ liệu bắt buộc bị thiếu;
- phần bị rút gọn;
- lý do chọn từng thẻ quan trọng.

### 6. Phân bổ 24.000 ký tự theo nhóm, không cắt phần đầu

Giới hạn ban đầu vẫn có thể dùng ký tự để tương thích, nhưng phải phân bổ theo nhóm:

```text
15% quy tắc bất biến và danh tính series
20% nhân vật và quan hệ liên quan
10% địa điểm và đạo cụ
15% mạch truyện đang mở
15% trạng thái hiện tại và tập gần nhất
20% Master Story, panel hoặc shot hiện tại
 5% điều cấm và yêu cầu đầu ra
```

Nhóm bắt buộc không được mất chỉ vì nhóm trước quá dài. Phần dư của nhóm ngắn có thể chuyển cho nhóm cần thêm. Sau này có thể đổi sang đếm token mà không thay hợp đồng bên ngoài.

### 7. Ưu tiên dữ liệu rõ ràng

Khi có mâu thuẫn, thứ tự ưu tiên là:

```text
Yêu cầu người dùng đã xác nhận cho tập hiện tại
> quy tắc canon và đặc điểm cố định đã duyệt
> trạng thái hiện tại đã duyệt
> Master Story đã duyệt
> thẻ nhớ đã duyệt
> tóm tắt tập và chặng
> văn bản Series Bible cũ làm dữ liệu dự phòng
```

Yêu cầu mới không được âm thầm phá đặc điểm cố định. Nếu người dùng thật sự muốn đổi canon, hệ thống phải tạo đề xuất thay đổi riêng để duyệt.

### 8. Kiểm tra canon trả về bằng chứng

Sau khi tạo prompt ảnh hoặc video, bộ kiểm tra đối chiếu:

- nhân vật và đặc điểm cố định;
- quan hệ và trạng thái cảm xúc;
- địa điểm và đạo cụ;
- mạch truyện và bí mật chưa được phép tiết lộ;
- trạng thái đầu và cuối đoạn;
- quy tắc phong cách và điều cấm.

Kết quả gồm `passed`, `blocking_conflicts`, `warnings`, `evidence_card_ids` và đề xuất sửa. Lỗi chặn không được chuyển prompt sang trạng thái đã đạt chất lượng. Người dùng có thể ghi đè thủ công nhưng phải nhập lý do và hệ thống lưu nhật ký.

### 9. Dấu vết ngữ cảnh phải an toàn

Lưu mã thẻ, phiên bản, dung lượng và lý do chọn; không lưu lại bí mật provider, token, cookie hoặc toàn bộ prompt nhạy cảm trong log. UI hiển thị tiếng Việt và cho phép mở thẻ nguồn để người dùng hiểu AI đã dựa vào đâu.

## Di chuyển dữ liệu

- Series cũ vẫn hoạt động khi chưa có thẻ nhớ.
- Dịch vụ tạo các thẻ nháp từ Series Bible, continuity và tóm tắt hiện có nhưng không tự duyệt.
- Hồ sơ nhân vật hiện tại tiếp tục được dùng trực tiếp.
- `series-memory.md` v2 vẫn đọc được trong giai đoạn chuyển tiếp; sau khi có bộ biên dịch mới, tệp được dựng theo phiên bản mới và không còn là payload duy nhất.

## Rủi ro và giảm thiểu

- Rủi ro tạo hai nguồn sự thật: chỉ dữ liệu cơ sở đã duyệt là chuẩn; Markdown là bản dựng.
- Rủi ro bộ chọn bỏ sót dữ liệu: luôn ghim quy tắc bất biến, trạng thái hiện tại và các thực thể xuất hiện rõ trong nhiệm vụ.
- Rủi ro tóm tắt AI làm sai canon: mọi thay đổi canon và trạng thái phải được duyệt.
- Rủi ro 24.000 ký tự vẫn thiếu: ghi rõ nhóm bị rút gọn và cho phép tăng dung lượng theo cấu hình sau này.
- Rủi ro kiểm tra canon báo sai: phân biệt lỗi chặn với cảnh báo và hỗ trợ ghi đè có lý do.

## Khả năng quay lui

Có thể tắt bộ chọn mới theo cấu hình và quay về ngữ cảnh Series Bible hiện tại. Các bảng thẻ nhớ và trạng thái chỉ bổ sung dữ liệu, không xóa trường cũ. Tệp Markdown có thể dựng lại từ cơ sở dữ liệu ở cả hai chế độ.
