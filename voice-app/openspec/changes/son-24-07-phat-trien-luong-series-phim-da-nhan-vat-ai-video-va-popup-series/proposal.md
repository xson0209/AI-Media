# 24-07 - Phát triển luồng series phim đa nhân vật AI Video và popup series

## Vì sao

Luồng AI Video hiện tại phù hợp với video đơn lẻ hoặc series video đơn giản, nhưng khi làm một series phim hoạt hình dài tập có nhiều nhân vật thì cách nhập liệu và chọn series hiện chưa đủ rõ. Người dùng cần một luồng series riêng để AI có thể tự chọn nhân vật, tự phát triển kịch bản theo dàn nhân vật, tạo prompt video nhiều nhân vật và vẫn giữ quyền duyệt khi AI đề xuất nhân vật mới ảnh hưởng canon.

Khu "Sổ tay series" trong AI Video hiện đang đặt thao tác tạo series mới, chọn series, sửa Series Bible và tạo tập mới trong cùng một panel. Khi danh sách series dài hoặc mỗi series có nhiều thông tin như mode, số tập, nhân vật, provider binding và continuity, một select inline không đủ để người dùng kiểm tra đúng series trước khi tạo tập. Cần chuyển thao tác "Tạo series mới / Chọn series" lên popup chi tiết, hiển thị rõ thông tin trước khi chọn.

## Mục tiêu

- Tạo proposal OpenSpec ngày 24-07, tên change bằng tiếng Việt không dấu và toàn bộ nội dung artifact bằng tiếng Việt.
- Phát triển luồng AI Video series nhiều nhân vật, chỉ bật khi project có `series_id`.
- Giữ nguyên luồng AI Video cơ bản không series.
- Cho AI tự chọn `episode_cast` từ `SeriesCharacterProfile`.
- Cho AI tự đề xuất nhân vật mới khi cần, nhưng dừng auto-run để người dùng duyệt trước khi ghi vào canon series.
- Cho người dùng duyệt nhân vật mới bằng ba quyết định: thêm vào Series, chỉ dùng trong tập này, hoặc từ chối.
- Resume auto-run từ checkpoint phù hợp sau khi người dùng duyệt nhân vật mới.
- Nâng prompt video series thành prompt nhiều nhân vật theo phong cách phim hoạt hình 3D, khóa nhận diện từng nhân vật.
- Thay select inline tạo/chọn series bằng popup rõ ràng cho các màn tạo/chọn series liên quan.

## Phạm vi

### Trong phạm vi

- UI popup "Tạo series mới" và "Chọn series" cho AI Video Assistant.
- Quy tắc hiển thị popup series có thể tái dùng cho Story Studio và luồng handoff truyện tranh sang series.
- Tóm tắt series rõ trong popup: tên, mode, số tập, số nhân vật, tóm tắt Series Bible, tóm tắt tập trước, provider binding, ngày cập nhật và cảnh báo mode không phù hợp.
- Luồng AI Video series nhiều nhân vật:
  - `episode_cast`;
  - nhân vật xuất hiện theo scene/shot/prompt;
  - đề xuất nhân vật mới;
  - gate duyệt nhân vật mới;
  - resume auto-run;
  - prompt video 3D nhiều nhân vật;
  - negative prompt chống lẫn/nhân bản/sai nhân vật.
- Backend/API/schema nếu cần để lưu artifact cast, proposal nhân vật mới và resume checkpoint.
- Tests cho backend, UI và spec behavior.

### Ngoài phạm vi

- Không thay đổi cách AI Video cơ bản không series đang chạy.
- Không tự render video bằng provider mới.
- Không tự tạo ảnh/clip nhân vật trong proposal này.
- Không cho full-auto tự ghi nhân vật mới vào canon nếu chưa có quyết định duyệt rõ của người dùng.
- Không đổi `series_mode` của series đã tồn tại nếu chưa có proposal riêng cho migration/chuyển mode.

## Thay đổi hành vi chính

1. Người dùng mở thao tác tạo/chọn series bằng popup thay vì phải đọc một select inline chật.
2. Popup chọn series hiển thị card chi tiết và chỉ cho chọn series phù hợp với ngữ cảnh:
   - AI Video tạo tập trực tiếp: ưu tiên/cho phép `video_story_only`.
   - Story Studio: cho phép `image_story_only` và `hybrid`.
   - Handoff từ truyện tranh: không cho chọn `video_story_only`.
3. Khi tạo tập AI Video từ series, AI tạo `episode_cast` từ character profiles đã có.
4. Nếu AI cần nhân vật mới có tên, foreground, thoại, vai trò câu chuyện hoặc khả năng tái xuất, auto-run dừng ở `status = "needs_review"` và `review_stage = "character_proposals"`.
5. Sau khi người dùng duyệt, hệ thống resume từ `resume_step` phù hợp thay vì chạy lại toàn bộ nếu không cần.
6. Prompt video series phải mô tả từng nhân vật rõ ràng trong không gian 3D, gồm vị trí, hành động, biểu cảm và identity lock.

## Tác động dự kiến

- Người dùng nhìn rõ series trước khi tạo/chọn, giảm chọn nhầm.
- Series phim hoạt hình có thể mở rộng lên nhiều nhân vật mà không bắt người dùng tự gán nhân vật cho từng shot.
- Canon series được bảo vệ vì AI chỉ được đề xuất, không được tự ghi nhân vật mới.
- Prompt video có chất lượng tốt hơn cho phim 3D nhiều nhân vật, giảm lỗi lẫn nhân vật, nhân bản nhân vật hoặc xuất hiện người ngoài ý muốn.

## Liên quan

- `4.tao-truyen-anh-va-video-truyen-theo-series`: nền tảng `series_mode`, `SeriesCharacterProfile`, Series Memory.
- `auto-chay-ai-video-nguyen-lieu`: nền tảng auto-run, `needs_review`, `review_stage`, continue/resume.
- `15.ket-noi-hop-dong-noi-dung-xuyen-suot-ai-video`: quality gate, continuity state ledger, dependency/stale.
- `13-phan-tich-truyen-tranh-tu-lien-ket-va-tao-series`: nguyên tắc approved/unreviewed, không dùng dữ liệu chưa duyệt làm canon.
