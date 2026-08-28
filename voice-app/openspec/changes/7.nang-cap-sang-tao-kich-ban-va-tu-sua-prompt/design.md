## Tổng quan thiết kế

```text
Gói ngữ cảnh đã đóng băng từ change 6
        |
        +--> AI tạo hướng Hook/giữ chân
        +--> AI tạo hướng Cảm xúc/drama
        +--> AI tạo hướng Hình ảnh/hành động
        |
        v
Ba candidate có cấu trúc
        |
        v
AI đánh giá độc lập theo rubric
        |
        +--> Chọn một candidate
        |
        +--> Tổng hợp phần tốt nhất
                 |
                 v
          Master Story chờ người dùng duyệt

Prompt nháp
   |
   v
Kiểm tra canon + chất lượng ngữ nghĩa
   |
   +--> Đạt: chờ người dùng duyệt
   |
   +--> Chưa đạt: AI sửa có giới hạn -> kiểm tra lại
```

## Quyết định thiết kế

### 1. Ba candidate dùng cùng một ảnh chụp ngữ cảnh

Trước khi tạo candidate, hệ thống tạo `context_snapshot_id` từ change 6. Cả ba yêu cầu AI dùng cùng phiên bản canon, trạng thái và nguồn tập hiện tại. Việc series thay đổi trong lúc đang chạy không làm ba candidate dùng ba nền dữ liệu khác nhau.

### 2. Ba yêu cầu độc lập và có chiến lược khóa

Mỗi candidate được tạo bằng một yêu cầu riêng, có chiến lược:

- hook và giữ chân mạnh;
- cảm xúc và drama mạnh;
- hình ảnh và hành động mạnh.

Các yêu cầu có thể chạy song song. Nếu một candidate lỗi schema hoặc lỗi tạm thời, chỉ candidate đó được thử lại. Hệ thống không được sao chép một candidate rồi thay vài câu để đủ số lượng.

### 3. Candidate có cấu trúc và dấu vết tạo

Mỗi candidate lưu:

```text
strategy_type
title
hook
logline
full_story
key_beats
character_emotions
visual_moments
motion_beats
retention_plan
must_have
avoid
continuity_updates
strengths_claimed
risks_claimed
context_snapshot_id
model_label
generation_attempt
created_at
```

Thông tin model chỉ dùng nhãn an toàn; không lưu credential hoặc nội dung nội bộ nhạy cảm.

### 4. Bước đánh giá tách khỏi bước tạo

Một yêu cầu đánh giá độc lập nhận ba candidate, rubric và gói canon cô đọng. Nó không được sửa candidate trong lúc chấm. Kết quả gồm điểm từng tiêu chí, lý do, bằng chứng, điểm mạnh, điểm yếu, rủi ro và khuyến nghị phần nên lấy để tổng hợp.

Rubric tối thiểu:

```text
Đúng canon và nguồn người dùng
Khác biệt chiến lược
Hook và khả năng giữ chân
Cảm xúc và logic nhân vật
Hình ảnh và khả năng chuyển thành panel/shot
Nhịp kể và payoff
Phù hợp thị trường, ngôn ngữ và mục tiêu đầu ra
Rủi ro sản xuất
```

Trọng số thay đổi theo `truyen_anh`, `video_truyen` hoặc `ca_hai`.

### 5. Tổng hợp là một bước sáng tạo có kiểm soát

Người dùng có thể chọn candidate đơn hoặc yêu cầu tổng hợp. Bước tổng hợp nhận ba candidate và đánh giá, đồng thời phải chỉ rõ phần nào được lấy từ candidate nào. Master Story cuối phải là một câu chuyện liền mạch, dùng đúng schema và qua kiểm tra canon trước khi chờ duyệt.

### 6. Bộ kiểm tra chất lượng prompt có điểm và lỗi chặn

Ngoài kiểm tra canon từ change 6, prompt được chấm theo:

```text
25 điểm: đúng canon và trạng thái truyện
20 điểm: nhận diện nhân vật và nhất quán hình ảnh
15 điểm: hành động rõ và phù hợp thời lượng
10 điểm: continuity với panel/segment trước và sau
10 điểm: camera, framing và bố cục
10 điểm: khả năng render, không mâu thuẫn nội bộ
 5 điểm: ngôn ngữ, voice và vùng phụ đề
 5 điểm: giữ chân, chuyển cảnh và âm thanh
```

Ngưỡng mặc định là 85/100 và không có lỗi chặn. Ngưỡng phải cấu hình được nhưng không được hạ âm thầm theo từng lần chạy.

Lỗi chặn tối thiểu:

- thay đổi đặc điểm cố định;
- sai nhân vật, đạo cụ, địa điểm hoặc bí mật canon;
- hành động chính không rõ hoặc vượt khả năng thời lượng;
- timeline trùng, thiếu hoặc đảo thứ tự;
- trạng thái đầu và cuối mâu thuẫn;
- prompt chứa chỉ dẫn loại trừ nhau;
- prompt ảnh bị viết như prompt video hoặc ngược lại.

### 7. Tự sửa chỉ sửa lỗi đã biết

Vòng sửa dùng prompt gốc, kết quả kiểm tra và canon liên quan. AI phải trả về prompt mới cùng danh sách thay đổi. Mỗi lần sửa tạo một phiên bản mới, không ghi đè bản cũ.

Mặc định tối đa hai lần sửa tự động. Nếu vẫn chưa đạt, trạng thái chuyển `needs_review` và UI giải thích phần còn lỗi. Người dùng có thể sửa thủ công hoặc yêu cầu tạo lại từ đầu.

### 8. Không dùng kết quả render thật trong change này

Chất lượng được đánh giá bằng schema, quy tắc, AI phản biện và bộ bài kiểm tra. Không gửi prompt sang Veo, không tiêu credit và không dựa vào clip provider để hoàn tất proposal này.

## Trạng thái đề xuất

Candidate:

```text
pending | generating | completed | failed | superseded
```

Đánh giá:

```text
pending | reviewing | completed | failed
```

Prompt:

```text
draft | checking | repairing | passed | needs_review | approved | stale
```

## Rủi ro và giảm thiểu

- Ba candidate vẫn giống nhau: dùng ba yêu cầu riêng, chiến lược khóa và kiểm tra độ khác biệt.
- AI tự chấm thiên vị: tách yêu cầu đánh giá, không cung cấp thứ tự ưu tiên và yêu cầu bằng chứng.
- Tổng hợp tạo câu chuyện rời rạc: kiểm tra schema, continuity và canon sau tổng hợp.
- Tự sửa làm prompt tệ hơn: giữ phiên bản, so sánh trước/sau, giới hạn số lần và không tự duyệt.
- Chi phí tăng: cho phép chạy song song, thử lại riêng phần lỗi và không gọi provider video.

## Khả năng quay lui

Có thể tắt tạo candidate AI và quay về workflow chọn Master Story thủ công. Các candidate, đánh giá và phiên bản prompt mới chỉ bổ sung dữ liệu. Prompt đã duyệt cũ vẫn sử dụng được nếu không bị stale vì thay đổi khác.
