# Khóa camera và giảm biến dạng khi render video AI

Ngày nghiên cứu: **2026-10-02**  
Phạm vi: kiểm chứng ba mẹo kỹ thuật và các tuyên bố thương mại trong bài đăng; đối chiếu với tài liệu chính thức của Runway, Kling, Google Flow/Veo và luồng sản xuất hiện tại của Voicebox.

Mã nguồn được đọc tại working tree ngày 2026-10-02, HEAD `4bfe467`, có các thay đổi chưa commit của phiên làm việc trước. Các số dòng bên dưới phản ánh working tree này, không chỉ nội dung commit. Nghiên cứu chỉ tạo báo cáo; không thay đổi code sản phẩm, dữ liệu dự án hoặc tài liệu vận hành hiện có.

## Kết luận nhanh

Ba mẹo trong bài đăng có một phần cơ sở, nhưng tiêu đề “khóa chặt camera” và lời hứa “không bị phế” là quá mạnh.

| Mệnh đề trong bài đăng | Đánh giá | Cách diễn đạt an toàn hơn |
| --- | --- | --- |
| Tách hành động phức tạp; một shot làm một việc | **Có cơ sở như nguyên tắc giảm độ khó.** Runway khuyên bắt đầu đơn giản và cảnh báo prompt quá phức tạp có thể cho kết quả bất ngờ. Kling khuyên câu ngắn, nội dung phù hợp thời lượng và nói rõ chuyển động vật lý phức tạp vẫn khó. | Ưu tiên một hành động chính với các chuyển động phụ phục vụ cùng beat. Chọn thời lượng theo model; không có quy tắc nhà cung cấp nào bắt buộc mọi shot phải 2–3 giây. |
| Gõ `35mm lens`, `dolly-in`, khóa điểm nét vào ngực/trán để mặt không biến dạng | **Đúng một phần, nhưng không phải khóa cứng.** Camera motion và lens/look là hai nhóm điều khiển khác nhau. Kling có công cụ camera movement riêng; Google cảnh báo một số lens nâng cao chưa được hỗ trợ và độ tin cậy thay đổi theo prompt/use case. Không tìm thấy tài liệu chính thức nào bảo đảm “focus vào ngực/trán” sẽ giữ mặt hoặc danh tính. | Viết camera motion, shot/framing và lens/look thành các trường riêng; mỗi shot chỉ dùng một chuyển động camera chính. Dùng ảnh tham chiếu/Elements/subject binding để giữ danh tính. Xem `35mm` là lựa chọn phong cách cần thử nghiệm, không phải tham số camera thật được đảm bảo. |
| Cho nhân vật đeo găng, đút tay túi hoặc cầm vật cố định để tránh dị tật tay | **Chưa được chứng minh như quy tắc.** Các tài liệu chính thức được kiểm tra không khuyến nghị găng tay hay túi áo như biện pháp bảo đảm. Việc giảm bậc tự do của bàn tay là một heuristic hợp lý, nhưng găng tay có thể trở thành chi tiết mới phải giữ nhất quán. | Khi bàn tay không phải nội dung chính, dùng một hành động ngắn, dễ quan sát với vật thể có điểm bám rõ; nếu bàn tay là nội dung chính, tách thành shot detail và kiểm tra nhiều mẫu. Luôn bắt đầu bằng ảnh đầu vào sạch vì lỗi tay/mặt trong ảnh có thể bị khuếch đại. |

Các nguồn được kiểm tra không đưa ra bảo đảm rằng một công thức prompt sẽ giữ nguyên hình dạng trong mọi lần render. Kết quả còn phụ thuộc model, mode, ảnh đầu vào, thời lượng, chuyển động, tỉ lệ khung hình, seed (nếu provider hỗ trợ) và cách provider diễn giải prompt.

**Có nội dung cần cập nhật trong luồng hiện tại, nhưng không nên sao chép nguyên văn bài đăng.** Những việc có bằng chứng cụ thể nhất là bảo toàn chỉ dẫn camera/continuity khi rút gọn prompt Flow, phân biệt camera đứng yên có chủ đích với field thiếu trong Product Video, và diễn đạt đúng trạng thái ảnh tham chiếu. Quy tắc một hành động chính đã có trong planner. Thêm `35mm` hoặc găng tay vào mọi prompt chưa có cơ sở để làm mặc định.

## Bốn khái niệm bài đăng đang trộn lẫn

