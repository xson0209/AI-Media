# Đề xuất: 02 — tạo truyện từ Gói nguồn

## Vì sao cần làm

Lát 01 đã chuẩn hóa `Gói nguồn / Source Package` cho cả nguồn truyện và nguồn video. Tuy nhiên Story Studio hiện vẫn còn một lớp trung gian riêng khi tạo candidate:

- tự compile source document thành payload riêng;
- tự cắt một bản text cho memory;
- tự nhét structured source theo shape cũ vào `creative_brief`;
- lưu fingerprint vào `dependency_fingerprint` nhưng fingerprint này chưa phản ánh rõ một Gói nguồn chuẩn duy nhất.

Điều này làm Story Studio vẫn có hai kiểu hiểu nguồn song song:

1. nguồn cũ dựa trên `compile_context()`;
2. nguồn chuẩn mới dựa trên `SourcePackage`.

Lát 02 cần gom Story Studio về một seam rõ hơn: candidate generation đọc Gói nguồn chuẩn, còn output công khai của candidate/master giữ nguyên.

## Thay đổi đề xuất

Refactor Story Studio để:

- compile Gói nguồn chuẩn từ `StoryEpisodeSourceDocument`;
- dùng Gói nguồn đó làm `structured_source` trong `creative_brief`;
- lưu fingerprint của Gói nguồn vào `dependency_fingerprint`;
- tách rõ ngôn ngữ giao diện và ngôn ngữ nội dung: giao diện vẫn hiển thị tiếng Việt, còn truyện/video dùng `target_language` do người dùng chọn;
- mở lựa chọn ngôn ngữ nội dung để không còn bị khóa cứng ở tiếng Việt/tiếng Anh;
- vẫn tạo đúng 3 candidate, vẫn chấm độc lập, vẫn chọn master như cũ;
- không đổi DB schema và không đổi shape chính của API.

## Phạm vi

Trong change này:

- Story Studio tạo candidate từ Gói nguồn chuẩn;
- structured source của candidate có shape rõ ràng hơn;
- Story Studio, Comic handoff và Video Inspiration không được nhầm “UI tiếng Việt” với “ngôn ngữ nội dung”;
- test xác nhận candidate payload bám vào Gói nguồn;
- test xác nhận lựa chọn ngôn ngữ nội dung không bị ép về `vi/en` trong các seam liên quan;
- validate, chạy test, fix lỗi nếu có, rồi test lại.

## Ngoài phạm vi

- Chưa refactor toàn bộ UI Story Studio ngoài phần nhãn/option ngôn ngữ liên quan trực tiếp.
- Chưa đổi quy trình tạo video handoff.
- Chưa thay đổi schema DB.
- Chưa triển khai stale/rebuild tổng thể cho mọi artifact.
- Chưa thay đổi chiến lược 3 candidate + select/synthesize master.

## Tên change

`02-tao-truyen-tu-goi-nguon`
