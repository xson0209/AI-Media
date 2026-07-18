# Ticket breakdown: Tái cấu trúc quanh Gói nguồn

Các ticket dưới đây được chia theo hướng “làm từng lát nhỏ”. Mỗi ticket nên xong được một phần có thể kiểm tra, không sửa tất cả cùng lúc.

## 01 — Chuẩn hóa Gói nguồn / Source Package

**Blocked by:** Không có — có thể bắt đầu ngay.

**Việc cần làm:** Tạo định nghĩa thống nhất cho Gói nguồn: nó chứa gì, dữ liệu nào là bắt buộc, dữ liệu nào là tùy chọn, cách ghi nguồn/bằng chứng, cách biết phần nào dùng cho truyện hay video.

**Tiêu chí xong:**

- [ ] Có một dạng Gói nguồn dùng chung cho phân tích truyện và phân tích video.
- [ ] Gói nguồn ghi được nguồn gốc dữ liệu và bằng chứng chính.
- [ ] Có test chứng minh Gói nguồn có thể được tạo và đọc lại ổn định.
- [ ] Chưa bắt buộc đổi toàn bộ luồng cũ trong ticket này.

## 02 — Cho phân tích truyện xuất ra Gói nguồn

**Blocked by:** Ticket 01.

**Việc cần làm:** Luồng phân tích truyện sau khi hiểu nội dung phải xuất được Gói nguồn. Mục tiêu là để các bước sau không phải tự hiểu lại truyện từ đầu.

**Tiêu chí xong:**

- [ ] Phân tích truyện tạo được Gói nguồn từ dữ liệu truyện.
- [ ] Gói nguồn có nhân vật, bối cảnh, timeline hoặc các đoạn quan trọng nếu dữ liệu có đủ.
- [ ] Kết quả cũ của phân tích truyện vẫn còn dùng được trong UI hiện tại.
- [ ] Có test xác nhận luồng phân tích truyện xuất Gói nguồn đúng.

## 03 — Cho phân tích video xuất ra Gói nguồn

**Blocked by:** Ticket 01.

**Việc cần làm:** Luồng phân tích video/video inspiration phải xuất được Gói nguồn, thay vì chỉ tạo dữ liệu riêng cho video.

**Tiêu chí xong:**

- [ ] Phân tích video tạo được Gói nguồn từ video hoặc dữ liệu video đã phân tích.
- [ ] Gói nguồn có timeline, hook, nhịp, cảnh/shot đáng chú ý và thông tin âm thanh nếu có.
- [ ] Kết quả video inspiration hiện tại vẫn còn dùng được.
- [ ] Có test xác nhận luồng phân tích video xuất Gói nguồn đúng.

## 04 — Tạo truyện từ Gói nguồn theo kiểu 3 bản ứng viên

**Blocked by:** Ticket 02.

**Việc cần làm:** Luồng tạo truyện đọc Gói nguồn, tạo 3 bản truyện hoàn chỉnh song song, chấm điểm, chọn master rồi render truyện cuối.

**Tiêu chí xong:**

- [ ] Tạo truyện không cần tự phân tích nguồn lại nếu đã có Gói nguồn.
- [ ] Có 3 bản truyện ứng viên hoàn chỉnh, không phải 3 mảnh rời.
- [ ] Có tiêu chí chấm điểm và chọn master.
- [ ] Từ master render được outline/chương/cảnh/lời thoại hoặc đầu ra tương đương.
- [ ] Có test xác nhận bản cuối bám vào master đã chọn.

## 05 — Tạo video từ Gói nguồn theo kiểu 3 bản ứng viên

**Blocked by:** Ticket 03.

**Việc cần làm:** Luồng tạo video đọc Gói nguồn, tạo 3 bản video hoàn chỉnh song song, chấm điểm, chọn master rồi render video cuối.

**Tiêu chí xong:**

- [ ] Tạo video không cần tự phân tích nguồn lại nếu đã có Gói nguồn.
- [ ] Có 3 bản video ứng viên hoàn chỉnh, mỗi bản có hướng hình ảnh, nhịp và lời/âm thanh đủ để đánh giá.
- [ ] Có tiêu chí chấm điểm và chọn master video.
- [ ] Từ master render được shot list, prompt video, voiceover, âm thanh hoặc metadata cần thiết.
- [ ] Có test xác nhận bản video cuối bám vào master đã chọn.

## 06 — Đánh dấu phần đã cũ và chỉ rebuild phần cần thiết

**Blocked by:** Ticket 04 và Ticket 05.

**Việc cần làm:** Khi nguồn hoặc master thay đổi, hệ thống phải biết phần nào phụ thuộc vào thay đổi đó để render lại đúng phần, không làm lại toàn bộ.

**Tiêu chí xong:**

- [ ] Nếu Gói nguồn đổi, truyện/video phụ thuộc được đánh dấu là cần cập nhật.
- [ ] Nếu master đổi, các phần render chi tiết phụ thuộc vào master được đánh dấu là cần render lại.
- [ ] Người dùng thấy được trạng thái “đã cũ / cần render lại” theo cách dễ hiểu.
- [ ] Có test xác nhận thay đổi nguồn chỉ làm stale đúng các phần liên quan.

## 07 — Làm rõ UI và thuật ngữ cho người không code

**Blocked by:** Ticket 04 và Ticket 05.

**Việc cần làm:** UI nên dùng các thuật ngữ dễ hiểu: Gói nguồn, bản ứng viên, bản master, render lại, cần cập nhật. Mục tiêu là người dùng biết hệ thống đang ở bước nào.

**Tiêu chí xong:**

- [ ] UI hoặc mô tả trong màn hình cho biết bước hiện tại: phân tích, tạo ứng viên, chọn master, render cuối.
- [ ] Người dùng phân biệt được “phân tích nguồn” và “tạo nội dung”.
- [ ] Người dùng hiểu “render lại” là tạo lại đầu ra từ master, không nhất thiết là xuất video cuối.
- [ ] Có kiểm tra thủ công hoặc test UI tối thiểu cho các trạng thái chính.

## Thứ tự làm đề xuất

```text
01
├── 02 ── 04 ──┐
└── 03 ── 05 ──┤
               ├── 06
               └── 07
```

Nghĩa là: làm Gói nguồn trước. Sau đó có thể làm nhánh truyện và nhánh video gần như độc lập. Khi cả hai nhánh đã có master/render, mới làm stale/rebuild và làm rõ UI.

Máy hiện tại chưa có `gh` CLI, nên các ticket này đang là bản nháp trong repo. Khi có `gh`, có thể publish mỗi mục thành một GitHub Issue riêng.
