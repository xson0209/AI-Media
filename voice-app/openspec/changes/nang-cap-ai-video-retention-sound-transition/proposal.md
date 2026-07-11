## Why

AI Video phase 2 đã tạo được story, shot, prompt video, voice, subtitle, package và render MP4, nhưng chất lượng giữ chân người xem vẫn phụ thuộc nhiều vào prompt tự do. Cần nâng workflow thành một lớp creative direction có cấu trúc để AI lập kế hoạch nhịp dựng, chuyển cảnh, góc quay và âm thanh rõ ràng, đồng thời không để output JSON sai định dạng làm hỏng pipeline.

## What Changes

- Thêm retention planning cho AI Video phase 2: hook, curiosity gap, beat curve, pattern interrupt, payoff và rủi ro drop-off theo timeline.
- Mở rộng shot planning để mỗi shot/segment có vai trò dựng rõ ràng, cut reason, visual surprise và camera grammar chống lặp góc máy hoặc bố cục.
- Thêm transition pack có loại chuyển cảnh, trigger, timing, lý do dựng, continuity risk và SFX đi kèm thay vì chỉ một note tự do.
- Thêm sound design plan ở cấp project và shot/segment: music mood/energy curve, ambience, SFX cue, silence drop, impact/riser/whoosh và mixing notes để voice không bị che.
- Mở rộng prompt video/package/render-readiness để hiển thị và xuất các chỉ dẫn retention, transition và sound design cho người dùng hoặc editor ngoài app.
- Thêm lớp normalize/validation nghiêm cho output Codex ở các bước story, shot, prompt, retention và sound: nhận alias phổ biến, fail rõ bằng tiếng Việt khi thiếu field bắt buộc, không lưu artifact bán hỏng.

## Capabilities

### New Capabilities
- `ai-video-retention-sound-direction`: Điều khiển creative direction cho AI Video phase 2 gồm retention map, camera/transition grammar, sound design cues và validation output AI có cấu trúc.

### Modified Capabilities
- None.

## Impact

- Backend AI Video phase 2 planning trong `backend/services/video_phase2.py` và các schema Pydantic liên quan.
- Database/API models cho shot, prompt hoặc artifact creative direction nếu cần lưu trường mới.
- Package/export để đưa retention map, transition pack và sound design plan vào ZIP hoặc file prompt tải xuống.
- Render readiness/render manifest có thể bổ sung metadata âm thanh/chuyển cảnh; việc mix SFX/BGM thật có thể đi theo giai đoạn sau nếu chưa có asset audio.
- Frontend AI Video Assistant cần hiển thị bản tiếng Việt dễ duyệt cho retention, transition và sound design mà không làm rối workflow hiện tại.
- Tests backend cho normalize/validate output Codex, quality gate giữ chân người xem, stale behavior và package content.
