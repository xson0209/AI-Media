## 1. Cấu hình mức âm thanh ở backend

- [x] 1.1 Thêm field mức âm thanh ba giá trị vào `VideoRenderSettings` trong `backend/models.py`, cho phép vắng giá trị, giữ nguyên field boolean tiếng gốc cũ
- [x] 1.2 Bổ sung hằng số mức chỉ dùng tiếng gốc vào nhóm hằng mức âm thanh trong `backend/services/video_rendering.py` và sửa comment ở đầu nhóm cho khớp việc cả ba mức đã được dùng
- [x] 1.3 Sửa hàm phân giải mức âm thanh: dùng field mới khi có giá trị, suy từ field boolean cũ khi field mới vắng ← (verify: cấu hình cũ với field boolean ở trạng thái giữ tiếng gốc vẫn ra mức kết hợp, không ra mức mặc định)
- [x] 1.4 Thêm tham số mức âm thanh vào query param của endpoint readiness trong `backend/routes/ai_video.py`

## 2. Điều kiện dựng và nguồn thời lượng

- [x] 2.1 Cho `resolve_shot_duration` nhận mức âm thanh dạng keyword tùy chọn, mặc định giữ hành vi hiện tại
- [x] 2.2 Ở mức chỉ dùng tiếng gốc, lấy thời lượng shot từ clip active, quay về `duration_seconds` của shot khi không đọc được thời lượng clip
- [x] 2.3 Cho `build_timeline_manifest` nhận mức âm thanh dạng keyword tùy chọn và truyền xuống hàm thời lượng
- [x] 2.4 Bỏ điều kiện giọng đọc trong `get_render_readiness` khi mức âm thanh là chỉ dùng tiếng gốc, giữ nguyên các điều kiện clip, phụ đề, runtime và watermark
- [x] 2.5 Truyền mức âm thanh vào `resolve_shot_duration` tại call site trong `get_render_readiness` và trong `build_timeline_manifest`
- [x] 2.6 Thêm cảnh báo tiếng Việt cho phân đoạn có clip không chứa audio khi ở mức chỉ dùng tiếng gốc ← (verify: readiness ở mức chỉ dùng tiếng gốc trên project có narration và chưa có giọng đọc trả về đủ điều kiện, và timeline manifest giữ đủ mọi shot)

## 3. Dựng audio ở mức chỉ dùng tiếng gốc

- [x] 3.1 Cho hàm quyết định nguồn tiếng nền theo phân đoạn nhận mức âm thanh, và ở mức chỉ dùng tiếng gốc thì không xét speech source của project
- [x] 3.2 Thêm nhánh dựng audio cho mức chỉ dùng tiếng gốc: dùng timeline tiếng gốc làm nguồn audio chính, không dựng timeline giọng đọc, không hạ mức, không trộn hai timeline
- [x] 3.3 Ghi mức âm thanh và quyết định từng phân đoạn vào timeline manifest như nhánh kết hợp đang làm
- [x] 3.4 Thêm cảnh báo tổng khi mọi phân đoạn ở mức chỉ dùng tiếng gốc đều im lặng
- [x] 3.5 Giữ nguyên bước trộn SFX/BGM của enhanced audio phía trên nguồn audio chính ← (verify: project tiếng Việt dùng speech source trích từ clip, dựng ở mức chỉ dùng tiếng gốc, phân đoạn có thoại vẫn phát tiếng gốc chứ không im lặng)

## 4. Điều kiện tạo phụ đề

- [x] 4.1 Cho `backend/services/video_subtitles.py` đọc mức âm thanh của project qua `render_settings_for_project`
- [x] 4.2 Bỏ điều kiện giọng đọc hoàn tất khi mức âm thanh là chỉ dùng tiếng gốc, giữ nguyên điều kiện cho hai mức còn lại
- [x] 4.3 Truyền mức âm thanh vào `resolve_shot_duration` tại hai call site trong `_shot_cue_models` ← (verify: tạo phụ đề trên project có narration nhưng chưa có giọng đọc ở mức chỉ dùng tiếng gốc không còn báo lỗi thiếu giọng đọc, và cue nằm đúng trong khoảng thời gian của shot)

