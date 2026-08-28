## 1. Khảo sát và hợp đồng dữ liệu

- [x] 1.1 Đối chiếu model/API hiện có của Video Inspiration, draft AI Video và rewrite pipeline.
- [x] 1.2 Chốt schema `deep_research`/`high_quality`, coverage metrics, limitations và provenance.
- [x] 1.3 Chốt schema candidate, score, synthesis version, fingerprint, revision và stage status.
- [x] 1.4 Chốt rubric version và giới hạn số candidate/số final version.

## 2. Nghiên cứu sâu → cấu hình AI Video

- [x] 2.1 Thêm action `Nghiên cứu sâu → Cấu hình Video AI` cho job đủ điều kiện.
- [x] 2.2 Gọi analysis với profile chất lượng sâu và lưu pending handoff theo job/revision.
- [x] 2.3 Khôi phục pending intent sau reload và điều hướng đúng một lần khi job thành công.
- [x] 2.4 Dựng analysis-only draft từ transcript, analysis package, frame notes, limitations và direction.
- [x] 2.5 Không yêu cầu `rewritten_script` đối với fast/deep handoff.
- [x] 2.6 Chuẩn hóa AI Video nhận draft: không tạo project, không auto-run, không set `full_materials` và không ghi đè cấu hình cuối.
- [x] 2.7 Hiển thị lỗi, cancel, stale và retry mà không redirect sai.

## 3. Tạo candidate theo batch

- [x] 3.1 Tạo 2–3 candidate trong một structured AI call hoặc bounded fallback.
- [x] 3.2 Validate từng candidate và giữ candidate hợp lệ khi một candidate lỗi.
- [x] 3.3 Lưu candidate theo revision, provenance và fingerprint.
- [x] 3.4 Hiển thị danh sách candidate, checkbox chọn bản và tiến trình tiếng Việt.

## 4. Chấm điểm batch

- [x] 4.1 Thêm hành động `Chấm điểm các bản đã chọn` và `Chấm điểm tất cả`.
- [x] 4.2 Chấm điểm nhiều candidate trong một structured AI call.
- [x] 4.3 Lưu điểm chi tiết theo rubric/version, lý do, strengths, weaknesses và recommendation.
- [x] 4.4 Không chấm lại khi fingerprint không đổi; cho phép retry riêng stage scoring.

## 5. Tổng hợp nhiều phiên bản

- [x] 5.1 Thêm lựa chọn tạo một bản cân bằng hoặc nhiều bản theo ưu tiên.
- [x] 5.2 Tổng hợp 1–N final version trong một batch call khi provider hỗ trợ.
- [x] 5.3 Lưu `source_basis`, score references, originality note và revision cho từng bản.
- [x] 5.4 Cho phép chọn một final version làm bản handoff AI Video.
- [x] 5.5 Không xóa hoặc ghi đè candidate/score/version cũ khi tạo revision mới.

## 6. Cache, queue và hiệu năng

- [x] 6.1 Thêm fingerprint/caching cho analysis, candidate, scoring và synthesis.
- [x] 6.2 Retry/resume theo stage, chỉ chạy lại downstream cần thiết khi input đổi.
- [x] 6.3 Áp dụng bounded concurrency theo workflow/planning pool hiện có.
- [x] 6.4 Ghi timing từng stage, token/character count và latency metadata an toàn.
- [x] 6.5 Thêm heartbeat cho stage dài và tránh false stale trong UI.

## 7. Kiểm thử

- [ ] 7.1 Test deep research tạo analysis package đủ coverage và limitations.
- [ ] 7.2 Test deep handoff không cần rewritten script và mở form cấu hình đúng.
- [ ] 7.3 Test reload/pending intent, cancel, fail, stale và retry.
- [ ] 7.4 Test batch candidate, checkbox selection, scoring và recommendation.
- [ ] 7.5 Test multi-version synthesis, chọn final version và provenance.
- [ ] 7.6 Test cache hit/miss, fingerprint change và resume sau lỗi từng stage.
- [ ] 7.7 Test không auto-run, không `full_materials`, không ghi đè market/ngôn ngữ/thời lượng/tỷ lệ/voice/run mode.
- [ ] 7.8 Chạy regression cho `/video-inspiration`, `/ai-video` và rewrite pipeline cũ.

## 8. Tài liệu và rollout

- [x] 8.1 Cập nhật hướng dẫn tiếng Việt cho hai nút và các trạng thái pipeline.
- [x] 8.2 Ghi rõ khác biệt giữa nghiên cứu sâu, candidate scoring và AI Video generation.
- [x] 8.3 Thêm feature flag hoặc kill switch cho batch/multi-version nếu provider hoặc tài nguyên không sẵn sàng.
- [x] 8.4 Cập nhật changelog/release notes sau khi apply và verify.
