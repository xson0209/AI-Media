## 1. Hợp đồng dữ liệu và migration

- [x] 1.1 Thêm model VideoPublishingMetadata liên kết duy nhất với project_id, gồm trạng thái, phiên bản, ngôn ngữ đích, dấu vân tay đầu vào, payload có cấu trúc, lỗi gần nhất, request id và thời gian tạo/cập nhật.
- [x] 1.2 Thêm migration idempotent cho bảng bộ nội dung đăng video, unique/index theo project và status, không làm thay đổi dữ liệu project cũ.
- [x] 1.3 Định nghĩa payload bắt buộc cho ba nền tảng youtube, tiktok và facebook; mỗi nền tảng có title, description, hashtags, thumbnail_prompt cùng trạng thái/revision nội bộ.
- [x] 1.4 Chuẩn hóa trạng thái missing, generating, completed, failed và stale; lưu revision và input_fingerprint để phân biệt output còn mới với output cần tạo lại.
- [x] 1.5 Thêm Pydantic request/response cho tạo tất cả nền tảng, tạo lại một nền tảng, đọc artifact và trả lỗi có mã ổn định bằng tiếng Việt.
- [x] 1.6 Export model mới qua lớp database hiện có và bổ sung thống kê cần thiết cho reset, xóa project và debug status.

## 2. Dịch vụ tạo bộ nội dung đăng video bằng Codex

- [x] 2.1 Tạo service riêng cho bộ nội dung đăng video, không nhồi logic mới vào route hoặc component AI Video hiện có.
- [x] 2.2 Biên dịch context từ topic, mục đích video, target audience khi có, target_language, CTA, detailed script/narration cuối, shot, prompt video cuối, continuity và dữ liệu series đã duyệt.
- [x] 2.3 Đảm bảo title, description và hashtag dùng ngôn ngữ người xem theo target_language; prompt thumbnail có thể dùng wording kỹ thuật dễ render nhưng không chỉ dẫn chữ hiển thị sai ngôn ngữ video.
- [x] 2.4 Dùng structured output schema để một lần gọi Codex trả đủ ba nền tảng và đủ bốn trường của mỗi nền tảng; thiếu bất kỳ trường bắt buộc nào phải coi là output không hợp lệ.
- [x] 2.5 Xây profile riêng cho YouTube, TikTok và Facebook về độ cô đọng, từ khóa, hook, CTA, hashtag, tỷ lệ/safe area và ngữ cảnh sử dụng; không dùng chung một title cho cả ba nền tảng.
- [x] 2.6 Tạo prompt thumbnail dạng văn bản có chủ thể thật của video, hook thị giác, bố cục, ánh sáng, tỷ lệ, safe area, continuity nhân vật và chỉ dẫn tránh watermark, logo hoặc chữ ngẫu nhiên; không gọi dịch vụ render ảnh trong change này.
- [x] 2.7 Validate và chuẩn hóa output: trim text, loại hashtag rỗng/trùng, giữ hashtag dạng mảng, chặn nội dung thiếu chủ đề, claim bịa đặt hoặc vượt giới hạn cấu hình của nền tảng.
- [x] 2.8 Chỉ ghi DB sau khi toàn bộ output yêu cầu hợp lệ; khi tạo lại một nền tảng phải giữ nguyên hai nền tảng còn lại và khi output lỗi phải giữ artifact hợp lệ gần nhất.
- [x] 2.9 Chạy mọi Codex call qua planning pool, retry/timeout và observability hiện có; log số ký tự, schema keys, platform và error code nhưng không log toàn bộ prompt hoặc nội dung người dùng dài.

## 3. API, dependency và vòng đời artifact

- [x] 3.1 Thêm API đọc bộ nội dung đăng video theo project, trả null hoặc trạng thái missing rõ ràng khi chưa tạo.
- [x] 3.2 Thêm API tạo/tạo lại với lựa chọn all, youtube, tiktok hoặc facebook, hỗ trợ force có kiểm soát và trả artifact hoàn chỉnh sau khi lưu.
- [x] 3.3 Chặn hai generation chạy đồng thời trên cùng project; request lặp không được tạo revision trùng hoặc ghi đè output mới hơn.
- [x] 3.4 Trả trạng thái/readiness rút gọn của bộ nội dung đăng video trong project status và auto-run summary mà không nhồi toàn bộ payload dài vào mọi response.
- [x] 3.5 Trả lỗi tiếng Việt nhất quán cho project không tồn tại, chưa có prompt/story đủ điều kiện, planning provider chưa sẵn sàng, output Codex sai schema và generation đang chạy.
- [x] 3.6 Tạo helper dependency/fingerprint để đánh stale khi topic, source/handoff, detailed script hoặc narration cuối, shot/prompt cuối, target_language, mục đích video, CTA, tỷ lệ hoặc continuity liên quan thay đổi; đổi riêng voice profile không được làm stale bộ nội dung đăng.
- [x] 3.7 Cập nhật reset generated data và delete project để xóa artifact mới, file liên quan nếu có và count tương ứng; không để row mồ côi.

