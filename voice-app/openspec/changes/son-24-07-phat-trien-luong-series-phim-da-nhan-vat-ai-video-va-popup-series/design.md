# Thiết kế

## Nguyên tắc

- Luồng AI Video cơ bản không có `series_id` giữ nguyên.
- Các hành vi mới chỉ tự động bật khi project thuộc series.
- Người dùng chỉ cần quản lý dàn nhân vật ở cấp series; AI tự chọn nhân vật phù hợp cho từng tập/cảnh/shot.
- AI được đề xuất nhân vật mới, nhưng không được tự ghi vào `SeriesCharacterProfile` nếu chưa được người dùng duyệt.
- Popup tạo/chọn series phải giúp người dùng kiểm tra đúng series trước khi tạo tập hoặc handoff.
- Toàn bộ label, cảnh báo, trạng thái và nội dung proposal này dùng tiếng Việt.

## Kiến trúc hiện có cần tận dụng

Backend hiện đã có:

- `VideoSeries` với `series_mode`, Series Bible, `latest_episode_number`, `revision`.
- `SeriesCharacterProfile` cho hồ sơ nhân vật có cấu trúc.
- `VideoSeriesResponse` trả `episode_count`, `story_episode_count`, `video_episode_count`, `character_profiles`, `provider_project_binding`.
- Auto-run có `status`, `current_step`, `review_stage`, `progress`.
- Trạng thái quality có `needs_review`, `blocked`, `stale`.
- Series Memory và dependency/stale tracking cho dữ liệu series.

Frontend hiện đã có:

- `AIVideoAssistant.tsx` với khu "Sổ tay series", select tạo/chọn series inline và popup "Tạo tập mới".
- `StoryStudio.tsx` có tạo/chọn series cho Story Studio.
- `ComicSeriesAnalysis.tsx` có khu handoff chọn tạo series mới hoặc thêm vào series hiện có.

Proposal này ưu tiên tái dùng API hiện có. Chỉ thêm field/API khi cần lưu artifact mới của luồng nhiều nhân vật.

## Popup tạo/chọn series

### Popup chọn series

Thay vì chỉ dùng `<select>`, các màn liên quan mở popup chọn series dạng card/list. Popup nhận một `context` để lọc và giải thích:

- `ai_video_direct`: tạo tập trực tiếp trong AI Video, chỉ cho chọn series `video_story_only`.
- `story_studio`: tạo tập trong Story Studio, cho chọn `image_story_only` và `hybrid`.
- `comic_handoff`: handoff truyện tranh sang Story Studio, cho chọn `image_story_only` và `hybrid`, không cho chọn `video_story_only`.
- `view_all`: quản lý/sửa series, có thể xem mọi series.

Mỗi card series hiển thị:

- tên series;
- loại series bằng tiếng Việt;
- số tập hiện tại;
- số tập truyện;
- số tập video;
- số hồ sơ nhân vật;
- trạng thái provider binding nếu có;
- ngày cập nhật;
- preview rút gọn của `character_bible`, `world_bible`, `style_bible`, `continuity_rules`, `negative_rules`, `previous_episode_summary`;
- cảnh báo nếu mode không phù hợp với ngữ cảnh hiện tại.

Popup cần có tìm kiếm theo tên series và filter theo mode. Series không phù hợp có thể bị ẩn theo mặc định hoặc hiện disabled với lý do tiếng Việt, tùy ngữ cảnh.

### Popup tạo series mới

Popup tạo series mới thay form inline dài bằng một dialog có cấu trúc:

1. Thông tin cơ bản:
   - tên series;
   - loại series: truyện ảnh, video, truyện + video;
   - giải thích ngắn tác động của từng mode.
2. Sổ tay series:
   - nhân vật cố định;
   - bối cảnh/world;
   - style hình ảnh;
   - quy tắc nhất quán;
   - điều cần tránh;
   - tóm tắt tập trước.
3. Preview trước khi lưu:
   - mode đã chọn;
   - luồng nào có thể dùng series này;
   - cảnh báo nếu chọn mode không phù hợp với nơi đang thao tác.
4. Hành động sau khi lưu:
   - chọn series vừa tạo;
   - mở quản lý nhân vật;
   - hoặc tạo tập mới ngay nếu đang ở AI Video.

### Không làm quá rộng

Popup chỉ làm rõ thao tác tạo/chọn series. Nó không thay thế toàn bộ màn quản lý Series Brain, nhân vật, reference, memory hoặc current state.

## Luồng AI Video series nhiều nhân vật

### Episode cast

Khi AI Video project có `series_id`, bước phát triển story phải đọc `SeriesCharacterProfile` và tạo artifact `episode_cast`.

Ví dụ cấu trúc logic:

```json
{
  "episode_cast": [
    {
      "character_profile_id": "char_1",
      "name": "An",
      "episode_role": "protagonist",
      "importance": "primary",
      "reason_vi": "Nhân vật chính của tập này"
    }
  ],
  "episode_only_guests": [],
  "new_character_proposals": []
}
```

`episode_cast` là dữ liệu của tập/project, không tự sửa `SeriesCharacterProfile`.

### Nhân vật theo scene/shot/prompt

Các artifact downstream nên biết nhân vật nào xuất hiện:

