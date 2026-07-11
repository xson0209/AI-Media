## Bối cảnh

Ứng dụng hiện chạy theo mô hình hai tiến trình chính: frontend Vite ở cổng `5173` và backend FastAPI ở cổng `17493`. Các giá trị này đang xuất hiện tại nhiều nơi như `package.json`, `start.sh`, `justfile`, Docker, Tauri Rust bridge, CORS backend và store/API client frontend. Khi cần đổi cổng, chạy Docker song song hoặc đóng gói desktop, rủi ro lệch cấu hình cao.

Backend đã có các thư mục `routes`, `services`, `database`, `utils`, `backends`, nhưng một số module đã vượt quá kích thước dễ bảo trì: `backend/services/video_phase2.py`, `backend/models.py`, `backend/routes/ai_video.py`, `backend/services/video_rendering.py`, `backend/services/video_projects.py`, `backend/services/video_auto_runs.py` và `app/src/lib/api/client.ts`. Điều này làm các thay đổi AI Video dễ kéo theo nhiều vùng không liên quan.

Ràng buộc chính là không làm thay đổi hành vi công khai: cổng mặc định, endpoint, schema phản hồi, dữ liệu dự án, đường dẫn lưu trữ và trải nghiệm UI phải tiếp tục hoạt động như trước.

## Mục tiêu / Không thuộc phạm vi

**Mục tiêu:**

- Có một nguồn cấu hình runtime rõ ràng cho backend host/cổng, frontend dev origin, CORS, data/model/cache directory và URL backend public.
- Giữ frontend và backend là hai port riêng trong dev, nhưng mọi nơi đọc cùng contract cấu hình.
- Tách backend theo phân lớp: lõi dùng chung, lớp API mỏng, lớp tính năng, lớp database/kho dữ liệu.
- Di chuyển dần các module AI Video lớn sang cấu trúc tính năng mà vẫn giữ import/route tương thích trong giai đoạn chuyển tiếp.
- Bổ sung kiểm thử để chứng minh cổng mặc định, CORS, health, API route và URL resolution không bị đổi hành vi.

**Không thuộc phạm vi:**

- Không đổi cổng mặc định `5173` và `17493`.
- Không đổi tên app, UI flow, render output, model backend hoặc dữ liệu đã lưu.
- Không viết lại toàn bộ backend trong một bước lớn.
- Không đổi public REST API hoặc schema chỉ vì đổi cấu trúc file.
- Không thêm framework cấu hình mới nếu standard library hoặc pattern hiện có đáp ứng được.

## Quyết định

### 1. Giữ tên file OpenSpec chuẩn, dùng tên change/spec tiếng Việt không dấu

Các artifact OpenSpec vẫn dùng `proposal.md`, `design.md`, `tasks.md`, `spec.md` vì CLI dựa vào tên này. Tên change và tên capability dùng tiếng Việt không dấu: `chuan-hoa-cong-va-phan-lop-backend`.

Phương án thay thế là đổi artifact thành `de-xuat.md`, `thiet-ke.md`, `cong-viec.md`, nhưng cách đó phá workflow OpenSpec và làm `openspec status` không xác định đúng artifact.

### 2. Tạo lớp cấu hình typed ở backend, giữ wrapper cũ

Backend sẽ có lớp cấu hình trung tâm, ví dụ `backend/core/config.py`, chứa default host/cổng, CORS origins, data directory, model/cache directory và feature flags. `backend/config.py` hiện tại được giữ như wrapper tương thích cho các import cũ trong giai đoạn chuyển tiếp.

Phương án thay thế là tiếp tục thêm biến môi trường trực tiếp trong từng file. Cách đó ít thay đổi ban đầu nhưng giữ nguyên vấn đề lệch cấu hình và khó kiểm thử.

### 3. Đặt boundary frontend/backend qua một helper URL duy nhất

Frontend sẽ dùng một helper/store duy nhất để xác định backend URL theo thứ tự: cấu hình build/runtime, URL do Tauri trả về, URL lưu trong store, fallback local `http://127.0.0.1:17493`. Các module web, Tauri và API client không tự hardcode fallback riêng.

Phương án thay thế là chỉ sửa từng hardcode khi gặp. Cách đó không đủ vì repo đã có nhiều điểm chứa cùng cổng.

