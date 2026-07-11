## Context

AI Video phase 2 hiện coi mỗi `VideoShot` là một prompt segment khi project có `target_duration_seconds`. Số prompt được tính bằng `ceil(target_duration_seconds / VIDEO_PROMPT_SEGMENT_SECONDS)`, trong đó `VIDEO_PROMPT_SEGMENT_SECONDS` đang cố định 10 giây. UI chỉ cho nhập thời lượng video và hiển thị số prompt ước tính.

Người dùng muốn kiểm soát cấu trúc trước khi tạo project: số prompt, thời lượng mỗi prompt và số cảnh nhỏ trong mỗi prompt. Ví dụ `6 prompt x 10s x 3 cảnh nhỏ` phải tạo video 60 giây, 6 prompt copy được sang công cụ video, và 18 cảnh nhỏ nằm trong timeline nội bộ của các prompt.

## Goals / Non-Goals

**Goals:**

- Cho phép cấu hình trực tiếp `prompt_segment_count`, `prompt_segment_duration_seconds` và `micro_scenes_per_prompt` cho project phase 2.
- Tự tính `target_duration_seconds = prompt_segment_count * prompt_segment_duration_seconds` để tránh mâu thuẫn giữa thời lượng và số prompt.
- Tạo đúng số prompt segment và đúng số cảnh nhỏ trong mỗi prompt.
- Lưu timeline cảnh nhỏ dưới dạng có cấu trúc để UI, export, prompt generation và test đều dùng cùng dữ liệu.
- Normalize được output Codex với các alias/shape phổ biến trước khi validate strict schema, để output đủ dữ liệu không bị fail chỉ vì tên field khác.
- Giữ tương thích project cũ đang chỉ có `target_duration_seconds` và mode 10 giây.

**Non-Goals:**

- Không thêm editor timeline riêng cho từng cảnh nhỏ trong change này.
- Không render video tự động từ cảnh nhỏ.
- Không tích hợp provider video cụ thể như Runway, Kling, Veo, Pika hoặc Luma.
- Không đổi lại toàn bộ mô hình scene lớn/shot hiện có; prompt segment vẫn dùng `video_shots` làm đơn vị chính.

## Decisions

### 1. Ba field cấu hình là nguồn sự thật cho project mới

Thêm các field nullable vào project phase 2:

- `prompt_segment_count`: số prompt segment người dùng muốn tạo.
- `prompt_segment_duration_seconds`: thời lượng mỗi prompt segment.
- `micro_scenes_per_prompt`: số cảnh nhỏ bên trong mỗi prompt.

Với project mới có đủ ba field, backend tính `target_duration_seconds` từ hai field đầu. UI hiển thị thời lượng như preview/derived value, không để người dùng nhập một thời lượng khác cùng lúc.

Phương án khác đã cân nhắc: tiếp tục nhập `target_duration_seconds` rồi thêm số cảnh nhỏ. Cách đó vẫn giấu số prompt thật sau công thức và không giải quyết nhu cầu nhập số prompt trực tiếp.

### 2. Project cũ fallback qua `target_duration_seconds`

Nếu project không có `prompt_segment_count`, backend giữ logic hiện tại: dùng `target_duration_seconds` và fallback 10 giây để tính số prompt. Hằng số 10 giây vẫn tồn tại như legacy/default, nhưng không còn là nguồn sự thật cho project đã cấu hình.

Phương án khác đã cân nhắc: migrate toàn bộ project cũ sang ba field mới. Cách đó dễ làm sai ý nghĩa với project cũ vì trước đây người dùng không chọn số cảnh nhỏ mỗi prompt.

### 3. Cảnh nhỏ được lưu có cấu trúc trong shot/prompt segment

Mỗi `VideoShot` trong segment mode vẫn đại diện cho một prompt segment. Thêm dữ liệu cảnh nhỏ có cấu trúc cho shot, ví dụ cột nullable `micro_scenes_json` lưu danh sách:

```json
[
  {
    "order": 1,
    "start_seconds": 0,
    "end_seconds": 3.3,
    "description_vi": "...",
    "visual_action": "...",
    "camera_note": "..."
  }
]
```

UI và export vẫn có thể render `vietnamese_description`, nhưng dữ liệu có cấu trúc là nguồn sự thật để kiểm tra đúng số cảnh nhỏ và tạo prompt timeline.

Phương án khác đã cân nhắc: tạo bảng `video_micro_scenes`. Bảng riêng query tốt hơn nhưng tăng migration/API surface đáng kể. Với change này, micro-scene chưa cần thao tác độc lập nên JSON trên shot đủ gọn và ít rủi ro hơn.

### 4. Normalize trước, validate sau

Codex output phải đi qua normalization trước khi chạy Pydantic model strict. Normalizer cần nhận các biến thể phổ biến:

- Danh sách segment: `shots`, `segments`, `prompt_segments`, `video_segments`, `segment_breakdown`.
- Segment lồng trong scene: `scenes[].shots`, `scenes[].segments`, `scenes[].prompt_segments`.
- Thứ tự segment: `shot_order`, `segment_order`, `prompt_order`, `order`, `index`.
- Cảnh nhỏ: `micro_scenes`, `microScenes`, `scenes`, `beats`, `timeline`, `timeline_beats`.
- Text/timeline alias: `segment_description_vi`, `description_vi`, `vietnamese_description`, `voiceover_text`, `narration`, `subject_movement`, `camera_movement`.

