# Tasks

## 1. Chuẩn bị và rà soát

- [x] 1.1 Rà soát các màn đang tạo/chọn series: AI Video Assistant, Story Studio và Comic Series Analysis handoff.
- [x] 1.2 Rà soát API `listVideoSeries`, `createVideoSeries`, `updateVideoSeries`, `createVideoSeriesEpisode` và response `VideoSeriesResponse`.
- [x] 1.3 Chốt mapping mode theo ngữ cảnh: AI Video direct, Story Studio, Comic handoff và quản lý tất cả series.

## 2. Popup tạo/chọn series

- [x] 2.1 Thiết kế component popup chọn series dùng card/list, tìm kiếm, filter mode, loading/error/empty state tiếng Việt.
- [x] 2.2 Hiển thị trên mỗi card: tên, mode, số tập, số tập truyện, số tập video, số nhân vật, provider binding, ngày cập nhật và preview Series Bible.
- [x] 2.3 Thêm cảnh báo/disabled state khi series không phù hợp với ngữ cảnh hiện tại.
- [x] 2.4 Thiết kế popup tạo series mới gồm tên, mode, giải thích mode, các trường Series Bible và preview trước khi lưu.
- [x] 2.5 Sau khi tạo series mới, cho phép chọn series vừa tạo, mở quản lý nhân vật hoặc tạo tập mới tùy màn gọi.
- [x] 2.6 Thay select inline trong khu "Sổ tay series" của AI Video bằng action mở popup, nhưng vẫn giữ thao tác sửa Series Bible hiện có.
- [x] 2.7 Đồng bộ pattern popup cho Story Studio và Comic handoff nếu đang tạo/chọn series trong các luồng đó.
- [x] 2.8 Bảo đảm toàn bộ copy UI của popup là tiếng Việt.

## 3. Schema/artifact cho AI Video series nhiều nhân vật

- [x] 3.1 Định nghĩa schema `episode_cast` cho AI Video project thuộc series.
- [x] 3.2 Định nghĩa schema `episode_only_guests` cho nhân vật chỉ dùng trong tập hiện tại.
- [x] 3.3 Định nghĩa schema `new_character_proposals` gồm profile đề xuất, lý do, mức ảnh hưởng canon, artifact bị ảnh hưởng và trạng thái duyệt.
- [x] 3.4 Thêm nơi lưu an toàn cho cast/proposal/resume metadata bằng migration hoặc JSON field hiện có, không phá dữ liệu project cũ.
- [x] 3.5 Bảo đảm project không có `series_id` không bắt buộc có các artifact này.

## 4. Backend service luồng nhiều nhân vật

- [x] 4.1 Khi `develop_story` chạy cho series, compile `SeriesCharacterProfile` vào context bắt buộc.
- [x] 4.2 Yêu cầu AI tạo `episode_cast` từ roster hiện có trước khi chia scene/shot.
- [x] 4.3 Yêu cầu AI ưu tiên nhân vật có sẵn và chỉ tạo nhân vật mới khi story thật sự cần.
- [x] 4.4 Phân loại proposal: background extra, episode-only guest, canon-impacting character.
- [x] 4.5 Chặn auto-run ở `needs_review` với `review_stage = "character_proposals"` khi có proposal cần duyệt.
- [x] 4.6 Thêm API quyết định proposal: thêm vào Series, chỉ dùng trong tập này, từ chối.
- [x] 4.7 Khi thêm vào Series, tạo `SeriesCharacterProfile`, ghi revision/memory/dependency phù hợp.
- [x] 4.8 Khi chọn episode-only, lưu vào artifact tập hiện tại và không ghi vào series canon.
- [x] 4.9 Khi từ chối, regenerate story/shot/prompt từ checkpoint an toàn.
- [x] 4.10 Resume auto-run từ `resume_step` sau khi mọi proposal bắt buộc đã có quyết định.

## 5. Prompt video 3D nhiều nhân vật

- [x] 5.1 Cập nhật prompt story/shot/prompt để hỗ trợ nhiều nhân vật trong series.
- [x] 5.2 Thêm `visible_characters` hoặc metadata tương đương cho scene/shot/prompt.
- [x] 5.3 Prompt video series phải mô tả từng nhân vật: identity lock, vị trí, hành động, biểu cảm và tương tác.
- [x] 5.4 Prompt video series phải dùng phong cách phim hoạt hình 3D/stylized 3D/cinematic 3D animation.
- [x] 5.5 Negative prompt phải chống identity swap, duplicate character, unintended named character và sai trang phục nhận diện.
- [x] 5.6 Không dùng rule "same main character only" trong luồng series nhiều nhân vật.
- [x] 5.7 Background extras chỉ được mô tả là anonymous/non-canon khi story/shot cần bối cảnh đông người.

## 6. UI review nhân vật mới

- [x] 6.1 Khi auto-run dừng ở `character_proposals`, hiển thị panel review tiếng Việt cạnh tiến trình auto-run.
- [x] 6.2 Hiển thị mỗi proposal bằng card gồm tên, vai trò, lý do, ảnh hưởng canon, mô tả ngoại hình/tính cách và artifact bị ảnh hưởng.
- [x] 6.3 Thêm ba action rõ: "Thêm vào Series", "Chỉ dùng trong tập này", "Từ chối".
- [x] 6.4 Sau mỗi quyết định, cập nhật UI để biết proposal nào đã xử lý, proposal nào còn chờ.
- [x] 6.5 Khi xử lý xong proposal bắt buộc, cho phép auto-run tiếp tục từ checkpoint.

## 7. Kiểm thử

- [x] 7.1 Test popup chọn series hiển thị đúng thông tin từ `VideoSeriesResponse`.
- [x] 7.2 Test popup lọc/disable series theo mode và ngữ cảnh.
- [x] 7.3 Test tạo series mới từ popup và chọn series vừa tạo.
- [x] 7.4 Test AI Video cơ bản không series vẫn tạo project/auto-run như trước.
- [x] 7.5 Test AI Video series tạo `episode_cast` từ `SeriesCharacterProfile`.
- [x] 7.6 Test auto-run dừng ở `character_proposals` khi AI đề xuất nhân vật named/foreground/canon-impacting.
- [x] 7.7 Test auto-run không dừng với anonymous background extras.
- [x] 7.8 Test approve-as-series-character tạo `SeriesCharacterProfile` và sync memory.
- [x] 7.9 Test episode-only không ghi vào series canon.
- [x] 7.10 Test reject proposal regenerate artifact bị ảnh hưởng từ checkpoint an toàn.
- [x] 7.11 Test prompt video series có nhiều nhân vật, 3D style và negative prompt chống lẫn nhân vật.
- [x] 7.12 Test UI copy tiếng Việt và thông báo lỗi không lộ raw status/code khó hiểu.

## 8. Tài liệu và nghiệm thu

- [x] 8.1 Cập nhật tài liệu tiếng Việt giải thích cách tạo/chọn series bằng popup.
- [x] 8.2 Cập nhật tài liệu tiếng Việt giải thích dàn nhân vật series, episode cast và nhân vật khách mời.
- [x] 8.3 Cập nhật tài liệu tiếng Việt giải thích vì sao full-auto vẫn dừng khi có nhân vật canon mới.
- [x] 8.4 Chạy `openspec validate son-24-07-phat-trien-luong-series-phim-da-nhan-vat-ai-video-va-popup-series --strict`.
- [x] 8.5 Sau khi apply code, chạy test backend/frontend liên quan và kiểm tra thủ công flow tạo/chọn series popup.
