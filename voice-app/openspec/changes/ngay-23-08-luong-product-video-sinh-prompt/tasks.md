## 1. Bảng DB và migration

- [x] 1.1 Thêm `ProductVideoProject` vào `backend/database/models.py`, bảng `product_video_projects`: `id`, `title`, `topic`, `target_language`, `aspect_ratio`, `visual_style`, `visual_style_preset`, `video_purpose`, `dialogue_mode`, `narration_density`, `call_to_action_style`, `target_duration_seconds`, `prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt`, `status`, `planning_status`, `planning_error`, `hook_text`, `retention_plan_json`, `sound_design_plan_json`, `created_at`, `updated_at`
- [x] 1.2 Thêm `ProductVideoShot` vào `backend/database/models.py`, bảng `product_video_shots`: `id`, `project_id` (FK), `shot_order`, `shot_type`, `framing`, `camera_angle`, `composition`, `camera_motion`, `subject_motion`, `environment_motion`, `lighting`, `mood`, `duration_seconds`, `beat_role`, `narration_text`, `retention_notes`, `transition_notes`, `sound_design_notes`, `created_at`
- [x] 1.3 Thêm `ProductVideoShotPrompt` vào `backend/database/models.py`, bảng `product_video_shot_prompts`: `id`, `project_id` (FK), `shot_id` (FK), `prompt`, `negative_prompt`, `prompt_explanation_vi`, `aspect_ratio`, `created_at`
- [x] 1.4 Export ba model mới trong `backend/database/__init__.py`
- [x] 1.5 Thêm `_migrate_product_video(engine)` ở cuối `backend/database/migrations.py` theo style `_migrate_automation_hub` (`migrations.py:1792-1829`): import model trong hàm, liệt kê `__table__`, `Base.metadata.create_all(checkfirst=True)`, tạo index `idx_product_video_shots_project_order`
- [x] 1.6 Gọi `_migrate_product_video(engine)` từ `run_migrations()` trong `backend/database/migrations.py` ← (verify: chạy `init_db()` trên DB trống tạo đủ 3 bảng; chạy lại lần hai không lỗi)

## 2. Pydantic model và validation

- [x] 2.1 Thêm `ProductVideoProjectCreate` vào `backend/models.py`: `topic` required, `target_language` dùng `video_language.VIDEO_TARGET_LANGUAGE_PATTERN`, `video_purpose` dùng `video_purpose.VIDEO_PURPOSE_PATTERN`, `aspect_ratio` pattern `^(9:16|16:9)$` default `9:16`, `target_duration_seconds` `ge=15, le=180`, `visual_style` max 2000, `visual_style_preset` max 40 không pattern
- [x] 2.2 Thêm `ProductVideoProjectUpdate` (mọi field optional) và `ProductVideoProjectResponse` (`from_attributes = True`, kèm `derived_clip_count` và `derived_duration_seconds`)
- [x] 2.3 Thêm `ProductVideoShotResponse`, `ProductVideoPromptResponse`, `ProductVideoPromptPackResponse` ← (verify: `aspect_ratio="1:1"` bị 422, `target_duration_seconds=10` và `=240` bị 422, `visual_style_preset` lạ vẫn 200)

## 3. Service — cấu hình và lập kế hoạch

- [x] 3.1 Tạo `backend/services/product_video.py` với docstring nêu rõ đây là bản rút gọn có chủ đích của `video_phase2.py`, kèm con trỏ tới hàm gốc
- [x] 3.2 Viết `resolve_segment_config(project)`: trả về số clip và thời lượng thực, snap độ dài clip về 4/6/8/10 giây theo `video_veo_chrome._normalize_requested_duration` (`:283-287`)
- [x] 3.3 Viết `create_project(data, db)`: gọi `video_purpose.resolve_purpose_settings()` để áp preset thể loại, lưu bản ghi, ghi đè `target_duration_seconds` khi cấu hình phân đoạn được set đủ ba giá trị
- [x] 3.4 Viết `PRODUCT_SHOT_TYPES` — vocabulary đóng 7 giá trị: `hero shot`, `macro detail`, `in-use/lifestyle`, `before-after`, `unboxing reveal`, `size comparison`, `CTA end-card`
- [x] 3.5 Viết `normalize_shot_type(value)`: map giá trị ngoài danh sách về giá trị gần nhất, không ghi nguyên giá trị lạ
- [x] 3.6 Viết `DEFAULT_BEAT_FRAMEWORK`: khung `hook → problem → product reveal → proof → CTA` giãn theo số clip, có comment đánh dấu là giá trị tạm của đợt 1
- [x] 3.7 Viết `plan_shots(project_id, db)`: gọi `ai_planning.run_codex_exec` với chỉ dẫn riêng cho product video, gán `beat_role` cho từng shot theo `DEFAULT_BEAT_FRAMEWORK` ← (verify: project 30 giây sinh ra đúng số shot, mỗi shot có `beat_role` và `shot_type` thuộc vocabulary)

