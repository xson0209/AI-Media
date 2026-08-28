## Context

Nạp clip Veo vào dự án hiện đi qua một đường duy nhất: mỗi shot một nút, mỗi lần một file. Giao diện dùng `<input type="file">` đọc `files?.[0]`, gọi `uploadVideoShotClip` → `POST /projects/{id}/shots/{shot_id}/clip` → `upload_shot_clip`. Toàn bộ ứng dụng hiện không có bất kỳ input nào bật `multiple`.

Backend đã có **hai** đường tạo clip, và chênh lệch giữa chúng là gốc của một vấn đề hiệu năng:

```
upload_shot_clip()       source="upload"    provider KHÔNG được set  → None
import_provider_clip()   source="provider"  provider=<tham số>       → "veo"
```

`import_provider_clip` nhận `source_path: Path` + `original_filename`, tự copy vào storage, tự probe metadata, tự vô hiệu clip cũ — nghĩa là phần khó của việc nạp theo lô đã tồn tại. Nó hiện chỉ được gọi từ `video_clip_generation.py` sau khi tự động tải clip từ trình duyệt.

Dữ liệu thực tế của dự án `Sơn test`: 18 clip đều là `(source='upload', provider=None)`, và `original_filename` là `1.mp4` … `18.mp4` khớp tuyệt đối với `shot_order` 1…18. Người dùng đã tự đặt tên theo số segment vì Google Flow không cho đặt tên file khi tải về, và prompt không tác động được tới tên file.

Về giao diện thiết lập dựng: công tắc tiếng gốc là checkbox đọc đảo dấu (`checked={!settings.mute_clip_audio}`), và thiết lập giữ trong `useState(DEFAULT_SETTINGS)` không lưu ở đâu. Hai luồng tự động (`video_auto_runs.py`, `video_clip_generation.py`) tạo `VideoRenderSettings()` mặc định nên không bao giờ đọc lựa chọn của người dùng.

Ràng buộc: giới hạn hiện có ở tầng nạp clip (700 MB, 120 giây, đuôi ∈ {mp4, mov, m4v, webm, mkv}) phải giữ nguyên. Trình duyệt không cho đọc đường dẫn thật của file đã chọn, chỉ cho tên file.

## Goals / Non-Goals

**Goals:**

- Nạp cả 18 clip trong một lượt chọn, khớp theo tên file dạng số.
- Người dùng thấy trước bảng khớp và tự quyết định có nạp hay không.
- Clip nạp theo lô có ghi hãng phát hành, để bước làm sạch dấu AI không phải dò cả 6 hãng.
- Lựa chọn nguồn tiếng gốc đọc được bằng tiếng Việt, không phải suy ngược từ dấu phủ định.
- Thiết lập dựng không mất khi tải lại trang, và luồng tự động tôn trọng lựa chọn đó.

**Non-Goals:**

- Không nhận file `.zip`. Người dùng giải nén rồi chọn thư mục.
- Không suy ra thứ tự từ nội dung video, thời gian tạo file, hay thứ tự chọn trong hộp thoại. Chỉ dựa vào tên file.
- Không tự sửa tên file hộ người dùng.
- Không thêm mức "chỉ tiếng gốc, bỏ giọng đọc" vào danh sách chọn.
- Không đổi giới hạn dung lượng, thời lượng, hay danh sách định dạng.
- Không bỏ nút nạp một clip cho từng shot.
- Không đụng luồng tự động sinh clip qua trình duyệt.

## Decisions

### 1. Khớp bằng tên file, không suy luận gì thêm

Quy tắc: lấy phần tên trước đuôi, đọc thành số nguyên, khớp với `shot_order`.

```
 "1.mp4"  → 1  → shot_order 1   ✓
"07.mp4"  → 7  → shot_order 7   ✓      (số 0 ở đầu vẫn đọc được)
"19.mp4"  → 19 → không có shot  ⚠ bỏ qua
"intro.mp4" → không đọc được số  ⚠ bỏ qua
```

