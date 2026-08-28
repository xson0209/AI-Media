## Context

Pipeline dựng MP4 tách hoàn toàn nhánh video khỏi nhánh audio rồi mux ở cuối:

```
        NHÁNH VIDEO                          NHÁNH AUDIO
        ───────────                          ──────────
   clip gốc (có thể có audio)           _build_audio_segments()
        │                                       │
        │  normalize: ffmpeg ... -an            ├── speech source = clip + có narration?
        │     strip sạch audio                  │    → rút audio TỪ CLIP (-vn, apad, atrim)
        ▼                                       │
   concat video (stream copy)                   ├── có file giọng đọc tổng hợp?
        │                                       │    → dùng file đó
        │                                       │
        │                                       └── còn lại
        │                                            → anullsrc = IM LẶNG
        │                                       │
        │                                  concat audio.wav
        │                                       │
        │                              enhanced_audio? → amix SFX/BGM
        ▼                                       ▼
   burn-in phụ đề  ─────────────────────►  mux cuối
                                    -map 0:v:0 -map 1:a:0 -c:a aac -shortest
```

Nhánh audio hiện có ba nhánh con, và nhánh thứ ba là `anullsrc` — nhánh "còn lại" chứ không phải một lựa chọn có chủ ý. Đây là nguồn gốc của việc phân đoạn không narration bị im lặng hoàn toàn dù clip gốc có tiếng.

Hai phát hiện quan trọng đã xác minh trực tiếp trong code:

**Speech source là theo NGÔN NGỮ PROJECT, không per-shot.** `speech_source_for_language()` trả về nguồn Veo-native khi và chỉ khi `target_language` là `vi`. Nghĩa là mọi project tiếng Việt đều rơi vào nhánh trích audio từ clip. Điều này quyết định phần lớn thiết kế bên dưới.

**Hiện chưa có duck nào cả.** Bước trộn SFX/BGM chỉ hạ `volume` tĩnh rồi `amix`, không có sidechain. Ghi chú "duck asset bổ sung" trong design của change `veo-native-vietnamese-speech` là ý định chưa được implement. Change này phải xây cơ chế hạ tiếng nền từ đầu.

Ngoài ra `amix` không set `normalize=0`, mà mặc định FFmpeg là bật — đã xác minh bằng `ffmpeg -h filter=amix`. Hệ quả là giọng đọc bị chia theo số input:

```
chỉ giọng đọc     →  giọng × 1.00
giọng + 1 SFX     →  giọng × 0.50
giọng + 3 SFX     →  giọng × 0.25
```

Đây là lỗi đang tồn tại, độc lập với tiếng nền, nhưng phải sửa trong cùng change: thêm tiếng nền là thêm một input nữa vào `amix`, nên nếu không sửa `normalize` thì tiếng nền sẽ bị quy oan là nguyên nhân làm giọng đọc chìm.

## Goals / Non-Goals

**Goals:**

- Phân đoạn không có narration mà clip có tiếng thì phát tiếng gốc, thay vì im lặng.
- Tiếng gốc làm nền dưới giọng đọc ở project dùng giọng đọc tổng hợp, tự động hạ mức khi có giọng.
- Không bao giờ cộng trùng cùng một nguồn audio vào chính nó.
- Giọng đọc giữ nguyên mức bất kể trộn thêm bao nhiêu nguồn.
- Công tắc tiếng gốc trên UI có tác dụng thật, không còn là nút chết.
- Mặc định giữ đúng hành vi cũ để project đang chạy không đổi kết quả.

**Non-Goals:**

- Không thêm chế độ "chỉ tiếng gốc" (bỏ giọng đọc). Để ngỏ cho sau.
- Không đổi kiểu dữ liệu `mute_clip_audio` trên API.
- Không thêm cấu hình tiếng gốc riêng cho từng phân đoạn.
- Không bỏ bước loại bỏ audio ở nhánh video, không đổi kiến trúc tách video/audio.
- Không đụng phần làm sạch watermark (đã xử lý ở change riêng).
- Không đổi cơ chế phụ đề.

