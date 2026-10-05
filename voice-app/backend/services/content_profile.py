"""Structured content profiles and genre templates for AI Video.

This module deliberately sits next to ``video_purpose`` rather than replacing
it.  Purpose controls language/dialogue/CTA compatibility; a content profile
describes what the video is about, who it is for and how it should be shaped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import video_purpose

CONTENT_PROFILE_VERSION = 1

CONTENT_OBJECTIVE_VALUES = {
    "entertain",
    "educate",
    "inform",
    "convert",
    "inspire",
}
CONTENT_OBJECTIVE_PATTERN = "^(entertain|educate|inform|convert|inspire)$"

CONTENT_GENRE_VALUES = {
    "general",
    "educational_explainer",
    "kids_educational",
    "kids_rescue",
    "kids_stem",
    "kids_song",
    "health_explainer",
    "relationship_soft_drama",
    "product_ad",
    "product_ugc",
    "news",
    "documentary",
    "developer_explainer",
}
CONTENT_GENRE_PATTERN = "^(general|educational_explainer|kids_educational|kids_rescue|kids_stem|kids_song|health_explainer|relationship_soft_drama|product_ad|product_ugc|news|documentary|developer_explainer)$"

AUDIENCE_AGE_BAND_VALUES = {
    "all_ages",
    "preschool_3_5",
    "kids_6_9",
    "tweens_10_12",
    "teens_13_17",
    "adults",
}
AUDIENCE_AGE_BAND_PATTERN = "^(all_ages|preschool_3_5|kids_6_9|tweens_10_12|teens_13_17|adults)$"

FORMAT_PROFILE_VALUES = {
    "short_15s",
    "short_30s",
    "short_60s",
    "explainer_90s",
    "kids_2m",
    "narrative_3m",
    "long_form",
}
FORMAT_PROFILE_PATTERN = "^(short_15s|short_30s|short_60s|explainer_90s|kids_2m|narrative_3m|long_form)$"

DISTRIBUTION_PLATFORM_VALUES = {
    "youtube",
    "youtube_kids",
    "tiktok",
    "facebook",
    "multi_platform",
}
DISTRIBUTION_PLATFORM_PATTERN = "^(youtube|youtube_kids|tiktok|facebook|multi_platform)$"

INTERACTION_MODE_VALUES = {
    "none",
    "pause_and_choose",
    "q_and_a",
    "count_and_repeat",
}
INTERACTION_MODE_PATTERN = "^(none|pause_and_choose|q_and_a|count_and_repeat)$"

SAFETY_POLICY_VALUES = {"standard", "kids_strict", "health_cautious", "editorial", "adult"}
SAFETY_POLICY_PATTERN = "^(standard|kids_strict|health_cautious|editorial|adult)$"

_LABELS = {
    "content_objective": {
        "entertain": "Giải trí",
        "educate": "Giáo dục",
        "inform": "Thông tin",
        "convert": "Chuyển đổi / bán hàng",
        "inspire": "Truyền cảm hứng",
    },
    "content_genre": {
        "general": "Nội dung tổng quát",
        "educational_explainer": "Giải thích / explainer",
        "kids_educational": "Kids · bài học ngắn",
        "kids_rescue": "Kids · cứu hộ & giải quyết vấn đề",
        "kids_stem": "Kids · STEM / garage",
        "kids_song": "Kids · bài hát & vận động",
        "health_explainer": "Sức khỏe · giải thích thận trọng",
        "relationship_soft_drama": "Tình cảm · tâm lý nhẹ",
        "product_ad": "Quảng cáo sản phẩm",
        "product_ugc": "Product UGC / beauty",
        "news": "Tin tức",
        "documentary": "Phóng sự / documentary",
        "developer_explainer": "Developer / GitHub explainer",
    },
    "audience_age_band": {
        "all_ages": "Mọi lứa tuổi",
        "preschool_3_5": "Mầm non · 3–5",
        "kids_6_9": "Trẻ em · 6–9",
        "tweens_10_12": "Thiếu nhi · 10–12",
        "teens_13_17": "Thiếu niên · 13–17",
        "adults": "Người lớn",
    },
    "format_profile": {
        "short_15s": "Short · 15 giây",
        "short_30s": "Short · 30 giây",
        "short_60s": "Short · 60 giây",
        "explainer_90s": "Explainer · 90 giây",
        "kids_2m": "Kids · 2 phút",
        "narrative_3m": "Narrative · 3 phút",
        "long_form": "Long-form",
    },
    "distribution_platform": {
        "youtube": "YouTube",
        "youtube_kids": "YouTube Kids",
        "tiktok": "TikTok",
        "facebook": "Facebook",
        "multi_platform": "Đa nền tảng",
    },
    "interaction_mode": {
        "none": "Không tương tác",
        "pause_and_choose": "Dừng & chọn đáp án",
        "q_and_a": "Hỏi – đáp",
        "count_and_repeat": "Đếm & lặp lại",
    },
    "safety_policy": {
        "standard": "Tiêu chuẩn",
        "kids_strict": "Kids · nghiêm ngặt",
        "health_cautious": "Sức khỏe · thận trọng",
        "editorial": "Biên tập / kiểm chứng",
        "adult": "Người lớn",
    },
}


@dataclass(frozen=True)
class GenreTemplate:
    key: str
    description_vi: str
    defaults: dict[str, Any]
    generation_guidance: tuple[str, ...]
    review_checks: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": _LABELS["content_genre"].get(self.key, self.key),
            "description": self.description_vi,
            "defaults": dict(self.defaults),
            "generation_guidance": list(self.generation_guidance),
            "review_checks": list(self.review_checks),
        }


_GENERAL_GUIDANCE = (
    "Giữ một ý chính, mở bằng hook rõ và kết bằng payoff phù hợp format.",
)
_GENERAL_CHECKS = (
    "Ý chính dễ hiểu trong vài giây đầu",
    "Ngôn ngữ và hình ảnh phù hợp audience đã chọn",
    "Không mâu thuẫn với source blocks hoặc continuity",
)

# These rules apply to every genre. They make the content-first contract
# explicit before any genre-specific guidance is added to the generation
# context: one audience problem, one useful promise, one original contribution
# and one natural next action.
_CONTENT_FIRST_GUIDANCE = (
    "Viết cho một audience cụ thể và một vấn đề lặp lại; không dùng lời hứa chung chung cho tất cả mọi người.",
    "Mỗi video phải có hook, một đóng góp thông tin/cảm xúc mới và payoff quan sát được; không kéo dài bằng hình đẹp hoặc lặp beat.",
    "Giữ một đóng góp nguyên bản từ brief, demo, phân tích, trải nghiệm hoặc nguồn đã kiểm chứng; không biến đổi hời hợt nội dung có sẵn.",
    "Chỉ dùng một CTA chính phù hợp với giá trị vừa hứa; nếu chưa có offer hoặc đích thật thì ưu tiên CTA xem tiếp, lưu hoặc gửi câu hỏi.",
)
_CONTENT_FIRST_CHECKS = (
    "Audience và vấn đề của video được nêu bằng một câu cụ thể",
    "Hook dẫn vào payoff; mỗi beat có thông tin, cảm xúc hoặc quyết định mới",
    "Claim, ví dụ và asset có nguồn/quyền dùng hoặc được ghi rõ là minh họa",
    "CTA khớp với nội dung và không hứa kết quả chưa có bằng chứng",
)
_KIDS_GUIDANCE = (
    "0:00–0:10: mở bằng nhiệm vụ/vấn đề trực quan và hook nhanh.",
    "0:10–0:30: đưa một câu hỏi để trẻ dừng, đoán hoặc chọn.",
    "0:30–1:20: thử nghiệm/giải pháp tối đa hai bước, mỗi bước có hành động nhìn thấy được.",
    "1:20–1:45: cho thấy kết quả và payoff cảm xúc tích cực.",
    "1:45–2:00: chốt một takeaway ngắn hoặc đoạn hát/vận động dễ nhớ.",
)
_KIDS_CHECKS = (
    "Từ ngữ, nhịp và độ phức tạp phù hợp lứa tuổi",
    "Không có hành động nguy hiểm dễ bắt chước hoặc cảnh gây sợ hãi quá mức",
    "Kết thúc tích cực, không cổ vũ bắt nạt hay làm nhục",
    "Nhân vật, màu sắc và đạo cụ nhất quán giữa các cảnh",
    "Có takeaway cụ thể mà trẻ/phụ huynh có thể nhắc lại",
)


GENRE_TEMPLATES: dict[str, GenreTemplate] = {
    "general": GenreTemplate(
        key="general",
        description_vi="Template linh hoạt cho ý tưởng chưa cần một thể loại chuyên biệt.",
        defaults={
            "content_objective": "entertain",
            "audience_age_band": "all_ages",
            "format_profile": "short_60s",
            "distribution_platform": "multi_platform",
            "interaction_mode": "none",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=_GENERAL_GUIDANCE,
        review_checks=_GENERAL_CHECKS,
    ),
    "educational_explainer": GenreTemplate(
        key="educational_explainer",
        description_vi="Giải thích một khái niệm bằng ví dụ cụ thể, dễ kiểm tra.",
        defaults={
            "content_objective": "educate",
            "audience_age_band": "all_ages",
            "format_profile": "explainer_90s",
            "distribution_platform": "youtube",
            "interaction_mode": "q_and_a",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=(
            "Chỉ giải thích một khái niệm chính; định nghĩa ngắn rồi đưa ví dụ đời thường.",
            "Tách fact, ví dụ và takeaway để người xem không nhầm mức độ chắc chắn.",
        ),
        review_checks=("Không dùng jargon nếu chưa giải thích", "Ví dụ đúng và không gây hiểu lầm"),
    ),
    "kids_educational": GenreTemplate(
        key="kids_educational",
        description_vi="Bài học ngắn cho trẻ với câu hỏi, thử nghiệm đơn giản và takeaway.",
        defaults={
            "content_objective": "educate",
            "audience_age_band": "kids_6_9",
            "format_profile": "kids_2m",
            "distribution_platform": "youtube_kids",
            "interaction_mode": "pause_and_choose",
            "safety_policy": "kids_strict",
            "made_for_kids": True,
        },
        generation_guidance=_KIDS_GUIDANCE,
        review_checks=_KIDS_CHECKS,
    ),
    "kids_rescue": GenreTemplate(
        key="kids_rescue",
        description_vi="Đội cứu hộ giải quyết một nhiệm vụ an toàn, khuyến khích hợp tác.",
        defaults={
            "content_objective": "entertain",
            "audience_age_band": "kids_6_9",
            "format_profile": "kids_2m",
            "distribution_platform": "youtube_kids",
            "interaction_mode": "pause_and_choose",
            "safety_policy": "kids_strict",
            "made_for_kids": True,
        },
        generation_guidance=_KIDS_GUIDANCE + ("Mô tả cứu hộ theo hướng hợp tác, không biến nguy hiểm thành trò bắt chước.",),
        review_checks=_KIDS_CHECKS,
    ),
    "kids_stem": GenreTemplate(
        key="kids_stem",
        description_vi="Garage STEM: quan sát, thử một giả thuyết và rút ra bài học.",
        defaults={
            "content_objective": "educate",
            "audience_age_band": "kids_6_9",
            "format_profile": "kids_2m",
            "distribution_platform": "youtube_kids",
            "interaction_mode": "count_and_repeat",
            "safety_policy": "kids_strict",
            "made_for_kids": True,
        },
        generation_guidance=_KIDS_GUIDANCE + ("Chỉ dùng thí nghiệm an toàn, không cần lửa, điện hở hoặc hóa chất.",),
        review_checks=_KIDS_CHECKS,
    ),
    "kids_song": GenreTemplate(
        key="kids_song",
        description_vi="Bài hát/vận động lặp lại một quy tắc hoặc thói quen tốt.",
        defaults={
            "content_objective": "entertain",
            "audience_age_band": "preschool_3_5",
            "format_profile": "kids_2m",
            "distribution_platform": "youtube_kids",
            "interaction_mode": "count_and_repeat",
            "safety_policy": "kids_strict",
            "made_for_kids": True,
        },
        generation_guidance=_KIDS_GUIDANCE + ("Dùng điệp khúc ngắn, động tác dễ làm theo và không yêu cầu đạo cụ nguy hiểm.",),
        review_checks=_KIDS_CHECKS,
    ),
    "health_explainer": GenreTemplate(
        key="health_explainer",
        description_vi="Giải thích sức khỏe phổ thông, tránh chẩn đoán hoặc hứa hẹn điều trị.",
        defaults={
            "content_objective": "educate",
            "audience_age_band": "adults",
            "format_profile": "explainer_90s",
            "distribution_platform": "youtube",
            "interaction_mode": "q_and_a",
            "safety_policy": "health_cautious",
            "made_for_kids": False,
        },
        generation_guidance=("Phân biệt thông tin giáo dục với tư vấn y khoa; nêu khi nào cần hỏi chuyên gia.",),
        review_checks=("Không chẩn đoán cá nhân", "Claim sức khỏe có nguồn hoặc được đánh dấu cần kiểm chứng"),
    ),
    "relationship_soft_drama": GenreTemplate(
        key="relationship_soft_drama",
        description_vi="Tình huống quan hệ đời thường, ưu tiên đồng cảm và ranh giới lành mạnh.",
        defaults={
            "content_objective": "inspire",
            "audience_age_band": "adults",
            "format_profile": "narrative_3m",
            "distribution_platform": "multi_platform",
            "interaction_mode": "q_and_a",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=("Xây conflict từ nhu cầu và hiểu lầm; tránh lãng mạn hóa kiểm soát, bạo lực hoặc thao túng.",),
        review_checks=("Nhân vật có agency", "Không bình thường hóa hành vi lạm dụng"),
    ),
    "product_ad": GenreTemplate(
        key="product_ad",
        description_vi="Quảng cáo ngắn: vấn đề, lợi ích, bằng chứng và CTA cụ thể.",
        defaults={
            "content_objective": "convert",
            "audience_age_band": "adults",
            "format_profile": "short_30s",
            "distribution_platform": "multi_platform",
            "interaction_mode": "none",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=("Không phóng đại claim; chỉ dùng bằng chứng có trong source hoặc asset sản phẩm.",),
        review_checks=("CTA rõ", "Claim có thể kiểm chứng", "Không ngụ ý kết quả chắc chắn"),
    ),
    "product_ugc": GenreTemplate(
        key="product_ugc",
        description_vi="UGC/presenter tự nhiên, cần reference asset để giữ đúng nhãn và hình sản phẩm.",
        defaults={
            "content_objective": "convert",
            "audience_age_band": "adults",
            "format_profile": "short_30s",
            "distribution_platform": "tiktok",
            "interaction_mode": "q_and_a",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=("Giữ giọng chia sẻ chân thật; không tự bịa thành phần, giá hoặc review người dùng.",),
        review_checks=("Sản phẩm khớp reference", "Nêu rõ trải nghiệm cá nhân là trải nghiệm cá nhân"),
    ),
    "news": GenreTemplate(
        key="news",
        description_vi="Tin tức theo 5W1H, tách fact/quote/opinion và thể hiện bất định.",
        defaults={
            "content_objective": "inform",
            "audience_age_band": "adults",
            "format_profile": "short_60s",
            "distribution_platform": "multi_platform",
            "interaction_mode": "none",
            "safety_policy": "editorial",
            "made_for_kids": False,
        },
        generation_guidance=("Nêu thời điểm và nguồn; không biến thông tin chưa xác minh thành khẳng định.",),
        review_checks=("Có nguồn", "Tách fact/quote/opinion", "Nêu uncertainty và correction path"),
    ),
    "documentary": GenreTemplate(
        key="documentary",
        description_vi="Kể chuyện người thật/sự kiện với bối cảnh, trích dẫn và nhịp quan sát.",
        defaults={
            "content_objective": "inform",
            "audience_age_band": "all_ages",
            "format_profile": "narrative_3m",
            "distribution_platform": "youtube",
            "interaction_mode": "none",
            "safety_policy": "editorial",
            "made_for_kids": False,
        },
        generation_guidance=("Tôn trọng nhân vật thật; không suy diễn động cơ ngoài nguồn được cung cấp.",),
        review_checks=("Quote đúng ngữ cảnh", "Phân biệt quan sát và diễn giải"),
    ),
    "developer_explainer": GenreTemplate(
        key="developer_explainer",
        description_vi="Giải thích repo/code theo cấu trúc, ví dụ chạy được và giới hạn rõ ràng.",
        defaults={
            "content_objective": "educate",
            "audience_age_band": "adults",
            "format_profile": "explainer_90s",
            "distribution_platform": "youtube",
            "interaction_mode": "q_and_a",
            "safety_policy": "standard",
            "made_for_kids": False,
        },
        generation_guidance=("Tách kiến trúc, luồng chạy và ví dụ; không khẳng định API/version nếu chưa đọc source.",),
        review_checks=("Code sample nhất quán với source", "Nêu version/license khi có"),
    ),
}


def _token(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _valid(value: str | None, values: set[str], fallback: str) -> str:
    token = _token(value)
    return token if token in values else fallback


def legacy_profile_for_purpose(video_purpose_value: str | None) -> dict[str, Any]:
    purpose = video_purpose.normalize_video_purpose(video_purpose_value)
    if purpose == "educational_explainer":
        return {"content_objective": "educate", "content_genre": "educational_explainer"}
    if purpose == "sales_ad":
        return {"content_objective": "convert", "content_genre": "product_ad"}
    if purpose == "localized_variant":
        return {"content_objective": "inform", "content_genre": "general"}
    return {"content_objective": "entertain", "content_genre": "general"}


def infer_format_profile(target_duration_seconds: int | None, *, is_kids: bool = False) -> str:
    try:
        seconds = int(target_duration_seconds or 0)
    except (TypeError, ValueError):
        seconds = 0
    if is_kids and 90 < seconds <= 150:
        return "kids_2m"
    if seconds <= 20:
        return "short_15s"
    if seconds <= 40:
        return "short_30s"
    if seconds <= 75:
        return "short_60s"
    if seconds <= 120:
        return "explainer_90s"
    if seconds <= 240:
        return "narrative_3m"
    return "long_form"


def resolve_content_profile(
    *,
    video_purpose_value: str | None = None,
    content_profile_version: int | None = None,
    content_objective: str | None = None,
    content_genre: str | None = None,
    audience_age_band: str | None = None,
    format_profile: str | None = None,
    distribution_platform: str | None = None,
    interaction_mode: str | None = None,
    safety_policy: str | None = None,
    made_for_kids: bool | None = None,
    learning_objective: str | None = None,
    target_duration_seconds: int | None = None,
) -> dict[str, Any]:
    legacy = legacy_profile_for_purpose(video_purpose_value)
    genre = _valid(content_genre, CONTENT_GENRE_VALUES, str(legacy["content_genre"]))
    template = GENRE_TEMPLATES.get(genre, GENRE_TEMPLATES["general"])

    def choose(name: str, value: Any, fallback: Any) -> Any:
        # Explicit values win; otherwise use the genre template, then legacy.
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
        return template.defaults.get(name, fallback)

    objective = _valid(
        choose("content_objective", content_objective, legacy["content_objective"]),
        CONTENT_OBJECTIVE_VALUES,
        str(legacy["content_objective"]),
    )
    is_kids = genre.startswith("kids_")
    age = _valid(choose("audience_age_band", audience_age_band, "all_ages"), AUDIENCE_AGE_BAND_VALUES, "all_ages")
    if is_kids and age in {"all_ages", "teens_13_17", "adults"}:
        age = str(template.defaults.get("audience_age_band", "kids_6_9"))
    inferred_format = infer_format_profile(target_duration_seconds, is_kids=is_kids)
    if format_profile is not None:
        format_default = format_profile
    elif target_duration_seconds is not None:
        format_default = inferred_format
    else:
        format_default = template.defaults.get("format_profile", inferred_format)
    fmt = _valid(format_default, FORMAT_PROFILE_VALUES, inferred_format)
    platform = _valid(choose("distribution_platform", distribution_platform, "multi_platform"), DISTRIBUTION_PLATFORM_VALUES, "multi_platform")
    interaction = _valid(choose("interaction_mode", interaction_mode, "none"), INTERACTION_MODE_VALUES, "none")
    safety = _valid(choose("safety_policy", safety_policy, "standard"), SAFETY_POLICY_VALUES, "standard")
    if is_kids:
        safety = "kids_strict"
        made = True
        if platform not in {"youtube_kids", "youtube", "multi_platform"}:
            platform = "youtube_kids"
        if fmt not in {"kids_2m", "short_60s", "short_30s", "short_15s"}:
            fmt = "kids_2m"
    else:
        made = bool(choose("made_for_kids", made_for_kids, False))
    learning = (learning_objective or "").strip()[:2000] or None
    return {
        "content_profile_version": int(content_profile_version or CONTENT_PROFILE_VERSION),
        "content_objective": objective,
        "content_genre": genre,
        "audience_age_band": age,
        "format_profile": fmt,
        "distribution_platform": platform,
        "interaction_mode": interaction,
        "safety_policy": safety,
        "made_for_kids": made,
        "learning_objective": learning,
    }


def template_for_genre(genre: str | None) -> GenreTemplate:
    return GENRE_TEMPLATES.get(_token(genre), GENRE_TEMPLATES["general"])


def profile_context_lines(profile: dict[str, Any]) -> list[str]:
    template = template_for_genre(str(profile.get("content_genre") or "general"))
    lines = [
        "Content Profile:",
        f"- Objective: {profile.get('content_objective')}",
        f"- Genre: {profile.get('content_genre')} ({_LABELS['content_genre'].get(str(profile.get('content_genre')), '')})",
        f"- Audience age: {profile.get('audience_age_band')}",
        f"- Format: {profile.get('format_profile')}",
        f"- Distribution: {profile.get('distribution_platform')}",
        f"- Interaction: {profile.get('interaction_mode')}",
        f"- Safety policy: {profile.get('safety_policy')}",
        f"- Made for kids: {'yes' if profile.get('made_for_kids') else 'no'}",
    ]
    if profile.get("learning_objective"):
        lines.append(f"- Learning objective: {profile['learning_objective']}")
    lines.append("Content-first generation guidance:")
    lines.extend(f"- {item}" for item in _CONTENT_FIRST_GUIDANCE)
    lines.append("Genre generation guidance:")
    lines.extend(f"- {item}" for item in template.generation_guidance)
    if profile.get("format_profile") == "long_form":
        lines.extend([
            "- Nội dung dài phải có câu hỏi trung tâm, lời hứa, payoff và các chương có thời lượng rõ.",
            "- Mỗi chương phải kế thừa trạng thái chương trước, thêm thông tin mới và có câu nối sang chương sau.",
            "- Không lặp beat hoặc kéo dài bằng cách quay vòng cùng một ý.",
        ])
    lines.append("Content-first review checks:")
    lines.extend(f"- {item}" for item in _CONTENT_FIRST_CHECKS)
    lines.append("Genre review checks:")
    lines.extend(f"- {item}" for item in template.review_checks)
    return lines


def options_payload() -> dict[str, Any]:
    def options(field: str, values: set[str]) -> list[dict[str, str]]:
        return [
            {"value": value, "label": _LABELS[field].get(value, value)}
            for value in sorted(values)
        ]

    return {
        "version": CONTENT_PROFILE_VERSION,
        "objectives": options("content_objective", CONTENT_OBJECTIVE_VALUES),
        "genres": [GENRE_TEMPLATES[key].as_dict() for key in GENRE_TEMPLATES],
        "audience_age_bands": options("audience_age_band", AUDIENCE_AGE_BAND_VALUES),
        "format_profiles": options("format_profile", FORMAT_PROFILE_VALUES),
        "distribution_platforms": options("distribution_platform", DISTRIBUTION_PLATFORM_VALUES),
        "interaction_modes": options("interaction_mode", INTERACTION_MODE_VALUES),
        "safety_policies": options("safety_policy", SAFETY_POLICY_VALUES),
    }


__all__ = [
    "CONTENT_PROFILE_VERSION",
    "CONTENT_OBJECTIVE_VALUES",
    "CONTENT_OBJECTIVE_PATTERN",
    "CONTENT_GENRE_VALUES",
    "CONTENT_GENRE_PATTERN",
    "AUDIENCE_AGE_BAND_VALUES",
    "AUDIENCE_AGE_BAND_PATTERN",
    "FORMAT_PROFILE_VALUES",
    "FORMAT_PROFILE_PATTERN",
    "DISTRIBUTION_PLATFORM_VALUES",
    "DISTRIBUTION_PLATFORM_PATTERN",
    "INTERACTION_MODE_VALUES",
    "INTERACTION_MODE_PATTERN",
    "SAFETY_POLICY_VALUES",
    "SAFETY_POLICY_PATTERN",
    "GENRE_TEMPLATES",
    "GenreTemplate",
    "infer_format_profile",
    "legacy_profile_for_purpose",
    "options_payload",
    "profile_context_lines",
    "resolve_content_profile",
    "template_for_genre",
]
