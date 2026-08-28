## Context

`/ai-video` chạy trọn gói tới MP4 qua sáu tầng: planning phase 1 → phase 2 story → shots → prompt pack → sinh clip qua Flow CDP → TTS → render. Sinh clip không dùng Veo REST API mà lái web app Google Flow qua Chrome DevTools Protocol (`backend/services/video_veo_chrome.py`), và model được đọc từ UI Flow chứ không do code chọn (`FLOW_MODEL_SELECTION_MODE = "use_current_flow_selection"`, `backend/services/video_provider_project_bindings.py:24`).

Ràng buộc quyết định kiến trúc của change này: ảnh sản phẩm chỉ đưa vào được qua Ingredients/References to Video trong UI Flow, và `backend/services/chrome_cdp.py` chưa có primitive upload file (`DOM.setFileInputFiles`). Người dùng vì vậy vẫn phải tự dán ảnh trong Flow. Nên tự động hoá phần sinh clip không mang lại giá trị cho luồng này — giá trị nằm ở chất lượng prompt.

Đã đo được một lỗi cụ thể của prompt hiện tại: chữ `LIBITU` trên màn TV trong một clip Veo thật biến dạng thành chuỗi vô nghĩa giữa frame đầu và frame cuối. Prompt của `/ai-video` không có bất kỳ chỉ dẫn nào về việc giữ nguyên nhãn sản phẩm.

## Goals / Non-Goals

**Goals:**
- Sinh prompt pack đủ chất lượng để dán trực tiếp vào Flow và ra được ba dạng content tham chiếu: UGC cầm sản phẩm, beauty shot studio, người thật thuyết trình quảng cáo.
- Chống hai lỗi đã xác định: nhãn sản phẩm biến dạng, và video tĩnh/đơn điệu.
- Không làm thay đổi hành vi của `/ai-video`.
- Tái dùng tối đa enum và helper đã có thay vì tạo bản sao.

**Non-Goals:**
- Sinh clip qua Flow CDP, TTS, ghép timeline, render MP4, phụ đề, watermark cleanup.
- Upload ảnh sản phẩm qua app.
- Điều khiển tỉ lệ khung hình thực tế của output Flow. `aspect_ratio` chỉ đi vào prompt dưới dạng chữ; chỗ duy nhất quyết định khung hình thật là UI Flow và bước render, mà bước render nằm ngoài phạm vi.
- Bảng beat dựa trên tài liệu chính thức nền tảng phân phối (đợt 2).

## Decisions

### Bảng DB riêng, không dùng chung `video_projects`

Ba bảng mới: `product_video_projects`, `product_video_shots`, `product_video_shot_prompts`.

Đây là quyết định của người dùng sau khi đã được cảnh báo về việc trùng code. Lý do chấp nhận được: `/ai-video` đang có 6 OpenSpec change dở dang, thêm cột phân loại vào `video_projects` sẽ chạm vào bảng mà cả 6 change kia đang sửa.

*Đã cân nhắc:* thêm cột discriminator vào `video_projects` và tái dùng toàn bộ phase 1/2. Ít code hơn đáng kể và được hưởng mọi tối ưu sẵn có, nhưng blast radius lớn hơn và rủi ro xung đột với các change đang mở.

*Đánh đổi phải chấp nhận:* phần planning cần cho tới prompt sẽ bị nhân bản một phần từ `video_phase2.py` (4600+ dòng). Chỉ port phần cần thiết, không copy cả file.

### Migration dùng `Base.metadata.create_all`, không raw SQL

Thêm `_migrate_product_video(engine)` ở cuối `backend/database/migrations.py`, gọi từ `run_migrations()`. Dùng style của `_migrate_automation_hub` (`migrations.py:1792-1829`): import model trong hàm để tránh circular import, liệt kê `__table__`, `create_all(checkfirst=True)`.

*Đã cân nhắc:* style raw SQL `CREATE TABLE IF NOT EXISTS` + `PRAGMA table_info` mà `_migrate_ai_video_assistant` dùng. Bỏ vì với bảng hoàn toàn mới thì nó buộc phải giữ đồng bộ định nghĩa cột ở hai chỗ (`database/models.py` và chuỗi SQL), là nguồn lỗi đã thấy trong file này.

Repo không dùng Alembic, có lý do được ghi rõ ở `migrations.py:1-18`. Không đổi.

### `visual_style_preset` không validate bằng pattern

Phong cách lưu hai cột: `visual_style` (text, max 2000, nguồn sự thật) và `visual_style_preset` (nullable, max 40, chỉ để nhớ lựa chọn UI).

Danh sách preset là thứ sẽ đổi thường xuyên theo kinh nghiệm dùng Flow. Nếu đưa vào `pattern` thì mỗi lần thêm một phong cách phải sửa Pydantic model, default trong migration, và test — đúng cái giá mà `video_purpose` đang phải trả với 6 preset cứng.

*Đã cân nhắc:* enum đầy đủ như `video_purpose.VIDEO_PURPOSE_PATTERN`. Bỏ vì phong cách không có ngữ nghĩa nào ở backend — nó không lái preset ngôn ngữ hay density như `video_purpose` làm, chỉ là text đi vào prompt.

