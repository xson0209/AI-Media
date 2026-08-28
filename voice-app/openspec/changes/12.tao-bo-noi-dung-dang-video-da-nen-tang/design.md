## Tổng quan thiết kế

    Project + Story + Narration + Retention + Prompt pack
                         |
                         v
              Context đầu vào đã giới hạn
                         |
                         v
              Structured Codex generation
                         |
                         v
             Mapping và validation atomic
                         |
                         v
              VideoPublishingMetadata
                         |
             +-----------+-----------+
             |           |           |
          YouTube      TikTok     Facebook
             |           |           |
        4 ô copy     4 ô copy     4 ô copy
                         |
                         v
                 Voice -> Subtitle

## Quyết định thiết kế

### 1. Bộ nội dung đăng video là artifact cấp project

Metadata đăng video mô tả toàn bộ video, không mô tả riêng một segment. Vì vậy hệ thống thêm artifact cấp project, tạm gọi VideoPublishingMetadata, thay vì thêm field vào VideoShotPrompt.

Không dùng video_projects.title làm tiêu đề đăng video. Field hiện tại là tên quản lý project, tên file hoặc tên package và có thể được người dùng đổi vì mục đích tổ chức nội bộ.

Mô hình lưu trữ đề xuất:

    id
    project_id
    status
    target_language
    platforms_json
    input_fingerprint
    revision
    stale
    failure_reason
    created_at
    updated_at

platforms_json có đúng ba key canonical:

    youtube
    tiktok
    facebook

Mỗi platform có:

    title
    description
    hashtags[]
    thumbnail_prompt
    status
    input_fingerprint
    revision

Hashtag được lưu dạng mảng đã chuẩn hóa. Frontend nối bằng một khoảng trắng khi hiển thị hoặc copy.

Trạng thái tổng thể chỉ là completed khi cả ba platform hợp lệ với fingerprint đầu vào hiện tại. Tạo lại một platform chỉ thay payload của platform đó sau khi validation thành công; hai platform còn lại được giữ nguyên. Nếu các platform còn lại đang stale thì toàn bộ artifact vẫn stale.

### 2. Một lần structured generation tạo đủ ba nền tảng

Mặc định một lần Codex call tạo toàn bộ YouTube, TikTok và Facebook để giữ cùng một lời hứa, chủ đề, CTA và nhận diện hình ảnh. Output chỉ được ghi sau khi cả ba platform qua mapping và validation.

Nếu một platform thiếu field, sai type hoặc vi phạm giới hạn cấu hình, toàn bộ attempt tạo tất cả bị từ chối và retry trong giới hạn hiện có. Artifact hợp lệ trước đó không bị xóa.

Khi người dùng chọn Tạo lại nền tảng, service chỉ yêu cầu output cho platform đó, validate bằng đúng platform profile rồi thay atomically đúng key đã chọn. Revision platform và revision artifact tăng sau commit. Prompt tạo lại phải nhận bản tóm tắt của hai platform còn lại để không tạo thông điệp mâu thuẫn.

### 3. Context đầu vào dùng nguồn sự thật đã duyệt và được giới hạn

Service tạo publishing metadata dùng:

- project topic và tên quản lý chỉ như ngữ cảnh, không copy máy móc thành title;
- target_language, video_purpose, call_to_action_style và aspect_ratio;
- detailed script hoặc narration cuối;
- hook, payoff, retention plan và target audience khi có;
- shot/segment summary và prompt explanation;
- visual style, continuity và Series/Project Memory liên quan;
- prompt video cuối ở dạng tóm tắt hoặc fingerprint, không đưa toàn bộ dữ liệu dài nếu không cần.

Context phải có giới hạn ký tự, redaction và type summary như các bước planning khác. Full source, full prompt pack hoặc narration dài không được ghi vào debug metadata.

### 4. Nội dung theo target_language

Title, description và hashtag hướng tới người xem phải dùng target_language của project. Prompt thumbnail có thể dùng ngôn ngữ kỹ thuật dễ hiểu cho công cụ tạo ảnh nhưng mọi chữ hiển thị được đề xuất, nếu có, phải phù hợp target_language.

UI, helper text, lỗi và trạng thái vẫn dùng tiếng Việt.

### 5. Tối ưu theo profile nền tảng, không hứa bảo đảm SEO

Backend định nghĩa profile nền tảng có version và có thể cập nhật. Profile điều khiển:

- độ dài và cấu trúc title/description;
- số lượng, định dạng và mức trùng lặp hashtag;
- cách dùng keyword tự nhiên, CTA và hook;
- tỷ lệ, safe area, bố cục và mức chi tiết của thumbnail prompt;
- quy tắc tránh claim không có trong source;
- quy tắc tránh hashtag stuffing, clickbait sai sự thật, watermark, logo hoặc random text.

Contract sử dụng cụm từ tối ưu cho khả năng khám phá và tỷ lệ nhấp theo profile nền tảng. Hệ thống không tuyên bố bảo đảm ranking.

