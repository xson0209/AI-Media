# Audit Cartoon — 28-08-2026

Audit trực tiếp trên `data/voicebox.db` sau khi chạy migration:

- 30 project có `title` hoặc `topic` chứa `Cartoon`.
- 420 shot trong 30 project.
- 420/420 shot có `speech_cues_json` và `english_narration`.
- 126/420 shot có active clip.
- 350 shot không có exact speech text trong prompt lưu trữ hiện tại; 94 trong số đó có clip active.

Kết quả này **không khớp** số liệu lịch sử 24 shot thiếu thoại và 7 clip đã render được ghi trong proposal. Audit đã được chạy và lưu lại đầy đủ; các con số 24/7 được giữ như baseline lịch sử, không thay thế bằng số liệu hiện tại. Không migrate hoặc regenerate prompt cũ dựa trên giả định 24/7 khi chưa xác định đúng snapshot.
