# Thiết kế: Gói nguồn chuẩn hóa

## Hiện trạng

Repo đang có nhiều cấu trúc nguồn:

- `comic_series_analysis.source_context.CompiledContext` dùng cho Story Studio.
- `StoryEpisodeSourceDocument` và `StoryEpisodeSourceChunk` giữ nguồn truyện đã duyệt.
- `video_project_memory.build_handoff_payload()` giữ dữ liệu phân tích video và kịch bản đã duyệt.
- `video_project_memory.source_blocks_from_payload()` format payload thành `VideoSourceBlockDraft`.
- `VideoSourceBlock` là input trực tiếp cho AI Video phase 2.

Điểm thiếu là một cấu trúc dùng chung để biểu diễn “nguồn đã hiểu và có thể dùng tiếp”.

## Hướng triển khai

### 1. Thêm module `source_package`

Module backend dùng chung sẽ có các khái niệm:

- `SourcePackage`: Gói nguồn đã chuẩn hóa.
- `SourcePackageBlock`: một khối nội dung có thứ tự, loại block, nội dung, evidence và metadata.
- `build_source_package()`: tạo Gói nguồn từ các block đã biết.
- `to_ai_video_source_blocks()`: chuyển Gói nguồn thành danh sách block tương thích AI Video.

Gói nguồn phải có:

- `schema_version`;
- `source_kind`;
- `source_ref_id`;
- `source_revision`;
- `title`;
- `summary`;
- `blocks`;
- `coverage_metrics`;
- `limitations`;
- `provenance`;
- `fingerprint`.

Fingerprint được tính từ dữ liệu ổn định của gói: schema, nguồn, revision, title/summary, block type/content/evidence/metadata, coverage, limitations và provenance.

### 2. Adapter truyện

Trong `comic_series_analysis.source_context`, thêm hàm compile Gói nguồn từ episode hiện tại.

Adapter này dùng lại logic hiện có:

- chỉ lấy source document hiện hành đã approved;
- chỉ dùng chunk `accepted`;
- giữ giới hạn char budget;
- báo số chunk bị bỏ qua;
- giữ source document id/revision và fingerprint.

Không đổi hành vi của `compile_context()` để tránh phá luồng hiện tại.

### 3. Adapter video

Trong `video_project_memory`, thêm helper tạo Gói nguồn từ handoff payload hiện tại.

Sau đó `source_blocks_from_payload()` không tự format toàn bộ danh sách block bằng tuple rời nữa, mà:

1. build Gói nguồn từ payload;
2. chuyển Gói nguồn sang `VideoSourceBlockDraft`.

Việc này giữ đầu ra tương thích nhưng đưa seam Gói nguồn vào đúng chỗ.

### 4. Kiểm thử

Thêm test cho:

- Gói nguồn truyện chỉ dùng chunk accepted;
- fingerprint đổi khi revision hoặc nội dung đổi;
- Gói nguồn video vẫn sinh đủ block `idea`, `rough_script`, `character_notes`, `style_notes`, `must_have`, `avoid`;
- block dài được truncate an toàn khi xuất sang AI Video.

## Rủi ro

- Nếu đổi format source blocks quá mạnh, test AI Video hiện có có thể fail.
- Nếu fingerprint tính thiếu dữ liệu, stale/rebuild sau này sẽ không đáng tin.
- Nếu Gói nguồn import ngược vào module domain cụ thể, seam sẽ bị chồng chéo.

## Kiểm soát

- Module Gói nguồn không import `comic_series_analysis`, `video_project_memory`, database model hay API model.
- Adapter domain-specific nằm ở module domain hiện có.
- Output `VideoSourceBlockDraft` giữ tương thích với test cũ.
- Không đổi DB schema trong bước này.