### 6. Prompt thumbnail là văn bản, chưa phải ảnh

thumbnail_prompt mô tả subject, hành động, biểu cảm, ánh sáng, màu sắc, bố cục, điểm nhấn, continuity, tỷ lệ và safe area cho từng nền tảng.

Prompt phải tránh yêu cầu công cụ tạo ảnh tự dựng nhiều chữ nhỏ. Nếu cần chừa chỗ đặt chữ, prompt chỉ dẫn vùng trống rõ ràng và tránh random text, watermark hoặc logo không có trong source.

Change này không thêm image provider, job tạo ảnh, file thumbnail, credit approval hoặc asset download.

### 7. Mapping deterministic và ghi atomic

Schema canonical không nhận platform ngoài youtube, tiktok và facebook. Mapper có thể hỗ trợ alias đã whitelist, nhưng phải từ chối:

- thiếu hoặc thừa platform;
- trùng platform;
- title, description hoặc thumbnail_prompt không phải string;
- hashtags không phải mảng string;
- hashtag rỗng, trùng sau normalize hoặc chứa khoảng trắng không hợp lệ;
- field bắt buộc rỗng;
- output vượt giới hạn profile;
- alias mơ hồ hoặc xung đột.

Validation hoàn tất trước mọi thao tác xóa hoặc thay artifact cũ. Attempt lỗi chỉ ghi debug event đã redaction và không ghi partial data.

### 8. Trạng thái, revision, fingerprint và stale

Trạng thái người dùng nhìn thấy:

    missing
    generating
    completed
    stale
    failed

input_fingerprint được tạo từ các nguồn ảnh hưởng trực tiếp như target language, video purpose, CTA, approved story/narration, prompt ids hoặc content hash, retention plan và visual style.

Artifact chuyển stale khi:

- story, narration, shot hoặc prompt cuối thay đổi;
- target_language, video_purpose hoặc call_to_action_style thay đổi;
- visual style hoặc continuity ảnh hưởng thumbnail thay đổi;
- user direction liên quan nội dung đăng thay đổi.

Đổi riêng voice_profile_id không làm stale publishing metadata. Tạo lại publishing metadata không làm stale voice hoặc subtitle.

### 9. API tách biệt và có retry

API đề xuất:

    POST /ai-video/projects/{project_id}/publishing-metadata
    GET  /ai-video/projects/{project_id}/publishing-metadata

POST nhận platform = all, youtube, tiktok hoặc facebook và force tùy chọn. all là mặc định. GET trả artifact mới nhất hoặc trạng thái missing. Error response dùng tiếng Việt, error code và request id; không trả raw structured output dài.

Retry sau lỗi metadata chỉ chạy lại bước metadata hoặc platform được chọn. Prompt hợp lệ, voice hợp lệ và subtitle hợp lệ không bị tạo lại nếu dependency không đổi.

### 10. Planning và workflow concurrency

Mọi Codex call của service mới phải đi qua video_planning_pool và observability hiện có. Auto-run dùng callback chờ/acquire giống develop_story, generate_shots và generate_prompts để UI thấy waiting_planning thay vì chạy planning vượt giới hạn.

Không đưa publishing generation vào TTS queue. Planning pool và voice generation queue tiếp tục là hai tài nguyên độc lập.

### 11. Thứ tự auto-run và gate duyệt

STEP_ORDER mới:

    validate
    develop_story
    waiting_planning
    review_story
    generate_shots
    generate_prompts
    generate_publishing_metadata
    review_prompts
    generate_clips
    waiting_clips
    generate_voice
    waiting_voice
    generate_subtitle
    generate_render
    waiting_render
    completed

Trong review_gated, publishing metadata được tạo trước review_prompts. Gate prompts hiển thị cả prompt video và bộ nội dung đăng. Nếu người dùng sửa hoặc tạo lại prompt trước khi tiếp tục, metadata cũ chuyển stale và auto-run phải tạo lại metadata trước voice.

Trong full_auto, hệ thống tự ghi nhận gate nhưng vẫn phải validate prompt và metadata trước khi gọi _voice_action.

### 12. Material target giữ tương thích

prompts_only giữ nguyên: story, shot và prompt video; không tạo publishing metadata, voice hoặc subtitle.

Thêm publishing_kit: story, shot, prompt video và publishing metadata; dừng trước voice/subtitle.

full_materials và video_clips bắt buộc có publishing metadata completed trước khi hoàn tất. Summary thêm publishing_metadata_status hoặc metadata_ready.

Client cũ không gửi target mới tiếp tục dùng default hiện tại và nhận thêm metadata trong full_materials mà không cần thay request shape.

### 13. UI gồm ba tab và mười hai ô copy

Section Nội dung đăng video được đặt sau Prompt video và trước Voice và phụ đề.

UI có ba tab hoặc segmented control:

    YouTube
    TikTok
    Facebook

Mỗi tab có bốn ô read-only:

    Tiêu đề video
    Mô tả
    Hashtag
    Prompt tạo ảnh bìa

