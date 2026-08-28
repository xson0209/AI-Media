## 1. Nền tảng và migration

- [x] 1.1 Thêm model Research Project, Research Source, Research Run, Research Idea, Research Script, Research Score, Research Chat và Research Handoff với status/revision/fingerprint cần thiết.
- [x] 1.2 Thêm migration additive/idempotent và đưa các bảng Research vào `Base.metadata.create_all` mà không đổi dữ liệu bảng cũ.
- [x] 1.3 Thêm storage helper cho thư mục project, manifest, memory revision, source artifact, run, idea, script và handoff; chỉ lưu path tương đối.
- [x] 1.4 Thêm schema version, enum/status constants, dependency fingerprint và helper redaction cho Research domain.

## 2. Research Project và memory

- [x] 2.1 Thêm Pydantic request/response cho CRUD project, multi-select context, memory, revision và filter trạng thái.
- [x] 2.2 Thêm service CRUD Research Project và compile context accepted-first theo giới hạn project/character.
- [x] 2.3 Thêm service compile `research-memory.md` và `manifest.json` từ DB; chỉ accepted item được đưa vào memory chuẩn.
- [x] 2.4 Thêm API route riêng dưới `/research` cho tạo/list/detail/update/archive/context/memory/revision.
- [x] 2.5 Thêm idempotency và stale dependency cho memory revision.

## 3. Nguồn nghiên cứu

- [x] 3.1 Thêm API nhận `video_url`, `video_upload`, `story_url`, `image_upload`, `text`, `docs_url` với giới hạn file/URL rõ ràng.
- [x] 3.2 Tạo Research Source Package contract và adapter boundary cho Video Inspiration, Comic Series Analysis và docs/text.
- [x] 3.3 Persist original bất biến, derivative metadata, progress, partial result, limitations và provenance.
- [x] 3.4 Bổ sung kiểm tra SSRF/redirect, MIME/magic bytes, byte/pixel/duration và redaction log cho source ingestion.
- [x] 3.5 Thêm endpoint list/detail/retry/approve source và chuyển accepted observations vào memory proposal, chưa tự approve canon.

## 4. Chạy hai AI và merge

- [x] 4.1 Thêm run request/response cho mode `research`, `creative`, `both` và selected project/source context.
- [x] 4.2 Tạo orchestration service chạy hai attempt độc lập, có timeout/cancellation/error isolation và lưu raw output ngoài memory.
- [x] 4.3 Thêm merge service tạo 3-5 option với contribution, evidence refs, bất đồng, limitations và recommendation candidate.
- [x] 4.4 Lưu provider/profile/token/cost metadata đã redaction và không ghi secret/config/raw output dài vào log.
- [x] 4.5 Thêm API list/detail/retry/merge run và kiểm thử run lỗi một bên không làm mất kết quả bên còn lại.

## 5. Chat phát triển nội dung

- [x] 5.1 Thêm model/API cho thread, message, branch và draft action của Research Project.
- [x] 5.2 Compile context chat từ accepted memory, episode ledger, selected related projects và source evidence theo budget.
- [x] 5.3 Thêm action tạo biến thể, phát triển tập sau, tăng drama, sửa logic, phát triển nhân vật và tạo script seed.
- [x] 5.4 Thêm approval flow cho idea/script/memory card; promotion phải tạo revision và giữ draft/rejected history.
- [x] 5.5 Thêm continuity fields cho hook, conflict, payoff, open loop, must-have, avoid và trạng thái nhân vật.

## 6. Chấm điểm và khuyên chọn

- [x] 6.1 Thêm rubric version với bảy tiêu chí, trọng số, ngưỡng safety gate và schema score thành phần.
- [x] 6.2 Implement scoring service tính weighted score 0-100, explanation, evidence refs, confidence và limitation.
- [x] 6.3 Implement originality/feasibility/constraint safety gate và trạng thái recommendation `recommended|alternative|blocked|stale`.
- [x] 6.4 Implement ranking, tie group trong khoảng 3 điểm và user override tách khỏi AI score.
- [x] 6.5 Đánh stale score theo dependency fingerprint khi source/script/rubric thay đổi.
- [x] 6.6 Thêm API score/list/recommendation/override và test các trường hợp thiếu evidence, điểm cao nhưng bị gate, tie và stale.

## 7. Handoff thẳng sang AI Video

