## Context

Làm sạch dấu AI khi dựng MP4 chạy qua một worker Python cô lập (`backend/workers/video_watermark_worker.py`) để backend chính không kế thừa dependency native của `remove-ai-watermarks`. Worker được spawn bởi `backend/services/video_watermark_cleanup.py`, và readiness được tổng hợp trong `backend/services/video_rendering.py` rồi trả ra UI qua `VideoRenderReadinessResponse`.

Trạng thái hiện tại đã được xác minh bằng cách chạy trực tiếp interpreter mà worker sử dụng:

```
remove watermark/.venv/Scripts/python.exe   (Python 3.12.10)
  av  cv2  remove_ai_watermarks  numpy      → có
  huggingface_hub  onnxruntime              → THIẾU

voice-app/backend/venv                       (Python backend chính)
  huggingface_hub  onnxruntime  numpy       → có
  av  cv2  remove_ai_watermarks             → THIẾU
```

Mỗi venv thiếu đúng phần bên kia có. Venv worker chưa được sync extra `migan` (định nghĩa trong `pyproject.toml` của repo watermark gồm `onnxruntime` và `huggingface-hub`).

Chuỗi nhân quả dẫn tới lỗi người dùng thấy:

```
UI chọn "Đẹp hơn — MI-GAN"
   │
   ▼
get_runtime_status(backend="migan")
   │  _configured_python(): VOICEBOX_WATERMARK_PYTHON → venv repo → sys.executable → PATH
   │  venv repo TỒN TẠI nên thắng trước khi fallback sang Python backend chính
   ▼
worker --check --backend migan
   ├─ import av / cv2 / remove_ai_watermarks   → pass
   ├─ hasattr(raiw, "remove_video_all")        → pass
   └─ if backend == "migan": import huggingface_hub
         → FAIL → WATERMARK_WORKER_MIGAN_MISSING
         → "Backend MI-GAN chưa sẵn sàng: No module named 'huggingface_hub'"
```

Ba yếu tố làm người dùng bị kẹt: script setup chỉ tìm `uv` trên `PATH` (mà `uv` không có trên `PATH` của máy này, đồng thời venv worker không có `pip` vì do `uv` tạo), thông báo lỗi không nói phải làm gì, và readiness không phân biệt được "thiếu dependency" với "model chưa tải".

Một chi tiết quan trọng về phạm vi: backend lấp vùng KHÔNG quyết định việc phát hiện dấu AI. `veo` nằm trong danh sách visible mark của package, detection phủ cả logo diamond hiện tại lẫn chữ "Veo" cũ, và provider trong pipeline là `veo` nên detector được nhắm đúng thay vì dò tự động. Backend chỉ quyết định vùng đã xoá được lấp lại đẹp cỡ nào: `cv2` là inpaint cổ điển (không tải model, hơi nhoè texture), `migan` là ONNX ~28 MB, ~1 GB RAM, ~0.19 s mỗi lần gọi, chất lượng gần LaMa. Nghĩa là chức năng xoá logo Veo hiện KHÔNG hỏng — người dùng chọn `cv2` vẫn xoá được, chỉ mất chất lượng vùng lấp.

## Goals / Non-Goals

**Goals:**

- Người dùng tự chuẩn bị được backend MI-GAN bằng script có sẵn, không cần cài `uv` toàn cục.
- Readiness phân biệt rõ ba trạng thái: thiếu dependency (lỗi, chặn), đủ dependency nhưng model chưa cache (cảnh báo, không chặn), sẵn sàng hoàn toàn.
- Thông báo lỗi đủ thông tin để tự sửa: module thiếu, Python đang chạy, lệnh cần chạy.
- UI cho biết trước lựa chọn nào chưa dùng được, thay vì để người dùng chọn rồi mới thấy lỗi.
- Giữ nguyên nguyên tắc: cleanup tắt thì không spawn worker, thiếu worker không chặn pipeline dựng MP4 cũ.

**Non-Goals:**

- Không tự động cài dependency hoặc tự tải model trong readiness.
- Không xử lý watermark ẩn/SynthID. `include_invisible` vẫn bị chặn cứng trong worker.
- Không đụng backend `lama` (~4.7 GB RAM).
- Không sửa pipeline dựng video/audio (thuộc change riêng về audio bed).
- Không dùng venv backend chính thay cho venv worker.
- Không đổi cơ chế cache derivative hay cache key hiện có.

## Decisions

### 1. Phân giải `uv`: `PATH` trước, venv dự án sau

Script thử `uv` trên `PATH` trước để tôn trọng bản `uv` người dùng tự cài, rồi mới fallback sang `uv.exe` đi kèm venv backend trong dự án. Thông báo lỗi khi thất bại phải nêu cả hai vị trí đã tìm.

Phương án khác đã cân nhắc: (a) chỉ dùng `uv` trong dự án — bỏ mất bản người dùng có thể đã cấu hình riêng; (b) dùng `pip` — không khả thi vì venv worker do `uv` tạo và không có `pip`; (c) hướng dẫn người dùng tự cài `uv` — chính là trạng thái hiện tại đang làm họ kẹt.

### 2. Kiểm tra cache model bằng tra cache, không tải

Worker tra cache HuggingFace cục bộ cho model MI-GAN thay vì gọi hàm tải. Lý do: readiness phải nhanh và không được gây tác dụng phụ mạng; timeout kiểm tra runtime hiện chỉ 30 giây, không đủ để tải model, và tải trong lúc kiểm tra sẽ biến một thao tác chẩn đoán thành thao tác tốn băng thông ngoài ý muốn.

