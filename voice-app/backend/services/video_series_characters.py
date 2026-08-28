"""Project-level character flow helpers for multi-character AI Video series."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .. import models
from ..database import (
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    VideoAutoRun as DBVideoAutoRun,
    VideoProject as DBVideoProject,
    VideoSeries as DBVideoSeries,
    VideoShot as DBVideoShot,
    VideoShotPrompt as DBVideoShotPrompt,
)
from . import series_references, video_rendering, video_series_memory, video_state

CHARACTER_FLOW_KEY = "series_character_flow"
REVIEW_STAGE = "character_proposals"
REVIEW_STEP = "review_character_proposals"
DEFAULT_RESUME_STEP = "generate_shots"
PENDING_STATUS = "pending_review"
DECISION_APPROVE = "approve_as_series_character"
DECISION_EPISODE_ONLY = "keep_episode_only"
DECISION_REJECT = "reject"

_ANONYMOUS_NAMES = {
    "",
    "anonymous",
    "unnamed",
    "background extra",
    "extra",
    "crowd",
    "silhouette",
    "người nền",
    "người nền vô danh",
    "nguoi nen",
    "nguoi nen vo danh",
    "người qua đường",
    "nguoi qua duong",
    "đám đông",
    "dam dong",
}


class VideoSeriesCharacterFlowError(ValueError):
    """Raised when a character proposal cannot be read or decided."""

    def __init__(self, message: str, *, error_code: str = "AI_VIDEO_CHARACTER_FLOW_ERROR"):
        super().__init__(message)
        self.error_code = error_code


def is_series_project(project: DBVideoProject | None) -> bool:
    return bool(project is not None and getattr(project, "series_id", None))


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _text(value: Any, *, max_length: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            import json

            text = json.dumps(value, ensure_ascii=False, default=str).strip()
        except Exception:
            text = str(value).strip()
    if max_length is not None and len(text) > max_length:
        return text[:max_length].rstrip(" ,.;:\n\t")
    return text


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "co", "có", "foreground", "named"}
    return False


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text[:48] or "character"


def _is_named_character(name: str) -> bool:
    normalized = re.sub(r"\s+", " ", name.strip().casefold())
    return normalized not in _ANONYMOUS_NAMES


def _profiles_for_series(series_id: str | None, db: Session) -> list[DBSeriesCharacterProfile]:
    if not series_id:
        return []
    return (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )


def _identity_text(profile: DBSeriesCharacterProfile) -> str:
    parts = [
        profile.face_description,
        profile.hair_description,
        profile.body_description,
        profile.signature_outfit,
        profile.fixed_traits,
    ]
    return "; ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())[:4000]


def _profile_to_cast(profile: DBSeriesCharacterProfile, source: dict[str, Any] | None = None) -> dict[str, Any]:
    source = source or {}
    role = _text(_first_present(source, "episode_role", "role", "story_role"), max_length=500)
    importance = _text(_first_present(source, "importance", "priority"), max_length=80) or "supporting"
    reason = _text(_first_present(source, "reason_vi", "reason", "selection_reason_vi"), max_length=2000)
    identity = _identity_text(profile)
    return {
        "character_profile_id": profile.id,
        "name": profile.name,
        "episode_role": role or profile.role,
        "importance": importance,
        "reason_vi": reason or f"Được chọn từ hồ sơ nhân vật series cho tập này: {profile.name}.",
        "identity_lock": identity or profile.fixed_traits or profile.additional_notes,
        "visual_identity": identity or profile.face_description or profile.signature_outfit,
        "fixed_traits": profile.fixed_traits,
        "personality": profile.personality,
        "speech_style": profile.speech_style,
    }


def _match_profile(item: dict[str, Any], profiles: list[DBSeriesCharacterProfile]) -> DBSeriesCharacterProfile | None:
    profile_id = _text(
        _first_present(item, "character_profile_id", "profile_id", "series_character_profile_id", "id")
    )
    if profile_id:
        for profile in profiles:
            if profile.id == profile_id:
                return profile
    name = _text(_first_present(item, "name", "character_name", "ten_nhan_vat"))
    if name:
        normalized = name.casefold()
        for profile in profiles:
            if profile.name.casefold() == normalized:
                return profile
    return None


def _normalize_episode_cast(raw_items: Any, profiles: list[DBSeriesCharacterProfile]) -> list[dict[str, Any]]:
    cast: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in _as_list(raw_items):
        item = _as_dict(raw_item)
        profile = _match_profile(item, profiles)
        if profile is None or profile.id in seen:
            continue
        cast.append(_profile_to_cast(profile, item))
        seen.add(profile.id)
    if not cast:
        cast = [_profile_to_cast(profile) for profile in profiles[:12]]
    return cast


def _normalize_episode_only_guests(raw_items: Any) -> list[dict[str, Any]]:
    guests: list[dict[str, Any]] = []
    for raw_item in _as_list(raw_items):
        item = _as_dict(raw_item)
        name = _text(_first_present(item, "name", "character_name", "label"), max_length=160)
        if not name:
            continue
        proposal_id = _text(_first_present(item, "proposal_id", "id"), max_length=120)
        guests.append(
            {
                "guest_id": _text(_first_present(item, "guest_id"), max_length=120)
                or f"guest-{_slug(name)}-{uuid.uuid4().hex[:8]}",
                "proposal_id": proposal_id or None,
                "name": name,
                "episode_role": _text(_first_present(item, "episode_role", "role"), max_length=500) or None,
                "appearance": _text(_first_present(item, "appearance", "face_description", "visual_identity"), max_length=4000) or None,
                "personality": _text(_first_present(item, "personality"), max_length=4000) or None,
                "speech_style": _text(_first_present(item, "speech_style", "voice_style"), max_length=4000) or None,
                "reason_vi": _text(_first_present(item, "reason_vi", "reason"), max_length=2000) or None,
                "approved_at": _text(_first_present(item, "approved_at"), max_length=80) or None,
            }
        )
    return guests


def _proposal_requires_review(proposal: dict[str, Any]) -> bool:
    name = _text(proposal.get("name"), max_length=160)
    if _is_named_character(name):
        return True
    if any(_boolish(proposal.get(key)) for key in ("foreground", "has_dialogue", "affects_plot", "reappears_likely")):
        return True
    impact = _text(proposal.get("canon_impact"), max_length=120).casefold()
    if impact and impact not in {"none", "low", "background", "background_extra", "episode_only", "non_canon"}:
        return True
    return False


def _normalize_proposals(raw_items: Any) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(_as_list(raw_items), start=1):
        item = _as_dict(raw_item)
        background_extra = _boolish(_first_present(item, "background_extra", "anonymous_extra", "non_canon_extra"))
        name = _text(_first_present(item, "name", "character_name", "label"), max_length=160)
        if not name:
            name = "người nền vô danh" if background_extra else "Nhân vật mới"
        proposal_id = _text(_first_present(item, "proposal_id", "id"), max_length=120)
        if not proposal_id:
            proposal_id = f"proposal-{_slug(name)}-{index}"
        while proposal_id in seen:
            proposal_id = f"{proposal_id}-{uuid.uuid4().hex[:6]}"
        seen.add(proposal_id)
        proposal = {
            "proposal_id": proposal_id,
            "name": name,
            "episode_role": _text(_first_present(item, "episode_role", "role", "story_role"), max_length=500) or None,
            "reason_vi": _text(_first_present(item, "reason_vi", "reason", "why"), max_length=4000) or None,
            "canon_impact": _text(_first_present(item, "canon_impact", "canon_level", "impact"), max_length=120) or "unknown",
            "reappears_likely": _boolish(_first_present(item, "reappears_likely", "will_reappear", "recurring")),
            "has_dialogue": _boolish(_first_present(item, "has_dialogue", "dialogue", "speaks")),
            "foreground": _boolish(_first_present(item, "foreground", "is_foreground", "foreground_character")),
            "affects_plot": _boolish(_first_present(item, "affects_plot", "plot_role", "plot_impact")),
            "background_extra": background_extra,
            "face_description": _text(_first_present(item, "face_description", "face", "appearance"), max_length=4000) or None,
            "hair_description": _text(_first_present(item, "hair_description", "hair"), max_length=4000) or None,
            "body_description": _text(_first_present(item, "body_description", "body"), max_length=4000) or None,
            "signature_outfit": _text(_first_present(item, "signature_outfit", "outfit", "wardrobe"), max_length=4000) or None,
            "personality": _text(_first_present(item, "personality"), max_length=4000) or None,
            "speech_style": _text(_first_present(item, "speech_style", "voice_style"), max_length=4000) or None,
            "fixed_traits": _text(_first_present(item, "fixed_traits", "identity_lock"), max_length=4000) or None,
            "additional_notes": _text(_first_present(item, "additional_notes", "notes"), max_length=4000) or None,
            "affected_artifacts": [
                _text(value, max_length=80)
                for value in _as_list(_first_present(item, "affected_artifacts", "affected_steps", "artifacts"))
                if _text(value)
            ],
            "status": _text(_first_present(item, "status"), max_length=80) or PENDING_STATUS,
            "decision": _text(_first_present(item, "decision"), max_length=80) or None,
            "decided_at": _text(_first_present(item, "decided_at"), max_length=80) or None,
            "decided_note_vi": _text(_first_present(item, "decided_note_vi", "note_vi"), max_length=2000) or None,
            "series_character_profile_id": _text(_first_present(item, "series_character_profile_id"), max_length=120) or None,
        }
        proposal["requires_review"] = _proposal_requires_review(proposal)
        if not proposal["requires_review"] and proposal["status"] == PENDING_STATUS:
            proposal["status"] = "background_extra"
        if not proposal["affected_artifacts"]:
            proposal["affected_artifacts"] = ["story", "shots", "prompts"] if proposal["requires_review"] else ["prompts"]
        proposals.append(proposal)
    return proposals


def project_character_flow(project: DBVideoProject | None) -> dict[str, Any]:
    if project is None:
        return {}
    retention = project.retention_plan_json if isinstance(project.retention_plan_json, dict) else {}
    flow = retention.get(CHARACTER_FLOW_KEY)
    return dict(flow) if isinstance(flow, dict) else {}


def set_project_character_flow(project: DBVideoProject, flow: dict[str, Any]) -> None:
    base = project.retention_plan_json if isinstance(project.retention_plan_json, dict) else {}
    retention = dict(base)
    retention[CHARACTER_FLOW_KEY] = flow
    project.retention_plan_json = retention
    flag_modified(project, "retention_plan_json")


def build_story_character_flow(project: DBVideoProject, db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not is_series_project(project):
        return None
    profiles = _profiles_for_series(project.series_id, db)
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
    flow = {
        "schema_version": 1,
        "project_id": project.id,
        "series_id": project.series_id,
        "series_revision": int(getattr(series, "revision", 1) or 1) if series else 1,
        "episode_cast": _normalize_episode_cast(
            _first_present(payload, "episode_cast", "cast", "selected_characters"),
            profiles,
        ),
        "episode_only_guests": _normalize_episode_only_guests(
            _first_present(payload, "episode_only_guests", "episode_guests", "guest_characters")
        ),
        "new_character_proposals": _normalize_proposals(
            _first_present(payload, "new_character_proposals", "character_proposals", "proposed_characters")
        ),
        "resume_step": DEFAULT_RESUME_STEP,
        "updated_at": _now_iso(),
    }
    return flow


def pending_required_proposals(project: DBVideoProject | None) -> list[dict[str, Any]]:
    flow = project_character_flow(project)
    proposals = _as_list(flow.get("new_character_proposals"))
    return [
        proposal
        for proposal in proposals
        if isinstance(proposal, dict)
        and bool(proposal.get("requires_review"))
        and (proposal.get("status") or PENDING_STATUS) == PENDING_STATUS
    ]


def has_pending_required_proposals(project: DBVideoProject | None) -> bool:
    return bool(pending_required_proposals(project))


def _flow_message(project: DBVideoProject | None, pending_count: int) -> str:
    if project is None:
        return "Không tìm thấy dự án video."
    if not project.series_id:
        return "Dự án không thuộc series nên không cần luồng duyệt nhân vật."
    if pending_count:
        return f"Có {pending_count} nhân vật mới cần duyệt trước khi auto-run chạy tiếp."
    return "Dàn nhân vật của tập đã sẵn sàng."


def character_flow_response(project: DBVideoProject, db: Session | None = None) -> models.VideoProjectCharacterFlowResponse:
    flow = project_character_flow(project)
    pending_count = len(pending_required_proposals(project))
    return models.VideoProjectCharacterFlowResponse(
        project_id=project.id,
        series_id=project.series_id,
        episode_cast=[
            models.EpisodeCastMember.model_validate(item)
            for item in _as_list(flow.get("episode_cast"))
            if isinstance(item, dict)
        ],
        episode_only_guests=[
            models.EpisodeOnlyGuest.model_validate(item)
            for item in _as_list(flow.get("episode_only_guests"))
            if isinstance(item, dict)
        ],
        new_character_proposals=[
            models.NewCharacterProposal.model_validate(item)
            for item in _as_list(flow.get("new_character_proposals"))
            if isinstance(item, dict)
        ],
        pending_required_count=pending_count,
        required_proposals_decided=pending_count == 0,
        resume_step=_text(flow.get("resume_step"), max_length=80) or None,
        message=_flow_message(project, pending_count),
    )


def get_character_flow(project_id: str, db: Session) -> models.VideoProjectCharacterFlowResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    return character_flow_response(project, db)


def _proposal_to_profile_create(proposal: dict[str, Any]) -> models.SeriesCharacterProfileCreate:
    name = _text(proposal.get("name"), max_length=160)
    if not _is_named_character(name):
        raise VideoSeriesCharacterFlowError(
            "Proposal này chưa có tên nhân vật rõ ràng để thêm vào Series.",
            error_code="AI_VIDEO_CHARACTER_PROPOSAL_NAME_REQUIRED",
        )
    return models.SeriesCharacterProfileCreate(
        name=name,
        role=_text(proposal.get("episode_role"), max_length=500) or None,
        face_description=_text(proposal.get("face_description"), max_length=4000) or None,
        hair_description=_text(proposal.get("hair_description"), max_length=4000) or None,
        body_description=_text(proposal.get("body_description"), max_length=4000) or None,
        signature_outfit=_text(proposal.get("signature_outfit"), max_length=4000) or None,
        personality=_text(proposal.get("personality"), max_length=4000) or None,
        speech_style=_text(proposal.get("speech_style"), max_length=4000) or None,
        fixed_traits=_text(proposal.get("fixed_traits"), max_length=4000) or None,
        additional_notes=_text(proposal.get("additional_notes") or proposal.get("reason_vi"), max_length=4000) or None,
    )


def _append_cast_from_profile(flow: dict[str, Any], profile: models.SeriesCharacterProfileResponse, proposal: dict[str, Any]) -> None:
    cast = [item for item in _as_list(flow.get("episode_cast")) if isinstance(item, dict)]
    if any(item.get("character_profile_id") == profile.id for item in cast):
        flow["episode_cast"] = cast
        return
    cast.append(
        {
            "character_profile_id": profile.id,
            "name": profile.name,
            "episode_role": proposal.get("episode_role") or profile.role,
            "importance": "supporting",
            "reason_vi": f"Được thêm vào Series từ proposal của tập này: {proposal.get('reason_vi') or profile.name}.",
            "identity_lock": "; ".join(
                part
                for part in [
                    profile.face_description,
                    profile.hair_description,
                    profile.body_description,
                    profile.signature_outfit,
                    profile.fixed_traits,
                ]
                if part
            )[:4000],
            "visual_identity": profile.face_description or profile.signature_outfit or profile.fixed_traits,
            "fixed_traits": profile.fixed_traits,
        }
    )
    flow["episode_cast"] = cast


def _append_episode_only_guest(flow: dict[str, Any], proposal: dict[str, Any]) -> None:
    guests = [item for item in _as_list(flow.get("episode_only_guests")) if isinstance(item, dict)]
    if any(item.get("proposal_id") == proposal.get("proposal_id") for item in guests):
        flow["episode_only_guests"] = guests
        return
    guests.append(
        {
            "guest_id": f"guest-{_slug(_text(proposal.get('name')))}-{uuid.uuid4().hex[:8]}",
            "proposal_id": proposal.get("proposal_id"),
            "name": proposal.get("name") or "Nhân vật khách",
            "episode_role": proposal.get("episode_role"),
            "appearance": proposal.get("face_description") or proposal.get("signature_outfit") or proposal.get("fixed_traits"),
            "personality": proposal.get("personality"),
            "speech_style": proposal.get("speech_style"),
            "reason_vi": proposal.get("reason_vi"),
            "approved_at": _now_iso(),
        }
    )
    flow["episode_only_guests"] = guests


def _resume_step_for_rejection(proposal: dict[str, Any], flow: dict[str, Any]) -> str:
    affected = {_text(value).casefold() for value in _as_list(proposal.get("affected_artifacts"))}
    if "story" in affected or "develop_story" in affected:
        return "develop_story"
    if "shots" in affected or "shot" in affected or "generate_shots" in affected:
        return "generate_shots"
    if "prompts" in affected or "prompt" in affected or "generate_prompts" in affected:
        return "generate_prompts"
    return _text(flow.get("resume_step"), max_length=80) or DEFAULT_RESUME_STEP


def _mark_regeneration_scope(project: DBVideoProject, resume_step: str, db: Session) -> None:
    now = datetime.utcnow()
    if resume_step == "develop_story":
        project.story_approved = False
        project.script_approved = False
        project.planning_status = "stale"
        project.status = "story_ready"
    if resume_step in {"develop_story", "generate_shots"}:
        for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all():
            if not shot.locked:
                shot.status = "stale"
                shot.prompt_status = "stale"
                shot.subtitle_status = "stale"
                shot.updated_at = now
        db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project.id).delete(synchronize_session=False)
    elif resume_step == "generate_prompts":
        for shot in db.query(DBVideoShot).filter(DBVideoShot.project_id == project.id).all():
            shot.prompt_status = "stale"
            shot.updated_at = now
        db.query(DBVideoShotPrompt).filter(DBVideoShotPrompt.project_id == project.id).delete(synchronize_session=False)
    video_rendering.mark_render_outputs_stale(project.id, db)
    video_state.mark_package_stale(project, db)
    project.updated_at = now


def _bump_series_revision(series_id: str, profile: models.SeriesCharacterProfileResponse, db: Session) -> None:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        return
    old_revision = int(series.revision or 1)
    series.revision = old_revision + 1
    series.updated_at = datetime.utcnow()
    series_references.record_version(
        db,
        series_id=series_id,
        entity_type="video_series",
        entity_id=series_id,
        revision=int(series.revision or 1),
        snapshot={
            "title": series.title,
            "series_mode": series.series_mode,
            "latest_episode_number": series.latest_episode_number,
            "added_character_profile_id": profile.id,
            "added_character_name": profile.name,
        },
        change_source="character_proposal_approval",
        change_reason=f"Thêm nhân vật {profile.name} từ proposal AI Video đã được duyệt.",
    )


def decide_character_proposal(
    project_id: str,
    proposal_id: str,
    data: models.CharacterProposalDecisionRequest,
    db: Session,
) -> models.CharacterProposalDecisionResponse | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None:
        return None
    if not project.series_id:
        raise VideoSeriesCharacterFlowError(
            "Dự án này không thuộc series nên không có proposal nhân vật series.",
            error_code="AI_VIDEO_PROJECT_NOT_SERIES",
        )
    flow = project_character_flow(project)
    proposals = [item for item in _as_list(flow.get("new_character_proposals")) if isinstance(item, dict)]
    proposal = next((item for item in proposals if item.get("proposal_id") == proposal_id), None)
    if proposal is None:
        raise VideoSeriesCharacterFlowError(
            "Không tìm thấy proposal nhân vật cần duyệt.",
            error_code="AI_VIDEO_CHARACTER_PROPOSAL_NOT_FOUND",
        )
    if proposal.get("status") != PENDING_STATUS:
        return models.CharacterProposalDecisionResponse(
            character_flow=character_flow_response(project, db),
            created_character_profile=None,
            auto_run_ready_to_continue=len(pending_required_proposals(project)) == 0,
            message="Proposal này đã có quyết định trước đó.",
        )

    created_profile: models.SeriesCharacterProfileResponse | None = None
    decision = data.decision
    now = _now_iso()
    if decision == DECISION_APPROVE:
        from . import video_projects

        created_profile = video_projects.create_character_profile(
            project.series_id,
            _proposal_to_profile_create(proposal),
            db,
        )
        if created_profile is None:
            raise VideoSeriesCharacterFlowError(
                "Không tìm thấy series để thêm nhân vật.",
                error_code="AI_VIDEO_SERIES_NOT_FOUND",
            )
        _bump_series_revision(project.series_id, created_profile, db)
        proposal["status"] = "approved_as_series_character"
        proposal["decision"] = DECISION_APPROVE
        proposal["decided_at"] = now
        proposal["decided_note_vi"] = data.note_vi
        proposal["series_character_profile_id"] = created_profile.id
        _append_cast_from_profile(flow, created_profile, proposal)
    elif decision == DECISION_EPISODE_ONLY:
        proposal["status"] = "episode_only"
        proposal["decision"] = DECISION_EPISODE_ONLY
        proposal["decided_at"] = now
        proposal["decided_note_vi"] = data.note_vi
        _append_episode_only_guest(flow, proposal)
    elif decision == DECISION_REJECT:
        resume_step = _resume_step_for_rejection(proposal, flow)
        proposal["status"] = "rejected"
        proposal["decision"] = DECISION_REJECT
        proposal["decided_at"] = now
        proposal["decided_note_vi"] = data.note_vi
        flow["resume_step"] = resume_step
        flow.setdefault("rejected_proposal_ids", []).append(proposal_id)
        _mark_regeneration_scope(project, resume_step, db)
    else:
        raise VideoSeriesCharacterFlowError(
            "Quyết định proposal không hợp lệ.",
            error_code="AI_VIDEO_CHARACTER_PROPOSAL_DECISION_INVALID",
        )

    flow["new_character_proposals"] = proposals
    flow["updated_at"] = now
    if "resume_step" not in flow:
        flow["resume_step"] = DEFAULT_RESUME_STEP
    set_project_character_flow(project, flow)
    db.commit()
    db.refresh(project)
    if project.series_id:
        video_series_memory.sync_series_memory_file(project.series_id, db)
    response = character_flow_response(project, db)
    _mark_character_reviewed_if_ready(project.id, db)
    return models.CharacterProposalDecisionResponse(
        character_flow=response,
        created_character_profile=created_profile,
        auto_run_ready_to_continue=response.required_proposals_decided,
        message=(
            "Đã thêm nhân vật vào Series."
            if decision == DECISION_APPROVE
            else "Đã giữ nhân vật trong phạm vi tập này."
            if decision == DECISION_EPISODE_ONLY
            else "Đã từ chối proposal và đánh dấu artifact cần tạo lại từ checkpoint an toàn."
        ),
    )


def _mark_character_reviewed_if_ready(project_id: str, db: Session) -> None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None or has_pending_required_proposals(project):
        return
    run = (
        db.query(DBVideoAutoRun)
        .filter(
            DBVideoAutoRun.project_id == project_id,
            DBVideoAutoRun.status == "needs_review",
            DBVideoAutoRun.review_stage == REVIEW_STAGE,
        )
        .order_by(DBVideoAutoRun.created_at.desc())
        .first()
    )
    if run is None or not isinstance(run.step_results_json, dict):
        return
    results = dict(run.step_results_json)
    results.setdefault("reviewed", {})[REVIEW_STAGE] = True
    run.step_results_json = results
    flag_modified(run, "step_results_json")
    db.commit()


def cast_prompt_text_from_project(project: DBVideoProject) -> str:
    flow = project_character_flow(project)
    cast = [item for item in _as_list(flow.get("episode_cast")) if isinstance(item, dict)]
    guests = [item for item in _as_list(flow.get("episode_only_guests")) if isinstance(item, dict)]
    lines: list[str] = []
    if cast:
        lines.append("Approved episode cast:")
        for item in cast[:20]:
            lines.append(
                "- "
                + "; ".join(
                    part
                    for part in [
                        f"{item.get('name')}",
                        f"profile_id={item.get('character_profile_id')}" if item.get("character_profile_id") else "",
                        f"role={item.get('episode_role')}" if item.get("episode_role") else "",
                        f"identity_lock={item.get('identity_lock') or item.get('visual_identity') or item.get('fixed_traits') or ''}",
                        f"personality={item.get('personality') or ''}",
                        f"canonical_voice={item.get('speech_style') or ''}",
                    ]
                    if part and part != "None"
                )
            )
    if guests:
        lines.append("Episode-only guests approved for this project:")
        for item in guests[:20]:
            lines.append(
                f"- {item.get('name')}; guest_id={item.get('guest_id')}; role={item.get('episode_role') or ''}; "
                f"appearance={item.get('appearance') or ''}; speech={item.get('speech_style') or ''}"
            )
    return "\n".join(lines).strip()


def story_development_instructions(project: DBVideoProject, db: Session) -> str:
    if not is_series_project(project):
        return ""
    profiles = _profiles_for_series(project.series_id, db)
    if profiles:
        roster = "\n".join(
            f"- {profile.name} (id={profile.id}, role={profile.role or 'chưa ghi'}): "
            f"identity={_identity_text(profile) or profile.additional_notes or 'chưa có identity lock chi tiết'}; "
            f"personality={profile.personality or 'chưa mô tả'}; canonical_voice={profile.speech_style or 'chưa mô tả'}"
            for profile in profiles[:30]
        )
    else:
        roster = "- Series chưa có hồ sơ nhân vật có cấu trúc; chỉ dùng Character Bible làm fallback và không tự ghi canon."
    return f"""
