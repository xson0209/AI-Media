"""Deterministic quality reports for AI Video output readiness."""

from __future__ import annotations

import math
import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..database import (
    PlatformRetentionDataset as DBPlatformRetentionDataset,
    StoryScenarioCandidate as DBStoryScenarioCandidate,
    VideoClipGenerationItem as DBVideoClipGenerationItem,
    VideoInspirationHandoff as DBVideoInspirationHandoff,
    VideoInspirationJob as DBVideoInspirationJob,
    VideoProject as DBVideoProject,
    VideoProjectContextSnapshot as DBVideoProjectContextSnapshot,
    VideoProjectMemoryCard as DBVideoProjectMemoryCard,
    VideoProjectTargetTimelineBeat as DBVideoProjectTargetTimelineBeat,
    VideoQualityReport as DBVideoQualityReport,
    VideoScene as DBVideoScene,
    VideoScenePrompt as DBVideoScenePrompt,
    VideoShot as DBVideoShot,
    VideoShotClip as DBVideoShotClip,
    VideoShotPrompt as DBVideoShotPrompt,
    VideoSubtitle as DBVideoSubtitle,
)

QUALITY_SECTIONS = (
    "input_analysis_quality",
    "handoff_quality",
    "project_memory_quality",
    "candidate_quality",
    "content_retention_quality",
    "originality_quality",
    "story_quality",
    "shot_quality",
    "prompt_quality",
    "voice_quality",
    "subtitle_quality",
    "cross_stage_consistency",
)
CONTENT_SECTION_KEYS = (
    "input_analysis_quality",
    "handoff_quality",
    "project_memory_quality",
    "candidate_quality",
    "content_retention_quality",
    "originality_quality",
    "story_quality",
    "cross_stage_consistency",
)
PRESENTATION_SECTION_KEYS = ("shot_quality", "prompt_quality", "voice_quality", "subtitle_quality")
QUALITY_STATUSES = {"not_checked", "checking", "passed", "needs_review", "blocked", "stale"}
DEFAULT_RUBRIC = {
    "content_weight": 0.75,
    "presentation_weight": 0.25,
    "content_minimum_without_special_confirmation": 0.60,
    "criteria": {
        "audience_problem_need": 15,
        "hook_promise_central_question": 15,
        "logical_progression": 15,
        "new_value_each_beat": 10,
        "emotion_stakes_or_evidence_growth": 10,
        "micro_payoff_payoff_cta": 10,
        "visual_supports_content": 10,
        "voice_delivery": 6,
        "text_and_subtitle": 5,
        "editing_and_audio_support": 4,
    },
}
CAMERA_ONLY_TERMS = {
    "camera",
    "cinematic",
    "lighting",
    "lens",
    "bokeh",
    "dolly",
    "pan",
    "tilt",
    "zoom",
    "shot",
    "close-up",
    "wide",
    "framing",
    "composition",
    "4k",
}

class VideoQualityError(ValueError):
    def __init__(self, message: str, *, error_code: str = "VIDEO_QUALITY_ERROR", status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code

def _now() -> datetime:
    return datetime.utcnow()

def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def _json_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None

def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()

def _tokens(value: Any) -> set[str]:
    return {part for part in re.findall(r"[\wÀ-ỹ]+", _text(value).lower()) if len(part) >= 3}

def _ordered_tokens(value: Any) -> list[str]:
    return [part for part in re.findall(r"[\wÀ-ỹ]+", _text(value).lower()) if len(part) >= 3]

def _jaccard(a: Any, b: Any) -> float:
    left = _tokens(a)
    right = _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))

def _sequence_overlap(source: str, target: str, *, window: int = 8) -> list[str]:
    source_tokens = _ordered_tokens(source)
    target_text = " ".join(_ordered_tokens(target))
    if len(source_tokens) < window or not target_text:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    for index in range(0, len(source_tokens) - window + 1):
        phrase = " ".join(source_tokens[index : index + window])
        if phrase in seen:
            continue
        if phrase and phrase in target_text:
            seen.add(phrase)
            hits.append(phrase)
        if len(hits) >= 5:
            break
    return hits

def _score_status(score: float, *, warnings: list[Any] | None = None, blocking: list[Any] | None = None) -> str:
    if blocking:
        return "blocked"
    if score >= 80 and not warnings:
        return "passed"
    if score >= 50:
        return "needs_review"
    return "blocked"

def _section(
    status: str,
    score: float,
    summary_vi: str,
    *,
    evidence: list[Any] | None = None,
    blocking_errors: list[Any] | None = None,
    warnings: list[Any] | None = None,
    recommended_actions: list[Any] | None = None,
    criteria_scores: dict[str, float] | None = None,
    confidence: float = 0.75,
) -> dict[str, Any]:
    status = status if status in QUALITY_STATUSES else "needs_review"
    return {
        "status": status,
        "score": round(max(0.0, min(100.0, float(score))), 1),
        "summary_vi": summary_vi,
        "evidence": evidence or [],
        "blocking_errors": blocking_errors or [],
        "warnings": warnings or [],
        "recommended_actions": recommended_actions or [],
        "criteria_scores": criteria_scores or {},
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
    }

def _rubric_payload(rubric: models.VideoQualityRubricConfig | None) -> dict[str, Any]:
    if rubric is None:
        return dict(DEFAULT_RUBRIC)
    content_weight = float(rubric.content_weight)
    presentation_weight = float(rubric.presentation_weight)
    if content_weight < 0.60 and not rubric.special_content_weight_confirmed:
        raise VideoQualityError(
            "Trọng số nội dung không được dưới 60% nếu chưa xác nhận cấu hình đặc biệt.",
            error_code="VIDEO_QUALITY_RUBRIC_CONTENT_WEIGHT_TOO_LOW",
        )
    payload = dict(DEFAULT_RUBRIC)
    payload.update(
        {
            "content_weight": content_weight,
            "presentation_weight": presentation_weight,
            "video_type": rubric.video_type,
            "special_content_weight_confirmed": rubric.special_content_weight_confirmed,
        }
    )
    return payload

def _latest_handoff_for_project(project_id: str, db: Session) -> DBVideoInspirationHandoff | None:
    return (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.created_project_id == project_id)
        .order_by(DBVideoInspirationHandoff.updated_at.desc())
        .first()
    )

def _job_for_handoff(handoff: DBVideoInspirationHandoff | None, db: Session) -> DBVideoInspirationJob | None:
    if handoff is None:
        return None
    return db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == handoff.job_id).first()

def _latest_subtitle(project_id: str, db: Session) -> DBVideoSubtitle | None:
    return (
        db.query(DBVideoSubtitle)
        .filter(DBVideoSubtitle.project_id == project_id)
        .order_by(DBVideoSubtitle.updated_at.desc(), DBVideoSubtitle.created_at.desc())
        .first()
    )

def _latest_retention_dataset(
    db: Session,
    *,
    project_id: str | None = None,
    job_id: str | None = None,
) -> DBPlatformRetentionDataset | None:
    query = db.query(DBPlatformRetentionDataset)
    if project_id:
        query = query.filter(DBPlatformRetentionDataset.project_id == project_id)
    elif job_id:
        query = query.filter(DBPlatformRetentionDataset.job_id == job_id)
    else:
        return None
    return query.order_by(DBPlatformRetentionDataset.created_at.desc()).first()

def _memory_cards(project_id: str, db: Session) -> list[DBVideoProjectMemoryCard]:
    return (
        db.query(DBVideoProjectMemoryCard)
        .filter(DBVideoProjectMemoryCard.project_id == project_id)
        .order_by(DBVideoProjectMemoryCard.card_type.asc(), DBVideoProjectMemoryCard.created_at.asc())
        .all()
    )