| Khái niệm | Ý nghĩa | Điều không thể suy ra chỉ từ câu prompt |
| --- | --- | --- |
| Tiêu cự — focal length, ví dụ `35mm` | Đặc tính ống kính liên quan góc nhìn và độ phóng đại; Nikon phân biệt ống kính tiêu cự cố định với ống zoom. Trong video AI, từ này có thể được model diễn giải như một phong cách hình ảnh. | Không xác định vị trí đặt máy, không khóa điểm nét hoặc giải phẫu gương mặt. |
| Điểm lấy nét — focus point | Vùng/chủ thể người quay muốn thấy rõ. Veo tách focus/lens effects khỏi camera positioning và composition. | Không phải cơ chế bảo toàn danh tính. `locked focal point on chest` cũng có thể bị hiểu như một điểm bố cục; chưa có tham số provider được xác minh cho công thức ngực/trán này. |
| Chuyển động máy — camera motion | `Dolly-in` đưa máy tiến gần chủ thể; `pan` xoay máy; `locked-off/static` muốn máy đứng yên. | Dolly-in không có nghĩa khóa máy đứng yên; camera mượt không chứng minh mặt/tay đúng. |
| Giữ nhân vật nhất quán — identity/subject consistency | Ảnh đầu vào, reference images, Elements và subject binding cung cấp thông tin về diện mạo chủ thể. | Gõ tên ảnh hoặc metadata trong prompt không đồng nghĩa đã gửi ảnh cho model. |

