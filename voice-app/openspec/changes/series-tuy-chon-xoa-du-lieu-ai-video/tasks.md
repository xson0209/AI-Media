## 1. Data Model Và Migration

- [x] 1.1 Thêm migration idempotent tạo bảng `video_series` với title, bible fields, rules, previous episode summary và timestamps.
- [x] 1.2 Thêm nullable `series_id`, `episode_number`, `episode_title` vào `video_projects` mà không backfill bắt buộc project cũ.
- [x] 1.3 Cập nhật ORM models và exports cho `VideoSeries`.
- [x] 1.4 Thêm Pydantic request/response models cho series create/update/detail/list và optional series metadata trên project response.
- [x] 1.5 Đảm bảo project cũ không có `series_id` vẫn serialize/list/get như standalone project.

## 2. Series Backend Services Và APIs

- [x] 2.1 Implement service tạo/list/get/update/delete series với validation title và bible field length.
- [x] 2.2 Implement endpoint CRUD series dưới `/ai-video/series` hoặc route tương đương.
- [x] 2.3 Implement tạo episode project từ series, tự set `series_id`, `episode_number`, `episode_title` và kế thừa cấu hình phù hợp.
- [x] 2.4 Implement logic tính episode number tiếp theo an toàn khi series đã có nhiều project.
- [x] 2.5 Implement detach episodes khi xoá series nhưng giữ projects.
- [x] 2.6 Implement xoá series cùng episodes chỉ khi có confirm/flag rõ ràng ở API service layer.
- [x] 2.7 Cập nhật list projects để trả optional series summary đủ cho frontend group recent projects.

## 3. Series Context Trong Planning

- [x] 3.1 Thêm helper build `series_context` cho project thuộc series và trả rỗng cho project standalone.
- [x] 3.2 Inject Series Bible vào story development prompt khi project thuộc series.
- [x] 3.3 Inject Series Bible vào shot breakdown prompt khi project thuộc series.
- [x] 3.4 Inject Series Bible vào video prompt pack prompt khi project thuộc series.
- [x] 3.5 Đảm bảo project standalone không bị thêm context series giả hoặc rỗng vào prompt.
- [x] 3.6 Thêm flow cập nhật previous episode summary/latest series summary có kiểm soát sau review hoặc bằng action explicit.
- [x] 3.7 Log debug event an toàn khi series context bị truncate hoặc thiếu trường cốt lõi.

## 4. Xoá Dữ Liệu Backend

- [x] 4.1 Thiết kế service operation chung cho delete/reset với log summary và error code tiếng Việt.
- [x] 4.2 Implement reset generated data giữ project, source blocks, series link, config, target language và voice profile.
- [x] 4.3 Reset generated data xoá đúng story/shots/prompts/voice/subtitle/package/render outputs/debug events theo project.
- [x] 4.4 Cập nhật xoá source block để reorder ổn định các block còn lại nếu cần.
- [x] 4.5 Khi xoá source block sau khi project đã generate data, mark planning/artifacts liên quan stale.
- [x] 4.6 Xử lý xoá source block cuối cùng bằng confirm/validation rõ ràng.
- [x] 4.7 Trước khi delete/reset, chặn project đang auto-run/planning active.
- [x] 4.8 Trước khi delete/reset, chặn hoặc cảnh báo project đang voice/render active.
- [x] 4.9 Bổ sung API reset generated data và chuẩn hoá response/error shape.
- [x] 4.10 Bổ sung debug event cho delete/reset/source-block delete gồm counts, ids và artifact types đã xoá, không log full content.

## 5. Strict Codex Mapping Và Validation

- [x] 5.1 Tách mapper/validator canonical cho story payload với alias whitelist và type summary.
- [x] 5.2 Tách mapper/validator canonical cho shot breakdown payload, kiểm tra scene order, shot order, duplicate và count.
- [x] 5.3 Tách mapper/validator canonical cho video prompt pack payload, kiểm tra expected shot/segment count, order và duplicate.
- [x] 5.4 Thêm mapper/validator cho Series Bible payload nếu có chức năng Codex tạo/cập nhật bible.
- [x] 5.5 Implement alias conflict detection: nhiều key alias cùng field nhưng dữ liệu mâu thuẫn thì reject.
- [x] 5.6 Implement required creative fields validation cho prompt video, gồm continuity/retention/transition/sound design notes.
- [x] 5.7 Đảm bảo validation fail không xoá prompt/shot/artifact cũ và không ghi partial data.
- [x] 5.8 Đảm bảo retry Codex chỉ ghi dữ liệu từ attempt đã pass mapping/validation đầy đủ.
- [x] 5.9 Thêm error codes/log events riêng cho mapping fail, count mismatch, order mismatch, alias conflict và required field missing.
- [x] 5.10 Redact technical details cho mapping failure: chỉ lưu keys, type summary, counts, ids và preview ngắn.