## 4. Tích hợp auto-run sau bước prompt

- [x] 4.1 Thêm persisted step generate_publishing_metadata ngay sau generate_prompts và trước review_prompts, đồng thời cập nhật step order, progress, status text và kiểu dữ liệu backend/frontend.
- [x] 4.2 Ở mode review_gated, dùng gate review_prompts hiện có để người dùng duyệt cả prompt video và bộ nội dung đăng; không thêm gate thứ ba.
- [x] 4.3 Ở mode full_auto với target full_materials, chạy đúng thứ tự prompt -> bộ nội dung đăng -> voice -> chờ voice -> phụ đề và chỉ hoàn tất khi các artifact bắt buộc còn mới.
- [x] 4.4 Giữ nguyên ý nghĩa prompts_only cho client cũ; thêm material target publishing_kit để tạo prompt + bộ nội dung đăng nhưng không tạo voice hoặc phụ đề.
- [x] 4.5 Với project đã có bộ nội dung đăng completed và fingerprint còn đúng, auto-run phải skip generation; chỉ tạo lại khi missing, stale, failed retryable hoặc người dùng force đúng phạm vi.
- [x] 4.6 Khi generation bộ nội dung đăng thất bại, auto-run phải dừng ở bước đó, giữ prompt đã tạo và không bắt đầu voice/phụ đề; retry phải tiếp tục từ artifact lỗi thay vì tạo lại story/prompt hợp lệ.
- [x] 4.7 Khi planning pool bận, auto-run dùng trạng thái waiting_planning và khôi phục đúng bước generate_publishing_metadata sau khi lấy được slot.
- [x] 4.8 Mở rộng summary với status/readiness, revision và số nền tảng đã sẵn sàng; UI không phải đọc raw step_results_json để biết bộ nội dung đăng đã xong hay chưa.
- [x] 4.9 Khôi phục/reconcile run sau app restart hoặc refresh để step mới không bị bỏ qua, chạy lặp hoặc tiếp tục sang voice khi artifact chưa được lưu hoàn chỉnh.

## 5. Voice và phụ đề sau bộ nội dung đăng

- [x] 5.1 Tái sử dụng service tạo voice theo shot/scene và voice profile hiện có; không tạo TTS engine hoặc hàng đợi song song mới cho feature này.
- [x] 5.2 Khi thiếu voice profile hoặc profile không hỗ trợ target_language, auto-run chuyển needs_input, giữ nguyên bộ nội dung đăng đã tạo và tiếp tục đúng bước voice sau khi người dùng sửa cấu hình.
- [x] 5.3 Chỉ tạo phụ đề sau khi mọi voice bắt buộc hoàn tất với audio path và duration hợp lệ; lỗi một voice phải chặn SRT nhưng không làm mất metadata đăng video.
- [x] 5.4 Khi tạo lại voice, sửa narration hoặc đổi target_language, đánh dấu cả subtitle_status cấp shot/scene và row SRT cấp project là stale; download/status không được báo SRT cũ là bản hiện hành.
- [x] 5.5 Sửa timeline phụ đề để shot/cảnh không narration vẫn làm tăng cursor theo duration timeline phù hợp, tránh cue phía sau xuất hiện sớm.
- [x] 5.6 Giữ mô tả chính xác rằng cue được căn theo duration audio/timeline hiện có; không cam kết forced alignment hoặc khớp từng từ khi chưa có dữ liệu timestamp từ engine.

## 6. Giao diện bộ nội dung đăng video

- [x] 6.1 Tạo component AIVideoPublishingMetadataPanel riêng và đặt ngay giữa phần Prompt video với phần Voice và phụ đề trong AI Video Assistant.
- [x] 6.2 Thêm query/mutation và apiClient/type tương ứng để đọc, tạo tất cả, tạo lại nền tảng hiện tại và refresh dữ liệu sau auto-run.
- [x] 6.3 Hiển thị ba tab YouTube, TikTok, Facebook; chuyển tab không làm mất nội dung hoặc trạng thái của nền tảng khác.
- [x] 6.4 Trong mỗi tab hiển thị đúng bốn ô riêng: Tiêu đề video, Mô tả, Hashtag và Prompt tạo ảnh thumbnail, tổng cộng mười hai output có thể copy độc lập.
- [x] 6.5 Đặt nút biểu tượng Copy có tooltip và aria-label bên phải từng ô, hỗ trợ clipboard fallback và thông báo tiếng Việt cho thành công/thất bại; không bắt người dùng copy toàn bộ panel.
- [x] 6.6 Hiển thị hashtag thành chuỗi copy-ready ngăn cách bằng khoảng trắng từ mảng có cấu trúc, không lưu chuỗi ghép ngược lại làm nguồn dữ liệu.
- [x] 6.7 Thêm action Tạo nội dung đăng, Tạo lại nền tảng này và Tạo lại tất cả; disable đúng lúc generation đang chạy hoặc auto-run đang sở hữu bước liên quan.
- [x] 6.8 Hiển thị đầy đủ empty, loading, generating, completed, stale và failed state; khi stale vẫn cho copy bản cũ nhưng phải ghi rõ cần tạo lại.
- [x] 6.9 Cập nhật progress auto-run và trạng thái needs_review để chỉ người dùng tới phần prompt + nội dung đăng trước khi tiếp tục sang voice.
- [ ] 6.10 Giữ video_projects.title là tên quản lý project, không dùng nó thay cho tiêu đề đăng video; kiểm tra responsive, keyboard focus, text wrapping và không để mười hai ô hoặc nút copy overlap trên desktop/mobile.