Nguồn định nghĩa: [Nikon — Understanding Focal Length](https://www.nikonusa.com/learn-and-explore/c/tips-and-techniques/understanding-focal-length), [Google Cloud — camera movements/lens effects](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide), [Veo — prompt guide/reference images](https://ai.google.dev/gemini-api/docs/veo#prompt-guide). Việc phân biệt lời mô tả với cơ chế giữ danh tính là kết luận tổng hợp; không phải tên một API chung cho các provider.

## Bằng chứng từ tài liệu chính thức

### Runway: bắt đầu đơn giản, kiểm soát motion theo từng thành phần

Runway Academy, tài liệu **Prompting Guide** cho Gen-4.5, khuyên bắt đầu với prompt đơn giản rồi thêm chi tiết từng bước. Tài liệu cảnh báo prompt cực kỳ phức tạp, nhiều đoạn, có thể làm model khó thỏa mãn đồng thời các chi tiết và tạo kết quả bất ngờ hoặc không tự nhiên. Đây là cơ sở cho việc tách hành động, nhưng không suy ra giới hạn cố định 2–3 giây.

Ở image-to-video, ảnh đầu vào cung cấp bố cục, chủ thể, ánh sáng và phong cách; prompt nên tập trung gần như hoàn toàn vào chuyển động. Runway cảnh báo các lỗi sẵn có như tay hoặc mặt bị mờ có thể bị nhấn mạnh khi chuyển ảnh thành video. Sửa lỗi ảnh đầu vào vì vậy là bước có cơ sở trực tiếp từ nhà cung cấp; chưa có benchmark trong nghiên cứu này để xếp hạng mức cải thiện so với câu “khóa tiêu cự”.

Runway tách motion thành các thành phần: hành động của chủ thể, chuyển động môi trường, chuyển động camera và phong cách/thời điểm. Tài liệu cho phép mô tả tuần tự tự nhiên hoặc bằng mốc thời gian, và khuyên dùng thời lượng cao hơn khi chuỗi hành động phức tạp hơn. Điều này ủng hộ việc chia beat, nhưng không nói mọi shot phải có một hành động duy nhất hoặc dài 2–3 giây.

Để giảm camera motion, Runway đưa các ví dụ như “locked-off camera remains perfectly still”, “camera must start and end on the exact same frame” và “minimal subject motion only”. Ngay sau đó, tài liệu nói các cách này có thể vẫn cần ổn định trong trình biên tập video. “Locked-off” trong prompt vì thế là một cách tăng xác suất, không phải khóa vật lý.

Nguồn: [Runway Academy — Prompting Guide](https://academy.runwayml.com/guides/prompting-guide) (truy cập 2026-10-02; trang mô tả Gen-4.5).

Help Center của Runway cũng có cách diễn đạt chính thức ngắn cho Gen-4: **“Locked camera. The camera remains still.”** Tài liệu camera Gen-4.5 đưa câu mạnh hơn: **“The camera is entirely motionless for the duration of the scene, with movement only occurring from the subject.”** FAQ nói static shot có thể khó, nhất là establishing/wide landscape shot; cần mô tả chuyển động bên trong cảnh và có thể phải ổn định trong trình biên tập video nếu còn drift nhẹ. Gen-4 khuyên ngôn ngữ tích cực, không dùng kiểu `No camera movement` như một mẹo tương đương.

Nguồn bổ sung: [Runway — Gen-4 Video Prompting Guide](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide), [Runway — Camera Terms, Prompts, & Examples](https://help.runwayml.com/hc/en-us/articles/47313504791059-Camera-Terms-Prompts-Examples). Agent đọc nguồn đã kiểm tra các trích dẫn này; phiên HTTP tổng hợp gặp 403 ở Help Center nhưng đọc được Runway Academy. Các hướng dẫn được gắn với phiên bản model của từng trang.

### Kling: Subject + Movement, chuyển động hợp vật lý, không có công thức ngực/trán

Tài liệu **Kling AI Image to Video Guide** nêu công thức `Subject + Movement` (và chuyển động nền khi cần). Với nhiều chủ thể, tài liệu yêu cầu mô tả các chuyển động tuần tự. Phần tips khuyên dùng từ/câu đơn giản, chuyển động phù hợp các quy luật vật lý và gần với tư thế trong ảnh; mô tả lệch mạnh khỏi ảnh có thể gây camera cut hoặc transition; những chuyển động vật lý phức tạp như bóng nảy hoặc quỹ đạo ném từ trên cao vẫn khó.

Tài liệu **Kling AI Text to Video Prompt Guide** tách `Subject + Subject Movement + Scene`, rồi mới thêm tùy chọn `Camera Language + Lighting + Atmosphere`. Tài liệu nói chuyển động chủ thể nên thẳng và phù hợp video 5 giây; phần tips khuyên nội dung hình ảnh đơn giản, có thể hoàn tất trong 5–10 giây. Tài liệu định nghĩa camera language (góc, lens, bokeh, depth of field) và ghi rõ phải phân biệt nó với camera motion control. Vì vậy `35mm lens` không đồng nghĩa với lệnh giữ chủ thể hay giữ nét.

Nguồn:

- [Kling AI — Image to Video Guide](https://kling.ai/quickstart/image-to-video-guide) (đăng 2025-11-24; truy cập 2026-10-02).
- [Kling AI — Text to Video Prompt Guide](https://kling.ai/quickstart/text-to-video-prompt-guide) (đăng 2025-11-24; truy cập 2026-10-02).

### Kling: camera movement là bộ điều khiển riêng

Tài liệu **Camera Movement** của Kling mô tả sáu điều khiển cơ bản (horizontal, vertical, zoom, pan, tilt, roll) và bốn master shot. Tài liệu nói người dùng có thể đưa lệnh camera và điều chỉnh độ dịch chuyển bằng tham số displacement. Đây là bằng chứng về một công cụ điều khiển riêng, không phải tác dụng bảo đảm của tên tiêu cự trong prompt. Trang hướng dẫn công bố năm 2025 không xác nhận mọi model/mode năm 2026 đều có các nút này; phải kiểm tra tính năng của model được chọn trước khi áp dụng.

Nguồn: [Kling AI — Camera Movement](https://kling.ai/quickstart/ai-camera-control-guide) (đăng 2025-11-24; truy cập 2026-10-02).

### Kling: giữ danh tính bằng reference/Element binding

Tài liệu **Elements** cho phép tải 1–4 ảnh của người, nhân vật, động vật, vật thể hoặc cảnh rồi mô tả hành động/tương tác. Kling nói mục tiêu của Elements là giữ các element nhất quán trong video, hữu ích cho diện mạo nhân vật qua nhiều shot.

Tài liệu **Kling VIDEO 3.0 Model Guide** mô tả `Bind Subject to Enhance Consistency`: khóa element để chủ thể vẫn rõ và ổn định ngay cả khi camera zoom, pan hoặc tilt; tài liệu cũng nói element reference giữ đặc điểm của chủ thể qua camera movement và scene development. Đây là cơ chế có chủ đích cho consistency; tài liệu không thay thế cơ chế này bằng “focus vào ngực/trán”.

Kling VIDEO 3.0 cũng cho phép video liên tục 3–15 giây và Custom Multi-Shot để cấu hình số shot cùng thời lượng. Điều này bác bỏ việc coi 2–3 giây là giới hạn phổ quát; đó chỉ có thể là lựa chọn thận trọng cho một shot rủi ro cao.

Nguồn:

- [Kling AI — Elements / character consistency](https://kling.ai/quickstart/ai-video-character-consistency) (đăng 2025-11-24; truy cập 2026-10-02).
- [Kling AI — VIDEO 3.0 Model Guide](https://kling.ai/quickstart/klingai-video-3-model-user-guide) (đăng 2026-02-06; truy cập 2026-10-02).

### Google Veo: lens và focus là mô tả quang học, độ tin cậy thay đổi

Google **Video generation prompt guide** tách các phần prompt thành chủ thể, hành động, góc máy, camera movement, lens/optical effects và style. Google định nghĩa static shot là camera đứng yên; pan/tilt là xoay từ vị trí cố định. Google cũng cảnh báo một số camera angle/lens nâng cao chưa được hỗ trợ chính thức và kết quả/độ tin cậy thay đổi theo prompt và use case.

Trang này liệt kê wide-angle, telephoto, shallow/deep depth of field và rack focus như các mô tả quang học. Nó không hứa rằng giá trị tiêu cự cụ thể hoặc điểm khóa trên ngực/trán sẽ giữ nhận dạng gương mặt. Với **negative prompt**, Google khuyên liệt kê những yếu tố không muốn xuất hiện, ví dụ `wall, frame`, thay vì câu lệnh `no walls` hoặc `don't show walls`. Điều này khác với hướng dẫn Runway Gen-4 về dùng ngôn ngữ tích cực trong prompt chính; không nên dùng một chính sách negative prompt chung cho mọi provider.

Google cũng phân biệt **zoom** với **dolly**: zoom thay đổi tiêu cự nhưng vị trí camera không chuyển động, còn dolly thay đổi vị trí camera. Vì vậy nếu “khóa” có nghĩa khung hình không đổi thì cần mô tả cả fixed framing, angle, lens/focus; `static camera` đơn lẻ không diễn đạt hết mục tiêu đó. Đây là checklist tổng hợp từ các khái niệm nhà cung cấp, không phải lời hứa mỗi thành phần sẽ được model tuân thủ chính xác.

Nguồn: [Google Cloud — Video generation prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide) (truy cập 2026-10-02).

### Flow/Veo: thời lượng và ảnh đầu vào phụ thuộc model/mode

Flow web và Gemini API là hai đường sử dụng khác nhau. Bảng tính năng Flow tại thời điểm đọc cho biết Veo 3.1 Lite/Fast hỗ trợ text/frames 4, 6 hoặc 8 giây; Ingredients/References chỉ hỗ trợ clip 8 giây. Veo 3.1 Quality có Frames to Video nhưng không hỗ trợ Ingredients/References trong bảng này. Flow cũng có model Gemini Omni với thời lượng và tính năng khác. Vì vậy không thể áp dụng một độ dài hoặc chế độ reference cho mọi model trong Flow.

Guide Gemini API riêng cho Veo mô tả `image`, `lastFrame` và `referenceImages` như các đầu vào thật; tối đa ba reference images. Bảng tham số cho Veo 3.1 có thời lượng 4/6/8 giây với điều kiện riêng, trong đó reference images cần 8 giây. Các giới hạn của API này không tự chứng minh UI Flow hoặc adapter Voicebox đang truyền cùng loại đầu vào.

Nguồn: [Google Flow — models & supported features](https://support.google.com/flow/answer/16352836), [Veo API — generation parameters](https://ai.google.dev/gemini-api/docs/veo#veo-model-parameters). Trang `/gemini-api/docs/video` hiện là tổng quan; phần Veo và prompting cụ thể nằm ở `/gemini-api/docs/veo`.

## Công thức thực dụng đã hiệu chỉnh

Dùng công thức dưới đây như một checklist prompt, không như lời bảo đảm:

```text
[Shot + thời lượng]
[Reference/subject anchor]
[Một hành động chính, có điểm bắt đầu và kết thúc]
[Một chuyển động camera chính hoặc locked-off]
[Framing/composition]
[Lens/look tùy chọn]
[Môi trường/ánh sáng]
[Điều kiện kết thúc và continuity]
```

### 1. Chốt input trước khi chốt prompt

- Dùng ảnh có mặt, tay, trang phục và đạo cụ rõ; sửa lỗi tay/mặt trước khi đưa vào image-to-video.
- Nếu model có reference/Elements/subject binding, dùng nó cho nhân vật lặp lại qua shot hoặc khi camera zoom/pan/tilt.
- Ghi rõ chủ thể bằng một tên mô tả ổn định (`the woman in the red jacket`, `the same subject from the reference image`). Đây là anchor ngôn ngữ, không phải identity lock.

### 2. Một shot = một beat có thể chấm điểm

- Đặt một hành động chính: `raises the cup once`, `turns her head slowly`, `takes one step and stops`.
- Nếu cần chuỗi hành động, dùng mốc thời gian hoặc tách thành shot; đừng nhồi chạy + nhảy rào + rút súng + bắn vào một prompt ngắn.
- Chọn thời lượng theo provider. 2–3 giây có thể là độ dài shot sau khi dựng hoặc một preset thử nghiệm nếu model hỗ trợ; đây là lựa chọn workflow cần đo, không phải quy tắc nhà cung cấp. Nếu provider chỉ sinh clip dài hơn, có thể chọn phần đạt để trim khi dựng. Hành động phải có đủ thời gian hoàn thành.

### 3. Tách camera motion khỏi lens/look

- **Camera motion:** `locked-off`, `slow pan left`, `slow dolly in`, `gentle tilt down`.
- **Shot/framing:** `medium close-up`, `waist-up`, `full shot`, `subject centered`.
- **Lens/look:** `normal perspective`, `35mm-style cinematic look`, `shallow depth of field`.
- Chỉ dùng một camera move chính trong shot. `dynamic dolly-in` và `locked-off camera` là hai mệnh đề mâu thuẫn; nếu cần cả hai, chuyển sang “slow dolly-in that settles into a locked hold” và kiểm tra riêng.
- `35mm` nên được coi là look/ý định thẩm mỹ cho đến khi provider chứng minh tham số đó được điều khiển ổn định. Không gắn lời hứa “khóa nét vào ngực/trán” vào prompt như một guarantee.

### 4. Xử lý bàn tay theo rủi ro

- Khi tay không phải trọng tâm: chọn hành động ngắn với vật thể có hình dạng/điểm bám rõ (`grips the mug handle and holds`), hoặc đặt tay ở tư thế ít thay đổi. Găng tay, tay trong túi và cầm vật cố định là lựa chọn mỹ thuật/heuristic, không phải phương pháp đã được nhà cung cấp bảo đảm.
- Khi tay là nội dung chính: tách một shot detail có tư thế xuất phát rõ, hạn chế số chuyển động ngón và tương tác xảy ra đồng thời, giữ giải phẫu đầy đủ. Close-up làm lỗi dễ lộ hơn; đây là cách cô lập và kiểm tra hành động, chưa phải cách được đo là luôn giảm lỗi. Tạo nhiều mẫu và kiểm tra cả chuyển động giữa các frame. Một shot có tay không được coi là đạt chỉ vì camera trông mượt.
- Mô tả tư thế và tiếp xúc mong muốn trong prompt chính. Chỉ dùng negative prompt theo định dạng provider hỗ trợ; ví dụ Google Cloud khuyên danh sách yếu tố cần tránh thay vì `no`/`don't`, còn Runway Gen-4 khuyên câu tích cực.

## Mẫu prompt có thể thử

Các ví dụ dưới đây là đề xuất chưa render trong nghiên cứu này. Thời lượng phải được chọn ở thiết lập/API của model; chữ `5-second` hoặc `4-second` trong prompt không tự thay đổi cấu hình render. Với segment mặc định 8 giây của Voicebox, có thể cho hành động kết thúc sớm rồi giữ tư thế ổn định, hoặc chọn phần đạt để cắt khi dựng. Chỉ nói `from the reference image` khi ảnh đã thực sự được đưa vào đúng chế độ của provider.

### A. Portrait ổn định, camera đứng yên

```text
Continuous 5-second shot. Medium close-up of the same woman from the reference image,
wearing the same red jacket. Locked-off camera remains perfectly still. Minimal subject
motion only: she slowly turns her head slightly toward camera and gives one small smile.
Face remains visible and centered. Soft window light. Continuous seamless shot throughout.
```

Đây là prompt giảm motion theo hướng Runway gợi ý. “Face remains visible and centered” chỉ là chỉ dẫn ưu tiên; nếu cần consistency mạnh hơn, bật reference/Elements.

Với Runway Gen-4 nên ưu tiên phiên bản ngôn ngữ tích cực:

```text
Locked camera. The camera remains still. Continuous medium close-up.
The woman slowly turns her head slightly toward camera and gives one small smile.
Fixed framing and soft stable window light throughout the shot.
```

### B. Dolly-in có kiểm soát

```text
Single continuous 5-second shot. Medium shot of the subject from the reference image.
The camera performs one slow, smooth dolly in while keeping the subject centered.
The subject lifts a ceramic cup once and holds it. Natural perspective and stable lighting
throughout the continuous shot. The motion finishes on a steady close framing.
```

Nếu muốn thử `35mm-style look`, thêm nó ở dòng lens/look và chạy A/B với bản không có dòng đó. Không trộn `locked-off` với `dolly-in` trong cùng một bản thử.

### C. Tay và đạo cụ là beat riêng

```text
Continuous 4-second close-up. Static camera. The subject's right hand grips the fixed
handle of a ceramic mug, lifts it a few centimeters once, then holds still. One deliberate
hand action, natural contact with the handle, stable sleeve and skin details, soft even light.
```

Nếu mẫu tay không ổn định, đổi góc/ảnh tham chiếu hoặc tách hành động; đừng mặc định rằng găng tay sẽ chữa được mọi lỗi.

## Quy trình A/B trước khi đưa prompt vào sản xuất

1. Giữ cố định model, ảnh đầu vào, tỉ lệ, độ phân giải, thời lượng và các tham số mà provider cho phép cố định. Riêng [Veo API docs](https://ai.google.dev/gemini-api/docs/veo) nói seed không bảo đảm deterministic; lưu seed hỗ trợ đối chiếu, không hứa tái tạo giống hệt.
2. Có thể bắt đầu pilot với ba mẫu mỗi nhánh trong ngân sách đã định. Đây là đề xuất lấy mẫu ban đầu, không đủ để kết luận thống kê về tỉ lệ lỗi. Nếu provider có seed, ghi lại seed; nếu không có, ghi rõ mỗi mẫu là một lần lấy mẫu độc lập.
3. So sánh từng cặp:
   - hành động đơn (`turns head`) với chuỗi hành động (`runs, jumps, draws`);
   - camera đứng yên với một dolly-in;
   - không nêu lens với `35mm-style look`;
   - tay trống với tay cầm đạo cụ cố định, rồi mới thử găng/túi nếu hợp mỹ thuật.
4. Chấm riêng bốn lỗi: camera jitter/cut ngoài ý muốn, drift mặt/trang phục, lỗi tay/đạo cụ, và hành động không hoàn tất trong thời lượng. Đừng gộp thành một điểm “đẹp/xấu” vì camera mượt vẫn có thể đi kèm tay hỏng.
5. Ghi số clip đạt/tổng số clip, số giây dùng được và chi phí mỗi clip đạt; giữ tiêu chí đánh giá giống nhau giữa các nhánh. Mở rộng số mẫu nếu muốn kết luận ổn định hơn. Khi đổi provider hoặc model, chạy lại A/B; không coi kết quả của Kling là bảo đảm cho Flow/Veo hoặc Runway.

## Liên hệ với pipeline Voicebox hiện tại

### Những phần đã có và cần giữ

Voicebox đã có các trường riêng cho `duration_seconds`, `camera_angle`, `framing`, `composition`, `camera_motion`, `subject_motion`, `environment_motion`, `start_frame`, `end_frame`, `lighting`, `mood` và `negative_prompt` trong [video_phase2.py](../../backend/services/video_phase2.py#L365) (`ShotPlan`: dòng 365; `VideoPromptPlan`: dòng 409). Schema chưa có field riêng cho `lens`, `focal_length` hoặc `focus_anchor`.

Planner đã yêu cầu mỗi shot/prompt có **một hành động chính**, tách scene có nhiều hành động thành nhiều shot, và giữ micro-scenes phục vụ cùng hành động ([shot rules, dòng 3520](../../backend/services/video_phase2.py#L3520); [prompt rules, dòng 4102](../../backend/services/video_phase2.py#L4102)). Vì vậy mẹo số 1 không phải một tính năng còn thiếu cần viết lại.

Segment mặc định là **8 giây với 4 micro-scenes**, và cấu hình project có thể override ([video_phase2.py, dòng 58 và 93](../../backend/services/video_phase2.py#L58)). Một micro-scene/timeline beat khoảng hai giây không đồng nghĩa provider tạo ra một clip độc lập hai giây. Cần phân biệt thời lượng clip sinh ra với thời lượng phần dùng trong bản dựng; builder đã có hai dòng `Video generation clip length` và `Usable timeline duration` ([dòng 3945](../../backend/services/video_phase2.py#L3945)).

Luồng clip được đối chiếu gọi [video_veo_chrome.py](../../backend/services/video_veo_chrome.py), điều khiển Google Flow qua Chrome CDP. Nó dùng model đang được chọn ở Flow và không tự đổi model ([video_provider_project_bindings.py, dòng 24](../../backend/services/video_provider_project_bindings.py#L24)). Các khả năng Runway/Kling trong báo cáo là đối chiếu kỹ thuật, chưa phải adapter sản phẩm đang hoạt động trong luồng này.

### P0 — bảo toàn chỉ dẫn camera/continuity trong prompt thực gửi

[video_clip_generation.py, dòng 91](../../backend/services/video_clip_generation.py#L91) giới hạn prompt ở 5.200 ký tự. Danh sách `FLOW_PROVIDER_PROMPT_SECTION_HEADINGS` nhận diện camera, subject, environment, start/end frame và continuity, **nhưng danh sách nhận diện không phải danh sách giữ lại**. `FLOW_PROVIDER_PROMPT_KEEP_SECTIONS` ở dòng 123 chỉ giữ retention, transition, sound và negative. Hàm [compact_prompt_for_veo_provider, dòng 235](../../backend/services/video_clip_generation.py#L235) lấy phần đầu trước `Video language:`/`Micro-scene timeline:`, rồi ghép các mục được giữ.

Đã chạy một kiểm tra cô lập, chỉ đọc source và thực thi bốn hàm xử lý chuỗi của compactor bằng AST; không import service/database và không gọi provider. Prompt mẫu 294 ký tự có camera lock và continuity nằm sau `Video language:` cho kết quả 157 ký tự:

```text
camera_clause_kept: false
continuity_clause_kept: false

Single continuous shot. A woman smiles gently.

Video language: English

Retention notes: A clear emotional reaction.

Negative prompt:
flicker, camera shake
```

Đây là bằng chứng về một trường hợp mất ràng buộc dù chưa chạm giới hạn 5.200 ký tự. Nếu câu camera/continuity đã có trong phần đầu, nó có thể vẫn còn; nghiên cứu không kết luận mọi prompt sản xuất đều mất camera. Luồng thực gửi kết quả này sang Flow tại [dòng 963–983](../../backend/services/video_clip_generation.py#L963).

**Đề xuất:** xem camera, framing, subject/environment motion, start/end state và continuity là nội dung cần bảo toàn khi compact; ghép gọn và có thứ tự ưu tiên, tránh rơi mất chỉ dẫn quan trọng khi cắt. Kiểm tra prompt sau compact, thay vì chỉ kiểm tra JSON planner ban đầu. Đây là điểm cần xử lý trước khi thêm field lens/focus mới.

### P1 — giữ camera đứng yên có chủ đích trong Product Video

**Một gap cần ưu tiên nếu muốn thêm camera lock vào Product Video:** [product_video.py](../../backend/services/product_video.py#L331) yêu cầu ít nhất hai trong ba motion field có nội dung chuyển động, nhưng lại coi `static`, `static camera`, `locked off`, `locked`, `fixed` là “blank”. [validate_motion_budget](../../backend/services/product_video.py#L402) bổ sung environment motion trước; nếu vẫn thiếu, nó thay camera motion bằng `DEFAULT_CAMERA_MOTION` là một slow push-in. Do đó một camera lock cố ý có thể bị fallback ghi đè khi hai trường còn lại không đạt budget. [Test hiện tại](../../backend/tests/test_product_video.py#L219) kiểm tra chính hành vi coi `static` là blank. Muốn hỗ trợ lock, cần phân biệt “không có camera motion do khóa máy có chủ đích” với “field bị thiếu”, đồng thời giữ subject/environment motion mà câu chuyện cần. Không nên buộc camera chuyển động chỉ để đủ hai field.

### P1 — diễn đạt đúng trạng thái ảnh tham chiếu và keyframe

`start_frame`/`end_frame` trong schema là **chuỗi mô tả**; builder nối chúng thành văn bản ([video_phase2.py, dòng 427 và 3931](../../backend/services/video_phase2.py#L427)). Chúng không phải bằng chứng đã tải ảnh keyframe lên provider.

Trong nhánh series, planner gọi `build_reference_prompt_package(..., provider_supports_references=False)` và chỉ đưa ID/metadata vào phần chỉ dẫn ([dòng 4057–4076](../../backend/services/video_phase2.py#L4057)). [series_references.py, dòng 551](../../backend/services/series_references.py#L551) ghi `sent=[]`, `skipped` với lý do chưa hỗ trợ gửi ảnh trực tiếp. Call hiện tại đến `submit_prompt_and_download` nhận prompt và thời lượng nhưng không nhận tham số ảnh/reference ([video_clip_generation.py, dòng 981](../../backend/services/video_clip_generation.py#L981)).

Vì vậy cần phân biệt **ảnh đã lưu trong series**, **metadata dùng để viết prompt**, và **ảnh thật đã gửi cho model**. Nếu người dùng đã thêm ảnh thủ công vào dự án Flow, đó là trạng thái của Flow cần kiểm tra riêng; chưa được các metadata này chứng minh. Muốn cải thiện giữ nhân vật, nghiên cứu tiếp luồng đưa ảnh vào mode Frames/Ingredients có hỗ trợ, theo model được chọn, và lưu trạng thái gửi thành công; không chỉ thêm câu `same character`.

### P2 — profile chuyển động đơn giản và review clip

[SEGMENT_CAMERA_VARIATION_PROFILES, dòng 280](../../backend/services/video_phase2.py#L280) hiện có profile ghép push-in + lateral drift, tilt + rack focus, handheld drift + push-in, hoặc fast tracking. Đây có thể là ý đồ thẩm mỹ hợp lệ, nhưng chưa phù hợp làm mặc định cho mọi shot ưu tiên ổn định. Nên có lựa chọn camera đứng yên/một chuyển động chậm, giữ trạng thái người dùng đã chọn, và A/B với profile đang dùng.

Gate prompt hiện kiểm tra sự phù hợp nội dung bằng văn bản và trạng thái quality của prompt ([video_quality.py, dòng 758](../../backend/services/video_quality.py#L758)). Việc gate này đạt không chứng minh clip không biến dạng: cần review output cho mặt/trang phục, tay/đạo cụ, camera drift/cut và hành động hoàn tất. Không coi chuỗi negative `bad hands`/`distorted face` là kiểm định hình ảnh; planner hiện có chúng ở [dòng 4114](../../backend/services/video_phase2.py#L4114).

Các cải tiến đáng cân nhắc sau đó là:

- cảnh báo khi một shot có quá nhiều động từ chính hoặc nhiều camera move mâu thuẫn;
- yêu cầu ghi rõ một hành động chính và mốc kết thúc;
- đưa camera motion và continuity lên trước phần giải thích dài;
- ghi rõ shot phụ thuộc vào tay/đạo cụ để ưu tiên review output và thử nhiều mẫu trong ngân sách;
- lưu model/provider cùng prompt để A/B không trộn kết quả giữa các engine;
- coi `35mm`, `rack focus`, `locked-off` là ý định cần kiểm tra, không phải assertion rằng provider đã thực thi chính xác.

Đây là khuyến nghị cập nhật workflow, chưa phải thay đổi code.

## Các tuyên bố tuyển dụng và chi phí

| Tuyên bố | Kết quả kiểm chứng |
| --- | --- |
| “Tôi cấp bot/tool, người học không tốn token hay credit” | Có thể là người tổ chức thanh toán hoặc dùng quota/gói có điều kiện. Điều đó không chứng minh tool tự làm mọi provider miễn phí. Google Flow ghi chi phí theo generation/model; có ngoại lệ Veo 3.1 Lite Lower Priority 0 credits cho Ultra subscriber/family plan manager tại thời điểm đọc. Ngoại lệ này gắn với tài khoản/gói và không chứng minh hệ thống của người đăng có nó. |
| “Có tiền ngay tuần đầu” | Bài đăng không cung cấp hợp đồng, cơ chế tính lương, điều kiện nghiệm thu hoặc chứng từ thanh toán để kiểm tra. Chưa xác minh được; không dùng làm dữ liệu dự báo thu nhập. |
| “Đang ngập hợp đồng quảng cáo/series cho khách ngoại” | Không có link portfolio, hợp đồng hoặc xác nhận khách hàng trong chất liệu được gửi. Chưa xác minh được. |
| Gắn thành công tài chính với ba mẹo prompt | Không có bằng chứng về quan hệ nhân quả. Ba mẹo kỹ thuật không chứng minh năng lực sản xuất, chất lượng giao hàng hay lợi nhuận. |

Nguồn cho cơ chế chi phí: [Google Flow — Manage your credits](https://support.google.com/flow/answer/16526234). Trang này nói credit tính theo **generation**, không phải request; một request có thể sinh nhiều output và các giới hạn có thể thay đổi. “Không trả tiền trực tiếp” cũng khác với “không trừ credit”. Nghiên cứu không có dữ liệu riêng của người đăng để kết luận các lời tuyển dụng đúng hoặc sai; đây là những claim chưa được xác minh.

## Nội dung nên dùng để cập nhật tài liệu vận hành

> Để giảm lỗi khi tạo video AI, ưu tiên ảnh đầu vào rõ và hợp tư thế, một hành động chính với thời lượng đủ, cùng một chuyển động camera dễ kiểm tra. Camera đứng yên và giữ nhân vật nhất quán là hai mục tiêu khác nhau; dùng ảnh/keyframe/reference thật trong mode được hỗ trợ, và kiểm tra chúng đã được gửi. Lens hoặc focus trong prompt mô tả ý đồ hình ảnh, không bảo đảm mặt/tay giữ nguyên. Găng tay, tay trong túi hoặc tư thế cầm vật chỉ là lựa chọn bố trí cảnh nếu hợp nội dung và continuity. Trước khi render, xem prompt thực gửi sau bước rút gọn; sau render, review cả clip và sửa hoặc tạo lại phần không đạt.

Đoạn này là đề xuất biên tập dựa trên các nguồn trên. Nó có thể bổ sung vào [docs/ai-video-prompt-structure.html](../ai-video-prompt-structure.html) và liên kết với [nghiên cứu cập nhật luồng nội dung](luong-noi-dung-cap-nhat-2026-10-02.md); hai tài liệu này chưa được sửa trong task nghiên cứu.

## Giới hạn nghiên cứu

- Tài liệu nhà cung cấp mô tả khả năng và prompt examples, không phải benchmark độc lập chứng minh tỉ lệ biến dạng trên mọi model.
- Chưa render các prompt mẫu, chưa chi token/credit cho Runway/Kling/Flow và chưa chạy một benchmark video. Kiểm tra compactor là kiểm tra chuỗi cô lập, không phải kiểm định chất lượng video hoặc end-to-end runtime.
- Không tìm thấy tài liệu chính thức nào xác nhận găng tay, tay trong túi, vật cố định, hoặc focus vào ngực/trán là quy tắc bảo đảm chống lỗi.
- Model, tên tính năng, thời lượng và mức hỗ trợ có thể thay đổi; cần kiểm tra lại tài liệu provider trước mỗi đợt sản xuất lớn.

## Nguồn

1. [Runway Academy — Prompting Guide](https://academy.runwayml.com/guides/prompting-guide)
2. [Kling AI — Image to Video Guide](https://kling.ai/quickstart/image-to-video-guide)
3. [Kling AI — Text to Video Prompt Guide](https://kling.ai/quickstart/text-to-video-prompt-guide)
4. [Kling AI — Camera Movement](https://kling.ai/quickstart/ai-camera-control-guide)
5. [Kling AI — Elements / character consistency](https://kling.ai/quickstart/ai-video-character-consistency)
6. [Kling AI — VIDEO 3.0 Model Guide](https://kling.ai/quickstart/klingai-video-3-model-user-guide)
7. [Google Cloud — Video generation prompt guide](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide)
8. [Runway — Gen-4 Video Prompting Guide](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide)
9. [Runway — Camera Terms, Prompts, & Examples](https://help.runwayml.com/hc/en-us/articles/47313504791059-Camera-Terms-Prompts-Examples)
10. [Google AI for Developers — Veo API guide](https://ai.google.dev/gemini-api/docs/veo)
11. [Google Flow — models & supported features](https://support.google.com/flow/answer/16352836)
12. [Google Flow — Manage your credits](https://support.google.com/flow/answer/16526234)
13. [Nikon — Understanding Focal Length](https://www.nikonusa.com/learn-and-explore/c/tips-and-techniques/understanding-focal-length)

Nguồn nội bộ: [video_phase2.py](../../backend/services/video_phase2.py), [video_clip_generation.py](../../backend/services/video_clip_generation.py), [video_veo_chrome.py](../../backend/services/video_veo_chrome.py), [video_provider_project_bindings.py](../../backend/services/video_provider_project_bindings.py), [series_references.py](../../backend/services/series_references.py), [product_video.py](../../backend/services/product_video.py), [video_quality.py](../../backend/services/video_quality.py). Các đoạn bằng chứng và số dòng được chỉ rõ ở mục pipeline.
