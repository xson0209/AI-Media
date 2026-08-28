## 1. Narrative Contract và Beat Graph

- [ ] 1.1 Thêm mô hình và migration additive cho Narrative Contract, revision, approval và candidate provenance.
- [ ] 1.2 Thêm mô hình Narrative Beat với thông tin mới, câu hỏi, open loop, micro-payoff, visual proof và state in/out.
- [ ] 1.3 Thêm API tạo, xem, sửa, duyệt, supersede và lập lịch sử contract/beat.
- [ ] 1.4 Tạo draft migration từ project cũ nhưng không tự duyệt.
- [ ] 1.5 Ngăn target timeline quay vòng source beat để giả tạo nội dung mới.

## 2. Candidate, critic và synthesis cho AI Video

- [ ] 2.1 Tách hoặc tái sử dụng engine ba candidate hiện có của Story Studio qua giao diện dùng chung.
- [ ] 2.2 Tạo đúng ba candidate độc lập từ cùng context snapshot theo ba chiến lược khóa.
- [ ] 2.3 Kiểm tra candidate khác nhau thật về hook, cấu trúc, cảm xúc và cách giải quyết.
- [ ] 2.4 Chạy critic tách biệt và lưu điểm, lý do, evidence, strengths, weaknesses và risks.
- [ ] 2.5 Cho chọn một candidate hoặc synthesis; lưu provenance phần được lấy.
- [ ] 2.6 Kiểm tra synthesis về canon, originality, hook-payoff và coherence; không tự duyệt.

## 3. Context theo nhiệm vụ

- [ ] 3.1 Tích hợp Project Memory compiler trực tiếp vào `develop_story`, shot, prompt, voice và subtitle.
- [ ] 3.2 Gọi Series Brain với đúng task type thay vì luôn dùng `video_story_development`.
- [ ] 3.3 Hợp nhất Series Canon và Project Memory theo thứ tự ưu tiên đã định nghĩa.
- [ ] 3.4 Lưu context snapshot ID và source refs trên từng artifact được tạo.
- [ ] 3.5 Ghim Narrative Contract, beat và approved narration; rút gọn evidence dài theo nhiệm vụ.
- [ ] 3.6 Test transcript nguồn không thể trở thành narration/voice/subtitle cuối.

## 4. Beat mapping và continuity

- [ ] 4.1 Thêm mapping narrative contract, revision, beat và production segment cho scene/shot/prompt/voice/subtitle.
- [ ] 4.2 Thêm Continuity State Ledger cho nhân vật, cảm xúc, kiến thức, địa điểm, đạo cụ và open loop.
- [ ] 4.3 Kiểm tra state out/state in giữa các beat và segment liền kề.
- [ ] 4.4 Cho phép transition có chủ đích kèm lý do và evidence.
- [ ] 4.5 Đánh dấu stale đúng phạm vi khi beat, narration hoặc state thay đổi.

## 5. Quality gate và targeted repair

- [ ] 5.1 Thêm `story_quality_gate` vào auto-run trước review story.
- [ ] 5.2 Thêm `prompt_quality_gate` vào auto-run trước review prompts.
- [ ] 5.3 Chặn canon, originality, hook-payoff, missing beat mapping, stale narration và continuity nghiêm trọng kể cả ở full auto.
- [ ] 5.4 Cho warning không chặn theo cấu hình nhưng phải lưu lịch sử và evidence.
- [ ] 5.5 Tạo targeted repair cho contract/beat, shot hoặc prompt với giới hạn tối đa hai lần.
- [ ] 5.6 Ngăn repair kỹ thuật đổi central promise, payoff, CTA hoặc narration đã duyệt.
- [ ] 5.7 Retry chỉ artifact lỗi và giữ nguyên artifact độc lập đã đạt.

## 6. Release Snapshot và ranh giới publishing

- [ ] 6.1 Thêm Video Content Release Snapshot có narrative, render và metadata revision.
- [ ] 6.2 Chỉ tạo snapshot sẵn sàng khi contract và quality gate hợp lệ.
- [ ] 6.3 Định nghĩa giao diện read-only để social publishing tiêu thụ snapshot.
- [ ] 6.4 Mark snapshot stale khi content, narration, prompt, voice, subtitle hoặc render dependency thay đổi.
- [ ] 6.5 Test publishing state không thể sửa ngược content artifacts.

## 7. Giao diện

- [ ] 7.1 Thêm màn review ba candidate, critic và synthesis cho AI Video.
- [ ] 7.2 Hiển thị Narrative Contract và beat timeline bằng tiếng Việt, gồm thông tin mới, open loop, payoff và state change.
- [ ] 7.3 Hiển thị mapping từ beat tới scene, shot, prompt, voice và subtitle.
- [ ] 7.4 Hiển thị lỗi continuity theo hai đoạn liền kề và hành động sửa ưu tiên.
- [ ] 7.5 Hiển thị quality gate trong auto-run và không ẩn blocking error sau tổng điểm.
- [ ] 7.6 Cho override có lý do nhưng giữ lịch sử lỗi và artifact revision.

## 8. Kiểm thử và vận hành

- [ ] 8.1 Test một video có hook, setup, escalation, micro-payoff và payoff hoàn chỉnh.
- [ ] 8.2 Test beat lặp hoặc có thể xóa bị content stagnation và không qua gate.
- [ ] 8.3 Test state continuity cho nhân vật, đạo cụ, địa điểm, cảm xúc và open loop.
- [ ] 8.4 Test chỉ một beat đổi thì chỉ dependency liên quan bị stale.
- [ ] 8.5 Test ba candidate cùng snapshot nhưng khác chiến lược và synthesis lưu provenance.
- [ ] 8.6 Test full auto dừng ở blocking error và review-gated dừng đúng cổng người dùng.
- [ ] 8.7 Test release snapshot bất biến và social publishing không ghi ngược content domain.
- [ ] 8.8 Chạy backend tests, frontend typecheck/build và OpenSpec strict validation.
- [ ] 8.9 Viết tài liệu tiếng Việt giải thích Narrative Contract, Beat Graph, continuity state và quality gate.
