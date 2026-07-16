"""Markdown memory file for long-running AI Video series."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import (
    SeriesCurrentState as DBSeriesCurrentState,
    SeriesCharacterProfile as DBSeriesCharacterProfile,
    SeriesMemoryCard as DBSeriesMemoryCard,
    StoryEpisode as DBStoryEpisode,
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoSeries as DBVideoSeries,
)
from . import video_storage

MAX_MEMORY_CONTEXT_CHARS = 24000
MAX_EPISODE_DETAIL_CHARS = 6000
MAX_SUMMARY_CHARS = 50000
RECENT_EPISODE_DETAIL_COUNT = 8
MEMORY_MARKER = "<!-- voicebox:series-memory:v2 -->"

def _clean_text(value: object | None) -> str:
    return str(value or "").strip()

def _truncate_text(value: object | None, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" ,.;:\n\t") + "...[truncated]"

def _iso(value: datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else "unknown"

def _episode_number(project: DBVideoProject) -> int:
    return int(getattr(project, "episode_number", None) or 0)

def _episode_label(project: DBVideoProject) -> str:
    number = getattr(project, "episode_number", None)
    title = _clean_text(getattr(project, "episode_title", None) or getattr(project, "title", None))
    if number:
        return f"Tập {int(number):02d} - {title or 'Chưa đặt tên'}"
    return title or "Tập chưa đánh số"

def _latest_render_by_project(project_ids: list[str], db: Session) -> dict[str, DBVideoRenderJob]:
    if not project_ids:
        return {}
    rows = (
        db.query(DBVideoRenderJob)
        .filter(DBVideoRenderJob.project_id.in_(project_ids), DBVideoRenderJob.status == "completed")
        .order_by(DBVideoRenderJob.completed_at.desc().nullslast(), DBVideoRenderJob.created_at.desc())
        .all()
    )
    latest: dict[str, DBVideoRenderJob] = {}
    for row in rows:
        latest.setdefault(row.project_id, row)
    return latest

def _episode_summary(project: DBVideoProject, render_job: DBVideoRenderJob | None = None) -> str:
    parts = [
        f"{_episode_label(project)}.",
        f"Topic: {_truncate_text(project.topic, 1200)}" if _clean_text(project.topic) else "",
        f"Story strategy: {_truncate_text(project.story_strategy, 4000)}" if _clean_text(project.story_strategy) else "",
        f"Continuity bible: {_truncate_text(project.continuity_bible, 4000)}" if _clean_text(project.continuity_bible) else "",
        f"Detailed script: {_truncate_text(project.detailed_script or project.script_text, 12000)}"
        if _clean_text(project.detailed_script or project.script_text)
        else "",
    ]
    if render_job is not None:
        parts.append(f"Latest render completed at: {_iso(render_job.completed_at or render_job.updated_at)}.")
    return "\n\n".join(part for part in parts if part).strip()

def _section(title: str, body: object | None, *, empty: str = "_Chưa có._") -> list[str]:
    text = _clean_text(body)
    return [f"### {title}", "", text or empty, ""]

def _character_profile_lines(profile: DBSeriesCharacterProfile) -> list[str]:
    lines = [
        f"### {profile.name}",
        "",
        f"- Role: {_clean_text(profile.role) or 'chưa có'}",
        f"- Face: {_clean_text(profile.face_description) or 'chưa có'}",
        f"- Hair: {_clean_text(profile.hair_description) or 'chưa có'}",
        f"- Body: {_clean_text(profile.body_description) or 'chưa có'}",
        f"- Signature outfit: {_clean_text(profile.signature_outfit) or 'chưa có'}",
        f"- Personality: {_clean_text(profile.personality) or 'chưa có'}",
        f"- Speech style: {_clean_text(profile.speech_style) or 'chưa có'}",
        f"- Fixed traits: {_clean_text(profile.fixed_traits) or 'chưa có'}",
    ]
    notes = _clean_text(profile.additional_notes)
    if notes:
        lines.append(f"- Notes: {notes}")
    lines.append("")
    return lines

def _memory_card_lines(card: DBSeriesMemoryCard) -> list[str]:
    content = card.content_json if isinstance(card.content_json, dict) else {}
    tags = ", ".join(str(item) for item in (card.tags_json or []) if str(item).strip())
    lines = [
        f"### {card.title}",
        "",
        f"- Type: `{card.card_type}`",
        f"- Status: `{card.status}`",
        f"- Revision: {card.revision}",
        f"- Importance: {float(card.importance or 0):.2f}",
        f"- Effective: {card.effective_from_episode or 'start'} -> {card.effective_to_episode or 'latest'}",
        f"- Source: `{card.source_type or 'manual'}` / `{card.source_id or ''}`",
    ]
    if tags:
        lines.append(f"- Tags: {tags}")
    body = _clean_text(content.get("text")) or _clean_text(content)
    lines.extend(["", body or "_Chua co noi dung._", ""])
    return lines

def _current_state_lines(state: DBSeriesCurrentState) -> list[str]:
    lines = [
        f"### State revision {state.revision}",
        "",
        f"- Approval: `{state.approval_status}`",
        f"- Based on episode: {state.based_on_episode_number}",
        f"- Approved at: {_iso(state.approved_at)}",
        "",
    ]
    for label, value in [
        ("Character states", state.character_states_json),
        ("Relationship states", state.relationship_states_json),
        ("Location states", state.location_states_json),
        ("Prop states", state.prop_states_json),
        ("Open threads", state.open_threads_json),
        ("Unresolved conflicts", state.unresolved_conflicts_json),
    ]:
        text = _clean_text(value)
        if text and text not in {"{}", "[]"}:
            lines.extend([f"#### {label}", "", text, ""])
    return lines

def _master_story_summary(episode: DBStoryEpisode) -> str:
    master = episode.master_story_json if isinstance(episode.master_story_json, dict) else {}
    parts = [
        f"Tập {episode.episode_number:02d} - {_clean_text(episode.title) or _clean_text(master.get('title')) or 'Chưa đặt tên'}.",
        f"Intent: {episode.output_intent}.",
        f"Hook: {_truncate_text(master.get('hook'), 800)}" if _clean_text(master.get("hook")) else "",
        f"Logline: {_truncate_text(master.get('logline'), 800)}" if _clean_text(master.get("logline")) else "",
        f"Full story: {_truncate_text(master.get('full_story'), 3000)}" if _clean_text(master.get("full_story")) else "",
    ]
    return "\n\n".join(part for part in parts if part).strip()

def _episode_detail(project: DBVideoProject, render_job: DBVideoRenderJob | None) -> list[str]:
    lines = [
        f"### {_episode_label(project)}",
        "",
        f"- Project ID: `{project.id}`",
        f"- Planning status: `{project.planning_status}`",
        f"- Project status: `{project.status}`",
        f"- Video language: `{project.target_language}`",
        f"- Updated at: {_iso(project.updated_at)}",
    ]
    if render_job is not None:
        lines.extend(
            [
                f"- Latest render status: `{render_job.status}`",
                f"- Latest render completed at: {_iso(render_job.completed_at or render_job.updated_at)}",
            ]
        )
    lines.extend(["", "#### Nội dung tập", ""])
    summary = _episode_summary(project, render_job)
    lines.append(_truncate_text(summary, MAX_EPISODE_DETAIL_CHARS) or "_Chưa có kịch bản đã tạo._")
    lines.append("")
    return lines

def _render_markdown(
    series: DBVideoSeries,
    character_profiles: list[DBSeriesCharacterProfile],
    memory_cards: list[DBSeriesMemoryCard],
    current_states: list[DBSeriesCurrentState],
    story_episodes: list[DBStoryEpisode],
    projects: list[DBVideoProject],
    renders_by_project: dict[str, DBVideoRenderJob],
) -> str:
    now = datetime.utcnow()
    ordered_projects = sorted(projects, key=lambda project: (_episode_number(project), project.created_at or now))
    recent_projects = ordered_projects[-RECENT_EPISODE_DETAIL_COUNT:]
    ordered_story_episodes = sorted(story_episodes, key=lambda episode: (episode.episode_number, episode.created_at or now))
    recent_story_episodes = ordered_story_episodes[-RECENT_EPISODE_DETAIL_COUNT:]
    lines: list[str] = [
        f"# Series Memory: {series.title}",
        "",
        MEMORY_MARKER,
        "",
        f"- Series ID: `{series.id}`",
        f"- Series mode: `{getattr(series, 'series_mode', None) or 'video_story_only'}`",
        f"- Updated at: {_iso(now)} UTC",
        f"- Story episode count: {len(ordered_story_episodes)}",
        f"- Video episode count: {len(ordered_projects)}",
        "",
        "## Cách AI phải dùng file này",
        "",
        "- Đọc Series Bible trước khi tạo tập mới.",
        "- Ưu tiên Hồ sơ nhân vật có cấu trúc; Character Bible cũ chỉ là fallback hoặc ghi chú bổ sung.",
        "- Dùng Episode Index để tránh lặp lại mạch truyện, bối cảnh, payoff hoặc xung đột đã dùng.",
        "- Dùng Latest episode summary và Recent Episode Details để nối tiếp continuity gần nhất.",
        "- Nếu người dùng nhập yêu cầu mới mâu thuẫn với file này, ưu tiên yêu cầu mới nhưng phải giữ identity chính của series.",
        "",
        "## Series Bible",
        "",
    ]
    lines.extend(_section("Character bible", series.character_bible))
    lines.extend(_section("World bible", series.world_bible))
    lines.extend(_section("Style bible", series.style_bible))
    lines.extend(_section("Continuity rules", series.continuity_rules))
    lines.extend(_section("Negative rules", series.negative_rules))
    lines.extend(_section("Latest episode summary", series.previous_episode_summary))
    lines.extend(["## Hồ sơ nhân vật", ""])
    if character_profiles:
        for profile in character_profiles:
            lines.extend(_character_profile_lines(profile))
    else:
        lines.append("_Chưa có Hồ sơ nhân vật có cấu trúc; dùng Character Bible nếu có._")
        lines.append("")
    lines.extend(["## Structured memory cards", ""])
    if memory_cards:
        for card in memory_cards:
            lines.extend(_memory_card_lines(card))
    else:
        lines.append("_Chua co the nho co cau truc. Series Bible cu chi la fallback._")
        lines.append("")
    lines.extend(["## Approved current state", ""])
    if current_states:
        for state in current_states:
            lines.extend(_current_state_lines(state))
    else:
        lines.append("_Chua co ban trang thai hien tai da duyet._")
        lines.append("")
    lines.extend(["## Story Studio Episode Index", ""])
    if ordered_story_episodes:
        for episode in ordered_story_episodes:
            title = _clean_text(episode.title) or "Chưa đặt tên"
            lines.append(
                f"- Tập {episode.episode_number:02d} - {title} | `{episode.output_intent}` | `{episode.approval_status}` | {_truncate_text(episode.source_digest, 220)}"
            )
    else:
        lines.append("_Chưa có Story Episode đã duyệt._")
    lines.extend(["", "## AI Video Episode Index", ""])
    if ordered_projects:
        for project in ordered_projects:
            render = renders_by_project.get(project.id)
            rendered = "rendered" if render is not None else "not_rendered"
            topic = _truncate_text(project.topic, 220)
            lines.append(f"- {_episode_label(project)} | `{project.status}` | `{rendered}` | {topic}")
    else:
        lines.append("_Chưa có tập nào._")
    lines.extend(["", "## Recent Story Episode Details", ""])
    if recent_story_episodes:
        for episode in recent_story_episodes:
            lines.extend(
                [
                    f"### Tập {episode.episode_number:02d} - {_clean_text(episode.title) or 'Chưa đặt tên'}",
                    "",
                    f"- Story Episode ID: `{episode.id}`",
                    f"- Output intent: `{episode.output_intent}`",
                    f"- Approval: `{episode.approval_status}`",
                    f"- Updated at: {_iso(episode.updated_at)}",
                    "",
                    _truncate_text(_master_story_summary(episode), MAX_EPISODE_DETAIL_CHARS)
                    or "_Chưa có Master Story đã duyệt._",
                    "",
                ]
            )
    else:
        lines.append("_Chưa có Story Episode đã duyệt._")
        lines.append("")
    lines.extend(["## Recent AI Video Episode Details", ""])
    if recent_projects:
        for project in recent_projects:
            lines.extend(_episode_detail(project, renders_by_project.get(project.id)))
    else:
        lines.append("_Chưa có tập nào._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def sync_series_memory_file(series_id: str, db: Session) -> Path | None:
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == series_id).first()
    if series is None:
        return None
    character_profiles = (
        db.query(DBSeriesCharacterProfile)
        .filter(DBSeriesCharacterProfile.series_id == series_id)
        .order_by(DBSeriesCharacterProfile.sort_order.asc(), DBSeriesCharacterProfile.created_at.asc())
        .all()
    )
    memory_cards = (
        db.query(DBSeriesMemoryCard)
        .filter(DBSeriesMemoryCard.series_id == series_id, DBSeriesMemoryCard.status == "approved")
        .order_by(DBSeriesMemoryCard.importance.desc(), DBSeriesMemoryCard.updated_at.desc())
        .all()
    )
    current_states = (
        db.query(DBSeriesCurrentState)
        .filter(DBSeriesCurrentState.series_id == series_id, DBSeriesCurrentState.approval_status == "approved")
        .order_by(DBSeriesCurrentState.revision.desc(), DBSeriesCurrentState.created_at.desc())
        .limit(3)
        .all()
    )
    story_episodes = (
        db.query(DBStoryEpisode)
        .filter(DBStoryEpisode.series_id == series_id, DBStoryEpisode.approval_status == "approved")
        .order_by(DBStoryEpisode.episode_number.asc(), DBStoryEpisode.created_at.asc())
        .all()
    )
    projects = (
        db.query(DBVideoProject)
        .filter(DBVideoProject.series_id == series_id)
        .order_by(DBVideoProject.episode_number.asc().nullslast(), DBVideoProject.created_at.asc())
        .all()
    )
    renders_by_project = _latest_render_by_project([project.id for project in projects], db)
    path = video_storage.get_series_memory_path(series_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _render_markdown(series, character_profiles, memory_cards, current_states, story_episodes, projects, renders_by_project),
        encoding="utf-8",
    )
    return path

def ensure_series_memory_file(series_id: str, db: Session) -> Path | None:
    path = video_storage.get_series_memory_path(series_id)
    if path.exists():
        try:
            if MEMORY_MARKER in path.read_text(encoding="utf-8", errors="ignore")[:1000]:
                return path
        except OSError:
            pass
    return sync_series_memory_file(series_id, db)

def read_series_memory_for_prompt(series_id: str, db: Session, *, limit: int = MAX_MEMORY_CONTEXT_CHARS) -> tuple[str, bool]:
    from . import series_brain

    try:
        compiled = series_brain.compile_prompt_context(
            series_id,
            db,
            task_type="video_story_development",
            max_chars=limit,
            persist_trace=False,
        )
        return compiled.context_text, bool(compiled.truncated_groups)
    except Exception:
        path = ensure_series_memory_file(series_id, db)
        if path is None or not path.exists():
            return "", False
        text = path.read_text(encoding="utf-8").strip()
        if len(text) <= limit:
            return text, False
        return text[:limit].rstrip(" ,.;:\n\t") + "\n...[series-memory truncated]", True

def record_rendered_episode(project_id: str, db: Session) -> Path | None:
    project = db.query(DBVideoProject).filter(DBVideoProject.id == project_id).first()
    if project is None or not project.series_id:
        return None
    series = db.query(DBVideoSeries).filter(DBVideoSeries.id == project.series_id).first()
    if series is None:
        return None
    latest_render = (
        db.query(DBVideoRenderJob)
        .filter(DBVideoRenderJob.project_id == project_id, DBVideoRenderJob.status == "completed")
        .order_by(DBVideoRenderJob.completed_at.desc().nullslast(), DBVideoRenderJob.created_at.desc())
        .first()
    )
    series.previous_episode_summary = _episode_summary(project, latest_render)[:MAX_SUMMARY_CHARS]
    if project.episode_number:
        series.latest_episode_number = max(int(series.latest_episode_number or 0), int(project.episode_number))
    series.updated_at = datetime.utcnow()
    path = sync_series_memory_file(series.id, db)
    db.commit()
    return path
