# Kiểm thử hồi quy series dài không gọi Veo

Bộ kiểm thử series dài dùng dữ liệu giả lập có chủ đích để kiểm tra trí nhớ, canon, candidate, prompt repair, voice/subtitle stub và stale có mục tiêu mà không gọi provider video.

## Bộ 30 tập

Bộ chạy thường xuyên nằm trong:

```text
backend/tests/test_long_series_regression.py
```

Test chính:

```text
test_long_series_regression_30_episodes_reports_metrics_without_video_provider
```

Bộ này tạo 30 tập với:

- nhiều nhân vật và địa điểm;
- sự kiện bắt buộc theo từng tập;
- bí mật cũ ở tập 3;
- thẻ gây nhiễu có importance thấp;
- dependency style cho prompt video;
- dependency style không liên quan cho voice để xác nhận không stale thừa;
- metric candidate/prompt/canon giả lập deterministic;
- xác nhận không có `VideoClipGenerationJob` hoặc `VideoShotClip`.

Chạy:

```powershell
python -m pytest backend/tests/test_long_series_regression.py -q
```

Nếu môi trường hiện tại chưa có pytest:

```powershell
python -m venv .codex-temp\pytest-venv
.codex-temp\pytest-venv\Scripts\python -m pip install -q pytest fastapi sqlalchemy pydantic python-multipart Pillow
.codex-temp\pytest-venv\Scripts\python -m pytest backend/tests/test_long_series_regression.py -q
```

## Bộ 100 tập tùy chọn

Test sau xác nhận dataset 100 tập có thể tạo lại và giữ answer key cho sự kiện rất cũ:

```text
test_optional_100_episode_dataset_keeps_old_event_answer_key
```

Bộ 100 tập nên chạy khi release hoặc khi thay đổi logic chọn memory/context budget.

## Metric báo cáo

Report trong test dùng key tiếng Việt:

- `ty_le_lay_dung_the_bat_buoc`
- `ty_le_khong_lay_the_gay_nhieu`
- `so_loi_canon_phat_hien`
- `so_loi_canon_bo_sot`
- `ty_le_candidate_khac_nhau_dat_yeu_cau`
- `ty_le_prompt_dat_sau_sua`
- `so_artifact_stale_dung`
- `so_artifact_stale_thua`
- `so_lan_goi_ai_gia_lap`
- `tong_dung_luong_ngu_canh`
- `goi_provider_video`

`goi_provider_video` phải bằng `0`. Bộ test này không submit Veo, không tải clip provider và không tiêu credit.

## Khi có lỗi

- Nếu tỷ lệ lấy đúng thẻ bắt buộc giảm, kiểm tra scoring trong `series_brain.compile_context`.
- Nếu thẻ gây nhiễu tăng, kiểm tra importance/tag/entity matching.
- Nếu stale thừa xuất hiện, kiểm tra `dependency_scope` được ghi khi tạo artifact và rule trong `series_references.SCOPE_AFFECTS`.
- Nếu `goi_provider_video` khác `0`, test hoặc code regression đã gọi sai pipeline provider thật.
