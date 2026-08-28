# Nghiên cứu thời gian chạy `/video-inspiration`

Ngày kiểm tra: 2026-08-22

## Kết luận

Có thể cho luồng `/video-inspiration` chạy lâu hơn, nhưng hiện tại không có một cấu hình timeout tổng duy nhất. Có ba lớp giới hạn độc lập:

1. Mỗi subprocess FFmpeg/yt-dlp có timeout mặc định 600 giây.
2. Mỗi lần gọi Codex AI có timeout 600 giây và bị hard-cap ở 600 giây.
3. Job bị API/UI xem là `stale` nếu 15 phút không cập nhật `updated_at`.

Điểm số 3 là rủi ro lớn nhất với video dài: STT xử lý tuần tự từng đoạn 25 giây nhưng không ghi heartbeat giữa các đoạn. Nếu một pha kéo dài quá 15 phút, backend task có thể vẫn chạy trong khi UI hiển thị “Bị gián đoạn” và ngừng polling.

Khuyến nghị không chỉ đổi một con số. Nên thêm heartbeat theo từng chunk/bước, đồng thời biến timeout thành cấu hình môi trường có validation. Sau đó có thể tăng stale threshold lên 45–60 phút như lớp bảo vệ dự phòng.

## Bằng chứng từ mã nguồn

### Luồng HTTP không bị giữ mở trong toàn bộ thời gian phân tích

`POST /video-inspiration/jobs/{job_id}/analyze` trả HTTP 202 và gọi `schedule_analyze`. Runner tạo background task rồi frontend polling trạng thái 2 giây/lần. Vì vậy client fetch không phải giới hạn thời gian tổng của phân tích.

Nguồn:

- `backend/routes/video_inspiration.py:97-105`
- `backend/services/video_inspiration_runs.py:213-223`
- `app/src/components/VideoInspiration/VideoInspiration.tsx:679-689`
- `app/src/lib/api/core/request.ts:232-247` — có `AbortController` để hủy chủ động, không đặt timer timeout tự động.

Ngoại lệ: endpoint tạo job từ URL tải video đồng bộ trước khi trả response; lần tải yt-dlp bị timeout 600 giây.

Nguồn:

- `backend/services/video_inspiration.py:827-865`

### Timeout media và AI hiện là 10 phút

Hai hằng số đều là 600 giây:

- `FFMPEG_TIMEOUT_SECONDS = 600`
- `AI_TIMEOUT_SECONDS = 600`

FFmpeg/yt-dlp đi qua `_run_command`, còn structured AI truyền timeout vào `ai_planning.run_codex_exec`.

Nguồn:

- `backend/services/video_inspiration.py:65-66`
- `backend/services/video_inspiration.py:273-280`
- `backend/services/video_inspiration.py:1600-1611`

AI planning còn hard-cap timeout ở 600 giây bằng `min(..., DEFAULT_CODEX_TIMEOUT_SECONDS)`. API model settings cũng khai báo `le=600`, nên chỉ đổi setting trong database/UI không thể vượt quá 10 phút.

Nguồn:

- `backend/services/ai_planning.py:27`
- `backend/services/ai_planning.py:770`
- `backend/models.py:364`
- `backend/models.py:380`

Muốn tăng một lần gọi Codex lên 20 phút cần thay đổi đồng bộ ít nhất default/cap trong `ai_planning.py`, giới hạn Pydantic trong `models.py`, và timeout được Video Inspiration sử dụng. Chỉ tăng `AI_TIMEOUT_SECONDS` sẽ vẫn bị `ai_planning.py` ép xuống 600 giây.

### Tổng workflow có thể lâu hơn nhiều so với 10 phút

Phân tích có hai lần AI nối tiếp: visual analysis và content analysis. Rewrite có bốn lần AI nối tiếp: brief, candidates, review, synthesis. Timeout 600 giây là giới hạn cho **mỗi lần gọi**, không phải toàn job.

Nguồn:

- `backend/services/video_inspiration.py:2795-2818`
- `backend/services/video_inspiration.py:2999-3028`

Theo giới hạn lý thuyết, riêng phần AI của analyze có thể gần 20 phút và rewrite gần 40 phút, chưa tính chờ queue, FFmpeg và STT.

### Ngưỡng stale 15 phút có thể kết luận sai khi job còn chạy

Backend tính stale bằng thời gian từ `updated_at` và hằng số `ACTIVE_JOB_STALE_SECONDS = 15 * 60`. Frontend nhận `is_stale`, đổi nhãn thành “Bị gián đoạn”, và `isJobActive` trả false; do đó polling tự động dừng.

Nguồn:

- `backend/services/video_inspiration.py:67-68`
- `backend/services/video_inspiration.py:722-740`
- `app/src/components/VideoInspiration/VideoInspiration.tsx:124-147`
- `app/src/components/VideoInspiration/VideoInspiration.tsx:679-689`