- [x] 7.1 Tạo Research Handoff preview/commit schema với accepted ids, score/recommendation, provenance, must-have/avoid và limitations.
- [x] 7.2 Chặn handoff candidate/rejected/stale hoặc thiếu approval; không để tạo project dở dang.
- [x] 7.3 Convert handoff thành SourcePackage/source blocks/Project Memory tương thích với AI Video hiện tại.
- [x] 7.4 Gọi primitive tạo AI Video project hiện có với idempotency/dependency fingerprint, không tạo pipeline planning mới.
- [x] 7.5 Trả deep-link `/ai-video?projectId=<id>` và giữ mapping Research Project → Handoff → AI Video Project.
- [x] 7.6 Không auto-run planning/generation sau commit; khi research revision đổi chỉ mark stale artifact phụ thuộc.
- [x] 7.7 Test commit lặp, stale sau đổi hook/script, provenance trace và project AI Video vẫn mở được.

## 8. Frontend route và trải nghiệm tiếng Việt

- [x] 8.1 Thêm route `/research` và lazy workspace component; không làm thay đổi redirect/root hoặc layout behavior route cũ.
- [x] 8.2 Thêm navigation item "Nghiên cứu ý tưởng" với icon Lucide, aria-label, active state và tooltip.
- [x] 8.3 Xây layout desktop/mobile cho project list, multi-select, sources, runs, options, scoring, chat, memory và handoff.
- [x] 8.4 Xây source picker cho link video, upload video, link truyện, upload ảnh, text/docs với progress/partial/error/retry.
- [x] 8.5 Xây run review với tab nghiên cứu, sáng tạo, hợp nhất; cho chọn option, xem score/recommendation và approve.
- [x] 8.6 Xây chat development với branch/draft actions/approval và continuity summary bằng tiếng Việt.
- [x] 8.7 Xây handoff confirmation, lựa chọn target AI Video, trạng thái commit và deep-link mở project mới.
- [x] 8.8 Bảo đảm keyboard navigation, focus, 44px target, wrapping, reduced motion, loading/error/empty/stale state và không horizontal scroll ở 375/768/1024/1440.

## 9. API client và regression

- [x] 9.1 Thêm typed API client/services/hooks cho Research domain, không sửa generated contract cũ ngoài phần cần tương thích.
- [x] 9.2 Thêm backend unit/integration tests cho migration, CRUD, source security, memory compile, run merge, scoring và handoff.
- [x] 9.3 Thêm regression tests chứng minh AI Video, Video Inspiration, Comic Series Analysis, Story Studio và task queue vẫn hoạt động bình thường.
- [x] 9.4 Chạy typecheck, lint, build frontend và backend test suite liên quan; sửa lỗi phát hiện.
- [x] 9.5 Chạy một AI request fixture ngắn có cờ explicit để kiểm tra token/cost metadata, timeout và redaction; không dùng lượt gọi thật trong unit tests.
- [x] 9.6 Chạy route/deep-link smoke test desktop/mobile và kiểm tra visual/interaction không chồng lấn.

## 10. Feature flag và bàn giao

- [x] 10.1 Thêm feature flag để tắt route/menu/job research mà không ảnh hưởng project AI Video đã handoff.
- [x] 10.2 Viết tài liệu tiếng Việt về Research Memory, scoring/recommendation, approval và handoff.
- [x] 10.3 Cập nhật changelog hoặc release note với route mới, ranh giới không ảnh hưởng luồng cũ và cách chạy AI Video sau handoff.
- [x] 10.4 Xác nhận OpenSpec status, toàn bộ task hoàn tất và kiểm tra git diff chỉ gồm phạm vi change hoặc thay đổi cần thiết.

## 11. Liên kết trực tiếp Series Memory

- [x] 11.1 Thêm contract và API tạo nguồn `series_memory` từ một Series hiện có, không yêu cầu dán tóm tắt.
- [x] 11.2 Compile canon đã duyệt bằng Series Brain, lưu snapshot, provenance, revision và dependency fingerprint read-only.
- [x] 11.3 Phát hiện Series Memory thay đổi, đánh dấu source stale và cho phép làm mới thủ công thành revision mới.
- [x] 11.4 Thêm source picker chọn Series hiện có, hiển thị revision, số tập, trạng thái liên kết và nút làm mới memory.
- [x] 11.5 Bổ sung test nguồn Series Memory, context nghiên cứu, stale/refresh, typecheck, lint, build và browser smoke test.
