# Giữ prompt và nhận diện nhân vật trong luồng Flow

Ngày nghiên cứu: 2026-10-02. Phạm vi: mã nguồn hiện tại của Dự án AI Video và tài liệu chính thức Google Flow/Veo; tập trung đề xuất số 1 trong [nghiên cứu camera](cong-thuc-khoa-camera-render-video-ai-2026-10-02.md). Đây là báo cáo nghiên cứu và thiết kế đề xuất, chưa thay đổi code sản phẩm.

## Kết luận

Muốn giữ nhân vật khi rút gọn prompt, cần bảo toàn **mô tả nhận diện cụ thể của các nhân vật trong shot**, hành động chính, yêu cầu camera và trạng thái đầu/cuối. Chỉ thêm câu chung `same character` hoặc thêm camera vào danh sách giữ lại chưa đủ.

Hiểu đơn giản: rút gọn prompt là bỏ phần giải thích và nội dung lặp, nhưng phải giữ nguyên thông tin "nhân vật nào, trông ra sao, làm gì, camera ở đâu". Để giữ ngoại hình qua nhiều shot, còn cần dùng lại ảnh đã duyệt hoặc nhân vật đã lưu trong Flow. Hai việc này bổ trợ nhau: bảo toàn văn bản bảo đảm ứng dụng gửi đủ yêu cầu; đầu vào hình ảnh cung cấp diện mạo thực tế để model tham chiếu.

Mã nguồn hiện có ba điểm làm mất thông tin:

1. Tạo clip tự động chỉ lấy trường `prompt` trong DB; camera, continuity, negative prompt và các trường riêng không được ghép tự động tại bước gửi.
2. Compactor bỏ nhiều section ngay cả khi prompt ngắn hơn giới hạn 5.200 ký tự mà ứng dụng đặt ra.
3. Nếu backend phải thêm segment prefix, marker `Micro-scene timeline:` được đặt trước main prompt. Compactor có thể giữ phần giới thiệu chung nhưng bỏ cả hành động và nhận diện cụ thể phía sau marker.

Các điểm trên được xác nhận bằng đọc source và kiểm tra hàm xử lý chuỗi cô lập. Chúng không chứng minh mọi prompt hiện tại đều gặp lỗi: chi tiết đã có trong phần đầu có thể vẫn còn. Flow hiện có Characters, Ingredients và Frames để dùng lại đầu vào hình ảnh; khả năng và thời lượng phụ thuộc model. Chưa có benchmark render trong nghiên cứu này để đo mức độ giữ nhân vật thực tế.

## 1. Đường đi dữ liệu hiện tại

### A. Dữ liệu planner được lưu thành các trường riêng