Phương án khác đã cân nhắc: (a) warm model ngay trong `--check` — vi phạm nguyên tắc "readiness không tự tải model" đã ghi trong tài liệu, và dễ timeout; (b) không kiểm tra gì — giữ nguyên cái bẫy readiness xanh nhưng render chết giữa đường.

Hệ quả cần chấp nhận: lần dựng đầu vẫn tải model, nên cảnh báo phải nêu rõ điều đó. Worker chạy trong process riêng nên không bị patch offline của backend chính, và môi trường không đặt biến buộc offline, nên việc tải hoạt động bình thường.

### 3. Model chưa cache là cảnh báo, không phải lỗi

Đủ dependency nhưng chưa cache model vẫn coi là sẵn sàng. Chặn dựng MP4 trong trường hợp này sẽ khiến người dùng không có cách nào tiến lên, vì con đường duy nhất để cache model chính là chạy một lần dựng. Cảnh báo cần nêu lần dựng đầu cần mạng và dung lượng tải xấp xỉ.

### 4. Probe từng backend, nhưng chỉ khi cleanup bật

Readiness probe cả `cv2` và `migan` để UI biết trạng thái từng lựa chọn, nhưng chỉ khi người dùng đã bật làm sạch watermark. Ràng buộc này giữ đúng nguyên tắc hiện hành trong tài liệu: cleanup tắt thì không spawn worker.

Điều kiện chặn dựng MP4 vẫn chỉ dựa trên backend đang chọn. Nếu `migan` chưa sẵn sàng mà người dùng đang chọn `cv2` thì vẫn phải dựng được — nếu không, một backend tuỳ chọn chưa cài sẽ chặn cả tính năng vốn đang hoạt động.

Chi phí: khi cleanup bật, số lần spawn worker cho readiness tăng từ một lên hai. Mỗi lần là một tiến trình ngắn chỉ import và tra cache, nằm trong ngân sách timeout kiểm tra hiện có.

### 5. Thông báo lỗi mang theo Python đang chạy

Nhánh thành công của `--check` đã trả về Python đang dùng, nhưng nhánh lỗi thì không — nên người dùng thấy lỗi mà không biết venv nào đang thiếu. Payload lỗi cần mang theo Python đang chạy và lệnh setup cần chạy. Điều này đặc biệt quan trọng ở đây vì máy có hai venv, một trong hai venv có sẵn thư viện bị báo thiếu, nên thiếu thông tin này người dùng rất dễ sửa sai venv.

### 6. UI dùng thuộc tính `disabled` sẵn có của thẻ option

Không cần sửa component select dùng chung. Thẻ `option` của HTML hỗ trợ `disabled` sẵn, nên chỉ cần đánh dấu ở tầng dựng danh sách lựa chọn. Khi readiness chưa có dữ liệu thì không vô hiệu hoá gì để tránh chặn oan trong lúc đang tải.

## Risks / Trade-offs

- **Người dùng sửa sai venv vì máy có hai venv chứa dependency chồng nhau** → Thông báo lỗi nêu rõ đường dẫn Python đang chạy và lệnh setup chính xác.
- **Lần dựng đầu với MI-GAN cần mạng, có thể fail giữa lúc render nếu mất mạng** → Readiness cảnh báo trước; cache derivative theo clip đã có nên lần chạy lại không mất công đã làm.
- **Thời gian dựng tăng đáng kể với MI-GAN vì logo Veo hiện gần như toàn clip** → Ước lượng: clip 8 giây ở 30 fps là khoảng 240 frame, ~0,19 s mỗi frame nên riêng phần lấp vùng đã khoảng 46 giây; sáu phân đoạn vào khoảng 4,6 phút chưa tính decode/encode. Timeout mặc định 1200 giây, nâng được tới 7200 giây qua biến môi trường. Cần nêu trong tài liệu để người dùng biết chọn `cv2` khi cần nhanh.
- **Probe hai backend làm readiness chậm hơn khi cleanup bật** → Chỉ probe khi cleanup bật; mỗi lần kiểm tra là tiến trình ngắn không tải model.
- **Tra cache HuggingFace có thể sai lệch nếu cache bị dọn giữa lúc kiểm tra và lúc render** → Coi kết quả tra cache là gợi ý chứ không phải bảo đảm; render vẫn có đường tải lại, và lỗi tải vẫn đi theo đường báo lỗi render hiện có.
- **Người dùng hiểu sai rằng chọn `cv2` là không xoá được logo Veo** → Tài liệu và thông báo cần nêu rõ backend chỉ ảnh hưởng chất lượng vùng lấp, không ảnh hưởng khả năng phát hiện.
- **Người dùng hiểu sai rằng làm sạch xong là video hết mọi watermark** → Giữ và làm rõ ghi chú hiện có: chỉ xử lý dấu nhìn thấy được hỗ trợ và metadata đã xác minh, không xử lý watermark ẩn.

## Migration Plan

1. Sync venv worker kèm extra `migan` bằng `uv` trong dự án để bổ sung `onnxruntime` và `huggingface-hub`.
2. Triển khai thay đổi worker, service readiness, contract API, UI và tài liệu.
3. Xác minh bằng cách chạy kiểm tra runtime thật cho cả `cv2` và `migan`, không mock.
4. Rollback: các thay đổi đều thuần readiness/chẩn đoán/tài liệu và script; hoàn nguyên không ảnh hưởng dữ liệu hay derivative đã cache. Nếu cần, người dùng vẫn dùng được `cv2` như trước.

## Open Questions

Không còn câu hỏi mở. Các quyết định về phân giải `uv`, cách kiểm tra cache, cách phân loại trạng thái model chưa cache, phạm vi probe và cách đánh dấu UI đều đã chốt ở phần Decisions.