def _target_beats(project_id: str, db: Session) -> list[DBVideoProjectTargetTimelineBeat]:
    return (
        db.query(DBVideoProjectTargetTimelineBeat)
        .filter(DBVideoProjectTargetTimelineBeat.project_id == project_id)
        .order_by(DBVideoProjectTargetTimelineBeat.beat_order.asc())
        .all()
    )

def _scenes(project_id: str, db: Session) -> list[DBVideoScene]:
    return (
        db.query(DBVideoScene)
        .filter(DBVideoScene.project_id == project_id)
        .order_by(DBVideoScene.scene_order.asc())
        .all()
    )

def _shots(project_id: str, db: Session) -> list[DBVideoShot]:
    return (
        db.query(DBVideoShot)
        .filter(DBVideoShot.project_id == project_id)
        .order_by(DBVideoShot.shot_order.asc())
        .all()
    )

def _latest_shot_prompts(project_id: str, db: Session) -> dict[str, DBVideoShotPrompt]:
    rows = (
        db.query(DBVideoShotPrompt)
        .filter(DBVideoShotPrompt.project_id == project_id)
        .order_by(DBVideoShotPrompt.shot_id.asc(), DBVideoShotPrompt.version.asc(), DBVideoShotPrompt.created_at.asc())
        .all()
    )
    result: dict[str, DBVideoShotPrompt] = {}
    for row in rows:
        result[row.shot_id] = row
    return result

def _latest_scene_prompts(project_id: str, db: Session) -> dict[str, DBVideoScenePrompt]:
    rows = (
        db.query(DBVideoScenePrompt)
        .filter(DBVideoScenePrompt.project_id == project_id)
        .order_by(DBVideoScenePrompt.scene_id.asc(), DBVideoScenePrompt.version.asc(), DBVideoScenePrompt.created_at.asc())
        .all()
    )
    result: dict[str, DBVideoScenePrompt] = {}
    for row in rows:
        result[row.scene_id] = row
    return result

