# Làm sạch dấu AI khi dựng MP4

Voicebox có thể xử lý dấu AI nhìn thấy được hỗ trợ và metadata AI đã xác minh trên từng active clip trước khi chuẩn hóa và ghép MP4. Tính năng mặc định **tắt** và chỉ chạy khi người dùng chủ động bật trong bảng **Dựng nhanh MP4**.

## Phạm vi an toàn

- Chỉ dùng cho nội dung bạn sở hữu hoặc có quyền chỉnh sửa.
- Clip nguồn không bị ghi đè hoặc xóa. Output đã xử lý là derivative trong `render_cache/watermark/`.
- MVP chỉ xử lý visible provider mark và verified metadata. Không chạy invisible watermark, SynthID regeneration, diffusion hoặc GPU model.
- **Watermark ẩn không được xử lý với bất kỳ cách lấp vùng nào.** Worker chặn cứng tuỳ chọn xử lý dấu ẩn, nên làm sạch xong không có nghĩa video đã hết mọi loại watermark. Giới hạn này không phụ thuộc vào việc chọn `cv2` hay `migan`.
- Nếu không tìm thấy dấu AI được hỗ trợ, render vẫn tiếp tục bằng output same-container và report ghi `no_supported_mark`; điều này không có nghĩa video không còn mọi loại watermark.
- Audio và timing phụ đề vẫn dùng contract nguồn hiện có. Với dự án tiếng Việt dùng Veo native speech, audio tiếp tục được trích từ active source clip gốc.

## Chuẩn bị worker development

Worker được cô lập khỏi Python runtime chính của Voicebox để tránh xung đột dependency. Mặc định backend tìm repo ở sibling `../remove watermark` và Python ở `.venv` của repo đó.

Từ thư mục Voicebox, chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-watermark-worker.ps1
```

Script tìm `uv` theo thứ tự: lệnh `uv` trên `PATH` trước, sau đó `uv.exe` đi kèm venv backend trong dự án (`backend\venv\Scripts\uv.exe`). Vì vậy không cần cài `uv` toàn cục. Script in ra nguồn `uv` đang dùng, và chỉ báo lỗi khi cả hai vị trí đều không có — thông báo lỗi nêu rõ cả hai nơi đã tìm.

Backend mặc định `cv2` không tải model. Nếu cần MI-GAN:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-watermark-worker.ps1 -Backend migan
```

### Cách lấp vùng và trạng thái model MI-GAN

Cách lấp vùng chỉ quyết định chất lượng vùng đã xoá được lấp lại, **không** quyết định phạm vi dấu AI được phát hiện. Chọn `cv2` vẫn xoá được dấu như `migan`, chỉ khác độ mịn của vùng lấp. `cv2` là inpaint cổ điển, không cần model. `migan` cần ONNX Runtime và model ONNX khoảng 28 MB.

Readiness báo trạng thái riêng cho từng backend, và không tự cài dependency hay tự tải model. Có ba trạng thái:

| Trạng thái | Ý nghĩa | Ảnh hưởng dựng MP4 |
| --- | --- | --- |
| Thiếu dependency | Venv worker chưa có module cần thiết | Chặn dựng **nếu** đó là backend đang chọn; thông báo nêu module thiếu, Python đang chạy worker và lệnh setup cần chạy |
| Đủ dependency, model chưa cache | Chỉ áp dụng cho `migan` | Không chặn. Cảnh báo lần dựng đầu cần mạng để tải khoảng 28 MB |
| Sẵn sàng hoàn toàn | Đủ dependency và model đã cache | Không chặn |

Chặn dựng MP4 chỉ dựa trên backend đang chọn: `migan` chưa sẵn sàng mà đang chọn `cv2` thì vẫn dựng được bình thường.

Model chưa cache không phải lỗi, vì cách duy nhất để cache model là chạy một lần dựng. Readiness cố tình tra cache cục bộ thay vì tải model, để việc kiểm tra luôn nhanh và không phát sinh lưu lượng mạng ngoài ý muốn.

Về chi phí thời gian: `migan` mất khoảng 0,19 giây mỗi frame lấp vùng. Với logo hiện gần như toàn clip, một clip 8 giây ở 30 fps (khoảng 240 frame) mất chừng 46 giây chỉ riêng phần lấp vùng, sáu phân đoạn vào khoảng 4,6 phút chưa tính decode/encode. Timeout mặc định mỗi clip là 1200 giây và nâng được tới 7200 giây qua `VOICEBOX_WATERMARK_TIMEOUT_SECONDS`. Cần nhanh thì chọn `cv2`.

Backend `lama` không nằm trong phạm vi Voicebox vì cần khoảng 4,7 GB RAM.

Nếu checkout nằm ở vị trí khác:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-watermark-worker.ps1 `
  -WatermarkRoot "D:\path\to\remove-watermark"

$env:VOICEBOX_WATERMARK_ROOT = "D:\path\to\remove-watermark"
$env:VOICEBOX_WATERMARK_PYTHON = "D:\path\to\remove-watermark\.venv\Scripts\python.exe"
```

`VOICEBOX_WATERMARK_PYTHON` cũng có thể là tên lệnh tìm được trên `PATH`, ví dụ `python`.

## Cấu hình runtime

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `VOICEBOX_WATERMARK_ROOT` | sibling `../remove watermark` | Checkout chứa `src/remove_ai_watermarks` và video API. |
| `VOICEBOX_WATERMARK_PYTHON` | `.venv` của checkout, sau đó Python khả dụng | Python chạy worker cô lập. |
| `VOICEBOX_WATERMARK_WORKER_SCRIPT` | worker đi cùng Voicebox | Override script cho chẩn đoán/đóng gói đặc biệt. |
| `VOICEBOX_WATERMARK_TIMEOUT_SECONDS` | `1200` | Timeout mỗi clip, giới hạn trong khoảng 60–7200 giây. |

Voicebox truyền thư mục FFmpeg/FFprobe đã detect vào `PATH` của worker. Readiness chỉ spawn `--check` khi cleanup được bật; khi tắt, thiếu worker không chặn pipeline dựng MP4 cũ. Khi cleanup bật, readiness kiểm tra cả `cv2` và `migan` để giao diện khoá trước lựa chọn chưa dùng được.

## Cache và báo cáo

Cache key gồm source path/size/mtime, detector mark, backend, temporal policy, worker protocol và exact package revision. Thay clip, đổi backend/policy hoặc đổi revision sẽ tạo derivative mới.

`timeline-manifest.json` ghi settings, revision và kết quả từng shot. `render-cache-summary.json` ghi hit/miss riêng cho normalize và watermark. Worker timeout, protocol lỗi hoặc output rỗng làm render fail strict với error code `VIDEO_RENDER_WATERMARK_*`; temp file được dọn và source/cache hợp lệ cũ được giữ nguyên.

## Ghi chú phát hành

Video API hiện phải được pin theo exact Git revision hoặc artifact tương đương, không chỉ theo version package. Bản production cần phân phối checkout/runtime worker tương thích hoặc cấu hình các biến môi trường nêu trên; Voicebox không tự clone hay cài dependency trong readiness.