## 6. Frontend Series UX

- [x] 6.1 Cập nhật API client/types cho series models, optional project series metadata và reset generated data endpoint.
- [x] 6.2 Cập nhật “Dự án gần đây” để group projects theo series và vẫn hiển thị project lẻ.
- [x] 6.3 Thêm menu `⋯` trên project item với chọn project, đổi tên nếu có, xoá dữ liệu đã tạo và xoá project.
- [x] 6.4 Thêm UI tạo series mới và chỉnh Series Bible.
- [x] 6.5 Thêm UI tạo tập mới trong series với episode number/title/topic.
- [x] 6.6 Hiển thị rõ project hiện tại là standalone hay episode thuộc series nào.
- [x] 6.7 Cập nhật auto-run/create project flow để project lẻ vẫn không cần chọn series.

## 7. Frontend Xoá Dữ Liệu UX

- [x] 7.1 Thêm confirm dialog xoá project với copy tiếng Việt rõ project và dữ liệu sẽ bị xoá.
- [x] 7.2 Thêm confirm dialog reset generated data, giải thích giữ source blocks/config/series link.
- [x] 7.3 Thêm nút xoá từng source block trong vùng nguồn nội dung/đoạn nhập.
- [x] 7.4 Sau khi xoá source block/reset/delete project, invalidate/refetch queries liên quan và chọn project kế tiếp hợp lý.
- [x] 7.5 Hiển thị lỗi tiếng Việt khi xoá bị chặn do auto-run/planning/voice/render active.
- [x] 7.6 Đảm bảo thao tác xoá không gây layout jump hoặc click nhầm trong sidebar recent projects.

## 8. Backend Tests

- [x] 8.1 Test migration tạo `video_series` và nullable columns, project cũ vẫn standalone.
- [x] 8.2 Test CRUD series và update Series Bible.
- [x] 8.3 Test tạo episode từ series kế thừa config và set episode number đúng.
- [x] 8.4 Test project standalone story/shots/prompt không nhận series context.
- [x] 8.5 Test project trong series inject character/world/style/summary vào story/shots/prompt planning.
- [x] 8.6 Test list projects trả metadata đủ để group series và standalone.
- [x] 8.7 Test delete source block mark stale và giữ block còn lại.
- [x] 8.8 Test reset generated data xoá artifacts/rows đúng nhưng giữ source/config/series link.
- [x] 8.9 Test delete/reset bị chặn khi auto-run/planning active.
- [x] 8.10 Test delete project thuộc series không xoá series nếu chỉ xoá project.
- [x] 8.11 Test strict mapping reject prompt pack thiếu/thừa/trùng/sai order và giữ prompt cũ.
- [x] 8.12 Test strict mapping reject alias conflict và field sai type không repair an toàn.
- [x] 8.13 Test retry Codex: attempt invalid rồi valid chỉ ghi attempt valid.
- [x] 8.14 Test debug redaction cho deletion và mapping failures.

## 9. Frontend Checks Và QA

- [x] 9.1 Chạy frontend typecheck cho AI Video Assistant và api client.
- [x] 9.2 Chạy focused backend tests cho series, deletion, mapping và existing AI Video planning regression.
- [ ] 9.3 Manual QA project lẻ: tạo project, auto-run, prompt pack, reset generated data, xoá project.
- [ ] 9.4 Manual QA series: tạo series, tạo 2 episode, xác nhận prompt planning dùng cùng nhân vật/bối cảnh/style.
- [ ] 9.5 Manual QA recent projects: series grouped đúng, project lẻ vẫn chọn trực tiếp được.
- [ ] 9.6 Manual QA xoá source block: project mark stale và không mất source blocks còn lại.
- [ ] 9.7 Manual QA mapping fail bằng fake/monkeypatch payload sai: UI/API báo lỗi rõ và dữ liệu cũ vẫn còn.
- [x] 9.8 Chạy `openspec validate series-tuy-chon-xoa-du-lieu-ai-video --strict` trước khi archive.