Nếu Codex trả timeline dạng text có mốc thời gian, normalizer có thể parse thành `micro_scenes`. Nếu output thiếu mốc nhưng có đủ mô tả tổng thể, normalizer có thể chia đều timeline theo `micro_scenes_per_prompt` và gắn mô tả tổng thể vào từng cảnh nhỏ để không fail giả. Nếu thiếu dữ liệu cốt lõi như nội dung visual hoặc narration required, hệ thống mới retry/fail với lỗi tiếng Việt rõ ràng.

Phương án khác đã cân nhắc: chỉ siết schema và yêu cầu Codex trả đúng tuyệt đối. Cách đó là nguyên nhân dễ gặp lỗi format khi model đổi tên field dù nội dung vẫn đúng.

Canonical output contract cho shot breakdown nên là:

```json
{
  "segments": [
    {
      "segment_order": 1,
      "duration_seconds": 10,
      "vietnamese_description": "0-3.3s: ...; 3.3-6.7s: ...; 6.7-10s: ...",
      "english_narration": "...",
      "primary_action": "...",
      "purpose": "...",
      "shot_type": "...",
      "camera_angle": "...",
      "framing": "...",
      "composition": "...",
      "camera_motion": "...",
      "subject_motion": "...",
      "environment_motion": "...",
      "transition_to_next": "...",
      "micro_scenes": [
        {
          "order": 1,
          "start_seconds": 0,
          "end_seconds": 3.3,
          "description_vi": "...",
          "visual_action": "...",
          "camera_note": "...",
          "continuity_note": "..."
        }
      ]
    }
  ]
}
```

Implementation vẫn phải nhận alias lệch format, nhưng mọi output sau normalization phải quy về contract này trước khi validate và persist.

### 5. Timeline được sinh từ cấu hình, không hardcode 0-3/3-6/6-10

Prompt instruction, generated prompt text và UI label phải dùng `prompt_segment_duration_seconds` và `micro_scenes_per_prompt`. Ví dụ:

- `10s / 3 cảnh`: `0-3.3s`, `3.3-6.7s`, `6.7-10s` hoặc làm tròn thân thiện.
- `8s / 4 cảnh`: `0-2s`, `2-4s`, `4-6s`, `6-8s`.

Backend nên có helper chung tạo timeline ranges để prompt builder, normalizer và tests dùng cùng logic.

### 6. Validation rõ ràng nhưng không chặn cấu hình hợp lý

Giới hạn đề xuất:

- `prompt_segment_count`: 1-100.
- `prompt_segment_duration_seconds`: 3-30.
- `micro_scenes_per_prompt`: 1-5.
- `target_duration_seconds` derived không vượt quá giới hạn hiện có 7200 giây.
- Cảnh báo hoặc chặn cấu hình khi thời lượng trung bình mỗi cảnh nhỏ quá ngắn; ngưỡng chặn đề xuất là dưới 1.5 giây/cảnh.

UI nên khuyến nghị 10 giây và 2-4 cảnh nhỏ mỗi prompt, nhưng không ép nếu người dùng có nhu cầu khác.

## Risks / Trade-offs

- Codex vẫn có thể trả thiếu dữ liệu thật sự -> Normalize alias trước, retry với lỗi validation cụ thể, sau đó hiển thị lỗi tiếng Việt nếu output vẫn thiếu nội dung cốt lõi.
- JSON micro-scene trên shot khó query hơn bảng riêng -> Chấp nhận vì phase này chỉ cần render/validate/export; nếu sau này edit từng cảnh nhỏ mới tách bảng.
- Thay hardcode 10 giây có thể ảnh hưởng prompt generation/package/readiness -> Thêm helper dùng cấu hình project và test các duration khác 10 giây.
- Người dùng có thể chọn cấu hình quá dày -> Validate range và cảnh báo/chặn khi trung bình mỗi cảnh nhỏ dưới ngưỡng an toàn.
- Project cũ không có field mới -> Fallback legacy và migration nullable để không phá dữ liệu.

## Migration Plan

1. Thêm cột nullable `prompt_segment_count`, `prompt_segment_duration_seconds`, `micro_scenes_per_prompt` vào `video_projects`.
2. Thêm cột nullable `micro_scenes_json` vào `video_shots` hoặc tên tương đương theo convention hiện có.
3. Không backfill bắt buộc cho project cũ; project cũ tiếp tục suy ra prompt count từ `target_duration_seconds` và 10 giây.
4. Với project mới, khi create/update nhận đủ ba field thì backend tính lại `target_duration_seconds` và đánh dấu package/prompt stale nếu cấu hình thay đổi.
5. Rollback an toàn: ẩn UI field mới, giữ cột nullable không dùng; fallback legacy vẫn hoạt động.

## Open Questions

- Có cần cho người dùng sửa ba cấu hình sau khi đã tạo prompt/voice/package không, hay chỉ cho sửa trước khi tạo segment breakdown?
- Nếu người dùng đổi `micro_scenes_per_prompt` khi đã có locked segment, hệ thống nên chặn đổi, unlock bắt buộc, hay chỉ regenerate segment chưa khóa?