### 4. Chia backend theo lõi, API và tính năng

Định hướng cấu trúc:

```text
backend/
  core/
    config.py
    logging.py
    lifecycle.py
    errors.py
  api/
    routes/
      health.py
      ai_video/
        projects.py
        auto_runs.py
        render.py
        subtitles.py
  features/
    ai_video/
      schemas.py
      service.py
      repository.py
      state.py
      render/
      subtitles/
      auto_runs/
  database/
    session.py
    models/
```

`backend/routes/*` hiện tại có thể giữ wrapper/import bridge trong giai đoạn đầu để tránh đổi toàn bộ registry route cùng lúc. Các route mới hoặc route đã tách sẽ chỉ điều phối request/response, còn logic nghiệp vụ nằm trong `features/*`.

Phương án thay thế là chỉ tách file lớn trong cùng thư mục `services`. Cách đó giảm kích thước file nhưng không tạo boundary rõ giữa API, nghiệp vụ và lưu trữ.

### 5. Tách AI Video theo lát nhỏ có kiểm chứng

Thứ tự ưu tiên là các vùng ít phụ thuộc nhất trước: cấu hình/cổng, health/CORS, frontend URL helper, sau đó AI Video projects, auto-runs, render và phụ đề/caption. Mỗi lát phải có test hoặc typecheck trước khi chuyển sang lát kế tiếp.

Phương án thay thế là di chuyển toàn bộ AI Video trong một PR lớn. Cách đó nhanh trên giấy nhưng rủi ro cao vì nhiều change AI Video đang tồn tại song song trong OpenSpec.

## Rủi ro / Đánh đổi

- [Rủi ro] Import cũ bị gãy khi di chuyển module → Giữ wrapper module, export lại symbol cũ và chỉ xóa wrapper sau khi toàn bộ caller đã chuyển.
- [Rủi ro] CORS hoặc URL backend thay đổi làm frontend mất kết nối → Thêm test cho default origins, custom origins và `getDefaultServerUrl`.
- [Rủi ro] Tauri vẫn hardcode cổng khác backend → Tạo một contract cấu hình rõ trong Rust bridge và kiểm tra health bằng cùng cổng mặc định `17493`.
- [Rủi ro] Tách file lớn làm thay đổi thứ tự side effect/lifecycle → Di chuyển startup/shutdown vào `core/lifecycle.py` trước, giữ `create_app()` là entry ổn định.
- [Rủi ro] Refactor chồng lên các change AI Video đang dở → Chỉ đổi cấu trúc khi có wrapper tương thích, tránh thay đổi schema hoặc logic pipeline.
- [Đánh đổi] Trong giai đoạn chuyển tiếp sẽ tồn tại cả đường dẫn cũ và mới → Chấp nhận tạm thời để giảm rủi ro, sau đó dọn wrapper bằng task riêng khi tests đã phủ đủ.

## Kế hoạch chuyển đổi

1. Thêm cấu hình runtime trung tâm và test cho default host/cổng/CORS/data/model/cache.
2. Cập nhật script, Docker, Tauri và frontend URL helper để đọc cùng contract hoặc cùng biến cấu hình.
3. Tách `backend/app.py` thành app factory, CORS setup và lifecycle rõ ràng; giữ `backend.main:app` không đổi.
4. Tạo skeleton `core`, `api`, `features` và bridge route tương thích.
5. Tách AI Video theo từng vùng nhỏ: dự án, chạy tự động, render, phụ đề/caption, resource management.
6. Chạy typecheck/test sau từng lát và bổ sung regression test cho endpoint public.

Rollback chủ yếu là quay lại wrapper cũ và giữ cổng mặc định hiện tại. Vì không đổi dữ liệu hoặc public API, rollback không cần migration dữ liệu.

## Câu hỏi mở

- Có cần hỗ trợ file `.env` riêng cho desktop/Tauri hay chỉ dùng biến môi trường hiện có?
- Có nên công bố endpoint cấu hình runtime đọc-only cho frontend hay chỉ resolve qua build/runtime env?
- Khi tách `backend/models.py`, nên ưu tiên theo domain AI Video trước hay tách database model toàn cục trước?
