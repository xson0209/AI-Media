## 1. Hợp đồng ngôn ngữ ở backend

- [ ] 1.1 Rà toàn bộ chỗ AI Video dùng `language`, `target_language`, `english_narration`, `vietnamese_description`, trạng thái voice, trạng thái subtitle, package readiness và export manifest.
- [ ] 1.2 Thêm helper hoặc constant backend cho ngôn ngữ video AI Video được hỗ trợ: `en` và `vi`.
- [ ] 1.3 Đảm bảo create/update video project chỉ nhận `target_language` hợp lệ cho AI Video, đồng thời giữ default `en` cho project cũ.
- [ ] 1.4 Cập nhật logic stale khi đổi `target_language` để đánh dấu story/script, unlocked shots, prompt, voice, subtitle và package là cần tạo lại.
- [ ] 1.5 Thêm comment hoặc alias type nếu cần để ghi rõ `english_narration` là field tương thích, chứa narration text theo ngôn ngữ video đã chọn.

## 2. Hành vi ngôn ngữ trong AI planning

- [ ] 2.1 Cập nhật project context builder của phase 2 để tách rõ ngôn ngữ UI/input và ngôn ngữ video.
- [ ] 2.2 Cập nhật prompt story development để detailed script, scene dialogue và narration được tạo theo `target_language`.
- [ ] 2.3 Cập nhật prompt shot breakdown để shot narration được tạo theo `target_language` và project tiếng Việt không yêu cầu English narration.
- [ ] 2.4 Cập nhật prompt video generation để speech, narration, subtitle và on-screen language hướng tới người xem khớp `target_language`.
- [ ] 2.5 Giữ các giải thích UI và mô tả hỗ trợ người dùng bằng tiếng Việt dù video language là `en` hay `vi`.
- [ ] 2.6 Đảm bảo normalize output từ Codex vẫn nhận key cũ `english_narration`, nhưng hiểu value là narration text theo ngôn ngữ video đã chọn.

## 3. Luồng voice và phụ đề

- [ ] 3.1 Cho phép `vi` trong schema AI Video narration request.
- [ ] 3.2 Cập nhật resolve language cho AI Video voice: ưu tiên language trong request, sau đó dùng `project.target_language`, cuối cùng fallback `en`.
- [ ] 3.3 Cập nhật tạo voice cho scene để gửi scene dialogue đúng ngôn ngữ video vào TTS pipeline.
- [ ] 3.4 Cập nhật tạo voice cho shot để gửi shot narration đúng ngôn ngữ video vào TTS pipeline và sửa lỗi empty narration cho language-neutral.
- [ ] 3.5 Giữ các gate engine/profile hiện có, gồm TADA Vietnamese experimental gate nếu liên quan, và trả lỗi tiếng Việt rõ ràng khi language không hỗ trợ.
- [ ] 3.6 Xác nhận subtitle generation dùng narration text đúng ngôn ngữ video và đánh stale subtitle khi narration hoặc `target_language` đổi.
- [x] 3.7 Khi AI Video tạo voice tiếng Việt với engine/profile `tada` và local TADA Vietnamese test bypass bật, truyền `model_size = "3B"` và `language = "vi"` để người dùng test trực tiếp thay vì rơi vào lỗi unsupported generic.
- [x] 3.8 Giữ TADA 1B tiếng Việt bị chặn và đảm bảo lỗi nói rõ cần TADA 3B/bypass hoặc engine khác, không fallback sang tiếng Anh.

## 4. Workflow và copy frontend

- [ ] 4.1 Cập nhật copy setup AI Video để `Ngôn ngữ video` nói rõ đây là ngôn ngữ người xem nghe và đọc trong video cuối.
- [ ] 4.2 Giữ UI app bằng tiếng Việt, nhưng label cho script/narration/voice/subtitle phải mô tả đúng output tiếng Anh hoặc tiếng Việt.
- [ ] 4.3 Gửi `target_language` khi tạo phase 2 project và bỏ các success notice hardcode video tiếng Anh.
- [ ] 4.4 Gửi `target_language` của selected project khi tạo voice cho scene hoặc shot, không hardcode `en`.
- [ ] 4.5 Cập nhật empty state và helper message hiện đang nói narration hoặc scene chỉ là tiếng Anh.
- [ ] 4.6 Thêm hoặc giữ validation UI khi voice/profile đã chọn không tạo được ngôn ngữ video hiện tại.

## 5. Package và tài liệu

- [ ] 5.1 Cập nhật package manifest để ghi video language là tiếng Anh hoặc tiếng Việt.
- [ ] 5.2 Cập nhật guide/script/shot-list trong package để không nói video tiếng Anh khi project là tiếng Việt.
- [ ] 5.3 Đảm bảo artifact voice và subtitle trong export tương ứng với ngôn ngữ video đã chọn.
- [ ] 5.4 Cập nhật tài liệu AI Video để giải thích ngôn ngữ video điều khiển kịch bản, voice, phụ đề và nội dung prompt hướng tới video.
- [ ] 5.5 Cập nhật ví dụ tài liệu gồm một project video tiếng Anh và một project video tiếng Việt.

## 6. Test và xác minh

- [ ] 6.1 Thêm backend test cho tạo AI Video project tiếng Anh và tiếng Việt, kiểm tra `target_language` lưu đúng.
- [ ] 6.2 Thêm backend test chứng minh prompt story/shot/video yêu cầu output tiếng Việt khi `target_language = "vi"` và tiếng Anh khi `target_language = "en"`.
- [ ] 6.3 Thêm backend test cho resolve language của AI Video voice, gồm explicit override, `project.target_language` và schema nhận `vi`.
- [ ] 6.4 Thêm backend test cho subtitle cue text và stale behavior sau khi đổi `target_language` hoặc narration.
- [ ] 6.5 Thêm backend test cho metadata video language trong package manifest/guide.
- [ ] 6.6 Chạy focused backend tests cho AI Video và các test TADA Vietnamese gate bị ảnh hưởng.
- [ ] 6.7 Chạy frontend type/build checks cho thay đổi UI AI Video.
- [ ] 6.8 Manual QA UI AI Video với cả lựa chọn English và Tiếng Việt: tạo project, AI phát triển kịch bản, tạo shot, tạo voice, tạo phụ đề và kiểm tra export readiness.
- [ ] 6.9 Manual QA TADA Vietnamese bypass với profile `Thoai 1 Vietnamese`: bật bypass, tạo voice cho một shot tiếng Việt bằng TADA 3B, nghe audio, rồi ghi nhận kết quả để quyết định accepted/rejected.
