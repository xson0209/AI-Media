## Cách tiếp cận

Thay một lần rewrite đơn bằng pipeline nhiều bước có cấu trúc:

```text
analysis đã có
  -> tạo creative brief ngắn
  -> tạo 2-3 bản nháp kịch bản khác hướng
  -> chấm điểm từng bản theo rubric
  -> tổng hợp bản cuối tốt nhất
  -> chuyển bản cuối thành các trường AI Video
  -> mở /ai-video?draft=video-inspiration
```

Pipeline này vẫn dùng dữ liệu gốc đã có: transcript, visual summary, frame notes, analysis_json và định hướng người dùng. Dữ liệu dài không nhồi hết vào `visual_style`; dữ liệu chi tiết đi vào source blocks.

## Trường đầu ra bắt buộc

Bản kịch bản tối ưu cuối cùng cần có cấu trúc máy đọc được, ví dụ:

- `title`: tên ý tưởng.
- `big_idea`: ý chính.
- `hook_3_5s`: hook giữ chân người xem trong 3-5 giây đầu.
- `viewer_question`: câu hỏi khiến người xem muốn ở lại.
- `curiosity_gap`: điều còn bỏ ngỏ để giữ tò mò.
- `script`: lời kể hoặc thoại chính.
- `segments`: các đoạn/cảnh.
- `retention_plan`: nhịp giữ chân người xem.
- `sound_design_plan`: hướng âm thanh và hiệu ứng âm thanh.
- `visual_suggestions`: gợi ý hình ảnh.
- `ai_video_source_blocks`: nội dung đã chia sẵn theo các ô AI Video.
- `originality_note`: ghi chú không copy sát video gốc.

## Hook 3-5 giây đầu

Hook ở đây là phần mở đầu giữ chân người xem trong 3-5 giây đầu tiên. Nó không chỉ là một câu chữ. Nó phải gồm:

- câu mở hoặc hành động mở đầu;
- hình ảnh mở đầu;
- cảm xúc hoặc câu hỏi tạo tò mò;
- lời hứa nội dung hoặc xung đột chính;
- âm thanh mở đầu nếu phù hợp, ví dụ silence drop, hit, riser nhẹ hoặc nhịp gõ.

Nếu video target là short, hook phải đủ rõ để người xem hiểu vì sao nên xem tiếp trước khi lướt qua.

## Retention

Retention plan cần mô tả:

- câu hỏi người xem đang giữ trong đầu;
- beat 1, beat 2, beat 3 theo timeline;
- pattern interrupt hoặc visual surprise;
- điểm payoff;
- rủi ro người xem rời video;
- cách giảm rủi ro đó bằng hình ảnh, nhịp kể hoặc âm thanh.

Video Inspiration chỉ chuẩn bị retention ở cấp kịch bản/draft. AI Video phase 2 vẫn có thể phát triển tiếp retention map chi tiết theo shot.

## Sound Design Và Âm Thanh

Sound design trong kịch bản là chỉ dẫn dựng, chưa phải file âm thanh thật. Nó cần gồm:

- mood nhạc nền;
- ambience nền;
- cue theo từng đoạn như tap, whoosh, impact, riser, crumble, silence drop;
- thời điểm cue xuất hiện;
- mục đích cue, ví dụ nhấn hook, chuyển cảnh, tạo căng thẳng, payoff;
- mixing notes, đặc biệt là không để nhạc/SFX che narration.

Nếu shot không có lời, sound design phải giúp đoạn đó không bị trống.

## Tạo Nhiều Bản Nháp

Hệ thống nên tạo 2-3 candidate khác nhau:

- một bản ưu tiên hook mạnh;
- một bản ưu tiên cảm xúc/câu chuyện;
- một bản ưu tiên hình ảnh/nhịp dựng nếu video gốc có visual rõ.

Mỗi candidate phải có cùng cấu trúc cơ bản để chấm điểm được. Không lưu candidate làm bản cuối cho tới khi qua bước đánh giá và tổng hợp.

## Chấm Điểm Và Tổng Hợp

Rubric chấm điểm nên gồm:

- hook 3-5 giây đầu;
- độ khác biệt so với video gốc;
- độ rõ ý;
- khả năng dựng thành video;
- retention;
- sound design và âm thanh;
- phù hợp định hướng người dùng;
- phù hợp ngôn ngữ đầu ra.

Bản cuối không nhất thiết copy nguyên candidate điểm cao nhất. Nó có thể lấy hook của bản A, cấu trúc của bản B và sound design của bản C, miễn là output cuối nhất quán.

## Handoff Sang AI Video

Khi đưa sang AI Video, draft phải điền sẵn:

- `idea`: title, big idea, hook 3-5s, viewer question.
- `rough_script`: script cuối, segment outline.
- `character_notes`: nhân vật, bối cảnh, continuity gợi ý.
- `style_notes`: visual style, nhịp dựng, retention, sound design.
- `must_have`: hook, payoff, beat quan trọng, định hướng người dùng.
- `avoid`: rủi ro copy sát, lỗi âm thanh che lời, đoạn quá tĩnh, visual lặp.
- `visualStyle`: bản tóm tắt ngắn dưới giới hạn backend.

Không tự set thị trường, ngôn ngữ final, thời lượng, tỷ lệ, voice profile hoặc chế độ chạy.

## Rủi ro

- Chạy nhiều AI request sẽ lâu hơn. UI cần progress rõ bằng tiếng Việt.
- Nhiều candidate có thể tốn tài nguyên. Mặc định nên giới hạn 2 hoặc 3.
- Nếu AI trả thiếu trường bắt buộc, không được ghi bản cuối sai cấu trúc.
- Không log full script/candidate dài trong debug technical details.