Lý do chọn cách đơn giản nhất: dữ liệu thật đã chứng minh nó đủ — 18/18 clip khớp tuyệt đối. Người dùng cũng đã xác nhận sẽ tự đặt tên theo số segment.

Phương án khác đã cân nhắc:

- **Dùng thứ tự chọn file trong hộp thoại**: trình duyệt không bảo đảm thứ tự trong `FileList` theo thứ tự người dùng nhìn thấy, và người dùng thường Ctrl+A nên thứ tự là thứ tự hệ điều hành sắp — với tên `1, 10, 11, …, 2` thì sai hoàn toàn.
- **Rút số bất kỳ trong tên** (ví dụ `Scene_03_final.mp4` → 3): linh hoạt hơn nhưng nhập nhằng khi tên có nhiều số (`clip_2_v3.mp4` là shot 2 hay shot 3?). Bảng khớp sẽ trở thành thứ người dùng phải kiểm tra kỹ thay vì chỉ nhìn qua. Để ngỏ cho sau nếu thực tế cần.
- **Cho người dùng gán tay từng file vào shot**: chính xác tuyệt đối nhưng đúng bằng công sức của việc bấm 18 lần hiện tại, tức không giải quyết gì.

### 2. Xem trước rồi mới nạp, không nạp ngay khi chọn

Chọn file **không** kích hoạt nạp. Giao diện dựng bảng khớp, người dùng bấm xác nhận thì mới gửi.

```
┌─────────────────────────────────────────┐
│  1.mp4    →  Segment 01        ✓        │
│  2.mp4    →  Segment 02        ✓        │
│  5.mp4    →  Segment 05  (thay clip cũ) │
│ 19.mp4    →  không có segment  ⚠        │
│ intro.mp4 →  không đọc được số ⚠        │
├─────────────────────────────────────────┤
│  16 file sẽ được nạp · 2 bỏ qua         │
│              [ Huỷ ]  [ Nạp 16 clip ]   │
└─────────────────────────────────────────┘
```

Lý do: nạp clip **ghi đè** — nó vô hiệu clip đang có của shot đó. Một lần chọn sai thư mục mà nạp thẳng là mất 18 clip đã nạp đúng. Bước xác nhận biến lỗi không hồi phục thành lỗi vô hại. Bảng cũng nêu rõ file nào sẽ thay clip đang có, để việc ghi đè là chủ ý chứ không phải phát hiện sau.

Phương án khác: nạp ngay và cho hoàn tác. Phức tạp hơn nhiều (phải giữ clip cũ, thêm đường phục hồi) mà lợi ích thấp hơn.

### 3. Nhiều request song song, không thêm endpoint nhận cả lô

Dùng lại `POST /projects/{id}/shots/{shot_id}/clip` cho từng file, gửi song song có giới hạn số request đồng thời.

Lý do:

- Không phải thiết kế và kiểm thử endpoint mới; toàn bộ validate hiện có (dung lượng, thời lượng, định dạng, probe) áp dụng nguyên vẹn.
- **Lỗi cô lập theo file** đến miễn phí: một file quá lớn thì đúng file đó lỗi, 17 file kia vẫn vào. Nếu gộp một request thì phải tự định nghĩa hành vi lỗi bộ phận, và phải quyết định có rollback hay không.
- Tiến độ theo từng file cũng đến miễn phí.

Nhược điểm phải chấp nhận: 18 request thay vì 1, và không có tính nguyên tử cho cả lô. Với ứng dụng chạy trên máy người dùng, cả hai đều không đáng lo — và tính nguyên tử ở đây **không mong muốn**, vì nạp được 16/18 vẫn hữu ích hơn là không nạp gì.

Giới hạn số request đồng thời để không nghẽn: file clip cỡ vài MB nhưng backend probe từng file bằng ffprobe.

### 4. Nạp theo lô đi qua đường có ghi hãng phát hành

Đây là quyết định nối change này với change hiệu năng. Đường nạp hiện tại không ghi `provider`, khiến bước làm sạch dấu AI phải dò cả 6 hãng.