## Decisions

### 1. Guard theo speech source: không bao giờ cộng trùng một nguồn

Đây là quyết định quan trọng nhất. Khi project dùng speech source trích từ clip, giọng đọc **chính là** audio của clip đó. Nếu lại lấy audio clip làm nền thì hai track là cùng một nguồn:

```
Phân đoạn có narration, project tiếng Việt:
   track giọng  = audio clip Veo          ┐
                                          ├── CÙNG MỘT NGUỒN
   track nền    = audio clip Veo × 0.3    ┘
   → cộng lại: comb filtering, nghe như vọng/echo, giọng méo
```

Bảng quyết định đầy đủ:

```
                                    nguồn giọng đọc     thêm nền?      thay đổi
──────────────────────────────────────────────────────────────────────────────────
Project VI, phân đoạn CÓ narration  = audio clip        ❌ guard        không đổi
Project VI, phân đoạn KHÔNG narr.   = (im lặng)         ✅ full        hết im lặng ★
Project EN, phân đoạn CÓ narration  = file TTS          ✅ ducked      TTS trên nền
Project EN, phân đoạn KHÔNG narr.   = (im lặng)         ✅ full        hết im lặng
Clip không có audio                 = bất kỳ            ❌ im lặng     không đổi
```

**Hệ quả cần nói rõ:** với project tiếng Việt — luồng chính hiện tại — change này **chỉ** cải thiện các phân đoạn không có narration. Phân đoạn có narration vốn đã lấy đủ audio clip nên guard giữ nguyên. Đây **không phải** "giọng đọc trên nền tiếng gốc" cho project tiếng Việt; phần đó chỉ áp dụng cho project dùng giọng đọc tổng hợp. Lợi ích thật cho luồng tiếng Việt là audio liền mạch cả video thay vì bị ngắt quãng ở các đoạn không thoại.

Phương án khác đã cân nhắc: (a) không guard, luôn thêm nền — gây méo giọng trên toàn bộ project tiếng Việt, không thể chấp nhận; (b) guard theo từng shot dựa trên nguồn audio thực tế của shot đó — chính xác hơn về lý thuyết nhưng speech source là thuộc tính project nên không có dữ liệu per-shot để phân biệt, và thêm dữ liệu đó là mở rộng phạm vi.

### 2. Trộn một lần trên toàn timeline, không trộn theo từng phân đoạn

Dựng timeline nền riêng, ghép lại, rồi hạ mức và trộn một lần với timeline giọng đọc:

```
_build_audio_segments()   →  voice.wav   (giữ nguyên + guard)
builder tiếng nền  MỚI    →  bed.wav     (rút -vn từ clip gốc, im lặng nếu không có)
                                  │
                   hạ mức nền theo tín hiệu giọng đọc
                                  │
                          trộn (không normalize)
                                  │
                        + SFX/BGM nếu được bật
                                  │
                               mux cuối
```

Lý do: hạ mức theo từng phân đoạn nghĩa là mỗi đoạn có một ngưỡng riêng, nghe không đều khi chuyển đoạn. Trộn một lần cho mức nền nhất quán, và tận dụng được bước ghép audio đã có.

### 3. Hạ tiếng nền bằng nén sidechain, giọng đọc là tín hiệu điều khiển

Dùng `sidechaincompress` — đã xác minh có trong FFmpeg đi kèm dự án. Giọng đọc làm sidechain (tín hiệu điều khiển), tiếng nền là tín hiệu bị nén. Tham số khởi điểm: mức nền khoảng 0,25–0,3; hạ thêm khoảng 8–10 dB khi có giọng; đáp ứng nhanh khi giọng vào, phục hồi khoảng 250 ms khi giọng dứt.

Phương án khác đã cân nhắc: hạ `volume` tĩnh như bước SFX/BGM đang làm — đơn giản hơn nhưng nền sẽ lấn giọng ở đoạn giọng nhỏ và quá chìm ở đoạn không có giọng; nén sidechain cho kết quả tự nhiên hơn với chi phí thêm một filter.

