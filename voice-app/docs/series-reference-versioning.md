# Quản lý ảnh tham chiếu, phiên bản và stale theo phạm vi

Tài liệu này mô tả cách vận hành ảnh tham chiếu và dependency snapshot cho series dài trong AI Video/Story Studio.

## Chọn và duyệt ảnh tham chiếu

Ảnh tham chiếu chỉ nên dùng cho dữ liệu canon đã ổn định:

- Nhân vật: chính diện, góc nghiêng, toàn thân, trang phục đặc trưng, biểu cảm hoặc ảnh khác có ghi rõ mục đích.
- Địa điểm: toàn cảnh, lối vào, nội thất, chi tiết nhận diện, ánh sáng hoặc ảnh khác có ghi rõ mục đích.
- Không dùng ảnh chưa chắc canon hoặc ảnh chỉ là moodboard tạm để tránh làm prompt mới lệch identity.

Luồng chuẩn:

1. Tải ảnh vào đúng series và đúng `entity_type`, `entity_id`, `reference_role`.
2. Hệ thống kiểm tra loại file, dung lượng, kích thước, checksum, tên file và lưu dưới thư mục artifact của app.
3. Ảnh mới luôn ở trạng thái `pending_approval`, `active=false`.
4. Người dùng duyệt ảnh bằng trạng thái `approved` và bật `active=true`.
5. Chỉ ảnh `approved` và `active` mới được đưa vào prompt package.

Nếu provider chưa hỗ trợ gửi ảnh tham chiếu trực tiếp, adapter phải báo `sent=[]`, đưa ảnh vào `skipped` kèm lý do tiếng Việt và dùng fallback metadata/text. Không hiển thị rằng provider đã nhận ảnh khi chưa gửi thật.

## Phiên bản và lịch sử

Các dữ liệu sau có revision hoặc version record:

- Series Bible/style qua `video_series.revision`.
- Hồ sơ nhân vật qua `series_character_profiles.revision`.
- Memory card và current state qua revision có sẵn.
- Ảnh tham chiếu qua `series_reference_assets.revision`.
- Master Story qua `story_episodes.revision`.
- Panel/adaptation qua `story_adaptations.revision`.
- Scene, shot, subtitle và package qua revision artifact.
- Video prompt dùng `video_shot_prompts.version`.

Mỗi thay đổi đã duyệt hoặc thay đổi có ảnh hưởng lưu `series_version_records` với:

- `entity_type`, `entity_id`, `revision`.
- Snapshot JSON đã loại metadata nhạy cảm.
- `changed_by`, `change_source`, `change_reason`.
- `created_at`.

API xem lịch sử:

```text
GET /ai-video/series/{series_id}/versions/{entity_type}/{entity_id}
```

Response có `items` và `diff_vi` để UI hiển thị thay đổi gần nhất bằng tiếng Việt.

## Dependency snapshot

Khi tạo artifact, hệ thống lưu artifact đã dùng dữ liệu nào:

```text
artifact_type
artifact_id
artifact_revision
dependency_type
dependency_id
dependency_revision
dependency_scope
```

Các scope chính:

- `visual_identity`: ngoại hình nhân vật.
- `reference_image`: ảnh tham chiếu đã dùng.
- `story_state`: Master Story, current state, memory/canon.
- `camera_style`: style hình ảnh, camera, bố cục.
- `dialogue`: lời thoại/narration.
- `language`: ngôn ngữ người xem.
- `voice_profile`: giọng/người nói.
- `timing`: timing voice/subtitle.

API ghi dependency:

```text
POST /ai-video/series/{series_id}/dependencies
```

Story Studio tự ghi dependency cho panel ảnh. Video prompt phase 2 tự ghi dependency cho prompt video. Voice/subtitle/package có thể ghi bằng API khi pipeline tương ứng tạo artifact.

## Stale theo phạm vi

Khi dữ liệu nguồn đổi revision, hệ thống so dependency snapshot thay vì stale toàn project.

Ví dụ:

- Đổi tóc nhân vật: stale panel/prompt có `dependency_type=character_profile`, `dependency_scope=visual_identity` cho nhân vật đó.
- Đổi style series: stale `video_prompt` hoặc panel/prompt có `camera_style`, không stale voice chỉ phụ thuộc `voice_profile` hoặc `language`.
- Đổi narration/timing: stale voice/subtitle/package có `dialogue`, `narration` hoặc `timing`, không stale prompt hình ảnh không phụ thuộc narration.
- Vô hiệu hóa ảnh tham chiếu: stale artifact có `reference_asset` đó.

API xem stale:

```text
GET /ai-video/series/{series_id}/stale-events?status=active
```

API yêu cầu tạo lại đúng phạm vi:

```text
POST /ai-video/series/{series_id}/stale-events/regenerate
```

Endpoint này ghi nhận yêu cầu tạo lại artifact cụ thể. Nó không tự xoá artifact cũ và không bắt tạo lại toàn project.
