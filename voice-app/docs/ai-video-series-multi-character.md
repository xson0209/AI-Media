# Luồng AI Video series đa nhân vật

Tài liệu này mô tả cách dùng popup tạo/chọn series và cách AI Video xử lý dàn nhân vật nhiều tập. Luồng mới chỉ áp dụng cho project có `series_id`; project AI Video độc lập vẫn chạy theo workflow cũ và không bắt buộc duyệt nhân vật series.

## Tạo và chọn series bằng popup

Các màn có thao tác chọn series dùng popup tiếng Việt thay cho select inline khi người dùng cần kiểm tra thông tin trước khi chọn.

- **AI Video Assistant**:
  - Khu `Sổ tay series` mở popup `Chọn series` ở chế độ quản lý tất cả series để xem, chọn và sửa Series Bible.
  - Popup `Tạo tập mới` chỉ chọn được series `video_story_only`, đúng luồng tạo tập video trực tiếp.
  - Popup tạo series mới cho phép nhập tên, loại series và các trường Series Bible: nhân vật cố định, world, style, quy tắc nhất quán, điều cần tránh và tóm tắt tập trước.
- **Story Studio**:
  - Popup chọn series chỉ dùng series `image_story_only` hoặc `hybrid`.
  - Popup tạo series mới cho phép nhập Series Bible ngay từ đầu, rồi chọn series vừa tạo để quản lý nhân vật hoặc tạo tập.
- **Comic Series Analysis handoff**:
  - Khi nối package truyện tranh vào series hiện có, popup chỉ cho chọn `image_story_only` hoặc `hybrid`.
  - Luồng tạo series mới vẫn đi qua API handoff để giữ nguyên package phân tích, script tối ưu và dữ liệu đã duyệt.

Trong popup chọn series, mỗi card hiển thị các thông tin cần kiểm tra trước khi chọn:

- tên series và loại series;
- số tập tổng, số tập truyện, số tập video;
- số hồ sơ nhân vật;
- provider binding nếu có;
- ngày cập nhật và revision;
- preview rút gọn của `character_bible`, `world_bible`, `style_bible`, `continuity_rules`, `negative_rules` và `previous_episode_summary`.

Nếu một series không phù hợp với ngữ cảnh hiện tại, card bị khóa và hiển thị lý do bằng tiếng Việt. Ví dụ: AI Video trực tiếp không chọn series truyện ảnh/hybrid; Comic handoff không chọn series video-only.

## Dàn nhân vật của tập

Khi project AI Video thuộc một series, bước phát triển story đọc `SeriesCharacterProfile`, Series Bible và Series Memory để tạo artifact dàn nhân vật cho riêng tập đó.

`episode_cast` là danh sách nhân vật series được AI chọn cho tập hiện tại. Mỗi phần tử gồm:

- `character_profile_id` nếu nhân vật đã có hồ sơ cấu trúc;
- `name`;
- `episode_role`;
- `importance`;
- `reason_vi`;
- `identity_lock`, `visual_identity` và `fixed_traits` khi có đủ dữ liệu.

`episode_cast` không tự sửa canon. Nó chỉ nói tập này dùng những nhân vật nào từ roster đã có.

`episode_only_guests` là các nhân vật chỉ được dùng trong tập hiện tại. Chúng có thể được sinh từ proposal đã được người dùng chọn `Chỉ dùng trong tập này`. Dữ liệu này được lưu trong artifact của project/tập, không ghi vào `SeriesCharacterProfile` và không trở thành Series Memory canon.

`new_character_proposals` là danh sách nhân vật AI đề xuất vì story cần thêm người mới. Mỗi proposal có:

- tên và vai trò trong tập;
- lý do đề xuất bằng tiếng Việt;
- mức ảnh hưởng canon;
- khả năng tái xuất;
- cờ rủi ro như foreground, có thoại, ảnh hưởng plot, background extra;
- mô tả nhận diện như mặt, tóc, dáng, trang phục, tính cách, cách nói, fixed traits;
- artifact bị ảnh hưởng như story, shots hoặc prompts;
- trạng thái duyệt.

Background extra vô danh, đám đông, silhouette hoặc người qua đường không thoại và không ảnh hưởng canon có thể được phân loại là không cần review. Prompt vẫn phải ghi rõ đó là background extra không phải nhân vật canon.

## Gate duyệt nhân vật mới

AI được phép đề xuất nhân vật mới, nhưng không được tự ghi nhân vật đó vào canon series. Vì vậy full-auto vẫn dừng nếu proposal có khả năng ảnh hưởng canon.

Auto-run dừng khi proposal có một trong các dấu hiệu:

- nhân vật có tên;
- nhân vật foreground;
- có thoại;
- có hành động ảnh hưởng plot;
- có khả năng tái xuất;
- tạo hoặc sửa quan hệ canon;
- sửa fixed traits hoặc continuity của nhân vật đã có.

Khi dừng, auto-run chuyển sang:

```text
status = "needs_review"
review_stage = "character_proposals"
current_step = "review_character_proposals"
```

UI hiển thị panel duyệt nhân vật mới cạnh tiến trình auto-run. Mỗi proposal có ba quyết định:

- **Thêm vào Series**: tạo `SeriesCharacterProfile`, tăng revision series, sync memory/dependency và đưa nhân vật vào `episode_cast`.
- **Chỉ dùng trong tập này**: lưu vào `episode_only_guests`, không ghi vào canon series.
- **Từ chối**: đánh dấu proposal bị từ chối và làm stale các artifact bị ảnh hưởng để regenerate từ checkpoint an toàn.

Sau khi mọi proposal bắt buộc có quyết định, nút tiếp tục auto-run chạy từ `resume_step`. Với proposal bị từ chối, `resume_step` phụ thuộc artifact bị ảnh hưởng:

- story bị ảnh hưởng: quay lại `develop_story`;
- shot bị ảnh hưởng: quay lại `generate_shots`;
- chỉ prompt bị ảnh hưởng: quay lại `generate_prompts`.

## Prompt video nhiều nhân vật

Prompt video của project series không dùng rule một nhân vật chính duy nhất. Prompt phải dùng đúng dàn nhân vật đã được duyệt cho tập hiện tại: `episode_cast` và `episode_only_guests`.

Mỗi prompt series cần mô tả theo hướng phim hoạt hình 3D/stylized 3D/cinematic 3D animation:

- identity lock riêng cho từng nhân vật;
- vị trí trong khung hình;
- hành động;
- biểu cảm;
- ai nói và ai phản ứng;
- tương tác hoặc tension giữa các nhân vật;
- camera/framing giúp đọc rõ nhiều nhân vật;
- continuity notes từ state của project/series.

Negative prompt cần chặn lỗi thường gặp khi có nhiều nhân vật: duplicate character, identity swap, unintended named character, wrong face, wrong hairstyle, wrong signature outfit và extra foreground character ngoài cast.

