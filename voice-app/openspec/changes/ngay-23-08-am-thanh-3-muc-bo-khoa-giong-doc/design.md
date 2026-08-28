## Context

Điều kiện dựng MP4 suy ra "shot bắt buộc phải có giọng đọc" từ một hàm duy nhất chỉ kiểm tra `english_narration` có chữ hay không (`backend/services/video_rendering.py:857`). Không có thiết lập nào tắt được điều đó. Với project mà mọi shot đều có lời kể nhưng người dùng không cần đọc thành tiếng, nút Dựng MP4 bị khóa cứng ở frontend bởi `!readiness?.ready` (`AIVideoRenderPanel.tsx:710`) và không có đường thoát nào.

Hai reason mà người dùng thấy là một nguyên nhân: `resolve_shot_duration` (`video_rendering.py:861-871`) cho shot có narration chỉ đọc `shot.audio_duration`, không bao giờ quay về `duration_seconds`. Không có giọng đọc nghĩa là không có thời lượng, nên bị chặn thêm lần thứ hai.

Codebase đã chừa sẵn chỗ cho mức thứ ba: `CLIP_AUDIO_MODE_CLIP_ONLY = "clip_only"` tồn tại ở `video_rendering.py:79` với comment nói rõ nó được reserve để mức mới không phải đổi API, nhưng chưa có nhánh nào dùng. Phía frontend lại có comment ngược lại ở `renderSettingsStore.ts:33-36` cho rằng mức thứ ba là vô nghĩa — lập luận đó giả định shot có narration thì luôn có giọng đọc, chính là giả định đang sai.

Ràng buộc hiện có cần tôn trọng:
- API dùng field boolean `mute_clip_audio`, chỉ chở được hai mức. Job đã lưu trong database và thiết lập đã lưu ở máy người dùng đều theo field này.
- Luồng dựng tự động đọc lại thiết lập của project qua `render_settings_for_project` (`video_rendering.py:1366`), nên mức mới tự lan sang render không giám sát.
- `duration_mode` chỉ có tác dụng khi thời lượng mục tiêu khác thời lượng clip (`video_rendering.py:2128`).
- Cue phụ đề chia theo tỉ lệ độ dài chữ trên thời lượng shot (`video_subtitles.py:197-248`), không đọc waveform.

## Goals / Non-Goals

**Goals:**
- Người dùng dựng được MP4 dùng tiếng gốc của clip mà không cần tạo giọng đọc.
- Ba mức âm thanh nằm trong một danh sách chọn duy nhất, mỗi mức nói rõ kết quả nhận được.
- Mọi project cũ, job cũ và thiết lập đã lưu cho ra kết quả không đổi.
- Timeline giữ đủ mọi shot ở mức mới; không shot nào bị bỏ âm thầm.

**Non-Goals:**
- Không đổi giá trị mặc định của mức âm thanh.
- Không đổi cách trộn SFX/BGM của enhanced audio.
- Không thêm mức thứ tư.
- Không sửa `english_narration` của shot, không thêm state mới cho `voice_status`.
- Không đổi bước làm sạch watermark.

## Decisions

### Thêm field mức âm thanh, giữ lại field boolean cũ

`VideoRenderSettings` nhận thêm một field mức âm thanh ba giá trị, và field boolean `mute_clip_audio` được giữ lại làm bản phản chiếu.

Field mới **phải** cho phép vắng giá trị. Job đã lưu trong database không có field mới; nếu field mới có giá trị mặc định cứng là mức chỉ dùng giọng đọc, thì job cũ đang ở mức kết hợp (`mute_clip_audio = false`) sẽ bị đọc thành mức chỉ dùng giọng đọc khi `model_validate_json` chạy ở `video_rendering.py:1382` và `:2145`. Kết quả là mất tiếng gốc mà không có lỗi nào báo ra. Vì vậy hàm phân giải mức đọc field mới trước, và chỉ khi field mới vắng thì mới suy từ boolean cũ.

*Đã cân nhắc*: đổi hẳn boolean thành enum và bỏ boolean. Loại bỏ vì phải viết migration cho `settings_json` của job cũ và cho thiết lập ở máy người dùng, đổi nhiều call site hơn, đổi lấy một field không còn dùng — không xứng với rủi ro.

### Mức chỉ dùng tiếng gốc bỏ hẳn nhánh trộn, không phải hạ mức xuống 0

Ở mức chỉ dùng tiếng gốc, timeline tiếng gốc trở thành nguồn audio chính trực tiếp, thay cho `audio.wav` của giọng đọc. Không dựng timeline giọng đọc, không `sidechaincompress`, không `amix`.

*Đã cân nhắc*: dùng lại nhánh kết hợp với mức nền 1.0 và trông cậy vào việc timeline giọng đọc toàn `anullsrc` nên bộ hạ mức không kích hoạt. Loại bỏ vì đúng một cách ngầm định: nó chỉ đúng khi project chưa có giọng đọc, và sẽ sai ngay khi project có giọng đọc mà người dùng vẫn chọn mức này. Cách tách nhánh còn bỏ được một lượt ffmpeg.

### Quy tắc bỏ tiếng nền cho giọng trích từ clip chỉ áp cho mức kết hợp

`clip_audio_bed_decision` hiện trả về nhánh bỏ tiếng nền khi project dùng speech source trích từ clip và phân đoạn có narration (`video_rendering.py:2909-2911`). Lý do gốc là tránh cộng trùng cùng một nguồn gây vọng tiếng.