Các tham số này là điểm khởi đầu có thể tinh chỉnh sau khi nghe thực tế, không phải hằng số bất biến.

### 4. Tiếng nền lấy từ clip gốc, không lấy bản đã làm sạch watermark

Trong luồng render, biến giữ đường dẫn video là bản đã qua làm sạch watermark. Tiếng nền **không** được dùng biến đó mà phải dùng đường dẫn clip gốc:

```
clip gốc ──┬──► làm sạch watermark ──► chuẩn hoá ──► nhánh VIDEO
           └────────────────────────────────────────► nhánh AUDIO (gốc)
```

Hai lý do: làm sạch watermark chỉ sửa hình không sửa tiếng nên đi qua nó là vô ích và tốn thêm; và đã có test khẳng định hợp đồng này (audio phải lấy từ clip gốc), nếu vi phạm thì test đỏ.

### 5. Tổng thời lượng tính từ timeline, không đọc từ enhanced render plan

Tổng thời lượng hiện chỉ tồn tại trong enhanced render plan. Nhưng tiếng nền phải chạy được cả khi enhanced render tắt, nên phải tính tổng trực tiếp từ timeline. Đọc từ plan sẽ làm tiếng nền phụ thuộc một tính năng không liên quan.

### 6. `mute_clip_audio`: giữ boolean ở API, ánh xạ sang khái niệm ba mức ở tầng render

Field này hiện tồn tại xuyên suốt API — model, route, kiểu dữ liệu frontend, client, giá trị mặc định của panel — nhưng **không xuất hiện ở bất kỳ đâu trong pipeline render**. Nó là nút chết, được để inert có chủ ý theo design của change `veo-native-vietnamese-speech`.

Quyết định: giữ boolean trên API để không phá tương thích, nhưng tầng render ánh xạ sang một khái niệm nguồn audio ba mức, hiện chỉ dùng hai mức (bỏ hẳn ↔ làm nền). Mức thứ ba (chỉ tiếng gốc) để ngỏ, không implement.

Lý do chọn cách này thay vì đổi thẳng thành enum ba mức: tránh đúng cái bẫy mà field này đã mắc một lần. Nếu sau muốn thêm mức thứ ba, chỉ cần mở rộng bảng ánh xạ chứ không phải sửa lại kiến trúc ở năm chỗ trên API. Đổi enum ngay bây giờ thì phải sửa model, route, kiểu frontend, client và panel, mà mức thứ ba lại còn xung đột với guard ở mục 1 (bỏ giọng đọc trong khi giọng đọc chính là tiếng clip là vô nghĩa) nên cần thêm luật riêng — chưa đáng làm lúc này.

Giá trị mặc định giữ nguyên là "bỏ tiếng gốc" để project đang chạy không đổi kết quả.

**Ghi chú lỗi thời cần biết:** design của change `veo-native-vietnamese-speech` có nêu "`mute_clip_audio` vẫn mặc định true ở settings nhưng nguồn audio hiệu lực do speech source quyết định; không expose generic mixing có thể gây chồng giọng trong change này". Ghi chú đó **đã lỗi thời** kể từ change này: field được nối vào render thật, và nguy cơ chồng giọng mà nó lo được xử lý bằng guard ở mục 1 chứ không bằng cách để field inert.

### 7. Tắt `normalize` khi trộn

Bước trộn phải tắt `normalize` để giọng đọc không bị chia theo số input. Mức của từng asset SFX/BGM vẫn do cấu hình asset quyết định như hiện tại.

Tác dụng phụ cần lường: sau khi tắt, SFX/BGM sẽ **nghe to hơn** so với hiện tại, vì trước đây chúng cũng bị chia nhỏ cùng giọng đọc. Đây là hành vi đúng (mức asset khớp cấu hình), nhưng là thay đổi cảm nhận được với project đang có SFX/BGM.

### 8. Bỏ hẳn bước trộn khi timeline nền toàn im lặng

