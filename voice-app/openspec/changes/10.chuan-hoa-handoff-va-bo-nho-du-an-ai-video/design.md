## Tổng quan thiết kế

```text
VideoAnalysisPackage từ change 9
        |
        v
Handoff có cấu trúc và chờ duyệt
        |
        +-- Bài học được phép học
        +-- Điều không được copy
        +-- Kịch bản mới
        +-- Retention map
        +-- Bằng chứng nguồn
        |
        v
Bộ nhớ Dự án
        |
        +-- Dự án đơn lẻ: nguồn chuẩn cấp dự án
        +-- Dự án series: kết hợp với Series Canon
        |
        v
Bộ biên dịch ngữ cảnh theo nhiệm vụ
        |
        +-- Story
        +-- Shot
        +-- Prompt
        +-- Voice
        +-- Subtitle
```

## Quyết định thiết kế

### 1. Handoff là một artifact bền vững

Thêm mô hình khái niệm `VideoInspirationHandoff`:

```text
id
job_id
analysis_package_id
schema_version
status
target_language
approved_script_revision
payload_json
created_project_id
created_at
updated_at
```

Trạng thái tối thiểu:

```text
draft | ready_for_review | approved | consumed | stale | failed
```

Frontend có thể tiếp tục dùng draft tạm để tạo trải nghiệm nhanh, nhưng project cuối phải được tạo từ handoff backend có mã và phiên bản. Reload trình duyệt không làm mất dữ liệu handoff đã duyệt.

### 2. Handoff giữ cấu trúc, không chỉ source block text

Payload tối thiểu:

```text
source_analysis_ref
target_audience
video_goal
platform
content_spine
hook_contract
retention_map
approved_script
character_and_setting_state
visual_grammar_to_learn
audio_grammar_to_learn
originality_boundaries
must_have
avoid
evidence_refs
limitations
```

Source blocks cũ vẫn được dựng để tương thích, nhưng AI Video ưu tiên dữ liệu có cấu trúc. Việc rút gọn phải theo nhóm và mức quan trọng, không cắt độc lập từng block mà không biết dữ liệu nào quan trọng hơn.

### 3. Tách nội dung nguồn và nội dung đích

Hệ thống duy trì ba lớp:

```text
Nguồn quan sát được
Video, transcript, shot, hình ảnh, âm thanh và retention dự đoán

Bài học được phép học
Insight, cấu trúc, nhịp nội dung, ngôn ngữ điện ảnh và âm thanh

Nội dung đích đã duyệt
Hook mới, câu chuyện mới, narration mới, hình ảnh mới và CTA mới
```

Transcript nguồn chỉ là bằng chứng và dữ liệu đối chiếu. Voice và subtitle bắt buộc dùng narration đích đã duyệt.

### 4. Bộ nhớ Dự án dùng cùng nguyên tắc với Bộ nhớ Series

Thêm `memory_scope = project` vào nền thẻ nhớ hoặc mô hình tương đương. Thẻ dự án tối thiểu gồm:

- `project_identity`;
- `target_audience`;
- `video_goal`;
- `content_spine`;
- `hook_and_payoff`;
- `retention_map`;
- `character_state`;
- `setting_state`;
- `visual_direction`;
- `audio_direction`;
- `voice_and_language`;
- `approved_decision`;
- `must_have`;
- `avoid`;
- `source_evidence`.

Chỉ dữ liệu người dùng nhập hoặc kết quả đã duyệt trở thành memory chuẩn. Candidate bị loại, prompt lỗi và suy luận confidence thấp được giữ trong lịch sử artifact nhưng không tự tham gia gói ngữ cảnh.

### 5. Dự án thuộc series có thứ tự ưu tiên rõ

```text
Canon cố định của series
> thay đổi series đã được duyệt
> yêu cầu dự án đã được người dùng xác nhận
> Master Story hoặc kịch bản dự án đã duyệt
> quyết định sáng tạo đã khóa
> dữ liệu đang làm việc chưa duyệt
```

