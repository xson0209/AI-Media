## Context

Luồng dựng MP4 hiện chạy tuần tự hoàn toàn. Vòng lặp theo từng clip trong `_render_job_steps` làm hai việc cho mỗi clip: làm sạch dấu AI rồi chuẩn hoá clip. Không có `ThreadPoolExecutor`, `asyncio.gather` hay `multiprocessing` nào trong luồng render; mọi lệnh ffmpeg và mọi lần gọi worker đều là `subprocess.run` chặn.

Số đo thực tế ngày 23-08 trên máy mục tiêu (Ryzen 7 5800H 8 nhân/16 luồng, RTX 3050 Laptop 4 GB), project 18 clip mỗi clip 8 giây, 1080p60:

```
Toàn bộ job, tắt làm sạch dấu AI          49 giây
Toàn bộ job, backend cv2                  1070 giây  (17,8 phút)
Toàn bộ job, backend migan                ~72 phút   (đo 83/303/327 giây cho clip 2/3/4)

Chuẩn hoá clip                            3 giây/clip   →  54 giây cho 18 clip
```

Bước làm sạch dấu AI chiếm 95–99% thời gian. Đo tải CPU trong 8 giây khi đang làm sạch: tiến trình Python của worker dùng 3,03 nhân, ffmpeg dùng 0,03 nhân, GPU 0%. Nghĩa là 13 trong 16 luồng CPU bỏ trống suốt cả job.

Đo riêng bước làm sạch bằng cách gọi worker trực tiếp trên clip thật, ngoài luồng render:

```
migan + dò 6 hãng   269,8 giây/clip   ← cấu hình đang dùng
migan + dò 1 hãng   235,7 giây/clip
cv2   + dò 6 hãng    37,6 giây/clip
cv2   + dò 1 hãng     8,7 giây/clip
```

Chạy song song gần tuyến tính vì mỗi worker chỉ chiếm khoảng 3 trong 16 luồng: 4 clip cùng lúc đạt 3,99 lần, 6 clip đạt 5,98 lần, 8 clip đạt 7,98 lần. Phép thử trên cả 18 clip với cv2 + dò 1 hãng + 6 luồng song song cho **78,6 giây wall-clock, 18/18 thành công**.

Ràng buộc quan trọng: `cleanup_clip_with_cache` và `_normalize_clip_with_cache` đều **không** nhận `Session` và không chạm database, nên an toàn khi gọi từ nhiều luồng. Nhưng `_update_job` gọi `db.commit()`, và `Session` của SQLAlchemy không an toàn khi dùng đồng thời từ nhiều luồng.

## Goals / Non-Goals

**Goals:**

- Hạ thời gian dựng MP4 của project 18 clip từ khoảng 72 phút xuống mức phút.
- Dùng hết số luồng CPU đang bỏ trống thay vì để 13/16 luồng nhàn rỗi.
- Bỏ phần công việc dò 5 hãng không liên quan trên từng khung hình.
- Người dùng luôn thấy đúng bước đang chạy, không còn dòng chữ đứng im nhiều phút.
- Giữ nguyên kết quả đầu ra: thứ tự clip, định dạng, cấu trúc và khoá cache.

**Non-Goals:**

- Không đổi thuật toán làm sạch dấu AI, không sửa package `remove-ai-watermarks`.
- Không chuyển encode sang NVENC (xem quyết định 5 — đã đo và là hướng phản tác dụng).
- Không thêm `onnxruntime-gpu`, không đưa MI-GAN lên GPU (xem quyết định 6).
- Không bỏ khoá một job render tại một thời điểm.
- Không cho chạy nhiều job render song song.
- Không đổi nhánh audio, cơ chế phụ đề, hay phần enhanced render.
- Không thêm cột database hay migration.

## Decisions

### 1. Đổi mặc định sang `cv2`, giữ `migan` là lựa chọn

Đây là thay đổi rẻ nhất và có tác động lớn nhất: 240 giây xuống 37,6 giây mỗi clip, chỉ bằng cách đổi một giá trị mặc định.

Điều kiện để dám khuyến nghị là chất lượng phải tương đương. Đã so hai bản cache thật của **cùng một clip**, một bản do job cv2 sinh ra và một bản do job migan sinh ra:

```
PSNR toàn khung          50,66 dB
SSIM                     0,9965
PSNR vùng logo Veo       49,64 dB
Cả hai backend           detected=veo, removed 192/192 khung
```

