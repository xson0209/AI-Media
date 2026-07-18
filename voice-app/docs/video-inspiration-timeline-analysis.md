# Phân tích Video Inspiration theo timeline

Tài liệu này mô tả gói phân tích `VideoAnalysisPackage` tạo bởi Video Inspiration sau change `9.phan-tich-video-da-phuong-thuc-theo-dong-thoi-gian`.

## Gói phân tích

Mỗi lần bấm **Phân tích video**, hệ thống tạo gói `video_analysis_package.v1` gồm:

- metadata video nguồn và chế độ phân tích;
- danh sách shot theo `start_seconds`, `end_seconds`, `duration_seconds`;
- keyframe gắn với từng shot;
- transcript segment có timestamp, nguồn và cấp chính xác;
- timeline âm thanh độc lập với transcript;
- chữ trên màn hình từ OCR hoặc vision;
- beat giữ chân dự đoán kèm bằng chứng timestamp;
- coverage metrics và limitations.

Gói được lưu trong DB tại `analysis_package_json` và dưới dạng artifact JSON trong thư mục `video_inspiration/<job_id>/analysis/`.

## Chế độ phân tích

`quick` dùng ít keyframe hơn và phù hợp khi cần phản hồi nhanh.

`high_quality` dùng ngưỡng phát hiện shot nhạy hơn và cho phép nhiều keyframe hơn ở shot dài hoặc có biến động.

Cả hai chế độ dùng cùng schema đầu ra để các bước sau không phải xử lý hai định dạng khác nhau.

## Timestamp transcript

Transcript được lưu thành segment. Trường `timestamp_precision` cho biết độ chính xác:

- `segment`: STT trả timestamp segment rõ ràng;
- `chunk`: hệ thống chỉ biết đoạn audio chunk, không biết thời điểm từng từ;
- `file`: chỉ có timestamp toàn file hoặc bản sửa của người dùng.

Hệ thống không tạo timestamp chính xác tới từng từ nếu STT không cung cấp dữ liệu đó.

## Chữ trên màn hình

Mỗi text event gồm:

- thời gian bắt đầu và kết thúc theo shot;
- nội dung chữ;
- vai trò như `hook`, `title`, `evidence`, `cta`, `source_subtitle` hoặc `unknown`;
- vùng tương đối nếu công cụ phân tích cung cấp;
- confidence;
- source `vision` hoặc `user_edited`.

Người dùng có thể sửa text event trong UI. Khi sửa, package cũ bị đánh dấu chưa còn đầy đủ để người dùng chạy lại phân tích nếu cần.

## Âm thanh

Timeline âm thanh không phụ thuộc transcript. Hệ thống có thể tạo các event:

- `speech`;
- `silence`;
- `energy_change`;
- `ambience`;
- `possible_audio_clutter`.

Các event âm thanh dùng bằng chứng kỹ thuật từ WAV đã tách. Hệ thống không khẳng định tên bài hát, nguồn nhạc hoặc loại SFX cụ thể nếu không có bằng chứng.

## Retention dự đoán

Retention trong Video Inspiration là `predicted_from_content`. Đây là dự đoán từ nội dung video, không phải dữ liệu retention thật từ nền tảng.

Mỗi beat giữ chân ưu tiên nội dung:

- câu hỏi người xem đang giữ;
- lời hứa nội dung;
- thông tin mới;
- thay đổi cảm xúc hoặc mức độ quan trọng;
- câu hỏi được trả lời;
- vòng mở mới;
- micro-payoff;
- lý do xem tiếp;
- rủi ro tụt giữ chân;
- bằng chứng từ shot, transcript, text event hoặc audio event.

Rubric mặc định ưu tiên 75% nội dung và 25% cách thể hiện. Vì vậy một đoạn ít cắt cảnh nhưng có thông tin mới vẫn có thể tốt; một đoạn dựng nhanh nhưng lặp ý vẫn bị coi là rủi ro.

## Coverage và limitations

Coverage metrics giúp biết phân tích đang đầy đủ hay chỉ một phần:

- `shot_coverage_ratio`;
- `visual_description_coverage_ratio`;
- `transcript_coverage_ratio`;
- `audio_event_coverage_ratio`;
- `retention_beat_coverage_ratio`.

`analysis_completeness` có ba trạng thái:

- `full`: các modality chính đủ phủ;
- `partial`: có phân tích nhưng thiếu một phần;
- `insufficient`: thiếu dữ liệu để kết luận.

UI phải hiển thị limitations để người dùng biết phần nào là quan sát được, phần nào là suy luận confidence thấp, và phần nào chưa phân tích được.

## Không gọi provider video

Capability này chỉ đọc video nguồn, trích audio/frame, chạy STT/vision/planning nếu được cấu hình, và lưu dữ liệu phân tích. Nó không gọi Veo, không submit prompt video, không tạo clip provider và không tiêu credit tạo video.
