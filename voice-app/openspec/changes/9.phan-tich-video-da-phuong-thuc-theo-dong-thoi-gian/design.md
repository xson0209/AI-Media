## Tổng quan thiết kế

```text
Video nguồn
  |
  +-- Metadata video
  +-- Phát hiện ranh giới shot
  +-- Keyframe theo shot
  +-- Transcript có timestamp
  +-- Chuyển động và camera
  +-- Chữ trên màn hình
  +-- Nhạc, SFX, im lặng và năng lượng
  |
  v
Timeline đa phương thức
  |
  v
Phân tích nội dung giữ chân
  |
  v
VideoAnalysisPackage có phiên bản và bằng chứng
```

## Quyết định thiết kế

### 1. Shot là đơn vị phân tích hình ảnh chính

Không tiếp tục coi 12 frame cách đều là đại diện đủ cho toàn video. Hệ thống phát hiện ranh giới shot bằng FFmpeg hoặc bộ phát hiện cảnh phù hợp, sau đó chọn keyframe trong từng shot. Shot ngắn hoặc ít thay đổi có thể dùng một keyframe; shot dài, có chuyển động hoặc có thay đổi quan trọng có thể dùng nhiều keyframe trong giới hạn tài nguyên.

Mỗi shot lưu tối thiểu:

```text
shot_order
start_seconds
end_seconds
duration_seconds
keyframe_ids
visual_description_vi
subjects_json
setting_json
camera_json
subject_motion_json
transition_in
transition_out
on_screen_text_json
confidence_json
```

### 2. Transcript giữ thời gian và nguồn chỉnh sửa

Thêm các segment transcript gồm thời gian bắt đầu, kết thúc, văn bản, ngôn ngữ, người nói nếu có và mức tin cậy. Bản người dùng sửa được lưu riêng với nguồn `user_edited`; không ghi đè mất transcript thô.

Nếu công cụ STT không trả timestamp chi tiết, hệ thống dùng timestamp cấp chunk hoặc đánh dấu độ chính xác thấp, không tạo timestamp giả chính xác tới từng từ.

### 3. Timeline âm thanh tách khỏi transcript

Âm thanh nguồn được phân tích thành các sự kiện:

```text
speech
music
ambience
sfx
silence
energy_change
possible_audio_clutter
```

Mỗi sự kiện có mốc thời gian, mô tả, mức tin cậy và bằng chứng kỹ thuật khi có. Phân tích không khẳng định tên bài hát hoặc nguồn âm thanh nếu không xác định được.

### 4. Chữ trên màn hình là dữ liệu nội dung

OCR hoặc vision trích chữ theo shot, kèm thời gian, vùng tương đối, ngôn ngữ, mức tin cậy và loại vai trò như hook, tiêu đề, bằng chứng, CTA hoặc phụ đề nguồn. Chữ có độ tin cậy thấp được hiển thị để người dùng sửa.

### 5. Giữ chân toàn video lấy nội dung làm trục

Rubric phân tích dự đoán sử dụng tỷ trọng:

```text
75% nội dung
25% cách thể hiện
```

Nội dung gồm:

- đúng vấn đề và nhu cầu người xem;
- hook và lời hứa;
- câu hỏi trung tâm và khoảng tò mò;
- thông tin mới ở mỗi beat;
- logic tiến triển;
- mức tăng của xung đột, giá trị hoặc cảm xúc;
- micro-payoff;
- payoff trả đúng lời hứa;
- CTA phù hợp;
- đoạn lặp, lan man hoặc không đóng góp.

Cách thể hiện gồm hình ảnh, camera, voice nguồn, chữ, nhịp dựng và âm thanh hỗ trợ nội dung.

### 6. Mỗi beat nội dung phải giải thích lý do xem tiếp

Mô hình `ContentRetentionBeat`:

```text
order
start_seconds
end_seconds
role
viewer_question_before
content_promise
new_information
emotional_or_stakes_change
question_answered
new_open_loop
micro_payoff
why_continue
drop_off_risks
evidence_refs
confidence
```

Một beat có nguy cơ cao nếu không cung cấp thông tin mới, không thay đổi cảm xúc/mức độ quan trọng, không trả lời hoặc mở câu hỏi hợp lý và có thể xóa mà không ảnh hưởng câu chuyện.

### 7. Phân biệt dự đoán và dữ liệu retention thật

Change này chỉ lưu `retention_source = predicted_from_content`. UI phải dùng từ “dự đoán” hoặc “nguy cơ”, không tuyên bố chắc chắn người xem đã rời đi. Dữ liệu retention thực tế từ nền tảng được xử lý ở change 11.

### 8. Gói phân tích có cấu trúc và phiên bản

`VideoAnalysisPackage` tối thiểu gồm:

```text
schema_version
job_id
source_metadata
shots
transcript_segments
audio_events
on_screen_text_events
content_retention_beats
hook_analysis
story_structure
visual_grammar
audio_grammar
strengths
weaknesses
rewrite_opportunities
originality_boundaries
limitations
coverage_metrics
created_at
```

Gói lưu trong cơ sở dữ liệu hoặc artifact JSON có đường dẫn quản lý bởi lớp storage. Dữ liệu chính không chỉ tồn tại trong một trường text dài.

### 9. Kiểm tra độ phủ trước khi hoàn tất

Hệ thống báo tỷ lệ thời lượng có shot, transcript, mô tả hình ảnh, âm thanh và beat nội dung. Không cho trạng thái “phân tích đầy đủ” nếu các modality bắt buộc thiếu vượt ngưỡng cấu hình. Người dùng có thể tiếp tục chế độ transcript-only hoặc visual-only nhưng phải thấy cảnh báo rõ.

### 10. Quản lý tài nguyên theo hai chế độ

Chế độ nhanh dùng ít keyframe và phân tích âm thanh cơ bản. Chế độ chất lượng cao dùng shot boundary đầy đủ, nhiều keyframe hơn, OCR, chuyển động và âm thanh chi tiết. Cả hai dùng cùng schema để phase sau không phải xử lý hai định dạng khác nhau.

## Di chuyển dữ liệu

- Job cũ vẫn mở được với `schema_version` cũ.
- Có thể nâng job cũ bằng cách chạy lại phân tích từ video nguồn nếu tệp còn tồn tại.
- `visual_summary` và `analysis_json` cũ vẫn được dựng từ gói mới để tương thích UI và API cũ.
- Không tự xóa frame hoặc transcript cũ trong migration.

## Rủi ro và giảm thiểu

- Video dài tạo quá nhiều shot: giới hạn theo thời lượng, sampling thích ứng và chạy nền.
- Timestamp STT thiếu chính xác: lưu cấp chính xác và không bịa độ chi tiết.
- OCR sai: lưu confidence và cho sửa.
- Phân tích âm thanh nhầm: phân biệt đo lường kỹ thuật với suy luận AI.
- Vision không xem được frame: ghi limitations và không tạo mô tả giả.
- Phân tích retention thành chấm hiệu ứng: giữ tỷ trọng nội dung 75% và yêu cầu bằng chứng nội dung.

## Khả năng quay lui

Có thể giữ chế độ phân tích cũ bằng cấu hình. Các bảng timeline và gói phân tích là dữ liệu bổ sung. UI cũ vẫn dùng `visual_summary`, transcript và analysis text được dựng từ gói mới.
