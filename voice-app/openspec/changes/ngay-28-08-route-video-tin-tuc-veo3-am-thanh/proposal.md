## Why

Đo trên DB thật ngày **28-08-2026** (`data/voicebox.db`, 30 project `Cartoon International`, 420 prompt đã lưu):

| Chỉ số | Số đo |
|---|---|
| Prompt có tín hiệu thoại | 396/420 (94%) |
| Prompt **thiếu** thoại | **24/420** (6%), rải ở 11 project |
| Trong 24 shot đó, DB **có sẵn** `speech_cues` + `english_narration` | **24/24** |
| Đã render thành clip (mất thoại trong MP4) | **7** |
| Còn ở tầng prompt, kịp chặn | **17** |

Nguyên nhân: **không có dòng code nào quyết định thoại có vào prompt hay không.** `generate_video_prompt_pack()` (`backend/services/video_phase2.py:3710`) đưa `speech_cues` làm context (`:3700`) rồi để LLM tự quyết, trong khi instruction tự mâu thuẫn — `:2688` yêu cầu viết câu thoại, `:3795` lại nói "voice và phụ đề được tạo ở bước sau". `_quality_check()` (`:3553-3577`) không kiểm thoại, nên prompt rỗng thoại vẫn pass thành `prompts_ready`.

Hai hệ quả đã xảy ra:

- **Mất thoại âm thầm.** Cartoon 28 mất 7/14 shot; Cartoon 27 mất 4 shot liên tiếp; Cartoon 06 mất câu chốt bài học ở s10; Cartoon 04 mất câu kết ở s14. Không có cảnh báo nào.
- **Không phát hiện được bằng probe.** 7 clip lỗi đo `mean -20.5…-23.2 dB`, nhóm đối chứng `-19.5…-22.4 dB` — **trùng hoàn toàn**, vì nhạc/ambience/SFX vẫn đầy. `has_audio=1` cho cả 126 clip. Chỉ thiếu **lời**, mà mức âm tổng không thấy.

Số đo trên là **bằng chứng cơ chế sai**, không phải danh sách việc cần dọn. Change này sửa cơ chế để **prompt sinh ra từ nay là đúng**; 30 project cartoon hiện có giữ nguyên trạng và không được migrate. Xem Non-Goals.

Ngoài ra `uses_veo_native_speech()` (`backend/services/video_speech.py:34-39`) suy nguồn lời **chỉ từ `target_language`**: `vi` → Veo tự đọc, còn lại → voice project. Với 30 project `en` này, prompt lưu yêu cầu thoại nhưng nhánh automation lại đi regex `video_clip_generation.py:138-140` **xoá câu voiceover** rồi nối lệnh cấm `spoken audio`. Prompt lưu và prompt gửi provider nói ngược nhau, và người dùng không chọn được nguồn lời.

## What Changes

Change này chia bốn giai đoạn, ưu tiên chặn thiệt hại đang tiếp diễn trước khi thêm route mới.

**A. Gate (chặn ngay 17 shot còn lại)** — `_quality_check` chặn shot có `speech_cues`/narration mà provider content không chứa thoại: chuyển `needs_review`, không cho Copy/Download, nêu rõ lý do tiếng Việt.

**B. Shared prompt/audio builder (fix gốc)** — audio contract do **code** sinh từ `speech_cues`, không phó mặc LLM. Một builder dùng chung cho Copy, Download, prompt pack, provider automation và `/news-video`. Planner bị cấm viết thoại vào field `prompt`; `prompt` chỉ còn visual. Provider content được **compose lúc đọc**, không lưu thành cột riêng.

**C. Dropdown nguồn lời (tách khỏi ngôn ngữ)** — thêm override nullable cho project và shot; `uses_veo_native_speech()` đọc override trước, `NULL` thì giữ nguyên fallback `speech_source_for_language`. Năm mode:

| Mode | Ai tạo speech | Lời trong prompt |
|---|---|---|
| `veo_narration` | Veo | nguyên văn, ngoài khung hình |
| `veo_dialogue` | Veo | nguyên văn, nhân vật thấy được, lip-sync |
| `voicebox_co_context` | Voicebox | có, nhưng cấm Veo đọc (canh nhịp/diễn) |
| `voicebox_khong_context` | Voicebox | không có |
| `none` | không ai | không có |

`speech_mode` là input duy nhất; `dialogue_mode` và `clip_audio_mode` là **dẫn xuất**, không cho set độc lập — nhờ vậy các tổ hợp vô nghĩa (double voice, Veo đọc mà prompt không có lời) trở thành không biểu diễn được.