def _candidate_items_from_job(job: DBVideoInspirationJob | None) -> list[dict[str, Any]]:
    if job is None:
        return []
    analysis = _as_dict(job.analysis_json)
    payload = analysis.get("rewrite_candidates")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("candidates", "items", "options"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [value for value in payload.values() if isinstance(value, dict)]
    return []

def _candidate_items_from_story(project: DBVideoProject, db: Session) -> list[dict[str, Any]]:
    if not project.story_episode_id:
        return []
    rows = (
        db.query(DBStoryScenarioCandidate)
        .filter(DBStoryScenarioCandidate.story_episode_id == project.story_episode_id)
        .order_by(DBStoryScenarioCandidate.created_at.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "strategy_type": row.strategy_type,
            "script_json": row.script_json,
            "score_json": row.score_json,
            "evaluation_json": row.evaluation_json,
            "context_snapshot_id": row.context_snapshot_id,
            "selected": bool(row.selected),
        }
        for row in rows
    ]

def _candidate_text(candidate: dict[str, Any]) -> str:
    parts = [
        candidate.get("strategy_type"),
        candidate.get("title"),
        candidate.get("hook"),
        candidate.get("big_idea"),
        candidate.get("script"),
        candidate.get("script_json"),
    ]
    return " ".join(_text(part) for part in parts)

def _evaluate_input_analysis(job: DBVideoInspirationJob | None) -> dict[str, Any]:
    if job is None:
        return _section(
            "needs_review",
            45,
            "Project chưa có VideoAnalysisPackage liên kết; báo cáo vẫn chạy bằng dữ liệu AI Video hiện có.",
            warnings=["Không tìm thấy analysis package nguồn."],
            recommended_actions=["Tạo project từ handoff Video Inspiration hoặc bổ sung analysis package nếu cần đối chiếu nguồn."],
        )
    package = _as_dict(job.analysis_package_json)
    coverage = _as_dict(package.get("coverage_metrics") or job.coverage_metrics_json)
    limitations = _as_list(package.get("limitations") or job.limitations_json)
    score = 55.0
    warnings: list[Any] = []
    if package:
        score += 20
    else:
        warnings.append("Chưa có VideoAnalysisPackage.")
    if package.get("content_retention_beats"):
        score += 12
    else:
        warnings.append("Analysis package chưa có content_retention_beats.")
    if package.get("shots") or package.get("transcript_segments"):
        score += 8
    else:
        warnings.append("Thiếu shot hoặc transcript segment để làm bằng chứng timeline.")
    if limitations:
        score -= min(8, len(limitations) * 2)
    blocking = [] if package else ["Thiếu analysis package đầu vào."]
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra độ phủ analysis package, transcript, shot và retention beat nguồn.",
        evidence=[{"coverage_metrics": coverage}, {"limitations": limitations[:8]}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Chạy lại phân tích video ở chế độ high_quality nếu coverage thấp hoặc thiếu timeline."],
    )

def _evaluate_handoff(handoff: DBVideoInspirationHandoff | None) -> dict[str, Any]:
    if handoff is None:
        return _section(
            "needs_review",
            50,
            "Chưa có handoff cấu trúc nên các kiểm tra nguồn-đích bị giới hạn.",
            warnings=["Không tìm thấy handoff liên kết project."],
            recommended_actions=["Tạo handoff từ Video Inspiration trước khi đánh giá originality và Project Memory đầy đủ."],
        )
    payload = _as_dict(handoff.payload_json)
    target = _as_dict(payload.get("target_content"))
    approved_script = _as_dict(target.get("approved_script"))
    warnings: list[Any] = []
    blocking: list[Any] = []
    score = 70.0
    if handoff.status == "stale":
        warnings.append("Handoff đã stale sau thay đổi nội dung đích.")
        score -= 25
    if not approved_script.get("script"):
        blocking.append("Handoff thiếu approved target script.")
        score -= 40
    if not payload.get("source_observations"):
        warnings.append("Handoff thiếu source_observations.")
        score -= 10
    if not payload.get("learnable_lessons"):
        warnings.append("Handoff thiếu learnable_lessons.")
        score -= 10
    if payload.get("originality_boundaries"):
        score += 10
    else:
        warnings.append("Chưa khai báo originality boundaries.")
    status = "stale" if handoff.status == "stale" and not blocking else _score_status(score, warnings=warnings, blocking=blocking)
    return _section(
        status,
        score,
        "Handoff được kiểm tra tách nguồn quan sát, bài học có thể học và nội dung đích đã duyệt.",
        evidence=[
            {"handoff_id": handoff.id, "status": handoff.status, "revision": handoff.revision},
            {"approved_script_revision": handoff.approved_script_revision},
        ],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Tạo lại handoff khi script đích, target language hoặc analysis package thay đổi."],
    )

def _evaluate_project_memory(cards: list[DBVideoProjectMemoryCard]) -> dict[str, Any]:
    required = {"project_identity", "video_goal", "content_spine", "hook_and_payoff", "approved_decision"}
    present = {card.card_type for card in cards if card.status == "approved"}
    missing = sorted(required - present)
    score = 50.0 + min(40.0, len(present) * 4.0)
    warnings = [f"Thiếu thẻ nhớ bắt buộc: {', '.join(missing)}."] if missing else []
    blocking: list[Any] = []
    if "approved_decision" not in present:
        blocking.append("Project Memory thiếu approved_decision nên voice/subtitle có thể dùng sai narration.")
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra Project Memory có các thẻ đã duyệt cho mục tiêu, hook/payoff và quyết định nội dung.",
        evidence=[{"approved_card_types": sorted(present), "card_count": len(cards)}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Tạo hoặc duyệt lại Project Memory từ handoff nếu thiếu thẻ bắt buộc."],
    )

def _evaluate_candidates(project: DBVideoProject | None, job: DBVideoInspirationJob | None, db: Session) -> dict[str, Any]:
    candidates = _candidate_items_from_job(job)
    if project is not None:
        candidates = candidates or _candidate_items_from_story(project, db)
    warnings: list[Any] = []
    blocking: list[Any] = []
    if len(candidates) < 3:
        warnings.append("Chưa có đủ ba candidate độc lập.")
    texts = [_candidate_text(candidate) for candidate in candidates[:3]]
    pairwise = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            pairwise.append(_jaccard(texts[i], texts[j]))
    too_similar = any(score > 0.72 for score in pairwise)
    if too_similar:
        blocking.append("Ba candidate quá giống nhau, có dấu hiệu chỉ đổi câu chữ.")
    has_critic = False
    if job is not None:
        analysis = _as_dict(job.analysis_json)
        has_critic = bool(analysis.get("rewrite_review"))
    has_critic = has_critic or any(_as_dict(candidate).get("evaluation_json") for candidate in candidates)
    if not has_critic:
        warnings.append("Chưa thấy critic/evaluation độc lập cho candidate.")
    has_trace = bool(
        db.query(DBVideoProjectContextSnapshot.id)
        .filter(DBVideoProjectContextSnapshot.task_type.in_(["story", "shot", "prompt_video"]))
        .first()
    ) if project is not None else False
    score = 45 + min(30, len(candidates) * 10) + (15 if has_critic else 0) + (10 if has_trace else 0)
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra số lượng candidate, độ khác biệt, critic độc lập và trace tổng hợp khi có.",
        evidence=[{"candidate_count": len(candidates), "pairwise_similarity": [round(item, 3) for item in pairwise]}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Tạo lại candidate theo ba hướng khác nhau nếu similarity cao hoặc thiếu critic."],
    )

def _evaluate_content_retention(beats: list[DBVideoProjectTargetTimelineBeat], dataset: DBPlatformRetentionDataset | None) -> dict[str, Any]:
    if not beats:
        return _section(
            "blocked",
            25,
            "Chưa có target timeline nên không thể kiểm tra retention theo beat.",
            blocking_errors=["Thiếu target timeline beat."],
            recommended_actions=["Tạo target timeline từ handoff hoặc chạy lại planning trước khi kiểm tra chất lượng."],
        )
    warnings: list[Any] = []
    beat_evidence: list[Any] = []
    complete = 0
    for beat in beats:
        checks = {
            "role": bool(_text(beat.role)),
            "new_information": bool(_text(beat.new_information)),
            "emotional_or_importance_change": bool(_text(beat.content) or _text(beat.visual_direction)),
            "question_answered": bool(_text(beat.micro_payoff)),
            "new_open_loop": bool(_text(beat.viewer_question)),
            "why_continue": bool(_text(beat.content)),
        }
        count = sum(1 for value in checks.values() if value)
        if count >= 5:
            complete += 1
        else:
            warnings.append(
                {
                    "code": "content_stagnation_risk",
                    "beat_order": beat.beat_order,
                    "message_vi": "Beat này thiếu đóng góp nội dung rõ ràng; không được bù điểm chỉ vì hình ảnh/chuyển cảnh đẹp.",
                    "checks": checks,
                }
            )
        beat_evidence.append({"beat_order": beat.beat_order, "checks": checks})
    score = 45 + (complete / max(1, len(beats))) * 45
    if dataset is not None:
        score += 5
        beat_evidence.append({"actual_retention_dataset_id": dataset.id, "source_type": dataset.source_type})
    else:
        warnings.append("Chưa nhập retention analytics thực tế; báo cáo dùng predicted retention.")
    return _section(
        _score_status(score, warnings=warnings),
        score,
        "Đã kiểm tra từng beat theo vai trò, thông tin mới, câu hỏi, micro-payoff và lý do xem tiếp.",
        evidence=beat_evidence[:30],
        warnings=warnings,
        recommended_actions=["Bổ sung câu hỏi/ngụ ý/micro-payoff cho beat bị content_stagnation_risk."],
        criteria_scores={
            "content_weight": 75,
            "presentation_weight": 25,
            "beat_contribution_coverage": round(complete / max(1, len(beats)) * 100, 1),
        },
    )

def _source_transcripts(handoff: DBVideoInspirationHandoff | None, job: DBVideoInspirationJob | None) -> list[str]:
    payload = _as_dict(handoff.payload_json) if handoff is not None else {}
    source = _as_dict(payload.get("source_observations"))
    transcripts: list[str] = []
    for item in _as_list(source.get("transcript_segments")):
        if isinstance(item, dict):
            transcripts.append(_text(item.get("text")))
        else:
            transcripts.append(_text(item))
    if job is not None and job.transcript_text:
        transcripts.append(job.transcript_text)
    return [item for item in transcripts if item]

def _target_narration(project: DBVideoProject | None, shots: list[DBVideoShot], scenes: list[DBVideoScene], job: DBVideoInspirationJob | None) -> str:
    parts: list[str] = []
    if job is not None:
        parts.append(job.rewritten_script or "")
        parts.append(job.big_idea or "")
        parts.append(job.hook or "")
    if project is not None:
        parts.extend([project.topic, project.script_text or "", project.detailed_script or "", project.creative_brief or ""])
    parts.extend(shot.english_narration or "" for shot in shots)
    parts.extend(scene.dialogue or "" for scene in scenes)
    return "\n".join(part for part in parts if _text(part))

def _evaluate_originality(
    project: DBVideoProject | None,
    handoff: DBVideoInspirationHandoff | None,
    job: DBVideoInspirationJob | None,
    shots: list[DBVideoShot],
    scenes: list[DBVideoScene],
) -> dict[str, Any]:
    source_text = "\n".join(_source_transcripts(handoff, job))
    target_text = _target_narration(project, shots, scenes, job)
    warnings: list[Any] = []
    blocking: list[Any] = []
    evidence: list[Any] = []
    if not source_text:
        warnings.append("Thiếu transcript nguồn nên chỉ kiểm tra originality bằng boundaries/handoff.")
    if not target_text:
        blocking.append("Thiếu narration/nội dung đích để kiểm tra originality.")
    similarity = _jaccard(source_text, target_text)
    overlaps = _sequence_overlap(source_text, target_text)
    if similarity > 0.55 or overlaps:
        blocking.append(
            {
                "code": "originality_copy_risk",
                "message_vi": "Nội dung đích giữ quá nhiều câu hoặc chuỗi diễn đạt từ nguồn.",
                "similarity": round(similarity, 3),
                "overlap_examples": overlaps[:3],
            }
        )
    payload = _as_dict(handoff.payload_json) if handoff is not None else {}
    if not payload.get("originality_boundaries"):
        warnings.append("Chưa có originality boundaries để phân biệt học cơ chế với copy chi tiết.")
    evidence.append(
        {
            "narration_similarity": round(similarity, 3),
            "sequence_overlap_count": len(overlaps),
            "mechanism_learning_allowed": True,
        }
    )
    score = 88 - similarity * 70 - min(35, len(overlaps) * 12)
    if payload.get("originality_boundaries"):
        score += 8
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã so sánh narration nguồn/đích và kiểm tra boundaries để học cơ chế mà không copy chi tiết.",
        evidence=evidence,
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Viết lại phần trùng theo nhân vật, bối cảnh, trật tự beat và câu chữ mới nếu originality bị chặn."],
    )