## 4. Service — sinh prompt và bốn ràng buộc chất lượng

- [x] 4.1 Viết `PRODUCT_FIDELITY_SECTION`: hằng số cố định, tiêu đề `Product fidelity — highest priority`, nêu đủ giữ nguyên chữ/typography/logo/màu/tỉ lệ và cấm redesign, cấm dịch, cấm sắp xếp lại, cấm biến dạng giữa frame đầu và frame cuối
- [x] 4.2 Viết `MOTION_CONSTRAINT_SECTION`: cấm đúng bốn kiểu gây drift (quay tròn hết vòng, spin nhanh, nhãn rời khung rồi quay lại, sản phẩm đi qua vật che); nêu rõ sản phẩm ĐƯỢC nâng, mang đi, nghiêng nhẹ, được tay người tương tác
- [x] 4.3 Viết `is_blank_motion(value)`: coi `none`, `n/a`, `static`, `no motion`, chuỗi trắng là rỗng
- [x] 4.4 Viết `validate_motion_budget(shot)`: đảm bảo tối thiểu 2 trong 3 field `camera_motion`/`subject_motion`/`environment_motion` không rỗng theo `is_blank_motion`; nếu thiếu thì điền `environment_motion` từ phong cách
- [x] 4.5 Viết `enforce_shot_variety(shots)`: không để hai shot liên tiếp trùng cả `shot_type` lẫn `framing`; nếu trùng thì đổi `framing` của shot sau
- [x] 4.6 Viết `build_prompt_text(shot, project)`: nối theo shape `video_phase2._prompt_text` (`:3615-3652`) — giữ `Retention notes`, `Transition notes`, `Sound design notes`, ba field chuyển động, `Aspect ratio` theo dropdown
- [x] 4.7 Chèn `hook_text` vào prompt của shot đầu tiên
- [x] 4.8 Gọi `video_speech.build_veo_native_speech_section(project, shot, db)` khi `target_language == "vi"` và append vào prompt; thêm chỉ dẫn giới hạn 18–20 chữ cho clip 8 giây
- [x] 4.9 Viết `generate_prompt_pack(project_id, db)`: gọi 4.4 và 4.5 trước khi build, lưu vào `product_video_shot_prompts` ← (verify: mọi prompt chứa `Product fidelity — highest priority`, có ≥2/3 field chuyển động không rỗng, không cặp shot liên tiếp trùng khung, project tiếng Việt có `Vietnamese spoken dialogue`)

## 5. Route backend

- [x] 5.1 Tạo `backend/routes/product_video.py`: `APIRouter(prefix="/product-video", tags=["product-video"], route_class=video_errors.AIVideoRoute)`
- [x] 5.2 Thêm endpoint CRUD: `GET /projects`, `POST /projects`, `GET /projects/{id}`, `PUT /projects/{id}`, `DELETE /projects/{id}`
- [x] 5.3 Thêm `POST /projects/{id}/shots` (lập kế hoạch) và `POST /projects/{id}/prompts` (sinh prompt pack)
- [x] 5.4 Thêm `GET /projects/{id}/prompt-pack` trả file tải về, mỗi shot một section có nhãn thứ tự
- [x] 5.5 Đăng ký router trong `register_routers()` của `backend/routes/__init__.py` ← (verify: `GET /product-video/projects` trả 200; không tồn tại endpoint nào tạo clip generation job, render job hay voice job)

## 6. Frontend — route và điều hướng

- [x] 6.1 Tạo `app/src/lib/constants/productVideoStyles.ts`: 7 preset (`ugc_street`, `studio_beauty`, `presenter_ad`, `macro_closeup`, `unboxing`, `flatlay`, `custom`) với `key`, `label` tiếng Việt, và `text` tiếng Anh theo shape chủ thể → chuyển động camera → chuyển động hậu cảnh → ánh sáng → giữ nguyên nhãn. Mỗi preset trừ `custom` phải mô tả ít nhất một nguồn chuyển động
- [x] 6.2 Thêm type và method vào `app/src/lib/api/types.ts` và `app/src/lib/api/client.ts`, queryKey namespace `['product-video', ...]`
- [x] 6.3 Thêm `productVideoRoute` vào `app/src/router.tsx` theo mẫu `aiVideoRoute` (`:180-184`), dùng `lazy()` như `researchRoute` (`:39-42`)
- [x] 6.4 Thêm `productVideoRoute` vào `routeTree` (`app/src/router.tsx:306-332`) và thêm `/product-video` vào `isWideWorkspace` (`:64-69`)
- [x] 6.5 Thêm tab vào mảng `tabs` của `app/src/components/Sidebar.tsx` (`:18-37`) với icon lucide và label tiếng Việt ← (verify: mở `/product-video` không 404, layout rộng đúng, sidebar highlight đúng tab)

