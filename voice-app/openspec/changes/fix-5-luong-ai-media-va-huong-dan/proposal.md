## Why

Năm workspace AI/media quan trọng hiện có nhiều thay đổi chưa được xác minh đồng bộ, nên trạng thái chạy thật, khả năng dùng dữ liệu hiện có và đường handoff giữa các workspace chưa có bằng chứng đầu-cuối đáng tin cậy. Cần một vòng kiểm thử trình duyệt, sửa lỗi và tài liệu hóa thống nhất để người dùng biết luồng nào hoạt động, cách vận hành và lựa chọn công cụ tối ưu cho từng chủ đề/mục đích.

## What Changes

- Chạy và xác minh đầu-cuối năm route `/story-studio`, `/comic-series-analysis`, `/ai-video`, `/research` và `/video-inspiration` trên frontend/backend thật.
- Ưu tiên dữ liệu thật đã có trong cơ sở dữ liệu hoặc tệp mẫu hợp lệ trong workspace; riêng Research phải dùng nội dung thật của project **“Nghiên cứu Series: Người Que”** làm dữ liệu chuẩn. Hạn chế tối đa dữ liệu ví dụ và không tạo tên kiểu `codex_test`; mọi dữ liệu phụ mới phải hữu ích cho chủ đề Người Que, có tên nhận diện rõ và không làm mất dữ liệu người dùng.
- Thu bằng chứng theo từng luồng gồm trạng thái UI, request API, console/backend log và ảnh chụp tại các mốc quan trọng.
- Sửa các lỗi được tái hiện trong UI, API hoặc lớp dịch vụ mà không hoàn tác các thay đổi dở dang không liên quan.
- Chạy lại toàn bộ năm luồng sau sửa lỗi cùng các gate typecheck, build và test backend/frontend phù hợp.
- Xuất một file HTML tiếng Việt hướng dẫn sử dụng, nêu điều kiện đầu vào, từng bước thao tác, đầu ra, lỗi thường gặp, handoff giữa các workspace và ma trận chọn luồng tối ưu theo chủ đề/mục đích.

## Capabilities

### New Capabilities

- `ai-media-workflow-quality-gate`: Quy định tiêu chí chạy thật, bằng chứng xác minh, vòng sửa lỗi và tài liệu hướng dẫn cho năm workspace AI/media.

### Modified Capabilities

Không có capability chính thức trong `openspec/specs/` cần thay đổi yêu cầu ở thời điểm đề xuất; các sửa lỗi sẽ khôi phục hoặc hoàn thiện hành vi đã được các change hiện hữu mô tả.

## Impact

- Frontend: router và các component Story Studio, Comic Series Analysis, AI Video, Research Workspace và Video Inspiration.
- Backend: route/service/model/database liên quan đến năm workspace và các handoff dữ liệu giữa chúng.
- Runtime/data: FastAPI tại cổng `17493`, Vite tại cổng `4000`, SQLite trong `data/`, tệp media/model/cache hiện có và các dịch vụ AI cục bộ được cấu hình.
- Verification: Playwright CLI, log frontend/backend, test Python, typecheck/build JavaScript và ảnh chụp trong `output/playwright/`.
- Documentation: một trang HTML độc lập đặt trong `docs/`, có thể mở trực tiếp, liên kết đến năm route đang chạy và dùng nội dung Người Que thật trong phần minh họa Research/handoff.