def _evaluate_story(project: DBVideoProject, beats: list[DBVideoProjectTargetTimelineBeat]) -> dict[str, Any]:
    warnings: list[Any] = []
    blocking: list[Any] = []
    score = 45.0
    if _text(project.detailed_script) or _text(project.script_text):
        score += 20
    else:
        blocking.append("Thiếu nội dung story/script.")
    if project.story_approved or project.script_approved:
        score += 15
    else:
        warnings.append("Story/script chưa được người dùng duyệt.")
    hookish = any((beat.role or "").lower() == "hook" or beat.beat_order == 1 for beat in beats)
    payoff = any(_text(beat.micro_payoff) for beat in beats[-2:] or beats)
    if hookish and payoff:
        score += 15
    else:
        warnings.append("Hook/payoff chưa rõ trong timeline cuối.")
    if project.series_id and not _text(project.continuity_bible or project.character_bible):
        warnings.append("Project thuộc series nhưng thiếu continuity/character context ở project.")
        score -= 5
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra story bám content spine, hook, retention timeline và payoff.",
        evidence=[{"story_approved": project.story_approved, "script_approved": project.script_approved}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Duyệt story/script và làm rõ payoff trước khi coi project sẵn sàng."],
    )

def _evaluate_scene_progression(scenes: list[DBVideoScene]) -> dict[str, Any]:
    """Identify repeat passages without claiming to assess meaning or intent."""
    blocking: list[Any] = []
    warnings: list[Any] = []
    seen: dict[str, int] = {}
    for index, scene in enumerate(scenes):
        # Compare the entire passage; repeated characters, motifs or short
        # catchphrases alone are not enough evidence to reject a story.
        passage = " ".join(re.findall(r"\w+", _text(scene.dialogue).casefold()))
        if len(passage.split()) < 12:
            continue
        previous = seen.get(passage)
        if previous is not None:
            finding = {
                "code": "repeated_scene_narration",
                "scene_id": scene.id,
                "scene_order": scene.scene_order,
                "repeats_scene_order": scenes[previous].scene_order,
                "excerpt": _text(scene.dialogue)[:240],
                "message_vi": "Cảnh này lặp nguyên đoạn lời kể đã có; hãy bổ sung diễn biến mới hoặc xác nhận dụng ý lặp lại.",
            }
            (blocking if previous == index - 1 else warnings).append(finding)
        seen[passage] = index
    score = max(0, 95 - len(blocking) * 30 - len(warnings) * 10)
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã đối chiếu các đoạn lời kể để phát hiện cảnh lặp nguyên văn; chưa đánh giá độ tương đồng ngữ nghĩa.",
        evidence=[{"scene_count": len(scenes), "repeat_count": len(blocking) + len(warnings)}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Viết lại lời kể ở cảnh được nêu để có diễn biến hoặc thông tin mới."] if blocking or warnings else [],
    )

def content_quality_fingerprint(project: DBVideoProject, db: Session) -> str:
    """Fingerprint only editorial inputs so downstream production does not rerun the gate."""
    handoff = _latest_handoff_for_project(project.id, db)
    payload = {
        "script": [project.detailed_script, project.script_text, project.retention_plan_json],
        "approval": [project.story_approved, project.script_approved],
        "language": project.target_language,
        "continuity": [project.series_id, project.continuity_bible, project.character_bible],
        "scenes": [[row.id, row.scene_order, row.dialogue, row.visual_description] for row in _scenes(project.id, db)],
        "beats": [[row.id, row.role, row.content, row.new_information, row.micro_payoff, row.viewer_question] for row in _target_beats(project.id, db)],
        "memory": [[row.id, row.revision, row.status] for row in _memory_cards(project.id, db)],
        "handoff": [handoff.id, handoff.revision, handoff.status, handoff.payload_json] if handoff else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

def _evaluate_shots(shots: list[DBVideoShot], beats: list[DBVideoProjectTargetTimelineBeat]) -> dict[str, Any]:
    if not shots:
        return _section(
            "needs_review",
            45,
            "Chưa có shot/segment để kiểm tra mapping từ nội dung sang sản xuất.",
            warnings=["Thiếu shot/segment."],
            recommended_actions=["Tạo shot breakdown trước khi chạy quality gate cuối."],
        )
    warnings: list[Any] = []
    mapped = 0
    for shot in shots:
        beat = beats[min(len(beats) - 1, max(0, int(shot.shot_order or 1) - 1))] if beats else None
        has_content = bool(_text(shot.vietnamese_description) or _text(shot.primary_action) or _text(shot.purpose))
        has_continuity = bool(_text(shot.composition) or _text(shot.transition_to_next) or _as_list(shot.micro_scenes_json))
        if beat and has_content:
            mapped += 1
        else:
            warnings.append({"shot_id": shot.id, "shot_order": shot.shot_order, "message_vi": "Shot chưa map rõ sang content beat."})
        if not has_continuity:
            warnings.append({"shot_id": shot.id, "message_vi": "Shot thiếu continuity hoặc micro-scene detail."})
    score = 45 + (mapped / max(1, len(shots))) * 45
    return _section(
        _score_status(score, warnings=warnings),
        score,
        "Đã kiểm tra mỗi shot có vai trò nội dung, hành động, continuity và mapping tới target beat.",
        evidence=[{"shot_count": len(shots), "mapped_count": mapped}],
        warnings=warnings[:30],
        recommended_actions=["Bổ sung purpose/primary_action/micro-scene cho shot chưa map beat."],
    )

def _evaluate_prompts(
    shots: list[DBVideoShot],
    beats: list[DBVideoProjectTargetTimelineBeat],
    shot_prompts: dict[str, DBVideoShotPrompt],
    scene_prompts: dict[str, DBVideoScenePrompt],
) -> dict[str, Any]:
    warnings: list[Any] = []
    blocking: list[Any] = []
    checked = 0
    aligned = 0
    if shots:
        for shot in shots:
            prompt = shot_prompts.get(shot.id)
            if prompt is None:
                warnings.append({"shot_id": shot.id, "message_vi": "Shot chưa có prompt video."})
                continue
            checked += 1
            beat = beats[min(len(beats) - 1, max(0, int(shot.shot_order or 1) - 1))] if beats else None
            content_text = " ".join(
                [
                    _text(beat.content if beat else ""),
                    _text(beat.new_information if beat else ""),
                    _text(beat.micro_payoff if beat else ""),
                    _text(shot.english_narration),
                    _text(shot.vietnamese_description),
                ]
            )
            prompt_text = " ".join([prompt.prompt, prompt.prompt_explanation_vi or "", prompt.retention_notes or ""])
            overlap = _jaccard(content_text, prompt_text)
            camera_only = bool(_tokens(prompt_text) & CAMERA_ONLY_TERMS) and overlap < 0.10
            if overlap >= 0.12 and not camera_only:
                aligned += 1
            else:
                item = {
                    "code": "prompt_missing_beat_content",
                    "shot_id": shot.id,
                    "shot_order": shot.shot_order,
                    "message_vi": "Prompt đẹp về camera/kỹ thuật nhưng chưa truyền thông tin mới, cảm xúc hoặc micro-payoff của beat.",
                    "content_overlap": round(overlap, 3),
                }
                blocking.append(item)
            if prompt.quality_status in {"failed", "blocked", "needs_review"}:
                warnings.append({"shot_id": shot.id, "quality_status": prompt.quality_status, "quality_check": prompt.quality_check})
    else:
        checked = len(scene_prompts)
        aligned = checked
    if checked == 0:
        return _section(
            "needs_review",
            45,
            "Chưa có prompt để kiểm tra.",
            warnings=["Thiếu prompt video hoặc prompt scene."],
            recommended_actions=["Tạo prompt trước khi chạy quality gate cuối."],
        )
    score = 45 + (aligned / max(1, checked)) * 45
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra prompt bám content beat trước khi tính điểm camera/kỹ thuật.",
        evidence=[{"prompt_count": checked, "aligned_prompt_count": aligned}],
        blocking_errors=blocking[:30],
        warnings=warnings[:30],
        recommended_actions=["Sửa prompt để thể hiện nội dung beat trước, rồi mới tối ưu camera/framing."],
    )