Ở mức chỉ dùng tiếng gốc không có timeline giọng đọc nào để cộng trùng, nên nhánh đó không được áp. Nếu áp, nó sẽ làm im lặng đúng những phân đoạn có thoại — hỏng nặng hơn cả lỗi ban đầu. Quyết định phân giải theo mức trở thành: mức chỉ dùng tiếng gốc thì dùng tiếng gốc nếu clip có audio, ngược lại im lặng, không xét speech source.

### Nguồn thời lượng ở mức chỉ dùng tiếng gốc là thời lượng clip

Thời lượng lấy từ clip active, quay về `duration_seconds` của shot khi không đọc được thời lượng clip. Thiếu cả hai thì vẫn chặn — không có nguồn thời lượng nào thì không dựng được.

Chọn thời lượng clip vì ở mức này audio phát ra chính là audio của clip; ép thời lượng khác sẽ cắt hoặc đóng băng giữa tiếng. Hệ quả phụ có lợi: thời lượng mục tiêu bằng thời lượng clip nên `duration_mode` tự mất tác dụng, không cần code đặc biệt.

*Đã cân nhắc*: luôn dùng `duration_seconds` của kịch bản. Loại bỏ vì sẽ lệch so với audio đang phát.

### Phụ đề chỉ được mở khả năng, không bị hệ thống bật tắt

Điều kiện tạo phụ đề bỏ yêu cầu giọng đọc khi mức âm thanh là chỉ dùng tiếng gốc (`video_subtitles.py:315`). Chế độ phụ đề vẫn do người dùng chọn.

Cue phụ đề chia theo tỉ lệ trên thời lượng shot, không đọc waveform, nên bỏ điều kiện là chạy đúng ngay. Nếu không sửa chỗ này, người dùng ở chế độ phụ đề nhúng chỉ đổi hai reason cũ thành reason mới "Chưa có phụ đề hoàn tất để burn vào video" — vẫn bị chặn.

`video_subtitles` không nhận cấu hình dựng từ người gọi, nên nó đọc mức âm thanh của project qua `render_settings_for_project`, cùng cơ chế mà luồng dựng tự động đã dùng.

### Không dùng cờ bỏ qua readiness

`settings.force` có thể vượt cổng readiness (`video_rendering.py:1417`) nhưng không được dùng ở đây. `build_timeline_manifest` bỏ hẳn shot có thời lượng `None` (`:883-884`), nên bản dựng ép buộc sẽ thiếu đúng những shot chưa có giọng đọc mà không báo gì. Phải sửa điều kiện readiness cho đúng.

### Chữ ký hàm mở rộng bằng tham số tùy chọn

`resolve_shot_duration` (4 call site) và `build_timeline_manifest` (1 call site sản phẩm, 4 call site test) nhận thêm tham số mức âm thanh dạng keyword tùy chọn, mặc định giữ hành vi hiện tại. Test cũ không phải sửa và trở thành lưới an toàn cho hành vi cũ.

## Risks / Trade-offs

**Job cũ trong database bị đọc sai mức, mất tiếng gốc mà không báo lỗi** → Field mức âm thanh cho phép vắng giá trị; hàm phân giải suy từ boolean cũ khi field vắng. Test hiện có ở `backend/tests/test_ai_video_backend.py:2314` dựng job với `mute_clip_audio=false` và phải tiếp tục ra mức kết hợp.

**Thiết lập đã lưu ở máy người dùng bị mất lựa chọn khi nâng cấp** → Hàm hợp nhất thiết lập suy mức từ boolean đã lưu khi blob cũ không có field mới. Kịch bản này nằm trong `app/scripts/verify-render-settings-persistence.mjs`.

**Danh sách validator và danh sách giá trị mặc định lệch nhau** → Script verify hiện có so khớp chính xác tập khoá của hai danh sách (`verify-render-settings-persistence.mjs:107-109`). Thêm field phải thêm vào cả `DEFAULT_RENDER_SETTINGS` và `VALIDATORS`, nếu không script này đỏ.

**Phân đoạn có thoại bị im lặng ở mức mới** → Rủi ro lớn nhất về chất lượng đầu ra. Nhánh quyết định nguồn tiếng nền ở mức chỉ dùng tiếng gốc không được xét speech source. Cần test riêng cho project `target_language=vi`.

**Người dùng chọn mức mới trên project mà mọi clip đều không có audio, nhận MP4 im lặng mà không hiểu vì sao** → Cảnh báo theo phân đoạn cho clip không có audio, và cảnh báo tổng khi toàn bộ timeline im lặng. Không chặn bản dựng, vì im lặng vẫn là kết quả hợp lệ mà người dùng có thể muốn.

**Endpoint readiness nhận cấu hình qua query param nên field mới phải được thêm ở bốn lớp** (`models.py`, `routes/ai_video.py`, `client.ts`, `types.ts`) → Thiếu một lớp thì danh sách chọn đổi mà checklist không đổi theo, nút vẫn xám. Khoá cache của query readiness đã chứa cấu hình (`AIVideoRenderPanel.tsx:126`) nên không cần thêm gì cho việc refetch.

## Migration Plan

Không cần migration database. Field mới nằm trong `settings_json` dạng JSON tự do, và mọi giá trị vắng đều được suy từ field boolean cũ.

Thiết lập ở máy người dùng cũng không cần bước xoá: hàm hợp nhất bỏ qua khoá không có validator và suy mức từ những khoá đã có.

Cách quay lại: bỏ field mới khỏi cấu hình. Job đã lưu với field mới sẽ quay về đọc field boolean cũ, và vì hai field luôn được ghi khớp nhau nên mức kết quả không lệch.

## Open Questions

Không còn. Nguồn thời lượng, hành vi phụ đề, giá trị mặc định và cách xử lý tương thích ngược đều đã chốt trong phần Decisions.
