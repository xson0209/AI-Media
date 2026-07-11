## Bối cảnh

AI Video Assistant phase 2 đã có cả `language` và `target_language` trong bảng `video_projects`. UI cũng đã có lựa chọn `Ngôn ngữ video`, nhưng hành vi thật vẫn đang giả định video đầu ra là tiếng Anh ở nhiều nơi: copy frontend nói AI viết video tiếng Anh, request tạo voice gửi `language: "en"`, prompt AI planning yêu cầu `english_narration`, subtitle lấy text từ `english_narration`, và schema request narration của AI Video chưa nhận `vi`.

Bạn đã xác nhận voice tiếng Việt hiện nghe ổn và muốn lựa chọn ngôn ngữ có ý nghĩa đúng: chọn English thì video tiếng Anh, chọn Tiếng Việt thì video tiếng Việt. Change này phải giữ hành vi tiếng Anh cũ cho project hiện có, đồng thời làm tiếng Việt thành lựa chọn chính thức trong workflow.

## Mục tiêu / Không làm

**Mục tiêu:**
- Dùng `VideoProject.target_language` làm nguồn sự thật cho ngôn ngữ người xem nghe và đọc trong AI Video project.
- Tạo kịch bản, narration scene/shot, request voice, phụ đề và metadata export bằng tiếng Anh hoặc tiếng Việt theo `target_language`.
- Giữ giao diện Voicebox bằng tiếng Việt mặc định.
- Không phá dữ liệu cũ, không đổi tên cột database trong change này.
- Kiểm tra hỗ trợ ngôn ngữ trước hoặc trong bước tạo voice để lỗi unsupported engine/profile hiển thị rõ bằng tiếng Việt.
- Cập nhật UI copy và docs để người dùng hiểu `Ngôn ngữ video` điều khiển video cuối, không chỉ điều khiển prompt.

**Không làm:**
- Không thêm TTS engine mới.
- Không redesign toàn bộ AI Video Assistant.
- Không làm video song ngữ nhiều track trong cùng một export.
- Không rename cột `english_narration`; việc đó có thể là cleanup sau khi behavior đã ổn định.
- Không cam kết mọi engine TTS đều hỗ trợ tiếng Việt; change này chỉ route đúng ngôn ngữ và báo lỗi rõ nếu engine/profile không hỗ trợ.

## Quyết định

### `target_language` điều khiển ngôn ngữ nội dung video

Dùng `project.target_language` cho mọi nội dung hướng tới người xem: detailed script, scene dialogue, shot narration, ngôn ngữ voice generation, text phụ đề, readiness checks, package manifest và nhãn UI mô tả nội dung video.

Phương án khác đã cân nhắc: thêm cột mới `video_language`. Cách đó rõ nghĩa hơn nhưng trùng vai trò với field đã có, cần migration/backfill và tăng rủi ro. Dùng lại `target_language` ít rủi ro hơn và khớp với UI hiện tại.

### `project.language` chỉ là ngôn ngữ UI/input context

Giữ `project.language` như hint cho nguồn nhập hoặc UI, không dùng nó để quyết định ngôn ngữ voice video. Service tạo voice của AI Video sẽ ưu tiên language override trong request, sau đó dùng `project.target_language`, cuối cùng fallback `en`.

Phương án khác đã cân nhắc: set `project.language` bằng `target_language` cho project mới. Cách này lại trộn lẫn ngôn ngữ input và ngôn ngữ output, khiến trường hợp nhập tiếng Việt để làm video tiếng Anh khó hiểu hơn.

### Giữ `english_narration` như field tương thích

Không rename `english_narration` trong change này. Vẫn lưu narration text ở field đó, nhưng prompt planning, UI label, subtitle, readiness và voice generation phải hiểu đây là narration theo ngôn ngữ video đã chọn.

Phương án khác đã cân nhắc: migrate sang `narration_text`. Cách đó sạch hơn nhưng chạm ORM, Pydantic model, frontend type, package logic, test và dữ liệu project cũ. Behavior người dùng cần có thể sửa trước mà chưa cần migration lớn.

### Prompt video phải không mâu thuẫn với ngôn ngữ video

