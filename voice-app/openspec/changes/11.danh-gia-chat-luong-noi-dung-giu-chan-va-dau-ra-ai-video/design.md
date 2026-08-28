## Tổng quan thiết kế

```text
VideoAnalysisPackage + Handoff + Project Memory
        |
        v
Ba phương án nội dung
        |
        v
Đánh giá độc lập + Tổng hợp
        |
        v
Timeline đích + Story + Shot + Prompt
        |
        v
Voice + Subtitle
        |
        v
Báo cáo chất lượng toàn luồng
        |
        +-- Retention dự đoán
        +-- Retention thực tế nếu có
        +-- Lỗi chặn
        +-- Cảnh báo
        +-- Gợi ý sửa
```

## Quyết định thiết kế

### 1. Báo cáo chất lượng có nhiều tầng

`VideoQualityReport` gồm:

```text
input_analysis_quality
handoff_quality
project_memory_quality
candidate_quality
content_retention_quality
originality_quality
story_quality
shot_quality
prompt_quality
voice_quality
subtitle_quality
cross_stage_consistency
blocking_errors
warnings
recommended_actions
overall_status
```

Không dùng một tổng điểm duy nhất để che lỗi chặn. Báo cáo có thể đạt điểm cao nhưng vẫn không được qua nếu vi phạm canon, hook-payoff, narration hoặc originality nghiêm trọng.

### 2. Rubric giữ chân ưu tiên nội dung

Điểm mặc định 100:

```text
15 điểm: đúng khách hàng, vấn đề và nhu cầu
15 điểm: hook, lời hứa và câu hỏi trung tâm
15 điểm: nội dung tiến triển có logic
10 điểm: thông tin hoặc giá trị mới ở mỗi beat
10 điểm: tăng cảm xúc, xung đột, mức độ quan trọng hoặc bằng chứng
10 điểm: micro-payoff, payoff và CTA
10 điểm: hình ảnh hỗ trợ nội dung
 6 điểm: voice và cách nói
 5 điểm: chữ và subtitle
 4 điểm: dựng và âm thanh hỗ trợ
```

Tổng nội dung là 75 điểm; cách thể hiện là 25 điểm. Trọng số có thể thay đổi theo loại video nhưng nội dung không được thấp hơn 60% nếu không có cấu hình đặc biệt được người dùng xác nhận.

### 3. Mỗi beat phải chứng minh đóng góp nội dung

Kiểm tra mỗi beat bằng sáu câu hỏi:

```text
Đoạn này có vai trò gì?
Người xem biết thêm điều gì?
Cảm xúc hoặc nhận thức thay đổi thế nào?
Câu hỏi nào được trả lời?
Câu hỏi nào khiến họ xem tiếp?
Nếu xóa đoạn này, câu chuyện mất gì?
```

Beat không có đóng góp rõ bị gắn `content_stagnation_risk`. Lặp có chủ đích để nhấn mạnh vẫn được phép nếu có lý do và không kéo dài quá mức.

### 4. Hook được chấm đa lớp và phải khớp payoff

Hook gồm:

- nội dung hoặc vấn đề;
- lời nói;
- hình ảnh;
- chữ trên màn hình;
- âm thanh;
- câu hỏi tâm lý;
- lời hứa giá trị.

Lỗi chặn gồm clickbait nghiêm trọng, lời hứa không được trả, hook không phù hợp khách hàng, hoặc hook dùng thông tin sai. AI có thể đề xuất ba biến thể hook mới nhưng người dùng duyệt bản chọn.

### 5. Candidate dùng chung một engine đánh giá

Video Inspiration và Story Studio dùng cùng hợp đồng ba candidate từ change 7. Candidate được tạo độc lập, dùng cùng context snapshot, kiểm tra khác biệt và chấm bằng critic tách biệt. Báo cáo lưu lý do, bằng chứng, điểm mạnh, điểm yếu, rủi ro và phần được lấy vào bản tổng hợp.

### 6. Độ nguyên bản được kiểm tra theo nhiều lớp

So sánh nguồn và bản đích ở:

- câu thoại hoặc narration;
- thứ tự ý và beat;
- nhân vật và bối cảnh cụ thể;
- chuỗi shot;
- hook và payoff;
- chữ trên màn hình;
- visual motif đặc trưng.