## 7. Frontend — form và prompt pack

- [x] 7.1 Tạo `app/src/components/ProductVideo/ProductVideo.tsx` theo cấu trúc `ResearchWorkspace.tsx` (route mỏng + sub-panel), không theo `AIVideoAssistant.tsx`
- [x] 7.2 Dựng 6 dropdown bằng `@/components/ui/select`: ngôn ngữ (`LANGUAGE_OPTIONS` từ `app/src/lib/constants/languages.ts:103`), tỉ lệ (2 giá trị), thể loại (`video_purpose`), thời lượng, cấu hình phân đoạn
- [x] 7.3 Dựng phần phong cách: dropdown 7 preset + textarea. Chọn preset điền sẵn text; sửa text thì `visual_style_preset` thành `custom`; chọn `custom` thì xoá trống
- [x] 7.4 Hiển thị số clip và thời lượng thực dẫn xuất ngay dưới dropdown thời lượng, dạng `15s → 2 clip × 8s = 16s thực tế`
- [x] 7.5 Dựng panel prompt pack: nút Copy cho từng shot, nút Download cho cả pack
- [x] 7.6 Bốn trạng thái UI: đang tải, lỗi kèm nút thử lại, rỗng kèm hướng dẫn bước tiếp theo, thành công ← (verify: chọn preset rồi sửa text rồi mở lại project thì textarea và preset nạp lại đúng; bước sinh prompt lỗi thì hiện nút thử lại chứ không hiện pack rỗng)

## 8. Test

- [x] 8.1 Tạo `backend/tests/test_product_video.py` với fixture `db` copy từ `test_ai_video_backend.py:227-238` và TestClient theo `:2651-2656`
- [x] 8.2 Test schema: ba bảng tồn tại sau `init_db()`; chạy `_migrate_product_video` lần hai không lỗi
- [x] 8.3 Test validation: `aspect_ratio="1:1"` → 422; `target_duration_seconds=10` → 422; `=240` → 422; `visual_style_preset` lạ → 200
- [x] 8.4 Test preset thể loại: `video_purpose="sales_ad"` áp đúng `target_language`, `narration_density`, `call_to_action_style`
- [x] 8.5 Test thời lượng dẫn xuất: chọn 15 giây với clip 8 giây trả về 2 clip và 16 giây
- [x] 8.6 Test prompt: mọi prompt chứa `Product fidelity — highest priority`; chứa cả ba dòng `Retention notes`/`Transition notes`/`Sound design notes` không rỗng; shot đầu có hook
- [x] 8.7 Test lời nói: project `target_language="vi"` có `Vietnamese spoken dialogue` trong prompt; project `="en"` thì không có
- [x] 8.8 Test chống video tĩnh: mọi prompt có ≥2/3 field chuyển động không rỗng; `Environment motion: none` bị coi là rỗng
- [x] 8.9 Test đa dạng shot: không cặp shot liên tiếp nào trùng cả `shot_type` lẫn `framing`
- [x] 8.10 Test vocabulary: mọi `shot_type` thuộc `PRODUCT_SHOT_TYPES`; giá trị lạ từ LLM bị map về giá trị gần nhất
- [x] 8.11 Test preset phong cách: cả 7 preset trừ `custom` đều mô tả ít nhất một nguồn chuyển động ← (verify: toàn bộ test file pass)

## 9. Kiểm tra không hồi quy và verification

- [x] 9.1 Chạy `cd backend && python -m pytest tests/test_product_video.py -v`
- [x] 9.2 Chạy `cd backend && python -m pytest tests/test_ai_video_backend.py -v` và xác nhận `backend/services/video_phase2.py` không bị sửa
- [x] 9.3 Chạy `cd backend && python -m pytest tests/test_backend_layering.py -v`
- [x] 9.4 Chạy `cd app && bun run build`
- [ ] 9.5 Chạy app, mở `http://localhost:4000/product-video`, tạo project `sales_ad` + 9:16 + tiếng Việt + preset `ugc_street` đã sửa text, chạy shots → prompts, kiểm prompt pack có đủ ba dòng ghi chú, block lời nói tiếng Việt, section product fidelity, và phần phong cách đã sửa ← (verify: copy một prompt dán vào Flow kèm ảnh sản phẩm ra được clip đúng dạng, nhãn sản phẩm đọc được ở cả frame đầu và frame cuối)