STT chia audio dài thành các đoạn 25 giây rồi gọi Whisper tuần tự. Trong vòng lặp này không có cập nhật progress/heartbeat vào job. Video được phép dài tối đa 30 phút, vì vậy trên máy chậm hoặc khi model phải tải, một pha STT có khả năng vượt ngưỡng stale 15 phút.

Nguồn:

- `backend/services/video_inspiration.py:55`
- `backend/services/video_inspiration.py:63-64`
- `backend/services/video_inspiration.py:999-1034`
- `backend/services/video_inspiration.py:1071-1097`
- `backend/services/video_inspiration.py:2746-2765`

### Queue cũng có thể làm người dùng thấy lâu

Workflow media cho phép tối đa ba workflow đồng thời. Codex planning cũng tối đa ba. Riêng STT Video Inspiration bị hard-cap một job, dù có environment variable.

Nguồn:

- `backend/services/video_workflow_pool.py:22-24,67-76`
- `backend/services/video_planning_pool.py:19-21,83-92`
- `backend/services/video_inspiration_runs.py:24-26,51-58`

Đặt `VOICEBOX_VIDEO_INSPIRATION_STT_CONCURRENCY=2` hiện không có tác dụng vì giá trị luôn bị `MAX_STT_CONCURRENCY = 1` ép xuống 1. Việc tăng concurrency có thể giảm thời gian chờ nhiều job, nhưng không làm một job đơn lẻ nhanh hơn và có nguy cơ tăng RAM/GPU, nên không phải thay đổi mặc định an toàn.

## Phương án đề xuất

### Phương án ưu tiên: heartbeat + timeout cấu hình

1. Thêm heartbeat cập nhật `updated_at` sau mỗi transcript chunk, mỗi frame hoặc theo nhịp 30–60 giây trong bước dài.
2. Chỉ coi stale khi đồng thời không còn run handle trong process và heartbeat đã quá hạn; hoặc dùng `last_heartbeat_at` riêng thay vì suy ra từ `updated_at` nghiệp vụ.
3. Chuyển các giá trị sang env có giới hạn hợp lý, ví dụ:
   - `VOICEBOX_VIDEO_INSPIRATION_FFMPEG_TIMEOUT_SECONDS=1200`
   - `VOICEBOX_VIDEO_INSPIRATION_AI_TIMEOUT_SECONDS=1200`
   - `VOICEBOX_VIDEO_INSPIRATION_STALE_SECONDS=3600`
4. Nâng cap AI planning và schema settings nếu thực sự cần Codex chạy quá 600 giây.
5. Giữ timeout theo từng bước, không đặt một timeout tổng cứng cho toàn workflow.

Ưu điểm: UI phản ánh đúng job còn sống; video dài không bị gắn stale giả; operator có thể điều chỉnh theo cấu hình máy.

### Bản vá tối thiểu

Nếu cần xử lý nhanh, tăng `ACTIVE_JOB_STALE_SECONDS` từ 15 lên 45 hoặc 60 phút. Điều này giảm stale giả nhưng không giải quyết việc job bị treo thật và không giúp một subprocess vượt timeout 600 giây.

Nếu lỗi thực tế là `AI planning timed out`, cần nâng cả:

- `AI_TIMEOUT_SECONDS`
- `DEFAULT_CODEX_TIMEOUT_SECONDS` và logic hard-cap
- `le=600` trong request/settings models

Nếu lỗi là FFmpeg/yt-dlp timeout, nâng `FFMPEG_TIMEOUT_SECONDS` hoặc tách timeout download khỏi timeout FFmpeg để dễ vận hành.

## Cải thiện tốc độ thay vì chỉ kéo dài timeout

Nếu mục tiêu thực tế là “đỡ phải chờ lâu”, các lựa chọn ít rủi ro hơn là:

- dùng chế độ `quick`, vì high quality lấy tối đa 36 keyframe thay vì 14;
- dùng model STT nhỏ/nhanh hơn khi độ chính xác cho phép;
- tránh chạy nhiều workflow media cùng lúc;
- ghi timing cho từng step để xác định nút thắt là download, STT, frame extraction, visual AI hay content AI;
- cân nhắc gộp hoặc rút gọn prompt/schema trước khi tăng timeout Codex.

Nguồn cho keyframe budget:

- `backend/services/video_inspiration.py:57-58`
- `backend/services/video_inspiration.py:1142-1146`

## Phạm vi xác minh

Nghiên cứu này dựa trên mã nguồn hiện tại của repository, là nguồn sở hữu hành vi runtime. Chưa thay đổi code và chưa chạy một video benchmark thật. Bước tiếp theo nên là lấy log/timing của một job chậm cụ thể để chọn đúng timeout và tránh che một deadlock hoặc lỗi provider bằng cách tăng giới hạn quá mức.