```
                          ┌─ hiện tại ──────────────────────┐
   file người dùng chọn ──┤ provider = None                 │→ dò 6 hãng
                          └─────────────────────────────────┘
                          ┌─ sau change ────────────────────┐
   file người dùng chọn ──┤ provider = <hãng đã chọn>       │→ dò 1 hãng
                          └─────────────────────────────────┘
```

Cách làm: cho tầng nạp clip nhận thêm hãng phát hành do người dùng chọn, mặc định là hãng đang dùng thực tế cho luồng này. `import_provider_clip` đã có sẵn tham số `provider` và đã tự probe/copy/vô hiệu clip cũ, nên không cần viết lại tầng lưu trữ.

Ràng buộc quan trọng: hãng phát hành **chỉ để tối ưu**, không phải để khẳng định nguồn gốc. Nếu người dùng chọn sai hãng thì bước làm sạch dò không thấy dấu và bỏ qua clip đó — mất tác dụng làm sạch nhưng **không** làm hỏng clip. Đây là lý do giá trị này an toàn khi để mặc định.

Phương án khác đã cân nhắc: giữ `provider=None` rồi để bước làm sạch tự dò một lần và ghi nhớ kết quả vào clip. Đúng đắn hơn về mặt dữ liệu (hãng do máy phát hiện, không do người khai) nhưng phải thêm đường ghi ngược vào bảng clip từ trong luồng render, và lần dò đầu vẫn tốn 6 lần. Để ngỏ như một cải tiến sau.

### 5. Danh sách chọn hai lựa chọn, không phải ba

```
Tiếng gốc của clip
┌──────────────────────────────────────────┐
│ Bỏ tiếng gốc, chỉ dùng giọng đọc      ▾ │  ← mặc định, giữ hành vi cũ
│ Giữ tiếng gốc làm nền                    │
└──────────────────────────────────────────┘
```

Design của change tiếng gốc có để ngỏ mức thứ ba ("chỉ tiếng gốc, bỏ giọng đọc"). Không đưa vào vì với dự án hiện tại nó **trùng nghĩa** với "giữ làm nền" — 18/18 shot không có thoại nên không có giọng đọc nào để bỏ. Thêm một lựa chọn không tạo ra khác biệt nào mà lại buộc đổi kiểu dữ liệu trên API, đúng thứ change kia cố tình tránh.

Field API giữ nguyên boolean. Danh sách chọn ánh xạ hai chiều sang boolean ở tầng giao diện. Lý do không đổi API: kiểu boolean đã đủ cho hai mức, và change tiếng gốc đã ghi rõ lý do giữ boolean rồi ánh xạ ở tầng render.

### 6. Lưu thiết lập trên máy, khôi phục có kiểm tra

Thiết lập lưu lại giữa các lần mở. Khi đọc lại, giá trị nào không hợp lệ hoặc thiếu thì lấy mặc định của khoá đó — không loại bỏ toàn bộ.

Lý do: thiết lập cũ có thể thiếu khoá mới thêm sau này, hoặc chứa giá trị đã bỏ. Nếu vì một khoá lạ mà bỏ hết thì người dùng mất toàn bộ lựa chọn, đúng vấn đề đang muốn sửa.

Phạm vi lưu: theo ứng dụng, không theo dự án. Đơn giản hơn, và các lựa chọn này là sở thích về cách dựng chứ không phải thuộc tính của dự án.

### 7. Luồng tự động đọc thiết lập từ dự án, không đọc từ giao diện

Hai luồng tự động chạy ở backend nên không thấy trạng thái giao diện. Cách nối: khi người dùng bấm dựng, thiết lập đã được gửi lên và lưu cùng job; luồng tự động lấy thiết lập của lần dựng gần nhất của dự án đó, không có thì dùng mặc định.

Lý do chọn cách này thay vì thêm bảng thiết lập riêng cho dự án: dữ liệu đã tồn tại (`settings_json` trên bảng job), không cần schema mới, và ngữ nghĩa dễ giải thích — "chạy tự động dùng lại thiết lập lần dựng gần nhất".

Phương án khác: thêm cột thiết lập mặc định trên bảng dự án. Rõ ràng hơn nhưng cần migration và thêm một chỗ nữa để đồng bộ.