**D. Route `/news-video` parity đầy đủ** — workspace tiếng Việt tại `/news-video`, **hoạt động giống `/ai-video`**: cùng `STEP_ORDER` auto-run, cùng `material_target`, cùng panel render và **dựng MP4 tại chỗ**. Khác biệt duy nhất: nhập tin tức thay nhập truyện, năm mode nguồn lời, và editorial gate.

Luồng người dùng đầu-cuối, bảy bước:

```
① Dán URL + nội dung bài / ý tưởng      ⑤ Chọn nguồn lời, duyệt hoặc tạo TTS
② AI sinh prompt theo từng shot          ⑥ Dựng MP4 (kèm xoá logo/watermark)
③ Copy prompt, tự dán lên Veo 3          ⑦ Tải MP4 về
④ Tự tải clip về, upload vào shot
```

Bước ⑥ tái dùng `AIVideoRenderPanel.tsx`, nên xoá logo/watermark (`settings.watermark_cleanup`), chọn backend và trạng thái worker có sẵn theo panel, không phải làm mới.

Ở bước ①, URL chỉ được **lưu làm ghi chú nguồn**; hệ thống không tự tải bài về đọc. Người dùng phải dán nội dung. Crawler tự đọc URL để phase 2.

## Capabilities

### New Capabilities

- `ai-video-shared-prompt-audio-contract`: gate thoại, builder dùng chung, override nguồn lời năm mode, và loại bỏ regex viết lại prose. Áp cho `/ai-video`, `/product-video`, `/video-inspiration`.
- `news-video-workspace`: route/API `/news-video` parity với `/ai-video`, gồm auto-run, voice, subtitle và dựng MP4.
- `news-video-veo-prompt-audio`: năm mode nguồn lời, resolver project→shot, adapter canonical và provider content.
- `news-video-manual-clip-handoff`: copy/download, tên file, mapping shot, probe và upload clip có xác nhận.
- `news-video-editorial-grounding`: kiểm nguồn/narration/disclosure tối thiểu trước khi cho copy prompt.

## Impact

- **Backend**: sửa `video_speech.py` (override), `video_phase2.py` (gate + instruction planner), `video_clip_generation.py` (bỏ regex viết lại), thêm `backend/routes/news_video.py`.
- **Data**: cột nullable `video_projects.speech_source`, `video_shots.speech_source_override`, bảng liên kết `news_video_workflows`. **Không** thêm `provider_ready_prompt` — compose lúc đọc để khỏi sinh artifact stale.
- **Ba chỗ dùng `speech_source_for_language` trực tiếp** (`video_packages.py:284,328,411`) phải đọc override, nếu không manifest ghi sai nguồn lời.
- **Frontend**: route `/news-video`, thêm vào `isWideWorkspace` (`router.tsx:83-89`), dropdown nguồn lời, và tái dùng `AIVideoRenderPanel` (gồm xoá logo/watermark) cùng `AIVideoPublishingMetadataPanel`.
- **Dữ liệu cũ**: không migrate, không regenerate, không thêm cột phân loại prompt. Prompt sinh trước change này giữ nguyên hành vi hiện tại.
- **Kiểm thử**: gate, snapshot năm mode, derive `dialogue_mode`/`clip_audio_mode`, regression ba route cũ khi override `NULL`.

## Phạm vi theo giai đoạn

**Trong change này:** A, B, C, D như trên — gồm dựng MP4 ở `/news-video`.

**Phase 2 (không chặn):** crawler tự đọc URL bài viết; mode thứ sáu `hon_hop` (Voicebox đọc lời dẫn + Veo đọc thoại nhân vật trong cùng shot) — cần routing mức cue và **phải chứng minh đường `CLIP_AUDIO_MODE_BED` chạy được trên render thật trước đã**; STT đối chiếu phát âm; claim ledger đầy đủ; bulk upload.

## Non-Goals

- **Không migrate prompt cũ.** 24 shot thiếu thoại và 7 clip đã mất lời giữ nguyên; muốn dùng lại project nào thì sinh lại prompt cho project đó theo cách thủ công. Không thêm cột phân loại prompt, không regenerate hàng loạt.
- Không tự đọc URL bài viết; URL chỉ là ghi chú nguồn.
- Không tự động gọi hoặc điều khiển Veo 3/Flow từ `/news-video`.
- Không thêm TTS engine hoặc voice cloning.
- Không yêu cầu Veo vẽ chữ, số liệu, logo, citation hay subtitle chính xác trong pixel.
- Không đổi hành vi ba route cũ khi override `speech_source` là `NULL`.
- Không đổi giá trị mặc định của `clip_audio_mode` toàn cục — News chỉ **suy ra** mức âm từ `speech_mode`, giữ nguyên non-goal của change `ngay-23-08-am-thanh-3-muc-bo-khoa-giong-doc`.
