## Ngày ghi nhận

22-07-2026

## Tổng quan thiết kế

```text
Nguồn nội dung + Series Memory + Project Memory
                    |
                    v
          Context Snapshot đã đóng băng
                    |
                    v
       Ba candidate độc lập + critic
                    |
                    v
        Narrative Contract đã duyệt
                    |
                    v
 Beat Graph + Continuity State Ledger
                    |
                    v
 Scene -> Shot -> Prompt -> Voice -> Subtitle
                    |
                    v
       Quality Gate + Targeted Repair
                    |
                    v
        Render/Release Snapshot đã duyệt
                    |
                    v
 Social Publishing Workflow chỉ đọc
```

## Quyết định thiết kế

### 1. Narrative Contract là nguồn chuẩn cấp video

Thêm artifact khái niệm `VideoNarrativeContract`:

```text
id
project_id
revision
status
context_snapshot_id
target_audience
video_goal
central_promise
central_question
content_spine
point_of_view
stakes
hook_contract
payoff_contract
cta_contract
tone_and_language
candidate_provenance
created_at
approved_at
```

Trạng thái tối thiểu:

```text
draft | reviewing | approved | blocked | stale | superseded
```

Chỉ contract `approved` mới được dùng làm nguồn chuẩn cho shot/prompt/voice/subtitle cuối. Bản cũ bất biến và được giữ để truy vết dependency.

### 2. Beat Graph thay target timeline cơ học

Mỗi `NarrativeBeat` gồm:

```text
id
narrative_contract_id
beat_order
role
start_seconds
end_seconds
content
new_information
viewer_question_in
question_answered
next_open_loop
emotional_change
stakes_change
micro_payoff
visual_proof
audio_direction
required_evidence
state_in
state_out
```

Beat không được tạo bằng cách quay vòng source beat để đủ segment. Nếu số segment lớn hơn số beat nội dung, hệ thống phải chia một beat thành các production segment có cùng `beat_id`, không giả tạo beat mới hoặc lặp nội dung.

### 3. Ba candidate dùng chung context snapshot

AI Video tái sử dụng engine candidate của Story Studio với ba hướng khóa:

- hook và giữ chân;
- cảm xúc và logic nhân vật;
- hình ảnh, hành động và khả năng sản xuất.

Ba candidate được tạo độc lập từ cùng một snapshot. Critic không sửa candidate trong lúc chấm. Bước synthesis phải lưu phần lấy từ candidate nào, kiểm tra lại canon, originality, hook-payoff và narrative coherence, rồi chờ người dùng duyệt.

### 4. Context được biên dịch theo từng nhiệm vụ

Mỗi bước tạo context snapshot riêng nhưng cùng tham chiếu contract revision:

```text
story: audience, goal, source lessons, content spine, hook/payoff, originality boundaries
shot: beat hiện tại, state in/out, visual/audio direction, continuity và duration
prompt: đúng production segment, action, start/end state, reference và negative rules
voice: narration đã duyệt, speaker, language, emotion, pacing và duration
subtitle: voice revision cuối, cue timing, keyword và safe area
```

Series canon có ưu tiên cao hơn Project Memory. Project Memory đã duyệt có ưu tiên cao hơn working draft. Transcript nguồn chỉ là evidence, không được dùng làm narration cuối.

### 5. Continuity State Ledger kiểm tra đoạn liền kề

State tối thiểu gồm:

- nhân vật xuất hiện, vị trí, ngoại hình và trang phục;
- cảm xúc và mức hiểu biết của nhân vật;
- địa điểm, thời điểm và điều kiện ánh sáng;
- đạo cụ đang có, vị trí và trạng thái;
- open loop đang mở hoặc đã đóng;
- bí mật hoặc payoff chưa được phép tiết lộ.

`state_out` của beat/segment trước phải tương thích với `state_in` của beat/segment sau. Chênh lệch có chủ đích phải có transition hoặc hành động giải thích.