Nếu mọi phân đoạn đều rơi vào nhánh guard hoặc clip không có audio, timeline nền sẽ toàn im lặng. Khi đó bỏ hẳn bước hạ mức và trộn, dùng trực tiếp timeline giọng đọc — tránh tốn thời gian xử lý và tránh mọi rủi ro biến đổi âm thanh không cần thiết. Đây cũng là đường giữ nguyên hành vi cũ cho project tiếng Việt thuần thoại.

### 9. Lỗi tiếng nền là fallback, không phải lỗi render

Theo đúng pattern của bước trộn SFX/BGM hiện có: lỗi thì ghi lý do fallback và tiếp tục bằng timeline giọng đọc, không làm cả job thất bại. Tiếng nền là cải thiện chất lượng, không phải yêu cầu bắt buộc của bản dựng.

Một chi tiết cần xử lý: đường ghi fallback hiện có gắn vào enhanced render plan, nhưng plan chỉ tồn tại khi enhanced render bật. Vì tiếng nền chạy độc lập, cần đường ghi fallback không phụ thuộc plan.

## Risks / Trade-offs

- **Cộng trùng nguồn audio gây vọng tiếng và méo giọng trên toàn bộ project tiếng Việt** → Guard theo speech source ở mục 1, kèm test riêng cho từng nhánh; đây là rủi ro nghiêm trọng nhất của change này.
- **Kỳ vọng sai về lợi ích cho project tiếng Việt** → Ghi rõ trong design và tài liệu: project tiếng Việt chỉ được cải thiện ở phân đoạn không narration; đã trao đổi và thống nhất trước khi làm.
- **SFX/BGM nghe to hơn sau khi tắt normalize** → Là hành vi đúng chứ không phải hồi quy; cần nêu khi bàn giao để không bị hiểu là lỗi mới.
- **Tiếng nền lấy sai từ bản đã làm sạch watermark** → Dùng đường dẫn clip gốc; đã có test khẳng định hợp đồng này nên vi phạm sẽ bị bắt.
- **Mức nền và độ hạ chưa vừa tai ngay lần đầu** → Tham số là điểm khởi đầu, tách rõ để tinh chỉnh; cần nghe thử bản dựng thật trước khi chốt.
- **Tăng thời gian dựng vì thêm một timeline audio và một bước trộn** → Bỏ hẳn bước trộn khi timeline nền toàn im lặng; audio nhẹ hơn video nhiều nên chi phí thêm nhỏ so với chuẩn hoá và encode video.
- **Hồi quy ở test cũ** → Rủi ro thấp: helper tạo clip trong test mặc định không có audio, nên clip test rơi vào nhánh im lặng và giữ nguyên hành vi. Assertion hiện có về chuỗi `amix` vẫn khớp sau khi thêm tuỳ chọn normalize.
- **Nhầm lẫn giữa hai thay đổi khi nghe kết quả** → Sửa `normalize` cùng lúc chính là để tránh việc tiếng nền bị quy oan là nguyên nhân giọng đọc chìm.

## Migration Plan

1. Sửa mức âm lượng khi trộn trước (tắt normalize) và chạy test để tách biệt tác động của nó khỏi phần tiếng nền.
2. Thêm builder timeline tiếng nền cùng bảng quyết định guard, chưa đấu vào luồng render.
3. Thêm bước hạ mức và trộn, rồi đấu vào luồng render sau bước ghép audio.
4. Nối `mute_clip_audio` vào tầng render qua bảng ánh xạ, giữ mặc định là bỏ tiếng gốc.
5. Thêm công tắc trên UI.
6. Dựng thử MP4 trên project tiếng Việt để xác nhận không vọng tiếng, và trên project dùng giọng đọc tổng hợp để xác nhận nền hạ đúng.
7. Rollback: mặc định là bỏ tiếng gốc nên hoàn nguyên chỉ cần tắt công tắc; các thay đổi không tạo dữ liệu mới cần migrate. Riêng việc tắt normalize là sửa lỗi nên không nên hoàn nguyên.

## Open Questions

Không còn câu hỏi mở về hành vi. Mức nền, độ hạ và thời gian phục hồi là tham số khởi điểm cần nghe thử để tinh chỉnh, không phải quyết định còn treo.
