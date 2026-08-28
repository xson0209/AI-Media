## Why

Luồng `/ai-video` chạy trọn gói tới MP4, nhưng với video bán sản phẩm thì phần sau lại vô dụng: ảnh sản phẩm chỉ đưa vào được qua Ingredients/References to Video trong chính web app Google Flow, mà app chưa có primitive upload file qua CDP (`chrome_cdp.py` chỉ có 4 method, không có `DOM.setFileInputFiles`). Người dùng vì vậy vẫn phải tự vào Flow dán ảnh và generate bằng tay.

Cái còn thiếu là một trang chuyên sinh **prompt** đủ tốt để dán vào Flow. Prompt hiện tại của `/ai-video` không có chỉ dẫn giữ nguyên nhãn sản phẩm — và hậu quả đã đo được: chữ `LIBITU` trên màn TV trong một clip Veo thật biến dạng thành chuỗi vô nghĩa giữa frame đầu và frame cuối (`docs/research/ai-video-perf-va-mo-rong-content-types.md` mục 2). Với video bán hàng, nhãn drift là mất trắng cả clip.

## What Changes

- Thêm route `/product-video` (frontend) và router backend prefix `/product-video`, độc lập với `/ai-video`.
- Thêm 3 bảng DB riêng: `product_video_projects`, `product_video_shots`, `product_video_shot_prompts`. Không dùng chung `video_projects`.
- Sáu dropdown cấu hình: ngôn ngữ, tỉ lệ, phong cách, thể loại, thời lượng, cấu hình phân đoạn.
- Tỉ lệ chỉ nhận `9:16` và `16:9` (bỏ `1:1` so với `/ai-video`).
- Thời lượng nhận 15–180 giây, hiển thị số clip và thời lượng thực dẫn xuất vì Veo snap độ dài clip vào 4/6/8/10 giây.
- Phong cách: 7 preset điền sẵn vào ô nhập tự do; lưu `visual_style` (text) + `visual_style_preset` (nullable, không validate bằng pattern).
- Prompt pack thêm bốn thứ `/ai-video` không có:
  - Section cố định `Product fidelity — highest priority` chống nhãn sản phẩm biến dạng.
  - Vocabulary đóng 7 shot type bán hàng, thay vì để LLM tự bịa `shot_type`.
  - Rule chống video tĩnh: mỗi shot tối thiểu 2 trong 3 field chuyển động không rỗng, và không hai shot liền nhau trùng cả `shot_type` lẫn `framing`.
  - Block lời nói tiếng Việt được chèn **ngay ở tầng sinh prompt**, thay vì chỉ ở tầng sinh clip như hiện nay.
- Không có: sinh clip qua Flow CDP, TTS, ghép timeline, render MP4, upload ảnh sản phẩm, watermark cleanup, phụ đề. Luồng dừng ở prompt pack.

## Capabilities

### New Capabilities
- `product-video-prompt-generation`: tạo và cấu hình project video sản phẩm, lập kế hoạch shot, và sinh prompt pack hoàn chỉnh để dán vào Google Flow. Bao gồm cả bốn yêu cầu chất lượng prompt ở trên.

### Modified Capabilities
Không có. `openspec/specs/` hiện trống và luồng `/ai-video` không đổi hành vi — route mới có chỉ dẫn LLM riêng nên không sửa `video_phase2.py`.

## Impact

**Code thêm mới:**
- `backend/routes/product_video.py`, `backend/services/product_video.py`
- `app/src/components/ProductVideo/ProductVideo.tsx`, `app/src/lib/constants/productVideoStyles.ts`
- `backend/tests/test_product_video.py`

**Code sửa (đều là thêm vào, không đổi hành vi cũ):**
- `backend/database/models.py` — 3 bảng mới
- `backend/database/migrations.py` — thêm `_migrate_product_video()` và gọi từ `run_migrations()`
- `backend/models.py` — Pydantic model mới
- `backend/routes/__init__.py` — đăng ký router
- `app/src/router.tsx` — route mới, `routeTree`, `isWideWorkspace`
- `app/src/components/Sidebar.tsx` — thêm tab
- `app/src/lib/api/types.ts`, `app/src/lib/api/client.ts` — type và method mới

**Tái dùng nguyên trạng, không sửa:**
- `backend/services/video_purpose.py`, `backend/services/video_language.py`
- `backend/services/video_speech.py` (`build_veo_native_speech_section`)
- `backend/services/video_errors.py` (`AIVideoRoute`)
- `app/src/lib/constants/languages.ts`, `app/src/components/ui/select.tsx`

**Phụ thuộc ngoài:** không thêm dependency nào.

**Follow-up đợt 2 (ngoài phạm vi change này):**
- Thay khung beat mặc định bằng bảng dựa trên tài liệu chính thức TikTok/YouTube/Meta.
- Thay vocabulary camera/lens/lighting bằng danh sách Google chính thức document ([Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)).
- Re-hook giữa video cho mốc 180 giây.