### Bốn cải tiến prompt nằm ở tầng chỉ dẫn LLM, không ở khung nhãn

Nội dung prompt đến từ ba tầng: khung nhãn cố định (`video_phase2.py:3615-3652`), giá trị do LLM điền, và câu mở cứng (`_segment_prompt_prefix`, `:3565-3589`). Shape khung đã đủ tốt — nó vốn đã có `Retention notes`, `Transition notes`, `Sound design notes`, và ba field chuyển động riêng biệt.

Nên bốn cải tiến được thực hiện bằng cách viết chỉ dẫn LLM riêng cho route mới, cộng một section cố định append vào prompt. Không sửa `video_phase2.py`.

- Section `Product fidelity — highest priority`: cố định, luôn append, không do LLM sinh. Lý do: đây là ràng buộc không được phép LLM bỏ sót.
- Vocabulary đóng 7 shot type: validate sau khi LLM trả về, map giá trị lạ về giá trị gần nhất thay vì ghi nguyên.
- Rule chuyển động: kiểm tối thiểu 2/3 field không rỗng sau khi LLM trả về. Đây là kiểm chứng được nên đặt ở tầng validate, không chỉ nhờ LLM tuân thủ.
- Rule không trùng khung: kiểm cặp shot liên tiếp sau khi sinh xong cả pack.

### Block lời nói chèn ở tầng sinh prompt

`build_veo_native_speech_section` (`backend/services/video_speech.py:187-260`) được thiết kế append-only và hiện chỉ được gọi ở `backend/services/video_clip_generation.py:977-981`. Route mới gọi trực tiếp hàm này ở tầng sinh prompt.

Gọi trực tiếp, không refactor `video_clip_generation.py`, để không chạm vào đường đi của `/ai-video`.

### Thời lượng là mục tiêu, không phải cam kết

`target_duration_seconds` validate 15–180. Số clip = `ceil(target / clip_duration)`. Vì Veo snap độ dài clip vào 4/6/8/10 giây (`video_veo_chrome.py:283-287`), thời lượng thực luôn là bội số của độ dài clip và thường khác giá trị người dùng chọn.

Giao diện hiển thị con số dẫn xuất theo thời gian thực. Không làm tròn im lặng.

## Risks / Trade-offs

**Trùng lặp logic planning với `video_phase2.py`** → Chỉ port phần cần cho tới prompt. Ghi rõ trong docstring của `services/product_video.py` rằng nó là bản rút gọn có chủ đích, kèm con trỏ tới hàm gốc, để lần sau sửa biết phải xem cả hai chỗ.

**LLM không tuân thủ vocabulary đóng hoặc rule chuyển động** → Không tin LLM. Cả hai được kiểm ở tầng validate sau khi LLM trả về, và có test khẳng định. Giá trị `shot_type` lạ được map về giá trị gần nhất.

**Section product fidelity không đảm bảo nhãn không drift** → Đây là giảm rủi ro, không phải loại bỏ. Bản chất model vẫn drift chữ. Kèm chỉ dẫn giảm chuyển động của chính sản phẩm (không phải triệt tiêu) và hướng dẫn người dùng kiểm frame cuối chứ không chỉ frame đầu.

**Rule "tối thiểu 2/3 field chuyển động" có thể bị lách bằng giá trị rỗng nghĩa** → LLM có thể trả về `Environment motion: none`. Validate phải coi các giá trị vô nghĩa (`none`, `n/a`, `static`, chuỗi trắng) là rỗng.

**Bảy preset phong cách là phỏng đoán ban đầu** → Ba preset đầu bám đúng ba video tham chiếu đã phân tích; bốn preset còn lại là suy luận. Đặt tất cả ở một file duy nhất `app/src/lib/constants/productVideoStyles.ts` để sửa một chỗ khi có dữ liệu thực tế.

**Thêm change thứ 7 vào 6 change đang dở** → Bảng và service riêng nên không chạm vào file mà các change kia đang sửa, trừ `migrations.py`, `models.py`, `routes/__init__.py`, `router.tsx`, `Sidebar.tsx` — đều là thêm vào cuối, ít khả năng xung đột.

## Migration Plan

Migration chỉ tạo bảng mới, không sửa bảng cũ, nên không cần rollback dữ liệu. `_migrate_product_video` idempotent nhờ `checkfirst=True`; chạy lại nhiều lần vô hại.

Nếu cần bỏ feature: xoá router khỏi `register_routers`, xoá route khỏi `routeTree` và `Sidebar`. Ba bảng để lại vô hại vì không có FK nào từ bảng cũ trỏ vào.

## Open Questions

- Danh sách từ khoá camera/lens/lighting Google chính thức document: chưa đọc được toàn văn [Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) vì `WebFetch` lỗi. Đợt 1 dùng vocabulary tự định nghĩa, đánh dấu là tạm.
- Cấu trúc beat cho từng mốc 15/30/60/180 giây từ tài liệu chính thức TikTok/YouTube/Meta: đang nghiên cứu. Đợt 1 dùng khung mặc định hook → problem → product reveal → proof → CTA, giãn theo số clip.
- Với mốc 180 giây (18–23 clip), chưa rõ có cần re-hook giữa video hay không. Để đợt 2.