Trên 40 dB thì mắt thường không phân biệt được; 50,7 dB nghĩa là hai bản gần như trùng nhau. Vậy `migan` tốn khoảng 27 lần thời gian mà không đổi lấy được chất lượng tương xứng.

Giữ `migan` trong danh sách chọn vì so sánh này chỉ làm trên một clip; có thể có clip mà logo nằm trên nền phức tạp hơn và `cv2` kém hơn rõ rệt. Người dùng cần đường thoát mà không phải sửa code.

Phương án khác đã cân nhắc: bỏ hẳn `migan`. Không chọn vì mất đường thoát, và vì bằng chứng chỉ có trên một clip nên chưa đủ để kết luận `migan` là vô dụng.

### 2. Suy ra hãng clip thay vì để dò tự động

`mark_for_provider` trả `"auto"` khi `provider` rỗng, và `"auto"` khiến bước quét chạy cả 6 detector template-matching trên mỗi khung hình. Nhưng báo cáo của chính worker ghi `visible_mark = veo`, tức 5/6 công sức bỏ đi.

Nguyên nhân gốc: có hai đường tạo clip. `upload_shot_clip` đặt `source="upload"` và **không có tham số `provider`**; `import_provider_clip` đặt `source="provider"` kèm `provider`. Cả 18 clip của project đang là `('upload', None)` vì nạp bằng tay.

Quyết định: khi clip không có `provider`, suy ra hãng từ dữ liệu đã có thay vì mặc định `"auto"`. Cache report của các lần làm sạch trước đã ghi `visible_mark` thật, nên có sẵn nguồn để suy.

Điểm cần nói rõ: change `ngay-23-08-nap-nhieu-clip-theo-so-va-dropdown-tieng-goc` xử lý nguyên nhân gốc — nạp clip có ghi `provider` — nên hai change bù nhau. Change này lo các clip **đã tồn tại** với `provider=None`; change kia lo các clip **nạp về sau**. Không phụ thuộc thứ tự triển khai.

Phương án khác đã cân nhắc: (a) bắt người dùng chọn hãng trên giao diện — thêm việc cho người dùng để giải quyết thứ hệ thống tự biết được; (b) chỉ sửa ở đường nạp clip mới và bỏ qua clip cũ — người dùng đang có clip cũ sẽ không thấy cải thiện.

### 3. Song song hoá bằng thread pool, giữ mọi thao tác database ở luồng chính

Vòng lặp theo từng clip là ứng viên song song hoá sạch: mỗi vòng ghi ra đường dẫn riêng theo khoá cache hoặc theo số thứ tự, và hai hàm nặng đều không chạm database.

Dùng thread pool chứ không phải process pool: phần việc thật nằm trong `subprocess.run`, vốn đã giải phóng GIL, nên thread là đủ và tránh chi phí tuần tự hoá dữ liệu giữa các process.

Kiến trúc:

```
luồng chính                          các luồng làm việc
───────────                          ──────────────────
gửi N việc theo từng clip     ──►    làm sạch dấu AI  (subprocess worker)
                                     chuẩn hoá clip   (subprocess ffmpeg)
nhận kết quả theo thứ tự      ◄──    trả về đường dẫn + báo cáo cache
cập nhật tiến độ + commit
ghép theo thứ tự timeline
```

Ba ràng buộc phải giữ:

- **Thứ tự.** Ghép video phải theo đúng thứ tự timeline, không theo thứ tự hoàn thành. Kết quả phải được xếp lại theo chỉ số trước khi ghép.
- **Database chỉ ở luồng chính.** `_update_job` gọi `db.commit()` và `Session` không an toàn đa luồng, nên luồng làm việc không được cập nhật tiến độ; chúng trả kết quả về và luồng chính mới ghi.
- **Tổng hợp cache an toàn.** `render_cache_summary` hiện được cộng dồn trong vòng lặp; khi song song thì phải tổng hợp từ kết quả trả về chứ không cộng dồn từ nhiều luồng.

Phương án khác đã cân nhắc: (a) `asyncio.gather` với `asyncio.to_thread` — tương đương về hiệu quả nhưng luồng render hiện là hàm đồng bộ chạy trong `asyncio.to_thread`, thêm một tầng async vào giữa làm khó đọc mà không lợi gì; (b) song song ở mức job thay vì mức clip — không giải quyết được trường hợp thường gặp nhất là một người dùng dựng một video, và phá khoá một job tại một thời điểm.

