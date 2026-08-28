# Đề xuất: 01 — chuẩn hóa Gói nguồn

## Vì sao cần làm

Các luồng phân tích truyện, phân tích video, tạo truyện và tạo video đang có nhiều kiểu “nguồn” khác nhau:

- truyện tranh có `source_context` và các chunk của `StoryEpisodeSourceDocument`;
- Video Inspiration có payload handoff và `ai_video_source_blocks`;
- AI Video có `VideoSourceBlock`;
- Story Studio tự compile context từ nguồn truyện khi tạo candidate/master.

Các cấu trúc này đang phục vụ được từng luồng riêng, nhưng chưa có một lớp chung để nói: “đây là Gói nguồn chuẩn mà các luồng sáng tạo sẽ đọc”. Vì vậy khi mở rộng sang tạo 3 bản ứng viên, chọn master, render lại và đánh dấu stale theo phụ thuộc, hệ thống dễ bị chồng chéo logic.

## Thay đổi đề xuất

Thêm một module backend dùng chung cho **Gói nguồn / Source Package**:

- có schema version chung cho Gói nguồn;
- gom được nguồn từ truyện hoặc video về cùng một cấu trúc;
- giữ được provenance, revision, limitations, coverage metrics và fingerprint;
- xuất được source blocks tương thích với AI Video;
- không làm thay đổi API/UI hiện tại trong lát đầu tiên.

Lát code đầu tiên sẽ dùng Gói nguồn ở hai điểm an toàn:

1. `comic_series_analysis.source_context` có thể compile Gói nguồn từ `StoryEpisodeSourceDocument`.
2. `video_project_memory` tạo source blocks thông qua Gói nguồn trước khi trả về `VideoSourceBlockDraft`.

## Phạm vi

Trong change này:

- tạo proposal/design/tasks/spec delta bằng tiếng Việt;
- refactor backend theo lát 01;
- thêm test cho Gói nguồn từ truyện và video;
- chạy test, fix lỗi nếu có, rồi test lại.

## Ngoài phạm vi

- Chưa chuyển toàn bộ Story Studio sang workflow 3 candidate/master/render.
- Chưa đổi UI.
- Chưa đổi database schema.
- Chưa xóa cấu trúc cũ.
- Chưa triển khai stale/rebuild cho mọi artifact downstream.

## Tên change

`01-goi-nguon-chuan-hoa`