Bộ nhớ Dự án không được đổi fixed trait, quy tắc thế giới hoặc trạng thái series đã duyệt. Nếu dự án phát hiện thay đổi dài hạn, hệ thống tạo đề xuất cập nhật series riêng.

### 6. Bộ biên dịch ngữ cảnh theo nhiệm vụ

Story nhận đối tượng, mục tiêu, insight, content spine, hook, retention và originality boundaries.

Shot nhận timeline đích, beat nội dung, trạng thái scene, continuity, hình ảnh và âm thanh liên quan.

Prompt nhận đúng segment, trạng thái đầu/cuối, hành động, camera, continuity, reference và retention role.

Voice nhận narration đích, người nói, ngôn ngữ, cảm xúc, tốc độ và thời lượng.

Subtitle nhận lời voice cuối, timing và quy tắc hiển thị; không nhận toàn bộ transcript nguồn.

### 7. Timeline đích được tái cấu trúc theo mục tiêu mới

Không sao chép timeline nguồn từng shot. Dịch vụ `TargetTimelinePlanner` nhận:

- content spine và retention map mới;
- thời lượng đích;
- số segment và giây mỗi segment;
- mục đích video;
- nền tảng và tỷ lệ;
- narration density;
- bài học nhịp dựng từ nguồn.

Kết quả là các beat đích mới, mỗi beat có nội dung, câu hỏi, thông tin mới, micro-payoff, hình ảnh, âm thanh và vai trò giữ chân. Mỗi beat giữ liên kết tới bài học nguồn nếu có nhưng không tái tạo chuỗi cảnh nguồn.

### 8. Truy xuất và rút gọn có ưu tiên

Không gửi toàn bộ analysis package vào mọi yêu cầu. Mỗi tác vụ chọn đúng dữ liệu và lưu `context_snapshot`. Dữ liệu bắt buộc như hook, payoff, content spine, narration đích và canon được ghim. Transcript nguồn, frame notes và evidence dài chỉ lấy đoạn liên quan.

### 9. Stale và phiên bản dùng nền change 8

Handoff lưu revision của analysis package và script. Project Memory, target timeline và artifact lưu dependency snapshot. Sửa transcript nguồn không tự stale voice nếu narration đích không đổi; sửa narration đích phải stale voice, subtitle và package liên quan.

### 10. Người dùng vẫn kiểm soát cấu hình sản xuất

Handoff không tự quyết định thị trường, ngôn ngữ cuối, thời lượng, tỷ lệ, voice hoặc chế độ chạy nếu người dùng chưa xác nhận. Tạo project mặc định ở chế độ thủ công và không bắt đầu auto-run.

## Di chuyển dữ liệu

- Handoff cũ từ sessionStorage vẫn nhập được và được chuyển thành handoff backend khi người dùng xác nhận.
- Source blocks cũ tiếp tục hiển thị và có thể dựng từ payload mới.
- Project cũ không có Project Memory dùng source blocks và trường project hiện tại làm fallback.
- Không bắt buộc mọi project phải thuộc series.

## Rủi ro và giảm thiểu

- Trùng dữ liệu giữa source blocks và payload mới: payload cấu trúc là chuẩn, source blocks là projection tương thích.
- Project Memory lưu quá nhiều bản nháp: chỉ approved decision và dữ liệu người dùng trở thành memory chuẩn.
- Timeline đích copy quá sát nguồn: bắt buộc originality boundaries và kiểm tra tương đồng ở change 11.
- Dữ liệu series và dự án mâu thuẫn: áp dụng thứ tự ưu tiên và tạo lỗi canon.
- Handoff phức tạp cho người không viết mã: UI trình bày theo mục Nội dung, Giữ chân, Hình ảnh, Âm thanh, Điều giữ lại và Điều tránh.

## Khả năng quay lui

Có thể tắt handoff cấu trúc và dựng source blocks cũ từ payload. Project Memory là dữ liệu bổ sung; project vẫn dùng các trường và source block hiện tại khi chức năng mới bị tắt.
