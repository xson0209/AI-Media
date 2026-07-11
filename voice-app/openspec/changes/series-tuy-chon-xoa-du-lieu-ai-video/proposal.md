## Why

AI Video hiện liệt kê project gần đây dạng phẳng và chưa expose thao tác xoá dữ liệu ngay trên UI, khiến người dùng khó dọn project hoặc xoá từng đoạn nội dung đã nhập. Đồng thời các video dài tập cần giữ cùng nhân vật, bối cảnh và style qua nhiều tập, nhưng series phải là tuỳ chọn để project lẻ hiện tại vẫn hoạt động như cũ.

Một vấn đề quan trọng khác là output Codex đôi khi trả sai key, sai thứ tự hoặc sai loại dữ liệu; nếu không có lớp mapping/validation nghiêm ngặt, dữ liệu story/shot/prompt có thể ghi sai vào project và làm hỏng continuity.

## What Changes

- Thêm cơ chế **series tuỳ chọn** cho AI Video: project có thể thuộc một series hoặc vẫn là project lẻ độc lập như hiện tại.
- Thêm **Series Bible** để lưu nhân vật, bối cảnh, style, continuity rules, negative rules và tóm tắt các tập trước; các tập trong series kế thừa context này khi gọi Codex.
- Thêm workflow tạo tập mới trong series, bao gồm episode number/title/topic và khả năng dùng lại series bible để giữ cùng nhân vật/bối cảnh.
- Cập nhật danh sách “Dự án gần đây” để có thể nhóm project theo series nhưng vẫn hiển thị project lẻ bình thường.
- Thêm UI/API xoá dữ liệu ở các mức: xoá project, xoá dữ liệu đã generate nhưng giữ nguồn nhập, và xoá từng đoạn nguồn nội dung/source block.
- Thêm confirm rõ ràng cho thao tác xoá, tránh xoá nhầm artifact hoặc xoá cả series khi chỉ muốn xoá một tập.
- Thêm lớp mapping/validation output Codex chặt hơn cho story, shots, prompt pack và series bible: validate id/order/count/type trước khi ghi DB, log lỗi rõ ràng và không ghi partial artifact sai.
- Không thay đổi project lẻ hiện có thành series bắt buộc và không đổi nguyên tắc prompt pack full-call trong một project.

## Capabilities

### New Capabilities
- `ai-video-optional-series`: Quản lý series tuỳ chọn cho AI Video, gồm Series Bible, episode projects, kế thừa continuity giữa tập và grouped recent projects UI.
- `ai-video-data-deletion`: Xoá project, xoá generated artifacts nhưng giữ source, và xoá từng source block/chat block với confirm và stale-state phù hợp.
- `ai-video-codex-output-mapping`: Chuẩn hoá, validate và map output Codex trước khi ghi dữ liệu AI Video để tránh sai key, sai order, sai count hoặc sai loại dữ liệu.

### Modified Capabilities
- Không có capability đã archive trong `openspec/specs` cần sửa trực tiếp.

## Impact

- Backend DB/model: thêm bảng series hoặc cấu trúc tương đương, quan hệ optional từ project tới series, episode metadata và các trường bible/summary cần thiết.
- Backend service/API: thêm CRUD series, tạo episode project từ series, xoá dữ liệu generated, xoá source block có stale propagation, và hardening mapping/validation Codex.
- Frontend AI Video Assistant: thêm grouped recent projects, menu xoá, confirm dialogs, màn quản lý Series Bible và flow tạo tập mới.
- Codex planning: inject Series Bible vào prompt story/shots/prompt pack khi project thuộc series; project lẻ không bị ảnh hưởng.
- Storage/artifacts: xoá đúng file prompt, voice, subtitle, package, render output, debug log tuỳ mức xoá; không xoá nhầm asset của project khác/tập khác.
- Tests: coverage cho optional series, project lẻ backward compatibility, delete levels, stale state, strict mapping failures và continuity injection.
