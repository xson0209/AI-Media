# Prompt thoại nhân vật Veo 3 — hướng dẫn dùng nhanh

Route `/news-video` hiện mặc định chọn **Presenter/nhân vật thoại trong Veo 3**.
Khi tạo shot và sinh prompt, hệ thống lưu phần hình ảnh riêng rồi ghép audio
contract lúc đọc/copy. Vì vậy câu thoại mới nhất luôn được lấy từ
`speech_cues_json`, không bị kẹt trong prompt cũ.

## Hai lựa chọn âm thanh

- **Presenter/nhân vật thoại trong Veo 3 (`veo_dialogue`)**: prompt yêu cầu
  nhân vật nhìn thấy nói đúng nguyên văn, giữ danh tính/giọng/trang phục và
  khớp khẩu hình. Veo 3 tự render giọng trong clip.
- **TTS Voicebox hậu kỳ (`voicebox_khong_context`)** hoặc **TTS Voicebox +
  ngữ cảnh (`voicebox_co_context`)**: prompt không yêu cầu Veo phát lời; sau
  khi upload clip, Voicebox tạo giọng đọc và hệ thống ghép vào MP4.

## Mẫu provider prompt

```text
A realistic newsroom presenter on camera, medium shot, stable identity and wardrobe.

AUDIO CONTRACT — VEO NATIVE DIALOGUE:
Nhân vật đang nhìn thấy phải phát âm thanh thoại tiếng Việt với khẩu hình khớp môi.
Giữ nguyên danh tính, giọng và trang phục; không đổi người nói, không diễn giải,
không thêm lời, phụ đề hay chữ trên hình.
Visible speaker Lan (visible_character): "Xin chào khán giả" — lip-sync required; speak exactly this line once.

NEGATIVE PROMPT:
subtitles, captions, text overlays, logos, watermarks, extra speakers, paraphrased dialogue
```

Chỉ cần bấm **Copy prompt** ở shot tương ứng, dán nguyên khối vào Veo 3 và
chọn đúng shot khi tải file về. Hệ thống không tự mở Veo, không đăng nhập và
không tiêu credit thay người dùng.