def _evaluate_voice(project: DBVideoProject, shots: list[DBVideoShot], scenes: list[DBVideoScene]) -> dict[str, Any]:
    warnings: list[Any] = []
    blocking: list[Any] = []
    targets: list[dict[str, Any]] = []
    if project.phase == "phase2" and any(_text(shot.english_narration) for shot in shots):
        for shot in shots:
            if not _text(shot.english_narration):
                continue
            targets.append(
                {
                    "kind": "shot",
                    "id": shot.id,
                    "order": shot.shot_order,
                    "status": shot.voice_status,
                    "duration": shot.audio_duration,
                    "target_duration": shot.duration_seconds,
                    "revision": shot.revision,
                }
            )
    else:
        for scene in scenes:
            if scene.no_narration or not _text(scene.dialogue):
                continue
            targets.append(
                {
                    "kind": "scene",
                    "id": scene.id,
                    "order": scene.scene_order,
                    "status": scene.voice_status,
                    "duration": scene.audio_duration,
                    "target_duration": scene.target_duration_seconds,
                    "revision": scene.revision,
                }
            )
    if not targets:
        return _section(
            "needs_review",
            50,
            "Không có narration cần voice hoặc chưa tạo story/shot có lời.",
            warnings=["Chưa có target voice để kiểm tra."],
        )
    completed = 0
    for target in targets:
        status = target["status"]
        if status == "completed":
            completed += 1
        elif status == "stale":
            blocking.append({"code": "voice_stale", "target": target, "message_vi": "Voice đang dùng narration cũ hoặc artifact đã stale."})
        else:
            warnings.append({"target": target, "message_vi": "Voice chưa hoàn tất."})
        audio_duration = target.get("duration")
        target_duration = target.get("target_duration")
        if audio_duration and target_duration and float(audio_duration) > float(target_duration) + 1.0:
            blocking.append(
                {
                    "code": "voice_too_long_for_segment",
                    "target": target,
                    "message_vi": "Voice dài hơn usable duration của segment; cần rút gọn, đổi nhịp hoặc chỉnh segment.",
                }
            )
    score = 45 + (completed / max(1, len(targets))) * 45
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra voice đúng trạng thái narration cuối, duration, stale và nguy cơ quá dài.",
        evidence=[{"voice_targets": targets[:50], "project_language": project.target_language, "voice_profile_id": project.voice_profile_id}],
        blocking_errors=blocking[:30],
        warnings=warnings[:30],
        recommended_actions=["Tạo lại voice sau khi narration đổi; rút gọn câu hoặc tăng duration khi voice quá dài."],
    )

def _subtitle_cues(row: DBVideoSubtitle | None) -> list[dict[str, Any]]:
    if row is None or not row.cues_json:
        return []
    value = row.cues_json
    if isinstance(value, str):
        try:
            import json

            parsed = json.loads(value)
        except Exception:
            return []
        return [item for item in parsed if isinstance(item, dict)]
    return [item for item in _as_list(value) if isinstance(item, dict)]

def _evaluate_subtitle(
    project: DBVideoProject,
    subtitle: DBVideoSubtitle | None,
    shots: list[DBVideoShot],
    scenes: list[DBVideoScene],
    beats: list[DBVideoProjectTargetTimelineBeat],
) -> dict[str, Any]:
    if subtitle is None:
        return _section(
            "needs_review",
            45,
            "Chưa có subtitle cuối để kiểm tra timing và text.",
            warnings=["Thiếu subtitle."],
            recommended_actions=["Tạo subtitle sau khi voice cuối hoàn tất."],
        )
    cues = _subtitle_cues(subtitle)
    warnings: list[Any] = []
    blocking: list[Any] = []
    if subtitle.status == "stale":
        blocking.append("Subtitle đang stale so với narration hoặc voice cuối.")
    if subtitle.status != "completed":
        warnings.append(f"Subtitle chưa completed: {subtitle.status}.")
    if not cues:
        blocking.append("Subtitle không có cue hợp lệ.")
    final_voice_text = _target_narration(project, shots, scenes, None)
    cue_text = " ".join(_text(cue.get("text")) for cue in cues)
    text_overlap = _jaccard(final_voice_text, cue_text)
    if final_voice_text and cue_text and text_overlap < 0.35:
        blocking.append({"code": "subtitle_voice_mismatch", "message_vi": "Subtitle không khớp voice/narration cuối.", "text_overlap": round(text_overlap, 3)})
    last_end = 0.0
    for cue in cues:
        start = float(cue.get("start_seconds") or 0)
        end = float(cue.get("end_seconds") or 0)
        if start < last_end - 0.05:
            blocking.append({"code": "subtitle_overlap", "cue": cue.get("index"), "message_vi": "Cue subtitle bị trùng timing."})
        if end <= start:
            blocking.append({"code": "subtitle_invalid_timing", "cue": cue.get("index"), "message_vi": "Cue subtitle có timing không hợp lệ."})
        text = _text(cue.get("text"))
        if len(text) > 84:
            warnings.append({"code": "subtitle_line_too_long", "cue": cue.get("index"), "message_vi": "Dòng subtitle quá dài, khó đọc trên mobile."})
        last_end = max(last_end, end)
    payoff_tokens = set()
    for beat in beats[-2:]:
        payoff_tokens |= _tokens(beat.micro_payoff)
    if payoff_tokens and cues:
        first_third = max(1, math.ceil(len(cues) / 3))
        early_text = " ".join(_text(cue.get("text")) for cue in cues[:first_third])
        if len(payoff_tokens & _tokens(early_text)) >= 3:
            warnings.append("Subtitle có nguy cơ tiết lộ payoff quá sớm.")
    score = 45 + (25 if subtitle.status == "completed" else 0) + min(25, text_overlap * 35)
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra subtitle khớp voice cuối, timing, độ đọc và nguy cơ tiết lộ payoff sớm.",
        evidence=[{"subtitle_id": subtitle.id, "status": subtitle.status, "cue_count": len(cues), "text_overlap": round(text_overlap, 3)}],
        blocking_errors=blocking[:30],
        warnings=warnings[:30],
        recommended_actions=["Tạo lại subtitle sau voice cuối; chia dòng ngắn và tránh đưa payoff lên quá sớm."],
    )

def _evaluate_cross_stage(
    sections: dict[str, dict[str, Any]],
    project: DBVideoProject | None,
    handoff: DBVideoInspirationHandoff | None,
    dataset: DBPlatformRetentionDataset | None,
) -> dict[str, Any]:
    blocking_sections = [key for key, section in sections.items() if section.get("status") == "blocked"]
    stale_sections = [key for key, section in sections.items() if section.get("status") == "stale"]
    warnings: list[Any] = []
    blocking: list[Any] = []
    if blocking_sections:
        blocking.append({"code": "upstream_blocking_errors", "sections": blocking_sections})
    if stale_sections:
        warnings.append({"code": "stale_sections", "sections": stale_sections})
    if project is not None and handoff is not None and handoff.target_language != project.target_language:
        blocking.append(
            {
                "code": "target_language_mismatch",
                "message_vi": "Target language của handoff và project không khớp.",
                "handoff_language": handoff.target_language,
                "project_language": project.target_language,
            }
        )
    if dataset is None:
        warnings.append("Chưa có retention thực tế; mọi kết luận retention là dự đoán.")
    score = 92 - len(blocking_sections) * 12 - len(stale_sections) * 8 - len(warnings) * 3
    return _section(
        _score_status(score, warnings=warnings, blocking=blocking),
        score,
        "Đã kiểm tra tính nhất quán xuyên suốt giữa analysis, handoff, memory, story, prompt, voice và subtitle.",
        evidence=[{"blocking_sections": blocking_sections, "stale_sections": stale_sections, "actual_retention_dataset": bool(dataset)}],
        blocking_errors=blocking,
        warnings=warnings,
        recommended_actions=["Sửa lỗi theo thứ tự: blocking upstream, stale artifact, rồi mới tối ưu presentation."],
    )