Luồng series nhiều nhân vật đang bật vì project có series_id.
Hồ sơ nhân vật series đã duyệt:
{roster}

Yêu cầu nhân vật bắt buộc cho story:
- Trước khi chia scene, chọn episode_cast từ hồ sơ nhân vật đã duyệt nếu có; mỗi item phải có character_profile_id, name, episode_role, importance và reason_vi.
- Ưu tiên roster có sẵn. Chỉ đề xuất nhân vật mới khi story thật sự cần.
- Nếu cần người nền vô danh, ghi là background extra/non-canon và không đặt tên riêng.
- Nếu tạo nhân vật mới có tên, foreground, thoại, vai trò plot, quan hệ canon hoặc khả năng tái xuất, trả trong new_character_proposals với requires_review=true; không tự ghi vào SeriesCharacterProfile.
- Có thể trả episode_only_guests cho nhân vật chỉ dùng trong tập hiện tại nếu không ảnh hưởng canon.
- Mỗi scene nên nêu nhân vật liên quan trong mô tả hoặc trường related_characters nếu cần.
""".strip()


def shot_breakdown_instructions(project: DBVideoProject) -> str:
    if not is_series_project(project):
        return ""
    cast_text = cast_prompt_text_from_project(project) or "Chưa có cast đã duyệt; dùng Series Bible nhưng không tự thêm nhân vật canon."
    return f"""
