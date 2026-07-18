# Spec: Tái cấu trúc luồng phân tích, tạo truyện và tạo video quanh Gói nguồn

## Vấn đề

Hiện tại các luồng phân tích truyện, tạo truyện, phân tích video và tạo video đang có dấu hiệu chồng chéo trách nhiệm. Một số nơi vừa hiểu nguồn, vừa chọn ý tưởng, vừa tạo đầu ra cuối. Điều này làm hệ thống khó mở rộng, khó kiểm tra chất lượng và dễ bị lệch khi cùng một nguồn được dùng cho nhiều kiểu đầu ra.

Vấn đề lớn nhất không phải là thiếu tính năng, mà là thiếu một điểm trung gian đủ chuẩn để các luồng dùng chung.

## Giải pháp

Tạo một lớp trung gian gọi là **Gói nguồn / Source Package**.

Gói nguồn là bản hiểu nguồn đã được chuẩn hóa. Nó chứa những thứ như: nguồn đến từ đâu, bằng chứng quan trọng, nhân vật, bối cảnh, timeline, đoạn đáng chú ý, cảm xúc, nhịp, ràng buộc và các phần đã được chọn để dùng tiếp.

Sau khi có Gói nguồn:

1. Luồng tạo truyện dùng Gói nguồn để tạo nhiều bản truyện ứng viên.
2. Luồng tạo video dùng Gói nguồn để tạo nhiều bản video ứng viên.
3. Hệ thống chấm điểm các bản ứng viên.
4. Chọn một bản master.
5. Từ master, render ra đầu ra chi tiết như chương, cảnh, lời thoại, prompt hình ảnh, shot list, voiceover, âm thanh và metadata.

Điểm quan trọng: không nên chạy lời thoại, hình cảnh và nhịp nội dung như ba phần rời ngay từ đầu. Nên tạo nhiều bản hoàn chỉnh song song, chọn master, rồi mới tách ra render chi tiết.

## User stories

1. Là người dùng tạo truyện, tôi muốn hệ thống hiểu nguồn một lần rồi dùng lại, để truyện tạo ra nhất quán hơn.
2. Là người dùng tạo video, tôi muốn video dùng cùng dữ liệu nguồn đã phân tích, để nội dung không bị lệch so với truyện hoặc nguồn gốc.
3. Là người dùng không biết code, tôi muốn nhìn được luồng xử lý đơn giản, để biết bước nào đang phân tích, bước nào đang tạo nội dung.
4. Là người dùng, tôi muốn hệ thống tạo nhiều bản ứng viên, để có lựa chọn tốt hơn thay vì chỉ nhận một bản duy nhất.
5. Là người dùng, tôi muốn hệ thống chọn bản tốt nhất theo tiêu chí rõ ràng, để kết quả không phụ thuộc vào may rủi.
6. Là người dùng, tôi muốn sau khi chọn master thì hệ thống mới tạo lời thoại, prompt, hình cảnh và âm thanh, để các phần này ăn khớp với nhau.
7. Là người dùng chỉnh sửa nguồn, tôi muốn hệ thống biết phần nào bị cũ, để chỉ làm lại phần cần thiết.
8. Là người dùng làm series dài, tôi muốn các tập sau vẫn giữ đúng nhân vật, bối cảnh và phong cách, để series không bị loạn.
9. Là người dùng kiểm tra chất lượng, tôi muốn biết vì sao một bản được chọn là tốt nhất, để có thể tin hoặc sửa tiêu chí.
10. Là người vận hành hệ thống, tôi muốn mỗi luồng có vai trò rõ, để dễ sửa lỗi và không làm hỏng luồng khác.
11. Là người phát triển tính năng mới, tôi muốn thêm đầu ra mới từ Gói nguồn, để không phải viết lại phần phân tích từ đầu.
12. Là người dùng tạo video, tôi muốn có shot list, voiceover, prompt video và nhịp chuyển cảnh từ cùng một master, để video cuối nhất quán.

## Quyết định triển khai

- **Gói nguồn là điểm nối chính** giữa phân tích và tạo nội dung.
- Luồng phân tích không nên tạo trực tiếp truyện/video cuối. Nó chỉ nên tạo Gói nguồn đủ tốt.
- Luồng tạo truyện đọc Gói nguồn, tạo nhiều bản truyện hoàn chỉnh, chọn master rồi render truyện cuối.
- Luồng tạo video đọc Gói nguồn, tạo nhiều bản video hoàn chỉnh, chọn master rồi render video cuối.
- Việc chạy song song nên áp dụng ở cấp **bản ứng viên hoàn chỉnh**, không áp dụng ở cấp các mảnh rời như lời thoại riêng, hình ảnh riêng, nhịp riêng.
- Sau khi master đã khóa, các phần chi tiết như lời thoại, prompt hình, âm thanh, metadata có thể render song song vì chúng cùng bám vào một master.
- Khi nguồn hoặc master thay đổi, hệ thống cần đánh dấu phần phụ thuộc là đã cũ để rebuild đúng chỗ.
- Refactor nên làm từng lát nhỏ, không sửa toàn bộ hệ thống cùng lúc.

## Quyết định kiểm thử

- Test nên kiểm tra hành vi bên ngoài: cùng một nguồn có tạo ra Gói nguồn đúng dạng không, luồng tạo truyện/video có dùng đúng Gói nguồn không, và phần render cuối có bám master không.
- Không nên test chi tiết nội bộ quá sâu, vì refactor có thể đổi cách tổ chức code nhưng không đổi hành vi người dùng.
- Cần có test cho Gói nguồn, test cho luồng truyện, test cho luồng video và test cho rebuild khi nguồn thay đổi.
- Repo đã có nhiều test backend cho comic analysis, comic handoff, story studio, video inspiration và AI video; nên tận dụng kiểu test hiện có thay vì dựng một hệ test mới.

## Ngoài phạm vi

- Không thay đổi model AI hoặc nhà cung cấp AI.
- Không tối ưu chi phí token/render trong spec này.
- Không thiết kế lại toàn bộ UI.
- Không thay đổi workflow xuất bản video cuối nếu chỉ là thay đổi downstream không liên quan Gói nguồn.
- Không yêu cầu rewrite toàn bộ các file lớn trong một lần.

## Ghi chú thêm

Nếu cần ưu tiên, làm theo thứ tự:

1. Chuẩn hóa Gói nguồn.
2. Chuyển phân tích truyện sang xuất Gói nguồn.
3. Chuyển phân tích video sang xuất Gói nguồn.
4. Chuyển tạo truyện sang đọc Gói nguồn.
5. Chuyển tạo video sang đọc Gói nguồn.
6. Thêm cơ chế đánh dấu stale/rebuild.

Máy hiện tại chưa có `gh` CLI, nên bản spec này đang được lưu trong repo trước. Khi có `gh`, có thể publish nội dung này lên GitHub Issues.
