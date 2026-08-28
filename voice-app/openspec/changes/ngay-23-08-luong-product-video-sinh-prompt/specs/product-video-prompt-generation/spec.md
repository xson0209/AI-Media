## ADDED Requirements

### Requirement: Tạo và cấu hình project video sản phẩm

The system MUST satisfy the product-video project configuration contract below.
Hệ thống PHẢI cho phép tạo một project video sản phẩm với sáu tham số cấu hình: ngôn ngữ nội dung (`target_language`), tỉ lệ khung hình (`aspect_ratio`), phong cách (`visual_style` + `visual_style_preset`), thể loại (`video_purpose`), thời lượng mục tiêu (`target_duration_seconds`), và cấu hình phân đoạn (`prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt`). Dữ liệu PHẢI được lưu vào bảng `product_video_projects`, KHÔNG được lưu vào `video_projects`.

#### Scenario: Tạo project với cấu hình đầy đủ
- **WHEN** client gửi `POST /product-video/projects` với `topic` không rỗng, `target_language="vi"`, `aspect_ratio="9:16"`, `video_purpose="sales_ad"`, `target_duration_seconds=30`
- **THEN** hệ thống trả về 200 kèm project có `id`, và bản ghi tồn tại trong bảng `product_video_projects`

#### Scenario: Thiếu topic
- **WHEN** client gửi `POST /product-video/projects` với `topic` là chuỗi rỗng
- **THEN** hệ thống trả về 422 và không tạo bản ghi nào

### Requirement: Tỉ lệ khung hình chỉ nhận dọc và ngang

The system MUST satisfy the aspect-ratio contract below.
Hệ thống PHẢI chỉ chấp nhận `aspect_ratio` là `9:16` hoặc `16:9`. Mọi giá trị khác PHẢI bị từ chối, kể cả `1:1` và `4:5` là các giá trị được `/ai-video` hoặc Story Studio cho phép.

#### Scenario: Tỉ lệ dọc hợp lệ
- **WHEN** client tạo project với `aspect_ratio="9:16"`
- **THEN** hệ thống trả về 200

#### Scenario: Tỉ lệ vuông bị từ chối
- **WHEN** client tạo project với `aspect_ratio="1:1"`
- **THEN** hệ thống trả về 422

### Requirement: Thời lượng 15 đến 180 giây và số clip dẫn xuất

The system MUST satisfy the duration and derived-clip contract below.
Hệ thống PHẢI chỉ chấp nhận `target_duration_seconds` trong khoảng 15 đến 180 giây. Hệ thống PHẢI tính và trả về số clip dẫn xuất cùng thời lượng thực tế, vì Veo snap độ dài clip vào 4/6/8/10 giây nên thời lượng thực luôn là bội số của độ dài clip và có thể khác giá trị người dùng chọn.

#### Scenario: Thời lượng trong khoảng hợp lệ
- **WHEN** client tạo project với `target_duration_seconds=30`
- **THEN** hệ thống trả về 200 và response chứa số clip dẫn xuất cùng thời lượng thực tế

#### Scenario: Thời lượng dưới ngưỡng
- **WHEN** client tạo project với `target_duration_seconds=10`
- **THEN** hệ thống trả về 422

#### Scenario: Thời lượng trên ngưỡng
- **WHEN** client tạo project với `target_duration_seconds=240`
- **THEN** hệ thống trả về 422

#### Scenario: Thời lượng không đạt được chính xác
- **WHEN** người dùng chọn 15 giây và độ dài clip là 8 giây
- **THEN** giao diện hiển thị số clip là 2 và thời lượng thực tế là 16 giây, không hiển thị 15 giây

### Requirement: Phong cách chọn preset hoặc nhập tự do

The system MUST satisfy the visual-style contract below.
Hệ thống PHẢI cho phép người dùng chọn một trong bảy preset phong cách (`ugc_street`, `studio_beauty`, `presenter_ad`, `macro_closeup`, `unboxing`, `flatlay`, `custom`) hoặc tự nhập nội dung phong cách. Giá trị `visual_style` là text tự do tối đa 2000 ký tự và là nguồn sự thật. Giá trị `visual_style_preset` tối đa 40 ký tự, nullable, KHÔNG được validate bằng pattern để danh sách preset thay đổi được mà không cần sửa model, migration và test.

#### Scenario: Chọn preset điền sẵn nội dung
- **WHEN** người dùng chọn preset `ugc_street`
- **THEN** ô nhập phong cách được điền sẵn đoạn mô tả của preset đó và người dùng vẫn sửa được nội dung

