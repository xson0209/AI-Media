# Spike word-budget TTS tiếng Việt — 28-08-2026

## Kết quả đo trong môi trường hiện tại

- Cơ sở dữ liệu `data/voicebox.db` có 2 generation đã lưu duration, đều là tiếng Anh.
- Không có generation hoặc shot audio tiếng Việt có `audio_duration`, vì vậy không thể giả vờ suy ra timing TTS tiếng Việt thật.
- Mẫu tiếng Anh: 27 từ / 25,28 giây ≈ 1,07 từ/giây (một mẫu duration bằng 0 bị loại).

Để có timing tiếng Việt thực tế thay vì suy đoán, ngày 28-08 đã chạy thêm một
spike bằng Microsoft Edge TTS voice `vi-VN-HoaiMyNeural` (8 câu cùng corpus đánh
giá TADA). File MP3 được tạo trong thư mục tạm `output/news-video-tts-spike-2026-08-28`
và đo duration bằng FFmpeg:

| Mẫu | Số từ | Duration (s) | Từ/giây |
|---|---:|---:|---:|
| short | 7 | 7,34 | 0,95 |
| tone | 13 | 11,69 | 1,11 |
| food | 16 | 14,35 | 1,11 |
| long | 32 | 33,77 | 0,95 |
| number | 17 | 18,05 | 0,94 |
| acronym | 15 | 15,29 | 0,98 |
| punctuation | 13 | 14,30 | 0,91 |
| dialogue | 16 | 18,29 | 0,87 |

Khoảng quan sát là **0,87–1,11 từ/giây** (trung bình xấp xỉ 0,98), thấp hơn
nhiều so với heuristic 2,5–3,0 từ/giây. Đây là timing của Edge TTS, không phải
TADA/Qwen nội bộ; TADA 3B chưa có model/cache trên máy và Qwen không được xem là
Vietnamese chính thức. Vì vậy spike này đủ để chứng minh 2,5–3,0 không thể được
coi là tốc độ TTS tiếng Việt phổ quát, nhưng chưa đủ căn cứ đổi ngưỡng sản phẩm
cho mọi engine.

## Quyết định an toàn

Resolver hiện vẫn giữ cảnh báo 2,5–3,0 từ/giây như một giới hạn nội dung ngắn,
không tự cắt câu. Khi engine Voicebox chính thức có timing tiếng Việt (Qwen hoặc
TADA sau khi được chấp thuận), cần chạy lại spike bằng chính engine đó rồi mới
điều chỉnh ngưỡng sản phẩm. Vượt ngưỡng luôn trả hướng dẫn rút ngắn hoặc chia shot.