Học insight, nhịp, loại hook hoặc camera grammar không tự coi là sao chép. Hệ thống phải chỉ rõ phần giống và lý do rủi ro, không chỉ trả một phần trăm mơ hồ.

### 7. Prompt được đánh giá theo nội dung trước hình thức

Mỗi prompt phải ánh xạ tới một target content beat. Kiểm tra prompt có thể hiện đúng thông tin mới, cảm xúc, hành động, micro-payoff và continuity không. Một prompt đẹp về camera nhưng không truyền nội dung beat phải bị đánh trượt hoặc cảnh báo nghiêm trọng.

Prompt quality tiếp tục dùng canon và repair của change 7. Repair không được đổi lời hứa, payoff hoặc narration đã duyệt nếu lỗi chỉ nằm ở camera hoặc kỹ thuật.

### 8. Voice và subtitle có quality gate riêng

Voice kiểm tra:

- đúng narration revision;
- phát âm và ngôn ngữ;
- tốc độ so với duration;
- khoảng ngắt và nhấn từ khóa;
- cảm xúc phù hợp beat;
- không cắt mất câu;
- mức âm lượng và nguy cơ bị nhạc/SFX che nếu có dữ liệu.

Subtitle kiểm tra:

- khớp nội dung voice cuối;
- timing không trùng hoặc vượt duration;
- độ dài dòng và tốc độ đọc;
- từ khóa và câu đầu xuất hiện đúng lúc;
- không tiết lộ payoff quá sớm;
- vùng hiển thị không che chủ thể theo metadata khi có.

### 9. Retention thật là dữ liệu tùy chọn

Thêm `PlatformRetentionDataset`:

```text
platform
video_duration_seconds
data_points
average_watch_time
completion_rate
rewatch_rate
cta_click_rate
conversion_rate
source_type
imported_at
```

Nguồn có thể là CSV/JSON theo định dạng hỗ trợ hoặc nhập tay. Không tự đăng nhập nền tảng. Dữ liệu được chuẩn hóa về phần trăm thời lượng để so sánh video khác duration.

### 10. So sánh predicted và actual không khẳng định nhân quả

Hệ thống căn mốc tụt, giữ ổn định hoặc xem lại với content beat, shot, lời nói, chữ và âm thanh. Báo cáo dùng ngôn ngữ “có tương quan”, “có khả năng liên quan” hoặc “cần kiểm chứng”, không nói chắc chắn một yếu tố là nguyên nhân nếu không có thử nghiệm kiểm soát.

### 11. Kiểm thử end-to-end không gọi Veo

Bộ kiểm thử gồm video fixture ngắn có đáp án timeline, retention beat, transcript, candidate, handoff, target timeline, prompt, voice và subtitle. AI được giả lập hoặc dùng dữ liệu cố định cho kiểm thử chính. Có thể tạo voice thật bằng engine hiện có nếu môi trường sẵn sàng, nhưng không submit prompt video hoặc tạo clip.

## Trạng thái chất lượng

```text
not_checked | checking | passed | needs_review | blocked | stale
```

Lỗi chặn tối thiểu:

- canon nghiêm trọng;
- hook-payoff không nhất quán;
- nội dung đích copy sát nguồn vượt chính sách;
- prompt không thể hiện beat bắt buộc;
- voice dùng sai narration hoặc ngôn ngữ;
- subtitle không khớp voice cuối;
- dữ liệu đầu vào thiếu nhưng hệ thống báo đầy đủ.

## Rủi ro và giảm thiểu

- Điểm số tạo cảm giác chính xác giả: luôn hiển thị tiêu chí, bằng chứng và confidence.
- AI critic thiên vị: dùng critic tách biệt, schema cố định và test fixture.
- Retention thật bị hiểu thành nguyên nhân: chỉ báo tương quan và khuyến nghị thử nghiệm.
- Quality gate làm pipeline chậm: kiểm tra theo tầng, chạy song song phần độc lập và cho phép chế độ nhanh.
- Người dùng không hiểu báo cáo: ưu tiên lỗi chính, ảnh hưởng và hành động sửa bằng tiếng Việt.

## Khả năng quay lui

Có thể tắt quality gate bắt buộc và dùng báo cáo ở chế độ tư vấn. Artifact cũ vẫn hoạt động; quality report là dữ liệu bổ sung và không xóa kết quả trước đó.