### 4. Số luồng: theo số nhân CPU, có chặn trên, cấu hình được

Mỗi worker làm sạch chiếm khoảng 3 luồng CPU. Chạy quá nhiều thì tranh CPU và giảm hiệu quả; chạy quá ít thì bỏ trống.

Đo được 4 clip đạt 3,99 lần, 6 clip đạt 5,98 lần, 8 clip đạt 7,98 lần — vẫn gần tuyến tính ở 8. Nhưng số đo này lấy khi máy tương đối rảnh; nếu người dùng đang làm việc khác thì đặt quá cao sẽ làm máy phản hồi chậm. Chọn mặc định suy từ số nhân CPU với chặn trên vừa phải, kèm biến môi trường để tăng khi cần, theo đúng cách các knob render hiện có được đặt.

Cần đặt chặn dưới là 1 để trên máy một nhân vẫn chạy được, và giá trị 1 phải cho kết quả giống hệt tuần tự — đây là đường thoát khi song song gây vấn đề.

Phương án khác đã cân nhắc: cố định một số như 4. Đơn giản hơn nhưng bỏ mất hiệu năng trên máy nhiều nhân và làm máy yếu bị quá tải.

### 5. Không chuyển encode sang NVENC — đã đo, phản tác dụng

Ghi lại rõ để tránh thử lại. FFmpeg đi kèm dự án **có** `h264_nvenc` và hwaccel `cuda`, nên hướng này trông rất hợp lý. Nhưng đo trên clip 8 giây thật, dùng nguyên chuỗi filter của `build_normalize_clip_command`:

```
libx264 -preset veryfast   4,24 giây   ← nhanh hơn
h264_nvenc                 6,38 giây
```

Clip chỉ 8 giây nên chi phí khởi tạo session NVENC lấn hết phần lợi, và libx264 vốn không đặt `-threads` nên đã tự dùng hết số nhân. Hơn nữa dù NVENC có nhanh gấp đôi thì cũng chỉ tiết kiệm khoảng 25 giây trên một job 72 phút — nhiễu so với phần làm sạch dấu AI.

### 6. Không đưa MI-GAN lên GPU

Ban đầu đây trông là cách dùng GPU đúng đắn: `region_eraser.py` hardcode `CPUExecutionProvider`, model `migan.onnx` chỉ 28 MB nên thừa sức vào 4 GB VRAM, và MI-GAN inference chính là phần chiếm 3,03 nhân CPU.

Nhưng sau quyết định 1 thì MI-GAN không còn nằm trên đường tới đích: `cv2` thay được `migan` với chất lượng gần như trùng và nhanh hơn 27 lần. Tối ưu một thứ đã bị đưa ra khỏi mặc định là công sức đặt sai chỗ. Thêm nữa `region_eraser.py` nằm ở repo ngoài (`D:/AI Media/AI Media Project/remove watermark`) nên sửa nó là vượt phạm vi dự án này, và `onnxruntime` trong venv của worker hiện chỉ có `CPUExecutionProvider` nên phải thêm gói mới cùng nhánh fallback cho máy không có NVIDIA.

Để ngỏ: nếu về sau phát hiện clip mà `cv2` xử lý kém và buộc phải dùng `migan`, thì GPU cho MI-GAN quay lại thành đáng làm.

### 7. Báo tiến độ theo bước thực tế đang chạy

Chuỗi tiến độ hiện đặt **sau** khi việc hoàn thành, nên nhãn luôn mô tả việc vừa xong chứ không phải việc đang chạy. Kết quả là "Đang chuẩn hoá clip 4/18" hiện suốt nhiều phút trong khi máy đang làm sạch dấu AI cho clip 5 — bước đắt nhất lại không có nhãn nào.

Thêm vào đó, từ 75% đến 100% không có mốc tiến độ nào, dù giai đoạn đó có bước ghép/xuất file cuối. Khi bật nhúng phụ đề thì bước này encode lại toàn bộ video, tức là một lượt encode dài nữa mà thanh tiến độ đứng im.

Quyết định: nhãn phải phản ánh bước đang chạy, và cả hai bước theo từng clip đều phải có nhãn riêng. Khi chạy song song thì đếm số clip đã hoàn thành thay vì số thứ tự đang xử lý, vì nhiều clip chạy cùng lúc nên "clip thứ 5" không còn nghĩa.