### 6. Artifact downstream phải có mapping bắt buộc

Scene, shot, video prompt, narration, voice và subtitle lưu tối thiểu:

```text
narrative_contract_id
narrative_revision
beat_id
production_segment_id nếu có
context_snapshot_id
dependency_revision
```

Artifact không có mapping hoặc dùng revision cũ chuyển `stale` hoặc `blocked`. Một prompt đẹp về camera nhưng không truyền thông tin, cảm xúc hoặc micro-payoff của beat không được coi là đạt.

### 7. Quality gate nằm trong đường chạy chính

Auto-run có cổng chất lượng sau story và sau prompt:

```text
develop_story
  -> story_quality_gate
  -> review_story
  -> generate_shots
  -> generate_prompts
  -> prompt_quality_gate
  -> review_prompts
  -> voice/subtitle/render
```

`full_auto` có thể tự đi qua cảnh báo cấu hình được, nhưng không được tự vượt blocking error về canon, originality, hook-payoff, missing beat mapping, stale narration hoặc continuity nghiêm trọng.

### 8. Targeted repair theo phạm vi dependency

Repair nhận artifact gốc, lỗi chất lượng, beat contract, state in/out và canon liên quan. Mặc định tối đa hai lần. Repair kỹ thuật không được đổi central promise, payoff, CTA hoặc narration đã duyệt nếu lỗi không thuộc nội dung đó.

Nếu một beat đổi, hệ thống stale scene/shot/prompt/voice/subtitle phụ thuộc beat đó và các đoạn sau bị ảnh hưởng continuity. Artifact độc lập không bị tạo lại.

### 9. Release Snapshot tách khỏi social publishing

Sau quality gate và render/review, hệ thống tạo `VideoContentReleaseSnapshot` có project ID, narrative revision, render artifact revision, metadata revision và trạng thái duyệt.

Luồng social publishing tương lai chỉ nhận snapshot này theo giao diện read-only. Kết quả đăng, post ID, permalink, retry hoặc lỗi nền tảng được lưu trong domain publishing và không ghi ngược vào content artifacts. Nếu content thay đổi, snapshot cũ chuyển stale và publishing phải tạo batch mới.

## Di chuyển dữ liệu

- Project cũ có thể tạo Narrative Contract draft từ `story_strategy`, `detailed_script`, `retention_plan_json`, Project Memory và target timeline hiện có.
- Không tự duyệt contract migration.
- Scene/shot cũ chưa có `beat_id` vẫn hiển thị nhưng không được coi là sẵn sàng cho quality gate mới cho tới khi mapping hoàn tất hoặc feature flag bị tắt.
- Database migration chỉ bổ sung bảng/cột; không xóa source block, Project Memory hoặc target timeline hiện có.

## Rủi ro và giảm thiểu

- Tăng số bước AI: tái sử dụng context snapshot, chạy candidate song song và chỉ repair phần lỗi.
- Beat graph quá chi tiết: giữ contract cấp nội dung tách khỏi production segment cấp dựng.
- Quality gate chặn quá nhiều: phân biệt blocking error, warning và override có lý do; không cho tổng điểm che lỗi chặn.
- State ledger báo sai: lưu evidence và cho người dùng xác nhận transition có chủ đích.
- Trùng nguồn sự thật: Narrative Contract đã duyệt là nguồn chuẩn nội dung; Project/Series Memory cung cấp context và canon, không ghi đè contract âm thầm.
- Social publishing làm bẩn content domain: chỉ giao tiếp bằng immutable/versioned release snapshot.

## Khả năng quay lui

Có thể tắt quality gate bắt buộc và quay về workflow hiện tại bằng feature flag. Dữ liệu contract, beat, state và snapshot chỉ bổ sung. Artifact cũ vẫn đọc được; không drop bảng hoặc ghi đè revision cũ khi rollback runtime.