Dàn nhân vật đã duyệt cho tập này:
{cast_text}

Yêu cầu shot cho series nhiều nhân vật:
- Mỗi shot/segment phải trả visible_characters nếu có nhân vật foreground.
- visible_characters phải nêu character_profile_id hoặc guest_id/name, vị trí trong khung hình, hành động, biểu cảm và tương tác.
- Chỉ dùng approved episode cast và episode-only guests đã duyệt. Background extras phải ghi anonymous/non-canon.
- Không tạo named foreground character mới ở bước shot nếu chưa có proposal được duyệt.
""".strip()


def video_prompt_instructions(project: DBVideoProject) -> str:
    if not is_series_project(project):
        return ""
    cast_text = cast_prompt_text_from_project(project) or "Chưa có cast đã duyệt; chỉ dùng nhân vật đã có trong Series Bible và tránh thêm nhân vật canon mới."
    return f"""
Dàn nhân vật được phép dùng trong prompt video series:
{cast_text}

Yêu cầu prompt video series:
- Prompt phải là phim hoạt hình 3D/stylized 3D/cinematic 3D animation nhiều nhân vật nếu shot có nhiều người.
- Với từng nhân vật nhìn thấy, mô tả identity lock, vị trí trong khung hình, hành động, biểu cảm và tương tác.
- Nêu rõ ai nói, ai phản ứng nếu có thoại hoặc phản ứng cảm xúc; giữ `speech_style`/canonical_voice của từng nhân vật và chỉ thay emotion/delivery theo bối cảnh tạm thời của shot.
- Không dùng quy tắc "same main character only"; thay bằng đúng approved episode cast và episode-only guests của tập.
- Negative prompt phải chặn duplicate character, identity swap, unintended named character, wrong face, wrong hairstyle, wrong signature outfit và extra foreground character ngoài cast.
""".strip()


def segment_continuity_rule(project: DBVideoProject) -> str:
    if not is_series_project(project):
        return (
            "Continuity rule: keep the same main character, same face/identity, same outfit or wardrobe logic, "
            "same visual style, same color palette, and the story state from the previous segment. "
            "Do not restart as a separate story."
        )
    cast_text = cast_prompt_text_from_project(project)
    cast_line = (
        "Use only the approved episode cast and approved episode-only guests for this project."
        if not cast_text
        else "Use only these approved characters for foreground story action:\n" + cast_text
    )
    return (
        "Multi-character series continuity rule: do not use a single-main-character-only assumption. "
        f"{cast_line}\n"
        "Lock each visible character's face, hair, body shape, signature outfit, personality, and story state. "
        "Prevent identity swaps, duplicates, wrong outfits, unintended named characters, and extra foreground characters outside the approved cast."
    )


def fallback_prompt_character_text(project: DBVideoProject) -> str:
    if not is_series_project(project):
        return (
            "Keep every visible character consistent with the approved project source and shot description: "
            "same identity, body proportions, face markers, outfit or wardrobe logic, color palette, and story state. "
            "Do not invent a named character, costume, or canon detail that is absent from the approved source."
        )
    cast_text = cast_prompt_text_from_project(project)
    if not cast_text:
        return (
            "Use the approved series characters only; keep every visible character's identity, face, hair, outfit, "
            "role, and story state locked across segments."
        )
    return (
        "Use this approved multi-character cast, with identity locked per character and no extra foreground named characters:\n"
        f"{cast_text}"
    )