## 5. Frontend: kiểu dữ liệu, lưu trữ, danh sách chọn

- [x] 5.1 Thêm field mức âm thanh vào kiểu `VideoRenderSettings` trong `app/src/lib/api/types.ts`
- [x] 5.2 Gửi field mức âm thanh trong tham số của lời gọi readiness ở `app/src/lib/api/client.ts`
- [x] 5.3 Thêm hằng ba mức, giá trị mặc định và validator tương ứng vào `app/src/lib/renderSettingsStore.ts`, thêm vào cả danh sách giá trị mặc định và danh sách validator
- [x] 5.4 Sửa hàm hợp nhất thiết lập đã lưu để suy mức từ field boolean cũ khi blob đã lưu không có field mới
- [x] 5.5 Sửa hàm ánh xạ hai chiều giữa mức đang chọn và field boolean cũ để hai field luôn khớp nhau
- [x] 5.6 Thay comment sai ở đầu nhóm hằng mức âm thanh: nêu đúng lý do mức chỉ dùng tiếng gốc khác mức kết hợp ← (verify: thiết lập đã lưu của bản cũ với field boolean ở trạng thái giữ tiếng gốc nạp lại ra mức kết hợp; tập khoá của danh sách validator khớp chính xác tập khoá của danh sách giá trị mặc định)
- [x] 5.7 Đổi danh sách chọn trong `app/src/components/AIVideoAssistant/AIVideoRenderPanel.tsx` thành nhãn "Âm thanh" với ba lựa chọn tiếng Việt
- [x] 5.8 Đổi phần diễn giải bên dưới danh sách theo mức đang chọn, nói rõ mức đó làm gì với giọng đọc và với tiếng gốc ← (verify: chọn mức chỉ dùng tiếng gốc trên project có narration và chưa có giọng đọc thì checklist báo đủ điều kiện và nút Dựng MP4 bấm được)

## 6. Kiểm thử

- [ ] 6.1 Thêm test: readiness ở mức chỉ dùng tiếng gốc trên project có narration và chưa có giọng đọc trả về đủ điều kiện, danh sách reason không còn mục về giọng đọc và thời lượng
- [ ] 6.2 Thêm test: `build_timeline_manifest` ở mức chỉ dùng tiếng gốc trả về đủ số shot của project
- [ ] 6.3 Thêm test: `resolve_shot_duration` ở mức chỉ dùng tiếng gốc lấy thời lượng clip, và quay về `duration_seconds` khi clip không đọc được thời lượng
- [ ] 6.4 Thêm test: cấu hình đã lưu không có field mức âm thanh và field boolean ở trạng thái giữ tiếng gốc vẫn phân giải ra mức kết hợp
- [ ] 6.5 Thêm test: quyết định nguồn tiếng nền ở mức chỉ dùng tiếng gốc trên project dùng speech source trích từ clip vẫn dùng tiếng gốc cho phân đoạn có narration
- [ ] 6.6 Thêm test: điều kiện tạo phụ đề ở mức chỉ dùng tiếng gốc không báo lỗi thiếu giọng đọc
- [ ] 6.7 Thêm test: phân đoạn có clip không chứa audio ở mức chỉ dùng tiếng gốc sinh cảnh báo và không chặn readiness
- [ ] 6.8 Cập nhật `app/scripts/verify-render-settings-persistence.mjs` cho ba mức và cho việc suy mức từ thiết lập đã lưu của bản cũ ← (verify: script chạy xanh, bao gồm phép so khớp tập khoá giữa danh sách validator và danh sách giá trị mặc định)

## 7. Chạy kiểm tra

- [ ] 7.1 Chạy `pytest backend/tests/test_ai_video_backend.py`
- [ ] 7.2 Chạy `pytest backend/tests/test_veo_native_vietnamese_speech.py`
- [ ] 7.3 Chạy `pytest backend/tests/test_video_publishing_metadata.py`
- [ ] 7.4 Chạy `npm run verify:render-settings` trong `app/`
- [ ] 7.5 Chạy `npm run typecheck` trong `app/`
- [ ] 7.6 Chạy `npm run build` trong `app/` ← (verify: mọi lệnh trên xanh; không lệnh nào bị bỏ qua hay báo lỗi còn tồn)