Mỗi ô có nút biểu tượng Copy với tooltip và aria-label riêng. Copy chỉ lấy giá trị của ô đang bấm. Có thể có Copy tất cả nhưng không thay thế copy từng trường.

Section có loading, empty, stale, failed và completed state; có Tạo lại nền tảng và Tạo lại tất cả. Layout desktop/mobile không overflow, textarea có kích thước ổn định và nội dung dài cuộn bên trong.

Nên tách UI thành AIVideoPublishingMetadataPanel thay vì tiếp tục tăng kích thước AIVideoAssistant.

### 14. Luồng thủ công và auto-run dùng cùng artifact

Ở luồng thủ công, sau khi generate prompt thành công, frontend yêu cầu backend tạo publishing metadata và hiển thị trạng thái riêng. Nếu metadata lỗi, prompt vẫn còn hợp lệ và UI hiển thị nút thử lại.

Ở auto-run, bước metadata được persist trong runner; không dựa duy nhất vào chuỗi mutation frontend. Reload hoặc restart có thể resume từ metadata nếu các dependency trước đó còn hợp lệ.

### 15. Voice và subtitle được tái sử dụng

Sau publishing metadata, auto-run tiếp tục dùng _voice_action, generation queue, sync status và generate_subtitle hiện có. Change không đổi engine, model selection, chunking, normalization hoặc hard cap voice.

Metadata không phải input của TTS hoặc SRT. Vì vậy chỉnh title, description, hashtag hoặc thumbnail prompt không được làm stale voice/subtitle.

### 16. Sửa tính đúng đắn của subtitle trong chuỗi mới

Subtitle cursor phải phản ánh vị trí timeline thật của mỗi segment. Với segment không lời, hệ thống vẫn tăng cursor theo duration timeline của segment trước khi tạo cue cho segment tiếp theo.

Khi scene/shot voice được tạo lại, hủy hoặc đổi duration, hệ thống phải đánh dấu cả subtitle_status cấp scene/shot và VideoSubtitle cấp project là stale. Readiness, download, package và render không được coi SRT cũ là completed.

Timing cue tiếp tục có thể dùng phân bổ theo text trong phạm vi change này, nhưng UI và tài liệu không được mô tả là forced alignment hoặc khớp từng từ tuyệt đối.

### 17. Reset, delete, package và quality

Reset generated data và delete project phải xóa publishing metadata. Package export có thể bổ sung file text/JSON của publishing kit nếu package contract được bật trong implementation, nhưng không phải điều kiện để người dùng copy từng ô.

Quality report có thể đọc metadata như artifact bổ sung; change này chỉ bắt buộc validation nguồn, field, platform, language và stale, không mở rộng sang chấm điểm marketing hoặc dự đoán lượt xem.

### 18. Messenger nằm ngoài scope

Platform canonical của change chỉ có youtube, tiktok và facebook. Messenger không có tab SEO. Nếu sau này cần nội dung gửi riêng, hệ thống thêm share_message dựa trên publishing kit thay vì giả lập title/description/hashtag của một nền tảng khám phá nội dung.

## Rủi ro và giảm thiểu

- Codex tạo title clickbait hoặc claim không có nguồn: bắt buộc source-grounding, validation và cảnh báo.
- Giới hạn nền tảng thay đổi: dùng platform profile có version và test, không rải magic number trong UI.
- Structured output dài hoặc sai type: schema chặt, giới hạn ký tự và retry có kiểm soát.
- Metadata stale nhưng UI vẫn cho copy: hiển thị cảnh báo stale rõ và không coi auto-run ready.
- Thêm bước planning làm auto-run lâu hơn: dùng planning pool, progress riêng và retry đúng bước.
- Prompt thumbnail yêu cầu chữ khó render: ưu tiên bố cục và vùng trống, tránh random text.
- SRT lệch sau đoạn không lời: thêm test timeline có silent segment.
- Voice mới nhưng SRT cũ vẫn được dùng: stale cả artifact phụ đề cấp project và chặn readiness/download phù hợp.

## Kế hoạch migration

1. Thêm bảng/artifact publishing metadata và migration idempotent.
2. Thêm model, mapper, service và API mà chưa bật auto-run.
3. Thêm UI đọc/tạo/copy bằng feature path hiện có.
4. Thêm step auto-run, material target publishing_kit và summary.
5. Sửa stale/timeline subtitle và thêm regression tests.
6. Bật metadata cho full_materials và video_clips.

Project cũ không có artifact mới hiển thị trạng thái missing và vẫn mở được. Không backfill tự động để tránh gọi Codex ngoài ý muốn; người dùng hoặc auto-run tạo artifact khi cần.

## Khả năng quay lui

Có thể ẩn section UI và bỏ step generate_publishing_metadata khỏi material target mới mà không xóa prompt, voice, subtitle hoặc render hiện có. Bảng metadata là dữ liệu bổ sung. Nếu rollback migration không được hỗ trợ tại runtime, code cũ vẫn có thể bỏ qua bảng mới.