## Risks / Trade-offs

**Người dùng đặt tên file sai quy ước, bảng khớp toàn dấu cảnh báo** → Bảng nêu rõ lý do bỏ qua từng file và ví dụ tên đúng, thay vì chỉ báo "không khớp". Nút nạp một clip cho từng shot vẫn còn nên luôn có đường thoát.

**Nạp theo lô ghi đè clip đã có mà người dùng không để ý** → Bảng khớp đánh dấu rõ file nào sẽ thay clip đang có, và phải bấm xác nhận mới nạp.

**Hãng phát hành do người dùng khai có thể sai** → Chỉ dùng để tối ưu bước dò dấu; sai thì mất tác dụng làm sạch chứ không làm hỏng clip. Không dùng giá trị này cho bất kỳ quyết định nào khác.

**Chọn nhầm thư mục và nạp đè cả 18 clip đúng** → Bước xác nhận là lớp chặn chính. Bảng khớp hiện tên file nên nhầm thư mục thấy được ngay.

**Nhiều request song song làm nghẽn backend** → Giới hạn số request đồng thời. Backend đã khoá một job render tại một thời điểm nên nạp clip không giành tài nguyên với việc dựng.

**Thiết lập lưu lại khiến lựa chọn cũ âm thầm có tác dụng ở lần dựng sau** → Đây là điều người dùng muốn. Nhưng nghĩa là bật tiếng gốc một lần thì các lần sau vẫn bật; giao diện phải luôn hiện giá trị đang có hiệu lực chứ không hiện mặc định.

**Luồng tự động dùng lại thiết lập lần trước có thể gây bất ngờ** → Ghi rõ trong giao diện rằng chạy tự động dùng thiết lập của lần dựng gần nhất. Chưa từng dựng thì dùng mặc định, tức giữ đúng hành vi hiện tại.

**Đổi checkbox thành danh sách chọn làm người dùng quen tay bị lạ** → Hai lựa chọn có nhãn tiếng Việt nói thẳng kết quả, không dùng phủ định. Mặc định giữ nguyên hành vi cũ nên không đổi kết quả của ai.

## Migration Plan

Không có migration dữ liệu. Không đổi schema, không đổi kiểu dữ liệu trên API.

Thứ tự triển khai:

1. Đường nạp clip có ghi hãng phát hành ở backend (dùng lại `import_provider_clip`), giữ đường nạp cũ.
2. Khớp tên file với số segment, kiểm thử riêng — đây là phần dễ sai nhất và kiểm được độc lập với giao diện.
3. Chọn nhiều file + bảng khớp + nạp song song.
4. Danh sách chọn tiếng gốc và lưu thiết lập.
5. Nối thiết lập vào hai luồng tự động.

Bước 1–3 và 4–5 độc lập nhau, làm song song được.

Quay lui: mỗi bước tự đứng được. Bảng khớp và chọn nhiều file là phần thêm vào, tắt đi thì nút nạp một clip cho từng shot vẫn nguyên. Danh sách chọn quay về checkbox không đổi dữ liệu vì field API không đổi. Bỏ lưu thiết lập thì quay lại hành vi hiện tại.

## Open Questions

- Có nên cho phép rút số từ tên file phức tạp hơn (`Scene_03.mp4`, `clip-3-final.mp4`) không? Hiện chỉ nhận tên thuần số. Chờ xem thực tế người dùng đặt tên thế nào.
- Bảng khớp có nên cho sửa tay ánh xạ của một file bị khớp sai không? Hiện chỉ xem và xác nhận. Thêm sửa tay làm phức tạp giao diện mà chưa rõ có cần.
- Hãng phát hành nên hiện thành lựa chọn cho người dùng, hay để mặc định ẩn? Hiện dự án chỉ dùng một hãng nên để mặc định là đủ; sẽ cần lựa chọn khi có hãng thứ hai.
- Số request đồng thời khi nạp: chưa đo. Cần thử với 18 file thật để chọn con số không làm nghẽn probe ở backend.