#### Scenario: Sửa nội dung sau khi chọn preset
- **WHEN** người dùng chọn preset `ugc_street` rồi sửa nội dung trong ô nhập
- **THEN** `visual_style` lưu đúng nội dung đã sửa và `visual_style_preset` chuyển thành `custom`

#### Scenario: Preset lạ không bị từ chối
- **WHEN** client tạo project với `visual_style_preset="mot_preset_chua_ton_tai"`
- **THEN** hệ thống trả về 200 và lưu nguyên giá trị đó

#### Scenario: Mọi preset đều mô tả chuyển động
- **WHEN** kiểm tra nội dung text của cả bảy preset trừ `custom`
- **THEN** mỗi preset chứa mô tả ít nhất một nguồn chuyển động và không preset nào mô tả shot hoàn toàn tĩnh

### Requirement: Prompt chứa section giữ nguyên nhãn sản phẩm

The system MUST satisfy the product-fidelity prompt contract below.
Mọi prompt sinh ra PHẢI chứa một section cố định có tiêu đề `Product fidelity — highest priority`. Section này PHẢI yêu cầu giữ nguyên chữ, typography, logo, màu và tỉ lệ bố cục của nhãn sản phẩm; PHẢI cấm redesign, dịch và sắp xếp lại nhãn; và PHẢI cấm nhãn biến dạng giữa frame đầu và frame cuối.

#### Scenario: Section luôn có mặt
- **WHEN** hệ thống sinh prompt cho bất kỳ shot nào của bất kỳ project nào
- **THEN** prompt chứa chuỗi `Product fidelity — highest priority`

#### Scenario: Section nêu đủ bốn điều cấm
- **WHEN** kiểm tra nội dung section product fidelity
- **THEN** section nêu rõ cấm redesign, cấm dịch nhãn, cấm sắp xếp lại nhãn, và cấm nhãn biến dạng giữa frame đầu và frame cuối

### Requirement: Shot type lấy từ vocabulary đóng

The system MUST satisfy the closed shot-type vocabulary contract below.
Hệ thống PHẢI chỉ dùng `shot_type` trong danh sách đóng bảy giá trị: `hero shot`, `macro detail`, `in-use/lifestyle`, `before-after`, `unboxing reveal`, `size comparison`, `CTA end-card`. LLM KHÔNG được tự phát minh giá trị `shot_type` ngoài danh sách này.

#### Scenario: Shot type hợp lệ
- **WHEN** hệ thống sinh prompt pack cho một project
- **THEN** mọi giá trị `shot_type` trong prompt pack đều thuộc danh sách bảy giá trị nói trên

#### Scenario: LLM trả về shot type ngoài danh sách
- **WHEN** LLM trả về `shot_type` không thuộc danh sách, ví dụ `dramatic wide establishing`
- **THEN** hệ thống thay bằng giá trị gần nhất trong danh sách thay vì ghi nguyên giá trị lạ vào prompt

### Requirement: Prompt không được sinh ra shot tĩnh

The system MUST satisfy the motion-budget contract below.
Mỗi prompt PHẢI chứa tối thiểu 2 trong 3 dòng `Camera movement:`, `Subject motion:`, `Environment motion:` với giá trị không rỗng. Ràng buộc giữ nguyên nhãn sản phẩm KHÔNG được thực hiện bằng cách bắt sản phẩm đứng yên; sản phẩm được phép nâng, mang đi, nghiêng nhẹ và được tay người tương tác, miễn là mặt có nhãn giữ hướng về camera và không bị bóp méo.

#### Scenario: Đủ hai nguồn chuyển động
- **WHEN** hệ thống sinh prompt cho bất kỳ shot nào
- **THEN** prompt có ít nhất 2 trong 3 dòng chuyển động với giá trị không rỗng

#### Scenario: Beauty shot studio vẫn có chuyển động hậu cảnh
- **WHEN** shot dùng phong cách `studio_beauty` mà chỉ có camera di chuyển
- **THEN** prompt vẫn chứa `Environment motion:` không rỗng, mô tả nguồn động của hậu cảnh

#### Scenario: Chỉ cấm bốn kiểu chuyển động gây drift
- **WHEN** kiểm tra chỉ dẫn chuyển động của sản phẩm trong prompt
- **THEN** prompt cấm quay tròn hết vòng, spin nhanh, nhãn rời khỏi khung rồi quay lại, và sản phẩm đi qua vật che; và KHÔNG cấm sản phẩm chuyển động nói chung

### Requirement: Hai shot liền nhau không được trùng khung