## Risks / Trade-offs

- **Chạy song song làm máy phản hồi chậm khi người dùng đang làm việc khác** → mặc định suy từ số nhân CPU với chặn trên vừa phải thay vì lấy hết; có biến môi trường để hạ; đặt về 1 là quay lại hành vi tuần tự.
- **Sai thứ tự clip sau khi ghép** → đây là rủi ro nghiêm trọng nhất vì nó làm sai nội dung video mà không báo lỗi. Kết quả phải xếp lại theo chỉ số timeline trước khi ghép, và cần ca kiểm thử riêng cho việc thứ tự hoàn thành khác thứ tự timeline.
- **Session SQLAlchemy bị dùng từ nhiều luồng gây lỗi khó tái tạo** → luồng làm việc không được nhận `Session`; mọi cập nhật tiến độ và commit chỉ xảy ra ở luồng chính.
- **`cv2` cho kết quả kém hơn trên clip chưa thử** → so sánh chất lượng chỉ làm trên một clip; `migan` vẫn còn trong danh sách chọn; nhãn tiếng Việt nói rõ đây là lựa chọn nhanh để người dùng biết có đường khác.
- **Suy ra hãng clip sai làm sót dấu AI** → khi không suy được thì phải quay về dò tự động chứ không được đoán bừa; sót dấu AI tệ hơn là chạy chậm.
- **Nhiều worker cùng lúc làm tăng đỉnh RAM** → mỗi worker là một process riêng nên RAM cộng dồn theo số luồng; chặn trên số luồng cũng là chặn trên RAM.
- **Cache mất tác dụng nếu khoá cache đổi** → change này không đổi thành phần khoá cache, nên cache đã có vẫn dùng được và không phải làm lại 5 clip đã xong.
- **Lỗi một clip khi chạy song song có thể làm mất thông tin lỗi của các clip khác** → cần quyết định rõ hành vi: một clip lỗi thì job lỗi như hiện tại, nhưng thông báo phải chỉ rõ clip nào lỗi.

## Migration Plan

Không có migration database, không đổi cấu trúc cache, không thêm gói phụ thuộc.

Thứ tự triển khai theo mức tăng dần của rủi ro, để mỗi bước đều đo được riêng:

1. Đổi mặc định sang `cv2` kèm nhãn tiếng Việt. Không đụng logic, tác động lớn nhất.
2. Suy ra hãng clip. Vẫn tuần tự, dễ kiểm chứng bằng cache report.
3. Song song hoá vòng lặp theo từng clip. Bước rủi ro nhất, làm sau khi hai bước trên đã xanh.
4. Sửa nhãn và mốc tiến độ. Không đổi hành vi, chỉ đổi thông tin hiển thị.

Đường lùi: đặt số luồng về 1 cho hành vi tuần tự; đổi lựa chọn backend về `migan` trên giao diện mà không cần sửa code.

## Open Questions

- Job render gần nhất thất bại với `VIDEO_RENDER_WATERMARK_PROTOCOL_INVALID` ("Watermark worker không trả JSON hợp lệ") sau khi chạy khoảng 45 phút và đạt 30%. Chưa xác định nguyên nhân; nghi worker in thêm gì đó ra stdout làm hỏng JSON. Chạy song song nhiều worker có thể làm lỗi này xuất hiện thường xuyên hơn. Cần điều tra riêng — có thể phải tách thành change riêng nếu nguyên nhân nằm ở package ngoài.
- Chưa rõ vì sao clip đầu tiên làm sạch nhanh hơn hẳn các clip sau (83 giây so với 303–327 giây). Có thể do số khung có dấu AI khác nhau, hoặc do một dạng khởi động nguội nào đó. Ảnh hưởng tới độ chính xác của con số ước tính nhưng không ảnh hưởng hướng đi.
- Số 78,6 giây là đo riêng bước làm sạch, gọi worker ngoài luồng render. Chưa chạy luồng render thật sau khi song song hoá nên chưa biết tổng thời gian job thực tế.
- Chưa quyết mức chặn trên của số luồng. Đo được tới 8 vẫn gần tuyến tính nhưng chưa thử 12 hay 16, và chưa đo trên máy đang chạy việc khác.