## 7. Kiểm thử backend và frontend

- [ ] 7.1 Test migration idempotent, unique một artifact trên mỗi project và project cũ mở được với trạng thái metadata missing.
- [ ] 7.2 Test service tạo đủ ba nền tảng, đủ bốn trường và đúng ngôn ngữ cho cả project en và vi.
- [ ] 7.3 Test profile nền tảng tạo output khác nhau hợp lý, hashtag được loại trùng và prompt thumbnail có subject, bố cục, tỷ lệ/safe area cùng ràng buộc tránh watermark/chữ ngẫu nhiên.
- [x] 7.4 Test output thiếu/sai schema không ghi payload dở dang, không tăng revision sai và vẫn giữ artifact hợp lệ gần nhất.
- [x] 7.5 Test tạo lại một nền tảng chỉ đổi nền tảng đó, giữ nguyên hai nền tảng còn lại và cập nhật revision/fingerprint đúng.
- [x] 7.6 Test stale cho mọi dependency bắt buộc và chứng minh đổi riêng voice profile không làm stale bộ nội dung đăng.
- [ ] 7.7 Test API happy path, project không tồn tại, thiếu prompt/story, provider lỗi, conflict generation, reset và delete project.
- [ ] 7.8 Test auto-run review_gated, full_auto, prompts_only, publishing_kit, skip artifact còn mới, retry lỗi metadata và resume sau restart theo đúng thứ tự bước.
- [x] 7.9 Test tạo lại voice làm row SRT cấp project stale, chặn tải SRT cũ và shot/cảnh im lặng không làm cue sau xuất hiện sớm.
- [ ] 7.10 Mock Codex/TTS trong test chính và xác nhận feature không gọi image provider, không tạo ảnh thumbnail thật, không đăng nhập hoặc đăng bài lên YouTube, TikTok, Facebook/Messenger.
- [ ] 7.11 Thêm kiểm thử component hoặc verification script cho ba tab, mười hai ô, copy từng trường, hashtag copy-ready, action tạo lại một/tất cả và các trạng thái loading/stale/error.
- [ ] 7.12 Kiểm tra step auto-run mới, review gate, summary readiness; chạy frontend typecheck/build, focused backend tests và Playwright QA phù hợp.

## 8. Tài liệu, QA thủ công và xác minh

- [ ] 8.1 Cập nhật tài liệu AI Video bằng tiếng Việt về vị trí copy title, description, hashtag, prompt thumbnail và thứ tự tiếp tục sang voice/phụ đề.
- [ ] 8.2 Thêm sơ đồ prompt video -> bộ nội dung đăng -> voice -> phụ đề, giải thích tab nào tạo output cho YouTube, TikTok và Facebook.
- [ ] 8.3 Ghi rõ tối ưu theo nền tảng/SEO/CTR không bảo đảm thứ hạng; change chỉ tạo prompt thumbnail dạng văn bản, không render ảnh, không tự đăng bài và không tạo biến thể Messenger riêng.
- [ ] 8.4 Manual QA luồng thủ công: tạo prompt, tạo bộ nội dung đăng, chuyển ba tab và copy riêng đủ mười hai trường.
- [ ] 8.5 Manual QA full_auto: prompt -> metadata đăng -> voice -> chờ voice -> SRT; xác nhận lỗi metadata chặn voice và lỗi voice chặn SRT đúng phạm vi.
- [ ] 8.6 Manual QA review_gated, publishing_kit, retry, refresh/reload và tạo lại riêng một nền tảng mà không mất output còn lại.
- [ ] 8.7 Manual QA desktop/mobile cho tab, textarea, title dài, hashtag dài, prompt thumbnail dài, nút copy và thông báo không chồng lấn.
- [x] 8.8 Chạy openspec list --json và openspec validate --changes --strict --json; xác nhận change 12 được nhận diện và không có lỗi artifact trước khi apply.