The system MUST satisfy the adjacent-shot variety contract below.
Trong một prompt pack, hai shot liên tiếp KHÔNG được trùng đồng thời cả `shot_type` và `framing`.

#### Scenario: Prompt pack nhiều shot
- **WHEN** hệ thống sinh prompt pack có từ 2 shot trở lên
- **THEN** không tồn tại cặp shot liên tiếp nào có cùng `shot_type` và cùng `framing`

### Requirement: Prompt chứa lời nói tiếng Việt ngay ở tầng sinh prompt

The system MUST satisfy the Vietnamese-speech prompt contract below.
Khi `target_language` là `vi`, prompt pack PHẢI chứa block lời nói tiếng Việt sinh bởi `build_veo_native_speech_section`. Block này hiện chỉ được chèn ở tầng sinh clip (`backend/services/video_clip_generation.py`); vì luồng này dừng ở prompt, block PHẢI được chèn ngay khi sinh prompt. Chỉ dẫn PHẢI nêu giới hạn khoảng 18 đến 20 chữ tiếng Việt cho một clip 8 giây.

#### Scenario: Project tiếng Việt có block lời nói
- **WHEN** hệ thống sinh prompt pack cho project có `target_language="vi"` và có lời thoại
- **THEN** prompt chứa chuỗi `Vietnamese spoken dialogue` và nội dung lời thoại

#### Scenario: Chỉ dẫn nêu giới hạn độ dài thoại
- **WHEN** prompt chứa block lời nói tiếng Việt
- **THEN** block nêu giới hạn khoảng 18 đến 20 chữ cho một clip 8 giây

#### Scenario: Project không phải tiếng Việt
- **WHEN** project có `target_language="en"`
- **THEN** prompt không chứa block lời nói tiếng Việt

### Requirement: Prompt giữ ghi chú giữ chân, chuyển cảnh và âm thanh

The system MUST satisfy the prompt-notes contract below.
Prompt PHẢI chứa ba dòng `Retention notes:`, `Transition notes:`, `Sound design notes:` với giá trị không rỗng, cùng hook cho shot đầu tiên.

#### Scenario: Ba dòng ghi chú có mặt
- **WHEN** hệ thống sinh prompt cho bất kỳ shot nào
- **THEN** prompt chứa cả ba dòng `Retention notes:`, `Transition notes:`, `Sound design notes:` với giá trị không rỗng

#### Scenario: Shot đầu tiên có hook
- **WHEN** hệ thống sinh prompt cho shot đầu tiên của project
- **THEN** prompt chứa nội dung hook mở đầu cho 0 đến 2 giây đầu

### Requirement: Xuất prompt pack để dán vào Flow

The system MUST satisfy the prompt-pack export contract below.
Hệ thống PHẢI cho phép copy prompt của từng shot và tải toàn bộ prompt pack. Giao diện PHẢI có bốn trạng thái: đang tải, lỗi kèm nút thử lại, rỗng, và thành công.

#### Scenario: Copy một prompt
- **WHEN** người dùng bấm nút copy trên một shot
- **THEN** nội dung prompt của shot đó được đưa vào clipboard

#### Scenario: Tải toàn bộ prompt pack
- **WHEN** người dùng gọi `GET /product-video/projects/{id}/prompt-pack`
- **THEN** hệ thống trả về file chứa prompt của mọi shot, mỗi shot một section có nhãn thứ tự

#### Scenario: Lỗi khi sinh prompt
- **WHEN** bước sinh prompt thất bại
- **THEN** giao diện hiển thị thông báo lỗi kèm nút thử lại, và không hiển thị prompt pack rỗng như thể đã thành công

#### Scenario: Chưa có shot nào
- **WHEN** project vừa tạo và chưa chạy bước lập kế hoạch
- **THEN** giao diện hiển thị trạng thái rỗng kèm hướng dẫn bước tiếp theo

### Requirement: Luồng dừng ở prompt pack

The system MUST satisfy the prompt-only workflow boundary below.
Route `/product-video` KHÔNG được gọi sinh clip qua Chrome DevTools Protocol, KHÔNG được gọi TTS, KHÔNG được ghép timeline và KHÔNG được render MP4. Hành vi của `/ai-video` PHẢI không đổi.

#### Scenario: Không có endpoint sinh clip
- **WHEN** kiểm tra các endpoint của router `/product-video`
- **THEN** không tồn tại endpoint nào tạo clip generation job, render job, hay voice job

#### Scenario: Luồng ai-video không đổi
- **WHEN** chạy bộ test hiện có của `/ai-video`
- **THEN** toàn bộ test vẫn pass và `backend/services/video_phase2.py` không bị sửa