[video_phase2.py:4326](../../backend/services/video_phase2.py#L4326) tạo `stored_prompt` bằng `_segment_aware_prompt_text`. [Dòng 4367](../../backend/services/video_phase2.py#L4367) lưu phần này vào `DBVideoShotPrompt.prompt`; camera, subject/environment motion, start/end frame, negative và continuity được lưu ở các cột khác tại dòng 4369–4383.

Trong khi đó, file prompt đầy đủ do [dòng 4390](../../backend/services/video_phase2.py#L4390) ghi ra dùng `_prompt_text`, ghép thêm camera, start/end frame và continuity ([dòng 3910](../../backend/services/video_phase2.py#L3910)). Vì vậy `prompt` trong DB và file prompt đầy đủ không phải cùng một chuỗi.

### B. Tạo clip tự động lấy riêng `prompt.prompt`

[video_clip_generation.py:963](../../backend/services/video_clip_generation.py#L963) gọi:

```python
provider_safe_prompt_for_veo(
    prompt.prompt,
    narration_context=...,
    native_speech_section=...,
)
```

Không có đối số camera/continuity/start/end/negative từ các cột riêng. Nếu main prompt chưa mô tả lại các chi tiết này, bước này không tự đưa chúng vào chuỗi gửi. Kết quả được truyền đến Flow tại [dòng 981](../../backend/services/video_clip_generation.py#L981).

Đường copy/download hiện có builder khác: [_provider_ready_prompt_text:4516](../../backend/services/video_phase2.py#L4516) ghép các trường camera/motion rồi gọi audio contract với negative và continuity nếu có speech mode; nếu không, nó dùng `_stored_prompt_download_text` chứa các trường riêng ([dòng 4482](../../backend/services/video_phase2.py#L4482)). Tạo clip tự động không gọi builder này. Đây là nguyên nhân hai đường có thể gửi nội dung khác nhau.

### C. Compactor cắt theo marker, không theo mức độ quan trọng

[video_clip_generation.py:91](../../backend/services/video_clip_generation.py#L91) đặt `FLOW_PROVIDER_PROMPT_MAX_CHARS = 5200`. Đây là cấu hình nội bộ được tìm thấy trong source, chưa có bằng chứng đó là giới hạn bắt buộc của Flow.

[Dòng 240](../../backend/services/video_clip_generation.py#L240) kích hoạt compact khi quá 5.200 ký tự **hoặc** có một trong các marker `Video language:`, `Micro-scene timeline:`, `Bản giải thích`. Vì vậy prompt vài trăm ký tự vẫn có thể bị compact.

[Dòng 243](../../backend/services/video_clip_generation.py#L243) lấy phần đầu trước `Video language:` hoặc `Micro-scene timeline:`. Sau đó giữ language và các mục có trong `FLOW_PROVIDER_PROMPT_KEEP_SECTIONS`: retention, transition, sound và negative ([dòng 123](../../backend/services/video_clip_generation.py#L123)). Danh sách này không giữ camera, start/end frame hoặc continuity.

`FLOW_PROVIDER_PROMPT_SECTION_HEADINGS` có nhận diện những heading đó ([dòng 97](../../backend/services/video_clip_generation.py#L97)), nhưng nhận diện ranh giới section không đồng nghĩa giữ section. Sau bước ghép, [_truncate_flow_provider_prompt:221](../../backend/services/video_clip_generation.py#L221) tiếp tục cắt chuỗi theo vị trí ký tự, với xử lý riêng để giữ negative. Chưa có xử lý riêng cho identity hoặc primary action.

### D. Prefix có thể nằm trước toàn bộ hành động cụ thể

[_segment_prompt_prefix:3858](../../backend/services/video_phase2.py#L3858) tạo phần duration, style, continuity chung, segment structure rồi `Micro-scene timeline:` tại dòng 3890. Nếu main prompt chưa có đầy đủ segment, duration và continuity marker, [_segment_aware_prompt_text:3908](../../backend/services/video_phase2.py#L3908) nối theo thứ tự:

```text
segment prefix
Micro-scene timeline:
timeline...

main prompt chứa nhân vật, hành động, camera cụ thể
```

Compactor cắt tại marker timeline nên có thể bỏ cả timeline lẫn main prompt phía sau. Một câu chung như `same face/identity` trong prefix còn lại chưa thể thay thế các đặc điểm cụ thể như màu mặt, kiểu tóc hoặc huy hiệu của nhân vật.

## 2. Kiểm tra cô lập đã thực hiện

Phương pháp: đọc source UTF-8, trích AST của bốn hàm compactor cùng các hằng số liên quan; với trường hợp prefix, thực thi thêm `_segment_prompt_prefix` và `_segment_aware_prompt_text` lấy từ source. Các dependency config/timeline/continuity được thay bằng dữ liệu mẫu qua `SimpleNamespace`. Không import service/database, không gọi provider, không tạo job hay tiêu credit.

| Trường hợp | Ký tự đầu vào → đầu ra | Kết quả |
| --- | --- | --- |
| Camera và `same red jacket` chỉ nằm sau `Video language:` | 260 → 157 | Mất cả camera và nhận diện áo. |
| Thêm cùng camera/nhận diện vào phần đầu, trước marker | 329 → 226 | Giữ cả hai chi tiết. |
| Prompt thuần ngắn, không có marker compact | 91 → 91 | Giữ nguyên. |
| Prompt dài, nhận diện áo nằm ở cuối | 6.419 → 5.191 | Nhận diện cuối bị cắt. |
| Dùng hàm thật để thêm prefix trước main prompt | 1.081 → 829 | Mất `opens a toolbox` và `yellow shoulder badge`; câu continuity chung còn. |

Ví dụ đầu vào cho trường hợp đầu:

```text
Single continuous shot. A woman smiles gently.

Video language: English
Camera movement: The camera remains entirely motionless.
Continuity notes: Same woman, same red jacket.
Retention notes: A clear emotional reaction.

Negative prompt:
flicker, camera shake
```

Đầu ra thực tế:

```text
Single continuous shot. A woman smiles gently.

Video language: English

Retention notes: A clear emotional reaction.

Negative prompt:
flicker, camera shake
```

Trường hợp prefix dùng một Dự án AI Video chưa gắn series, segment 8 giây, 4 micro-scenes, với main prompt về robot đỏ có mặt tròn bạc và huy hiệu vai vàng đang mở hộp dụng cụ. Đây là một trường hợp tái hiện có điều kiện, không phải thống kê tần suất xuất hiện trong các dự án hiện có.

### Kiểm tra bổ sung đường copy/auto và ngân sách

Probe tái hiện nằm tại [.codex-run/prompt_identity_compaction_probe.py](../../.codex-run/prompt_identity_compaction_probe.py), chạy từ root bằng `python -X utf8 .codex-run/prompt_identity_compaction_probe.py`. Probe thực thi các hàm xử lý chuỗi lấy trực tiếp từ AST, với config, project/shot và helper không liên quan được thay bằng fixture; không import service hoặc gọi database/browser/provider.

| Trường hợp bổ sung | Kết quả thực thi | Ý nghĩa |
| --- | --- | --- |
| Prefix thật đứng trước prompt về Mai tóc bob đen, áo đỏ, cười một lần, camera đứng yên | 1.189 → 973 ký tự sau compact; mất cả main prompt, áo đỏ và camera | Lỗi không cần prompt dài mới xảy ra. |
| Copy so với auto trên cùng fixture, nhánh không có speech mode | Copy 1.740 ký tự có main prompt/camera/continuity/negative; auto 1.187 ký tự thiếu cả bốn | Đối chiếu prompt copy chưa xác nhận nội dung auto gửi. Auto có thêm context note sau compact. |
| Main prompt đã đủ segment/duration/continuity nên không thêm prefix | Main prompt được giữ | Xác nhận nhánh lỗi có điều kiện, không phải mọi prompt. |
| Series giả lập có 20 nhân vật, mỗi identity dài, prefix dùng cast thật | 12.149 → 4.883 ký tự; chỉ còn 8/20 `profile_id`, không còn fixed traits của nhân vật cuối | Nhét cả roster vào mỗi shot có thể làm mất nhân vật ở cuối khi cắt. Đây là fixture, không phải số liệu của một series đang chạy. |
| Visual dài ghép native speech sau compact | Visual sau compact 5.184, audio 1.916, payload cuối 7.101 ký tự | Ngân sách 5.200 hiện không bao trùm payload cuối. Chưa có bằng chứng payload 7.101 bị Flow từ chối. |

## 3. Nhân vật hiện được mô tả ở đâu?

[video_series_characters.py:133](../../backend/services/video_series_characters.py#L133) đã tạo mô tả identity từ `face_description`, `hair_description`, `body_description`, `signature_outfit`, `fixed_traits`. [_profile_to_cast:144](../../backend/services/video_series_characters.py#L144) đưa chúng vào cast đã duyệt dưới `identity_lock`/`visual_identity`.

[cast_prompt_text_from_project:645](../../backend/services/video_series_characters.py#L645) đưa identity vào phần mô tả cast. [video_prompt_instructions:722](../../backend/services/video_series_characters.py#L722) yêu cầu planner mô tả từng nhân vật nhìn thấy, vị trí, hành động và tương tác. [segment_continuity_rule:739](../../backend/services/video_series_characters.py#L739) đưa quy tắc giữ mặt, tóc, hình thể, trang phục vào prefix; nhánh series còn đưa approved episode cast vào prefix.

Như vậy đã có dữ liệu nền để giữ nhận diện. Điểm thiếu là đảm bảo **đúng các đặc điểm của nhân vật trong shot có mặt trong chuỗi cuối**, sau mọi bước ghép, compact và thêm audio. Câu `same main character` trong nhánh chưa gắn series chỉ là quy tắc chung; nó không chứa diện mạo cụ thể và không chứng minh model biết nhân vật từ đoạn trước.

Một hạn chế khác: adapter hiện nhận prompt/thời lượng nhưng không nhận file reference/keyframe ([video_veo_chrome.py:1877](../../backend/services/video_veo_chrome.py#L1877)). Planner gọi package reference với `provider_supports_references=False` ([video_phase2.py:4060](../../backend/services/video_phase2.py#L4060)); report reference trả `sent=[]` ([series_references.py:551](../../backend/services/series_references.py#L551)). Vì vậy giữ mô tả trong prompt và gửi ảnh thật là hai công việc riêng. Không thể dùng status metadata hiện tại để khẳng định ảnh đã được Veo nhận; nếu ảnh được thêm thủ công trong Flow thì cần kiểm tra trạng thái đó riêng.

## 4. Thiết kế đề xuất để giữ nhân vật khi compact

Đây là thiết kế được suy ra từ các điểm mất dữ liệu đã xác nhận, chưa phải tính năng đã có.

### 4.1. Một builder chung cho prompt thực gửi

Builder nhận cả Dự án AI Video, shot, DB prompt và cast/profile đã duyệt. Các đường copy, download và tự động gửi dùng cùng bước biên dịch nội dung cốt lõi; audio được ghép theo speech mode đã chọn. Không sửa bằng cách chỉ thay input thành file prompt cũ vì file đó có thể chứa phần giải thích và audio contract cũ.

Builder phải lấy dữ liệu từ các trường riêng một cách xác định, không phụ thuộc việc planner có tình cờ lặp camera/identity trong prose hay không.

### 4.2. Tách đặc điểm cố định khỏi trạng thái của shot

Giữ các đặc điểm cố định từ profile được duyệt: mặt, tóc, hình thể, đặc điểm phân biệt, trang phục đặc trưng hoặc quy tắc thay trang phục đã được duyệt. Trạng thái tạm thời như biểu cảm, tư thế, vị trí, đạo cụ và cảm xúc thuộc shot.

Trong cảnh nhiều nhân vật, mỗi nhân vật phải có mô tả riêng và vị trí rõ ràng. Chỉ đưa nhân vật thật sự thấy trong shot vào đoạn nhận diện; danh sách toàn bộ nhân vật của tập là thông tin planning, không nên trở thành danh sách người bắt buộc xuất hiện trong mọi shot. Shot hiện có nguồn `visible_characters` trong `retention_json` ([video_phase2.py:3916](../../backend/services/video_phase2.py#L3916)). Nếu thiếu dữ liệu xác định nhân vật nào xuất hiện, cần báo thiếu trước khi tự chọn hoặc cắt bỏ một nhân vật.

### 4.3. Compact theo cấu trúc và ưu tiên, không cắt theo marker chung

Các phần cần giữ theo ý định đã duyệt:

- diện mạo cụ thể của từng nhân vật nhìn thấy và phong cách hình ảnh;
- hành động chính, chủ thể thực hiện và mốc kết thúc;
- camera, bố cục và chuyển động chủ thể/môi trường;
- trạng thái đầu/cuối và continuity cần thiết;
- thông số clip thực tế cùng chính sách audio theo mode đã chọn.

Có thể bỏ phần giải thích tiếng Việt, heading thừa, nội dung lặp, metadata dùng để planning và các ghi chú dựng ngoài provider khi chúng không cần cho việc sinh clip. Việc bỏ hay rút gọn negative/retention/transition/sound phải theo tính năng provider và ý định cảnh; không ưu tiên chúng cao hơn nhận diện/hành động mặc định như danh sách hiện tại.

Tính ngân sách trên **chuỗi cuối gồm audio/context**, vì hiện tại native speech hoặc narration context được thêm sau compact ([video_clip_generation.py:272](../../backend/services/video_clip_generation.py#L272)). Nếu phần bắt buộc vẫn không vừa ngân sách, trả kết quả cần review/rút cảnh; không âm thầm cắt mất đặc điểm của nhân vật để vừa số ký tự.

### 4.4. Kiểm tra chuỗi cuối trước khi gửi

Gate phải kiểm tra kết quả sau compact: đủ nhận diện của các nhân vật đã duyệt trong shot, hành động chính, camera đã chọn và trạng thái cần giữ. Việc JSON ban đầu đầy đủ hoặc chất lượng prompt đã passed chưa xác minh các phần này còn trong chuỗi cuối ([video_phase2.py:3824](../../backend/services/video_phase2.py#L3824); [video_clip_generation.py:369](../../backend/services/video_clip_generation.py#L369)).

Nên lưu hash của chuỗi thực gửi, revision của profile/reference, độ dài và danh sách phần đã bỏ; cho phép xem prompt thực gửi để đối chiếu với prompt đầy đủ. Adapter Chrome đã so sánh văn bản nhập vào ô Flow với chuỗi được truyền cho nó ([video_veo_chrome.py:840](../../backend/services/video_veo_chrome.py#L840)); bước đó xác nhận nhập đúng chuỗi nhưng chưa xác nhận chuỗi đã bảo toàn ý định từ DB.

Cần thêm một quy tắc giải quyết mâu thuẫn: camera đã duyệt của shot phải được ưu tiên so với style mặc định. Prefix hiện yêu cầu `real camera movement` ([video_phase2.py:3883](../../backend/services/video_phase2.py#L3883)); nếu shot yêu cầu camera đứng yên, hai chỉ dẫn này xung đột. Khi giữ camera cố định, vẫn cho phép chủ thể/môi trường chuyển động theo shot. Khóa ngoại hình và giữ camera đứng yên là hai yêu cầu khác nhau.

### 4.5. Ví dụ phần cốt lõi sau khi ghép

Ví dụ minh họa thiết kế, chưa phải benchmark prompt Veo:

```text
Character: one stylized 3D red robot with a silver circular face,
short rectangular limbs, and a yellow badge on its left shoulder.
Keep these exact colors, proportions, face design, and badge placement
throughout the clip. Only this approved character is visible.

Action: the robot slowly opens one toolbox, then holds it open.
Start: both feet planted, toolbox closed on the table.
End: same position and appearance, toolbox open.

Camera: a fixed eye-level medium shot. The camera remains entirely
motionless throughout this continuous shot.
Style: the approved stylized 3D design and color palette.
```

Khác biệt cần đạt là câu “giữ nhân vật” có đối tượng và đặc điểm cụ thể, camera có yêu cầu rõ, hành động không bị bỏ vì đứng sau heading timeline. Không nên tự thêm huy hiệu, màu áo hoặc tư thế vào nhân vật của người dùng: ví dụ này dùng nhân vật giả để minh họa cách bảo toàn dữ liệu đã duyệt.

## 5. Flow có những cách nào để dùng lại nhân vật?

Các nguồn dưới đây được đọc trực tiếp từ Google ngày 2026-10-02. Đây là khả năng của Flow/Veo được nhà cung cấp mô tả, không phải bằng chứng app hiện đã tích hợp hoặc video sẽ luôn giống 100%.

### 5.1. Characters: lưu một nhân vật để dùng lại

[Google Flow — Manage projects, assets & collections, mục Characters](https://support.google.com/flow/answer/16935308#flowcharacters) hướng dẫn tạo một character bằng 1 hoặc 2 ảnh, đặt tên, chọn giọng và lưu; một character phải có ít nhất một ảnh mới dùng được. [Create videos — Add characters](https://support.google.com/flow/answer/16353334) hướng dẫn gõ `@` kèm tên và mô tả cách dùng nhân vật.

Google mô tả tính năng này giữ mặt, trang phục và giọng nhất quán qua nhiều generation. Cần phân biệt mô tả khả năng của nhà cung cấp với kết quả đã đo: nghiên cứu này chưa render để kiểm chứng mức độ nhất quán. Hai trang trên chưa liệt kê riêng ma trận Characters theo từng model; cần kiểm tra feature thực tế trên tài khoản/model trước khi tích hợp. Không suy ra Characters hoạt động trên mọi model chỉ từ bảng hỗ trợ Ingredients.

**Áp dụng:** nếu Flow đang dùng có mục Characters, lưu bộ ảnh đã duyệt thành một nhân vật rồi chọn đúng character đó cho từng shot. Hồ sơ nhân vật Series trong app và character asset trong Flow hiện chưa có đường nối tự động được xác nhận trong adapter. Gõ tên hoặc ID dưới dạng chữ thường không tương đương đính kèm ảnh/character asset.

### 5.2. Ingredients/References: dùng cùng ảnh qua các shot

[Google Flow — Create videos, mục Add visual references](https://support.google.com/flow/answer/16353334) nói có thể dùng lại cùng ảnh nhân vật và vật thể từ clip này sang clip khác bằng ingredients. Người dùng chọn Video → Ingredients, thêm media từ thiết bị/project, hoặc dùng `@` để tìm asset đã tải lên, rồi mô tả cách các reference được sử dụng trong clip.

Google khuyên ảnh nhân vật/sản phẩm có nền đơn giản hoặc đã tách chủ thể; ảnh địa điểm/style tránh chứa thêm chủ thể ngoài ý định; prompt phải bổ trợ ảnh, và các ảnh nên có cùng phong cách. Với app đang yêu cầu stylized 3D, nên dùng ảnh nhân vật đã duyệt đúng phong cách đó để tránh chỉ dẫn hình/text mâu thuẫn.

**Áp dụng:** khi đổi góc máy hoặc sang bối cảnh khác, dùng lại ảnh gốc của cùng nhân vật; thay phần hành động và bố trí của shot. Trong cảnh nhiều nhân vật, liên kết rõ từng asset với từng nhân vật/vị trí, không chỉ ghi `same characters`.

### 5.3. Frames: dùng ảnh đầu/cuối cho một shot

[Google Flow — Create videos, mục Add start & end frames](https://support.google.com/flow/answer/16353334) hướng dẫn thêm ảnh vào start frame/end frame và mô tả hành động hoặc chuyển tiếp giữa các ảnh. [Edit videos & build scenes, mục Save video frames](https://support.google.com/flow/answer/16935718) xác nhận có thể dừng video tại một frame, dùng **Save frame**, rồi dùng ảnh đã lưu làm ingredient hoặc start/end frame cho generation sau.

**Áp dụng:** nếu shot sau tiếp nối ngay trạng thái của shot trước, lấy một frame đã duyệt gần cuối làm start frame tiếp theo. Chỉ nối từ frame có mặt/tay/đạo cụ đúng; nếu frame đã méo thì dùng ảnh gốc hoặc tạo lại frame phù hợp. Nếu đổi góc hoặc vị trí hẳn, ưu tiên reference nhân vật gốc và chuẩn bị start frame mới đúng shot thay vì ép ảnh cuối cũ cho mọi trường hợp. Đây là cách bố trí workflow được suy ra từ tính năng, chưa phải benchmark so sánh.

### 5.4. Chọn mode theo model, không tự đổi model của người dùng

Theo [Google Flow — Models & supported features](https://support.google.com/flow/answer/16352836), snapshot ngày đọc:

| Model trong Flow | Frames: first hoặc first+last | Ingredients/References | Extend |
| --- | --- | --- | --- |
| Veo 3.1 Lite | 4/6/8 giây, cả hai tỉ lệ khung hình | Chỉ 8 giây, cả hai tỉ lệ | Có, 8 giây; có thể extend clip 8 giây của Lite/Fast/Quality bằng Lite |
| Veo 3.1 Fast | 4/6/8 giây, cả hai tỉ lệ | Chỉ 8 giây, cả hai tỉ lệ | Không |
| Veo 3.1 Quality | 4/6/8 giây, cả hai tỉ lệ | Không được hỗ trợ trong bảng hiện tại | Không |
| Gemini Omni Flash 1.1 | 4/6/8/10 giây, cả hai tỉ lệ | 4/6/8/10 giây, cả hai tỉ lệ | Coming soon |

Extend dành cho kéo dài hành động; không phải lựa chọn mặc định cho mọi lần chuyển shot. Không áp thời lượng 2–3 giây như giới hạn bắt buộc cho mọi model/mode. Có thể giữ một hành động chính, tạo clip ở thời lượng được hỗ trợ và trim phần dùng được trong bản dựng; app cần giữ đúng cả trạng thái continuity lẫn kết thúc có thể dùng.

Binding app hiện dùng model đang chọn và không tự thay model ([video_provider_project_bindings.py:24](../../backend/services/video_provider_project_bindings.py#L24), [video_veo_chrome.py:1999](../../backend/services/video_veo_chrome.py#L1999)). Nếu mode giữ nhân vật mong muốn không được model đang chọn hỗ trợ, cần hiển thị lựa chọn cho người dùng trong bước triển khai; không tự chuyển Quality sang Fast/Lite hoặc Omni. Các khả năng này có thể thay đổi theo model, khu vực và phiên bản Flow.

### 5.5. Không trộn khả năng Flow web với Veo API

[Veo API guide](https://ai.google.dev/gemini-api/docs/veo) có đầu vào image, last frame và tối đa 3 reference images trong những model/config được hỗ trợ; tài liệu nói ảnh nhân vật/người/sản phẩm hướng dẫn model giữ diện mạo. Seed được mô tả là không bảo đảm deterministic. Giới hạn và tham số này thuộc API; không suy ra adapter Chrome hiện có các đối số đó hoặc số ảnh tối đa trong mọi mode Flow web.

[Google Cloud — Video prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide#camera-movements) định nghĩa static/fixed shot là camera đứng yên. Guide cũng có ví dụ chuỗi nhiều hành động. Vì vậy "một hành động chính" là lựa chọn giảm độ phức tạp để dễ kiểm soát và review, không phải tuyên bố model không thể thực hiện hơn một hành động. Giữ camera/focus/lens trong text chưa thay thế reference hình ảnh để giữ identity.

## 6. Luồng đề xuất cụ thể cho app

```text
Hồ sơ/ảnh nhân vật đã duyệt
  → xác định đúng nhân vật nhìn thấy trong shot
  → ghép identity + hành động + camera + đầu/cuối + audio
  → rút phần phụ và kiểm tra phần bắt buộc còn đủ
  → gắn đúng Character/Ingredients/Frames theo mode được chọn
  → xác nhận prompt và ảnh/asset thực sự có trong đầu vào Flow
  → generate theo model đang chọn
  → review cả clip trước khi dùng frame/kết quả cho shot sau
```

Có hai ưu tiên triển khai nối tiếp:

1. **Bảo toàn yêu cầu trong văn bản:** dùng một builder chung, compact theo cấu trúc, chỉ đưa visible cast vào shot, bảo vệ identity/hành động/camera/trạng thái/audio và lưu prompt cuối để kiểm tra. Bước này có thể xử lý các lỗi đã tái hiện mà chưa cần tích hợp ảnh.
2. **Đưa ảnh/character asset thật vào Flow:** ánh xạ hồ sơ/ảnh đã duyệt sang asset trong đúng Flow project và đúng mode; xác nhận asset đã gắn trước khi Generate. `sent` chỉ được ghi khi có bằng chứng gửi/gắn thành công, không chỉ dựa vào cờ `provider_supports_references`. Nếu tính năng không khả dụng, thể hiện rõ còn dùng text hoặc cần chọn mode; không báo đã khóa bằng ảnh.

ID nhân vật phục vụ liên kết dữ liệu nội bộ, không tự cung cấp diện mạo cho model. Đổi profile/reference revision phải làm kết quả phụ thuộc hết hiệu lực trong đúng phạm vi; dùng cơ chế revision/dependency hiện có theo [series-reference-versioning.md](../series-reference-versioning.md), không tạo một nguồn canon song song.

## 7. Ví dụ dễ áp dụng ngay

Giả sử nhân vật đã duyệt là robot đỏ, mặt tròn bạc, tay/chân chữ nhật ngắn, huy hiệu vàng ở vai trái. Lưu ảnh gốc đúng thiết kế này; chọn lại cùng Character hoặc ingredient cho cả hai shot. Nếu dùng Veo 3.1 Fast/Lite Ingredients, chọn clip 8 giây theo bảng hỗ trợ.

Giữ nguyên phần nhận diện dưới đây ở cả hai shot:

```text
Use the attached approved reference for the same stylized 3D red robot.
Preserve its silver circular face, short rectangular limbs,
red body color, and yellow badge on its left shoulder.
Keep the approved proportions and surface materials throughout the shot.
```

Shot 1 thêm:

```text
One continuous shot. The robot slowly opens the toolbox, then holds it open.
Start: robot standing at the table, toolbox closed.
End: same robot and position, toolbox fully open.
Fixed eye-level medium shot. The camera remains entirely motionless.
```

Shot 2 thêm:

```text
Continue from the approved start frame with the toolbox already open.
The same robot gently leans forward to look inside, then holds its pose.
Keep its body colors, silver face design, proportions, and left-shoulder badge.
Fixed eye-level medium shot. The camera remains entirely motionless.
```

`attached approved reference` chỉ dùng khi đã gắn ảnh thật; `approved start frame` chỉ dùng khi đã gắn frame đúng. Từ shot 1, chọn **Save frame** ở frame sạch gần cuối và dùng cho shot 2 nếu tiếp nối cùng bối cảnh/góc. Nếu frame đó đã lỗi, quay lại ảnh chuẩn/frame được sửa, tránh nối lỗi qua các shot. Có thể thay hành động, tư thế và biểu cảm trong phạm vi story đã duyệt; không tự thay khuôn mặt, tỉ lệ, màu hoặc dấu hiệu phân biệt.

Đây là prompt minh họa cấu trúc, chưa render kiểm chứng. Khi review clip, xem liên tục và đối chiếu frame đầu/giữa/cuối với ảnh chuẩn: ngoại hình, màu/trang phục, dấu hiệu nhận diện, số lượng/vị trí nhân vật và kết quả hành động. Kiểm tra prompt đạt chỉ là kiểm tra đầu vào; kiểm tra video mới đánh giá kết quả.

## 8. Tiêu chí xác nhận khi triển khai

Các kiểm tra có giá trị vì xác nhận hành vi người dùng cần:

1. Camera/continuity chỉ tồn tại ở các cột riêng vẫn có trong prompt gửi thật.
2. Main action và identity sau prefix/timeline vẫn được giữ.
3. Prompt dài loại nội dung phụ trước; không mất một nhân vật hoặc đặc điểm bắt buộc mà vẫn báo passed.
4. Hai nhân vật khác nhau giữ đúng thuộc tính và vị trí; cast cả tập không bị đưa vào shot ngoài ý định.
5. Copy/download/tự động gửi dùng cùng nội dung cốt lõi; speech mode và source visual đã chọn vẫn đúng.
6. Gate chặn trường hợp sau compact thiếu nội dung bắt buộc.

Đây là tiêu chí đề xuất cho bước sửa code sau nghiên cứu, chưa có test sản phẩm mới được thêm. Probe nghiên cứu chỉ xác nhận hành vi xử lý chuỗi. Muốn đánh giá độ giữ nhân vật trong video cần render thử theo cùng model, mode, reference và ngân sách, rồi xem mặt, tóc, trang phục, đặc điểm phân biệt ở đầu/giữa/cuối clip.

## Nguồn và giới hạn

Nguồn chính của báo cáo là mã nguồn hiện tại: [video_clip_generation.py](../../backend/services/video_clip_generation.py), [video_phase2.py](../../backend/services/video_phase2.py), [video_series_characters.py](../../backend/services/video_series_characters.py), [video_speech.py](../../backend/services/video_speech.py), [series_references.py](../../backend/services/series_references.py), [video_veo_chrome.py](../../backend/services/video_veo_chrome.py). Số dòng và điều kiện của từng phát hiện được dẫn ở các mục trên.

Nguồn nhà cung cấp được đọc trực tiếp:

- [Google Flow — Create videos](https://support.google.com/flow/answer/16353334): Characters, Ingredients, Frames và best practices cho reference.
- [Google Flow — Manage projects, assets & collections](https://support.google.com/flow/answer/16935308): tạo/lưu character với ảnh để dùng lại.
- [Google Flow — Edit videos & build scenes](https://support.google.com/flow/answer/16935718): Save frame và tiếp tục footage bằng Extend.
- [Google Flow — Models & supported features](https://support.google.com/flow/answer/16352836): ma trận mode/thời lượng theo model.
- [Google AI for Developers — Veo](https://ai.google.dev/gemini-api/docs/veo): reference images, first/last frame và giới hạn seed của API.
- [Google Cloud — Video generation prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide): camera và cấu trúc mô tả hành động.

Không sửa code sản phẩm hoặc thay đổi đang có trong workspace. Không tạo video, không tiêu token/credit render, không kiểm tra chất lượng hình ảnh thực tế và không chạy full test suite. Nghiên cứu dùng source của working tree hiện tại, chưa phải bản release đã triển khai trên mọi server. Khả năng trên tài liệu nhà cung cấp cần được kiểm tra lại trên model/tài khoản thực tế khi triển khai; chưa đưa ra bảo đảm nhân vật giống 100% sau render.