def _section_scores(sections: dict[str, dict[str, Any]], keys: tuple[str, ...]) -> float:
    scores = [float(sections[key].get("score", 0)) for key in keys if key in sections]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)

def _collect_report_lists(sections: dict[str, dict[str, Any]]) -> tuple[list[Any], list[Any], list[Any], dict[str, Any]]:
    blocking: list[Any] = []
    warnings: list[Any] = []
    actions: list[Any] = []
    evidence: dict[str, Any] = {}
    for key, section in sections.items():
        for item in _as_list(section.get("blocking_errors")):
            blocking.append({"section": key, "detail": item})
        for item in _as_list(section.get("warnings")):
            warnings.append({"section": key, "detail": item})
        for item in _as_list(section.get("recommended_actions")):
            actions.append({"section": key, "detail": item})
        evidence[key] = section.get("evidence") or []
    return blocking, warnings, actions, evidence

def _overall_status(sections: dict[str, dict[str, Any]], blocking: list[Any], warnings: list[Any]) -> str:
    if blocking or any(section.get("status") == "blocked" for section in sections.values()):
        return "blocked"
    if any(section.get("status") == "stale" for section in sections.values()):
        return "stale"
    if warnings or any(section.get("status") == "needs_review" for section in sections.values()):
        return "needs_review"
    if all(section.get("status") == "passed" for section in sections.values()):
        return "passed"
    return "needs_review"

def _project_dependencies(
    project: DBVideoProject,
    db: Session,
    *,
    handoff: DBVideoInspirationHandoff | None,
    job: DBVideoInspirationJob | None,
    cards: list[DBVideoProjectMemoryCard],
    beats: list[DBVideoProjectTargetTimelineBeat],
    scenes: list[DBVideoScene],
    shots: list[DBVideoShot],
    shot_prompts: dict[str, DBVideoShotPrompt],
    subtitle: DBVideoSubtitle | None,
    dataset: DBPlatformRetentionDataset | None,
) -> dict[str, Any]:
    return {
        "project": {"id": project.id, "updated_at": _json_datetime(project.updated_at), "planning_status": project.planning_status},
        "analysis_package": {
            "job_id": job.id if job else None,
            "schema_version": job.analysis_schema_version if job else None,
            "updated_at": _json_datetime(job.updated_at) if job else None,
            "has_package": bool(job and job.analysis_package_json),
        },
        "handoff": {
            "id": handoff.id if handoff else None,
            "revision": int(handoff.revision or 0) if handoff else None,
            "status": handoff.status if handoff else None,
            "updated_at": _json_datetime(handoff.updated_at) if handoff else None,
        },
        "memory": [{"id": row.id, "revision": row.revision, "status": row.status, "updated_at": _json_datetime(row.updated_at)} for row in cards],
        "target_timeline": [{"id": row.id, "revision": row.revision, "updated_at": _json_datetime(row.updated_at)} for row in beats],
        "scenes": [{"id": row.id, "revision": row.revision, "voice_status": row.voice_status, "subtitle_status": row.subtitle_status, "updated_at": _json_datetime(row.updated_at)} for row in scenes],
        "shots": [{"id": row.id, "revision": row.revision, "prompt_status": row.prompt_status, "voice_status": row.voice_status, "subtitle_status": row.subtitle_status, "updated_at": _json_datetime(row.updated_at)} for row in shots],
        "prompts": [{"id": row.id, "shot_id": row.shot_id, "version": row.version, "quality_status": row.quality_status, "created_at": _json_datetime(row.created_at)} for row in shot_prompts.values()],
        "subtitle": {"id": subtitle.id, "revision": subtitle.revision, "status": subtitle.status, "updated_at": _json_datetime(subtitle.updated_at)} if subtitle else None,
        "retention_dataset": {"id": dataset.id, "created_at": _json_datetime(dataset.created_at)} if dataset else None,
        "provider_clip_item_count": db.query(DBVideoClipGenerationItem.id).filter(DBVideoClipGenerationItem.project_id == project.id).count(),
        "active_clip_count": db.query(DBVideoShotClip.id).filter(DBVideoShotClip.project_id == project.id).count(),
    }

def _job_dependencies(job: DBVideoInspirationJob, db: Session, dataset: DBPlatformRetentionDataset | None) -> dict[str, Any]:
    handoffs = (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.job_id == job.id)
        .order_by(DBVideoInspirationHandoff.updated_at.asc())
        .all()
    )
    return {
        "analysis_package": {
            "job_id": job.id,
            "schema_version": job.analysis_schema_version,
            "updated_at": _json_datetime(job.updated_at),
            "has_package": bool(job.analysis_package_json),
            "analysis_completeness": job.analysis_completeness,
        },
        "handoffs": [{"id": row.id, "revision": row.revision, "status": row.status, "updated_at": _json_datetime(row.updated_at)} for row in handoffs],
        "retention_dataset": {"id": dataset.id, "created_at": _json_datetime(dataset.created_at)} if dataset else None,
    }