- scene: nhân vật chính trong cảnh, quan hệ/tension của cảnh;
- shot: `visible_character_ids`, `episode_guest_ids`, vị trí, hành động, biểu cảm;
- prompt: block `visible_characters` được biên dịch thành prompt video.

Nếu chưa thêm cột riêng, implementation có thể lưu tạm trong JSON metadata/payload hiện có với migration an toàn, nhưng spec phải yêu cầu output có cấu trúc để test được.

## Đề xuất nhân vật mới và gate duyệt

AI có thể sinh `new_character_proposals` khi story cần nhân vật chưa có trong roster.

Auto-run phải dừng khi proposal thuộc một trong các nhóm:

- nhân vật có tên;
- nhân vật foreground;
- nhân vật có thoại;
- nhân vật có hành động ảnh hưởng plot;
- nhân vật có khả năng tái xuất;
- nhân vật tạo/sửa quan hệ canon;
- nhân vật sửa fixed traits hoặc continuity của nhân vật đã có.

Auto-run không cần dừng với:

- người nền vô danh;
- đám đông;
- silhouette;
- người qua đường không tên;
- extra không thoại, không canon.

Khi dừng:

```text
status = "needs_review"
review_stage = "character_proposals"
current_step = "review_character_proposals"
resume_step = "develop_story" | "generate_shots" | "generate_prompts"
```

Người dùng có ba quyết định:

- `approve_as_series_character`: lưu thành `SeriesCharacterProfile`, cập nhật revision/memory, resume bằng context mới.
- `keep_episode_only`: lưu trong artifact tập hiện tại, không ghi series canon, resume.
- `reject`: đánh dấu rejected, regenerate artifact bị ảnh hưởng từ checkpoint an toàn.

Full-auto cũng phải tôn trọng gate này. Full-auto không được tự thêm nhân vật canon.

## Prompt video 3D nhiều nhân vật

Prompt AI Video series phải chuyển từ tư duy "một nhân vật chính duy nhất" sang "dàn nhân vật được duyệt".

Mỗi prompt cần có:

- style: phim hoạt hình 3D/stylized 3D/cinematic 3D animation;
- danh sách nhân vật nhìn thấy;
- identity lock cho từng nhân vật;
- vị trí trong khung hình;
- hành động riêng;
- biểu cảm riêng;
- ai nói, ai phản ứng;
- quan hệ/tension trong shot;
- camera/framing hỗ trợ đọc rõ nhiều nhân vật;
- continuity notes từ state in/out;
- negative prompt chống nhân vật ngoài ý muốn, nhân bản nhân vật, đổi mặt/đổi tóc/đổi trang phục nhận diện.

Prompt không được mặc định yêu cầu "same main character only" trong luồng series nhiều nhân vật. Thay vào đó, prompt phải nói rõ chỉ dùng approved episode cast và episode-only guests đã được duyệt cho tập hiện tại.

## Resume và stale

Khi người dùng duyệt/từ chối nhân vật mới, hệ thống phải xác định artifact nào bị ảnh hưởng:

- Nếu plot phụ thuộc nhân vật: regenerate từ story.
- Nếu chỉ shot/prompt cần nhân vật: regenerate từ shot hoặc prompt.
- Nếu chỉ prompt bị thiếu mô tả nhận diện: regenerate prompt.

Artifact đã tạo trước khi quyết định nhưng phụ thuộc vào proposal chưa duyệt không được coi là approved/canonical.

Nếu `SeriesCharacterProfile` mới được thêm vào series, các context snapshot downstream phải dùng revision mới hoặc bị đánh dấu stale đúng phạm vi.

## UI/UX

### Popup series

Yêu cầu UI:

- dễ đọc trên màn hình nhỏ;
- dùng card thay vì select khi cần xem nhiều thông tin;
- có tìm kiếm/filter;
- có empty state tiếng Việt;
- có loading/error state tiếng Việt;
- có badge mode rõ ràng;
- không yêu cầu người dùng hiểu code/status raw.

### Review nhân vật mới

Khi auto-run dừng ở `character_proposals`, UI hiển thị danh sách proposal dạng card:

- tên;
- vai trò;
- lý do AI tạo;
- mức ảnh hưởng canon;
- có thể tái xuất hay không;
- mô tả mặt/tóc/dáng/trang phục;
- tính cách/cách nói;
- scene/shot bị ảnh hưởng;
- ba nút quyết định.

Sau khi quyết định xong toàn bộ proposal bắt buộc, UI cho auto-run tiếp tục.

## Rủi ro và xử lý

- Rủi ro: popup quá nhiều thông tin. Xử lý: chỉ hiển thị summary trước, mở rộng chi tiết khi cần.
- Rủi ro: AI tạo quá nhiều nhân vật. Xử lý: giới hạn số proposal mỗi tập và yêu cầu AI ưu tiên roster có sẵn.
- Rủi ro: full-auto bị dừng nhiều lần. Xử lý: chỉ dừng với nhân vật named/foreground/canon-impacting, không dừng với extra vô danh.
- Rủi ro: prompt nhiều nhân vật làm video model lẫn mặt. Xử lý: identity lock từng nhân vật và negative prompt chống identity swap/duplicate.
- Rủi ro: chọn sai mode series. Xử lý: popup giải thích mode và disable series không phù hợp với ngữ cảnh.