Prompt video cho project tiếng Anh phải chỉ dẫn video dùng tiếng Anh ở các phần người xem nghe/đọc. Prompt video cho project tiếng Việt phải chỉ dẫn video dùng tiếng Việt ở narration, speech, subtitle hoặc text onscreen nếu có.

Implementation vẫn có thể dùng thuật ngữ kỹ thuật tiếng Anh cho camera, motion, lighting, negative prompt nếu hữu ích cho tool tạo video, nhưng không được chỉ dẫn viewer-facing language khác với `target_language`.

Phương án khác đã cân nhắc: giữ toàn bộ prompt video bằng tiếng Anh để dễ dùng với tool ngoài. Bạn đã chốt rằng chọn tiếng Việt thì video phải là tiếng Việt, nên nếu dùng English technical wording thì vẫn phải nói rõ video nói/hiển thị tiếng Việt.

### Validate voice language ở biên AI Video

AI Video phải gửi `target_language` khi tạo voice. Backend schema phải nhận `vi` cho AI Video narration request, sau đó dùng các gate engine/profile hiện có, gồm TADA Vietnamese gate nếu liên quan. UI phải hiển thị lỗi tiếng Việt rõ ràng nếu voice profile/engine không tạo được ngôn ngữ đã chọn.

Phương án khác đã cân nhắc: để TTS backend fail sâu bên dưới. Cách đó làm người dùng gặp lỗi muộn, khó hiểu và readiness/package không giải thích được thiếu bước nào.

### TADA 3B Vietnamese local test bypass

Khi người dùng chọn video tiếng Việt và voice profile dùng engine `tada`, AI Video được phép dùng đường test rõ ràng cho TADA 3B Vietnamese nếu bypass local đã bật. Luồng này phải truyền `model_size = "3B"` và `language = "vi"` vào generation request; nếu không truyền model size, backend dễ rơi về default không phải TADA 3B và trả lỗi `VIDEO_VOICE_LANGUAGE_UNSUPPORTED` dù profile tiếng Việt đang tồn tại.

Đường bypass này chỉ để nghe thử chất lượng tiếng Việt trực tiếp trong app. Nó không được mở TADA 1B tiếng Việt, không được quảng bá là support chính thức, và không được tự fallback sang tiếng Anh nếu TADA 3B không chạy được.

## Rủi ro / Đánh đổi

- Tên field `english_narration` dễ làm developer hiểu nhầm -> Giảm rủi ro bằng comment, type helper và test ghi rõ field này là narration text tương thích theo ngôn ngữ video.
- Chất lượng tiếng Việt phụ thuộc engine/profile được chọn -> Giảm rủi ro bằng validation và lỗi rõ ràng, không silent fallback sang tiếng Anh.
- Bypass TADA 3B Vietnamese có thể tạo audio nghe được nhưng chưa đạt chất lượng ổn định -> Giữ nhãn thử nghiệm, chỉ bật khi người dùng/developer chủ động test, và yêu cầu review corpus trước khi coi là usable rộng rãi.
- Codex có thể vẫn sinh tiếng Anh nếu prompt mơ hồ -> Giảm rủi ro bằng instruction target-language rõ ràng và test/stub kiểm tra prompt tiếng Việt khi `target_language = "vi"`.
- Project tiếng Anh cũ có thể bị đánh stale quá rộng nếu update logic không cẩn thận -> Chỉ đánh stale khi `target_language` hoặc narration text thật sự đổi.
- Tool tạo video ngoài có thể hiểu prompt tiếng Anh tốt hơn prompt tiếng Việt -> Cho phép thuật ngữ kỹ thuật provider-friendly, nhưng bắt buộc ngôn ngữ người xem nghe/đọc phải đúng `target_language`.

## Kế hoạch migration

- Không cần migration phá dữ liệu vì `target_language` và các field narration đã tồn tại.
- Project cũ thiếu `target_language` tiếp tục fallback `en`, giữ hành vi phase 2 hiện tại.
- Khi người dùng đổi `target_language` trên project đã có artifact, đánh stale story/script, shot, prompt, voice, subtitle và package để tạo lại bằng ngôn ngữ mới.
- Rollback đơn giản: revert code; dữ liệu vẫn tương thích vì không xóa/rename cột.