def _build_project_report(project: DBVideoProject, db: Session, rubric: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    handoff = _latest_handoff_for_project(project.id, db)
    job = _job_for_handoff(handoff, db)
    cards = _memory_cards(project.id, db)
    beats = _target_beats(project.id, db)
    scenes = _scenes(project.id, db)
    shots = _shots(project.id, db)
    shot_prompts = _latest_shot_prompts(project.id, db)
    scene_prompts = _latest_scene_prompts(project.id, db)
    subtitle = _latest_subtitle(project.id, db)
    dataset = _latest_retention_dataset(db, project_id=project.id)

    sections: dict[str, dict[str, Any]] = {}
    sections["input_analysis_quality"] = _evaluate_input_analysis(job)
    sections["handoff_quality"] = _evaluate_handoff(handoff)
    sections["project_memory_quality"] = _evaluate_project_memory(cards)
    sections["candidate_quality"] = _evaluate_candidates(project, job, db)
    sections["content_retention_quality"] = _evaluate_content_retention(beats, dataset)
    sections["originality_quality"] = _evaluate_originality(project, handoff, job, shots, scenes)
    sections["story_quality"] = _evaluate_story(project, beats)
    sections["shot_quality"] = _evaluate_shots(shots, beats)
    sections["prompt_quality"] = _evaluate_prompts(shots, beats, shot_prompts, scene_prompts)
    sections["voice_quality"] = _evaluate_voice(project, shots, scenes)
    sections["subtitle_quality"] = _evaluate_subtitle(project, subtitle, shots, scenes, beats)
    sections["cross_stage_consistency"] = _evaluate_cross_stage(sections, project, handoff, dataset)
    dependencies = _project_dependencies(
        project,
        db,
        handoff=handoff,
        job=job,
        cards=cards,
        beats=beats,
        scenes=scenes,
        shots=shots,
        shot_prompts=shot_prompts,
        subtitle=subtitle,
        dataset=dataset,
    )
    return sections, dependencies

def _build_job_report(job: DBVideoInspirationJob, db: Session, rubric: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    handoff = (
        db.query(DBVideoInspirationHandoff)
        .filter(DBVideoInspirationHandoff.job_id == job.id)
        .order_by(DBVideoInspirationHandoff.updated_at.desc())
        .first()
    )
    dataset = _latest_retention_dataset(db, job_id=job.id)
    sections: dict[str, dict[str, Any]] = {
        "input_analysis_quality": _evaluate_input_analysis(job),
        "handoff_quality": _evaluate_handoff(handoff),
        "project_memory_quality": _section("not_checked", 0, "Chỉ kiểm tra Video Inspiration job; chưa có Project Memory project-level."),
        "candidate_quality": _evaluate_candidates(None, job, db),
        "content_retention_quality": _section(
            "passed" if _as_dict(job.analysis_package_json).get("content_retention_beats") else "needs_review",
            80 if _as_dict(job.analysis_package_json).get("content_retention_beats") else 45,
            "Đã kiểm tra predicted retention trong analysis package nguồn.",
            warnings=[] if _as_dict(job.analysis_package_json).get("content_retention_beats") else ["Thiếu content_retention_beats trong analysis package."],
        ),
        "originality_quality": _evaluate_originality(None, handoff, job, [], []),
        "story_quality": _section("needs_review", 55, "Job chưa tạo project AI Video nên chưa kiểm tra story cuối."),
        "shot_quality": _section("not_checked", 0, "Job chưa tạo project AI Video nên chưa có shot."),
        "prompt_quality": _section("not_checked", 0, "Job chưa tạo project AI Video nên chưa có prompt."),
        "voice_quality": _section("not_checked", 0, "Job chưa tạo project AI Video nên chưa có voice."),
        "subtitle_quality": _section("not_checked", 0, "Job chưa tạo project AI Video nên chưa có subtitle."),
    }
    sections["cross_stage_consistency"] = _evaluate_cross_stage(sections, None, handoff, dataset)
    return sections, _job_dependencies(job, db, dataset)

def _persist_report(
    db: Session,
    *,
    project_id: str | None,
    job_id: str | None,
    scope: str,
    rubric: dict[str, Any],
    sections: dict[str, dict[str, Any]],
    dependencies: dict[str, Any],
) -> models.VideoQualityReportResponse:
    blocking, warnings, actions, evidence = _collect_report_lists(sections)
    content_score = _section_scores(sections, CONTENT_SECTION_KEYS)
    presentation_score = _section_scores(sections, PRESENTATION_SECTION_KEYS)
    total_score = content_score * float(rubric["content_weight"]) + presentation_score * float(rubric["presentation_weight"])
    overall = _overall_status(sections, blocking, warnings)
    now = _now()
    row = DBVideoQualityReport(
        id=str(uuid.uuid4()),
        project_id=project_id,
        job_id=job_id,
        scope=scope,
        status=overall,
        overall_status=overall,
        content_score=round(content_score, 1),
        presentation_score=round(presentation_score, 1),
        total_score=round(total_score, 1),
        rubric_json=rubric,
        sections_json=sections,
        blocking_errors_json=blocking,
        warnings_json=warnings,
        recommended_actions_json=actions,
        evidence_json=evidence,
        dependencies_json=dependencies,
        override_history_json=[],
        revision=1,
        checked_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return models.VideoQualityReportResponse.model_validate(row)

def run_project_quality_report(
    project_id: str,
    data: models.VideoQualityRunRequest | None,
    db: Session,
) -> models.VideoQualityReportResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    rubric = _rubric_payload((data or models.VideoQualityRunRequest()).rubric)
    sections, dependencies = _build_project_report(project, db, rubric)
    return _persist_report(
        db,
        project_id=project.id,
        job_id=dependencies.get("analysis_package", {}).get("job_id"),
        scope="project",
        rubric=rubric,
        sections=sections,
        dependencies=dependencies,
    )

def run_project_content_quality_report(
    project_id: str,
    db: Session,
) -> models.VideoQualityReportResponse | None:
    """Check editorial inputs before expensive shot, voice and clip generation.

    This deliberately does not require an Inspiration handoff, Project Memory,
    prompts, voice or subtitles: those are optional for direct AI Video
    projects and are checked by the final report instead.
    """
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    handoff = _latest_handoff_for_project(project.id, db)
    job = _job_for_handoff(handoff, db)
    cards = _memory_cards(project.id, db)
    beats = _target_beats(project.id, db)
    scenes = _scenes(project.id, db)
    sections: dict[str, dict[str, Any]] = {
        "story_quality": _evaluate_story(project, beats),
        "scene_progression_quality": _evaluate_scene_progression(scenes),
    }
    if beats:
        sections["content_retention_quality"] = _evaluate_content_retention(beats, None)
    if handoff is not None:
        # Source-specific checks are meaningful only when this project was
        # actually created from a source handoff.
        sections["handoff_quality"] = _evaluate_handoff(handoff)
        sections["originality_quality"] = _evaluate_originality(project, handoff, job, [], scenes)
    sections["cross_stage_consistency"] = _evaluate_cross_stage(sections, project, handoff, None)
    rubric = dict(DEFAULT_RUBRIC)
    rubric["stage"] = "preproduction_content"
    rubric["content_fingerprint"] = content_quality_fingerprint(project, db)
    dependencies = _project_dependencies(
        project, db, handoff=handoff, job=job, cards=cards, beats=beats,
        scenes=scenes, shots=[], shot_prompts={}, subtitle=None, dataset=None,
    )
    dependencies["content_fingerprint"] = rubric["content_fingerprint"]
    return _persist_report(
        db,
        project_id=project.id,
        job_id=job.id if job else None,
        scope="project_content",
        rubric=rubric,
        sections=sections,
        dependencies=dependencies,
    )

def run_job_quality_report(
    job_id: str,
    data: models.VideoQualityRunRequest | None,
    db: Session,
) -> models.VideoQualityReportResponse | None:
    job = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == job_id).first()
    if job is None:
        return None
    rubric = _rubric_payload((data or models.VideoQualityRunRequest()).rubric)
    sections, dependencies = _build_job_report(job, db, rubric)
    return _persist_report(
        db,
        project_id=job.created_video_project_id,
        job_id=job.id,
        scope="video_inspiration_job",
        rubric=rubric,
        sections=sections,
        dependencies=dependencies,
    )

def _latest_report_query(db: Session, *, project_id: str | None = None, job_id: str | None = None):
    query = db.query(DBVideoQualityReport)
    if project_id:
        query = query.filter(DBVideoQualityReport.project_id == project_id, DBVideoQualityReport.scope == "project")
    elif job_id:
        query = query.filter(DBVideoQualityReport.job_id == job_id, DBVideoQualityReport.scope == "video_inspiration_job")
    else:
        raise ValueError("project_id or job_id is required")
    return query.order_by(DBVideoQualityReport.checked_at.desc(), DBVideoQualityReport.created_at.desc())

def _current_project_dependencies_for_report(row: DBVideoQualityReport, db: Session) -> dict[str, Any] | None:
    if not row.project_id or row.scope != "project":
        return None
    project = db.query(DBVideoProject).filter(DBVideoProject.id == row.project_id).first()
    if project is None:
        return None
    handoff = _latest_handoff_for_project(project.id, db)
    job = _job_for_handoff(handoff, db)
    return _project_dependencies(
        project,
        db,
        handoff=handoff,
        job=job,
        cards=_memory_cards(project.id, db),
        beats=_target_beats(project.id, db),
        scenes=_scenes(project.id, db),
        shots=_shots(project.id, db),
        shot_prompts=_latest_shot_prompts(project.id, db),
        subtitle=_latest_subtitle(project.id, db),
        dataset=_latest_retention_dataset(db, project_id=project.id),
    )

def _current_job_dependencies_for_report(row: DBVideoQualityReport, db: Session) -> dict[str, Any] | None:
    if not row.job_id or row.scope != "video_inspiration_job":
        return None
    job = db.query(DBVideoInspirationJob).filter(DBVideoInspirationJob.id == row.job_id).first()
    if job is None:
        return None
    return _job_dependencies(job, db, _latest_retention_dataset(db, job_id=job.id))

def _mark_stale_if_needed(row: DBVideoQualityReport, db: Session) -> DBVideoQualityReport:
    if row.overall_status in {"not_checked", "checking", "stale"}:
        return row
    current = _current_project_dependencies_for_report(row, db) or _current_job_dependencies_for_report(row, db)
    if current is None or current == row.dependencies_json:
        return row
    warnings = list(_as_list(row.warnings_json))
    warnings.append(
        {
            "section": "cross_stage_consistency",
            "detail": "Artifact đầu vào đã đổi sau lần kiểm tra gần nhất; báo cáo được đánh dấu stale.",
        }
    )
    row.status = "stale"
    row.overall_status = "stale"
    row.warnings_json = warnings
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row

def get_latest_project_report(project_id: str, db: Session) -> models.VideoQualityReportResponse | None:
    row = _latest_report_query(db, project_id=project_id).first()
    if row is None:
        return None
    return models.VideoQualityReportResponse.model_validate(_mark_stale_if_needed(row, db))

def list_project_reports(project_id: str, db: Session, *, limit: int = 20) -> models.VideoQualityReportListResponse:
    rows = _latest_report_query(db, project_id=project_id).limit(limit).all()
    items = [models.VideoQualityReportResponse.model_validate(_mark_stale_if_needed(row, db)) for row in rows]
    total = db.query(DBVideoQualityReport.id).filter(DBVideoQualityReport.project_id == project_id).count()
    return models.VideoQualityReportListResponse(items=items, total=total)

def get_latest_job_report(job_id: str, db: Session) -> models.VideoQualityReportResponse | None:
    row = _latest_report_query(db, job_id=job_id).first()
    if row is None:
        return None
    return models.VideoQualityReportResponse.model_validate(_mark_stale_if_needed(row, db))

def override_report(report_id: str, data: models.VideoQualityOverrideRequest, db: Session) -> models.VideoQualityReportResponse | None:
    row = db.query(DBVideoQualityReport).filter(DBVideoQualityReport.id == report_id).first()
    if row is None:
        return None
    history = list(_as_list(row.override_history_json))
    history.append(
        {
            "at": _now().isoformat(),
            "from_status": row.overall_status,
            "to_status": data.status,
            "reason": data.reason,
            "overridden_by": data.overridden_by,
            "blocking_errors_preserved": row.blocking_errors_json or [],
        }
    )
    row.status = data.status
    row.overall_status = data.status
    row.override_history_json = history
    row.revision = int(row.revision or 1) + 1
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return models.VideoQualityReportResponse.model_validate(row)

def _normalize_retention_points(data: models.PlatformRetentionDatasetCreateRequest) -> list[dict[str, Any]]:
    duration = max(0.001, float(data.video_duration_seconds))
    points: list[dict[str, Any]] = []
    for index, item in enumerate(data.data_points, start=1):
        raw = item.model_dump(mode="json")
        timestamp = raw.get("timestamp_seconds")
        percent = raw.get("duration_percent")
        if timestamp is None and percent is not None:
            timestamp = duration * float(percent) / 100.0
        if percent is None and timestamp is not None:
            percent = float(timestamp) / duration * 100.0
        point = {
            "index": index,
            "timestamp_seconds": round(float(timestamp or 0.0), 3),
            "duration_percent": round(float(percent or 0.0), 3),
            "retention_percent": raw.get("retention_percent"),
            "rewatch_rate": raw.get("rewatch_rate"),
            "label": raw.get("label"),
            "note": raw.get("note"),
        }
        points.append(point)
    points.sort(key=lambda item: (item["duration_percent"], item["timestamp_seconds"]))
    return points

def _link_retention_findings(
    points: list[dict[str, Any]],
    *,
    project_id: str | None,
    db: Session,
) -> list[dict[str, Any]]:
    if not project_id:
        return []
    beats = _target_beats(project_id, db)
    if not beats or len(points) < 2:
        return []
    duration = max((beat.end_seconds or 0.0) for beat in beats) or 1.0
    findings: list[dict[str, Any]] = []
    previous = points[0]
    for point in points[1:]:
        current_retention = point.get("retention_percent")
        previous_retention = previous.get("retention_percent")
        if current_retention is None or previous_retention is None:
            previous = point
            continue
        drop = float(previous_retention) - float(current_retention)
        rewatch = point.get("rewatch_rate")
        if drop < 12 and not (rewatch is not None and float(rewatch) >= 8):
            previous = point
            continue
        timestamp = float(point["duration_percent"]) / 100.0 * duration
        beat = next((item for item in beats if item.start_seconds <= timestamp <= item.end_seconds), beats[-1])
        finding_type = "drop" if drop >= 12 else "rewatch"
        findings.append(
            {
                "finding_type": finding_type,
                "timestamp_seconds": round(timestamp, 3),
                "duration_percent": point["duration_percent"],
                "beat_order": beat.beat_order,
                "beat_role": beat.role,
                "content": beat.content,
                "shot_or_audio_context": {
                    "new_information": beat.new_information,
                    "micro_payoff": beat.micro_payoff,
                    "visual_direction": beat.visual_direction,
                    "audio_direction": beat.audio_direction,
                },
                "language_vi": (
                    "Điểm retention này có khả năng liên quan tới nội dung/shot cùng thời điểm và cần kiểm chứng; "
                    "báo cáo không khẳng định đây là nguyên nhân chắc chắn."
                ),
                "retention_delta": round(drop, 3),
                "retention_percent": current_retention,
                "rewatch_rate": rewatch,
            }
        )
        previous = point
    return findings[:100]

def create_project_retention_dataset(
    project_id: str,
    data: models.PlatformRetentionDatasetCreateRequest,
    db: Session,
) -> models.PlatformRetentionDatasetResponse | None:
    if db.query(DBVideoProject.id).filter(DBVideoProject.id == project_id).first() is None:
        return None
    points = _normalize_retention_points(data)
    findings = _link_retention_findings(points, project_id=project_id, db=db)
    now = _now()
    row = DBPlatformRetentionDataset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        platform=data.platform,
        video_duration_seconds=data.video_duration_seconds,
        data_points_json=[point.model_dump(mode="json") for point in data.data_points],
        normalized_points_json=points,
        average_watch_time=data.average_watch_time,
        completion_rate=data.completion_rate,
        rewatch_rate=data.rewatch_rate,
        cta_click_rate=data.cta_click_rate,
        conversion_rate=data.conversion_rate,
        source_type=data.source_type,
        linked_findings_json=findings,
        imported_at=now,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return models.PlatformRetentionDatasetResponse.model_validate(row)

def list_project_retention_datasets(project_id: str, db: Session, *, limit: int = 20) -> models.PlatformRetentionDatasetListResponse:
    rows = (
        db.query(DBPlatformRetentionDataset)
        .filter(DBPlatformRetentionDataset.project_id == project_id)
        .order_by(DBPlatformRetentionDataset.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(DBPlatformRetentionDataset.id).filter(DBPlatformRetentionDataset.project_id == project_id).count()
    return models.PlatformRetentionDatasetListResponse(
        items=[models.PlatformRetentionDatasetResponse.model_validate(row) for row in rows],
        total=total,
    )

def create_job_retention_dataset(
    job_id: str,
    data: models.PlatformRetentionDatasetCreateRequest,
    db: Session,
) -> models.PlatformRetentionDatasetResponse | None:
    if db.query(DBVideoInspirationJob.id).filter(DBVideoInspirationJob.id == job_id).first() is None:
        return None
    points = _normalize_retention_points(data)
    now = _now()
    row = DBPlatformRetentionDataset(
        id=str(uuid.uuid4()),
        job_id=job_id,
        platform=data.platform,
        video_duration_seconds=data.video_duration_seconds,
        data_points_json=[point.model_dump(mode="json") for point in data.data_points],
        normalized_points_json=points,
        average_watch_time=data.average_watch_time,
        completion_rate=data.completion_rate,
        rewatch_rate=data.rewatch_rate,
        cta_click_rate=data.cta_click_rate,
        conversion_rate=data.conversion_rate,
        source_type=data.source_type,
        linked_findings_json=[],
        imported_at=now,
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return models.PlatformRetentionDatasetResponse.model_validate(row)
