## Tổng quan thiết kế

Change này nối hai khả năng trong cùng một workflow nhưng giữ chúng thành hai đường hành động rõ ràng:

```text
Video nguồn
  ├─> Nghiên cứu sâu
  │     └─> analysis package + analysis-only draft
  │            └─> /ai-video?draft=video-inspiration
  │
  └─> Tối ưu nhiều phiên bản
        ├─> tạo 2–3 candidate trong một batch
        ├─> người dùng chọn candidate
        ├─> chấm điểm batch
        ├─> tổng hợp 1–N phiên bản
        └─> chọn bản cuối → draft AI Video
```

## A. Nghiên cứu sâu và handoff cấu hình

### Profile chất lượng

MVP dùng `analysis_mode = high_quality`, tương ứng với budget keyframe và ngưỡng shot hiện có. Nếu sau này cần profile trung gian, profile phải ghi rõ:

- số keyframe hoặc coverage mục tiêu;
- modality nào được phân tích đầy đủ;
- limitations/coverage metrics;
- model và rubric đã dùng.

Không dùng từ `nhanh` để mô tả chất lượng thấp hơn. “Nhanh” trong UX chỉ có nghĩa là một hành động và xử lý nền; nhãn đề xuất là `Nghiên cứu sâu → Cấu hình Video AI`.

### Pending handoff

Frontend ghi pending intent theo `job_id`, analysis revision và action. Khi job chuyển terminal thành công, UI dựng draft và điều hướng một lần. Intent phải khôi phục được sau reload trong cùng session; lỗi, cancel hoặc stale không được tự điều hướng.

### Analysis-only draft

Draft có thể không có rewritten script. Các source blocks gồm:

- `idea`: title, main idea, hook và provenance;
- `rough_script`: transcript gốc và hướng phát triển, có ghi rõ chưa phải script cuối;
- `character_notes`: nhân vật, bối cảnh, visual summary và frame notes;
- `style_notes`: visual rhythm, camera, mood, retention evidence và sound limitations;
- `must_have`: insight, hook, strengths, opportunities và user direction;
- `avoid`: weaknesses, originality boundary, limitations và cảnh báo không copy sát nguồn.

AI Video chỉ nạp dữ liệu vào form. Nó phải để người dùng tự chọn mục đích, ngôn ngữ cuối, thời lượng, tỷ lệ, voice và run mode; không tạo project hoặc auto-run.

## B. Candidate, chấm điểm và nhiều phiên bản

### Batch candidate generation

Một structured AI call trả về 2–3 candidate có cùng schema để so sánh được. Mỗi candidate có `variant_id`, hướng sáng tạo, hook, big idea, script, segments, retention, visual suggestions, sound design và originality note.

Ưu tiên batch call thay vì một subprocess cho mỗi candidate để giảm overhead. Nếu provider không hỗ trợ batch, dùng bounded concurrency tối đa theo workflow pool hiện có; không mở task vô hạn.

### Candidate selection và scoring

UI hiển thị checkbox cho từng candidate và hai hành động:

- `Chấm điểm các bản đã chọn`;
- `Chấm điểm tất cả`.

Scoring gửi các candidate đã chọn trong một request, trả rubric theo candidate gồm hook, clarity, originality, retention, production feasibility, sound design và alignment với user direction. Rubric phải có version để fingerprint và audit.

### Multi-version synthesis

Sau scoring, người dùng chọn chiến lược:

- tổng hợp một bản cân bằng;
- tạo nhiều bản theo các ưu tiên khác nhau;
- chọn bản điểm cao nhất làm seed.

Một synthesis call có thể trả về 1–N final versions. Mỗi bản giữ `source_basis` trỏ tới candidate và score đã dùng. Bản cuối chỉ được handoff khi đã có trạng thái hợp lệ và không stale.

### Cache, revision và resume

Fingerprint tối thiểu:

```text
analysis_revision
+ target_language
+ user_direction
+ candidate_count
+ selected_variant_ids
+ rubric_version
+ model
```

Các stage độc lập được lưu riêng: `analysis`, `candidate_generation`, `candidate_scoring`, `variant_synthesis`, `selected_final`. Nếu một stage fail, retry chỉ chạy stage đó và các stage downstream cần thiết. Nếu input fingerprint đổi, revision cũ chuyển stale nhưng vẫn đọc được.

### Trạng thái và tiến trình

UI hiển thị tiếng Việt, ví dụ:

- `Đang nghiên cứu sâu`;
- `Đang tạo các hướng kịch bản`;
- `Đang chấm điểm các bản đã chọn`;
- `Đang tổng hợp nhiều phiên bản`;
- `Đã sẵn sàng cấu hình Video AI`.

Technical details chỉ lưu metadata, count, fingerprint rút gọn, latency và error code; không log full transcript, script hoặc binary frame.

## Tương thích và ranh giới

- Giữ endpoint và model Video Inspiration hiện có tương thích ngược.
- Tái sử dụng `analysis_package_json`, structured AI runner, workflow/planning pool và draft handoff hiện có.
- Chuẩn hóa hành vi nhận draft của AI Video theo contract: không set `full_materials`, không auto-run và không ghi đè cấu hình cuối.
- Không biến handoff draft thành backend handoff/project creation.

## Rủi ro và giảm thiểu

- Nghiên cứu sâu lâu: chạy background, heartbeat, progress và stale threshold phù hợp.
- Nhiều candidate làm tăng token: giới hạn 2–3, batch output và cache.
- Provider trả một candidate lỗi: validate từng candidate, giữ candidate hợp lệ và cho retry stage.
- Synthesis tạo bản sao sát nguồn: giữ originality rubric, warning và source provenance.
- Handoff làm mất cấu hình người dùng: test form import với project state rỗng và tất cả cấu hình phải do người dùng chọn.

