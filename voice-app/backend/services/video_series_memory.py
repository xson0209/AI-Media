"""Markdown memory file for long-running AI Video series."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import (
    VideoProject as DBVideoProject,
    VideoRenderJob as DBVideoRenderJob,
    VideoSeries as DBVideoSeries,
)
from . import video_storage

MAX_MEMORY_CONTEXT_CHARS = 24000
MAX_EPISODE_DETAIL_CHARS = 6000
MAX_SUMMARY_CHARS = 50000
RECENT_EPISODE_DETAIL_COUNT = 8

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
    projects: list[DBVideoProject],
    renders_by_project: dict[str, DBVideoRenderJob],
) -> str:
    now = datetime.utcnow()
    ordered_projects = sorted(projects, key=lambda project: (_episode_number(project), project.created_at or now))
    recent_projects = ordered_projects[-RECENT_EPISODE_DETAIL_COUNT:]
    lines: list[str] = [
        f"# Series Memory: {series.title}",
        "",
        "<!-- voicebox:series-memory:v1 -->",
        "",
        f"- Series ID: `{series.id}`",
        f"- Updated at: {_iso(now)} UTC",
        f"- Episode count: {len(ordered_projects)}",
        "",
        "## Cách AI phải dùng file này",
        "",
        "- Đọc Series Bible trước khi tạo tập mới.",
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
    lines.extend(["## Episode Index", ""])
    if ordered_projects:
        for project in ordered_projects:
            render = renders_by_project.get(project.id)
            rendered = "rendered" if render is not None else "not_rendered"
            topic = _truncate_text(project.topic, 220)
            lines.append(f"- {_episode_label(project)} | `{project.status}` | `{rendered}` | {topic}")
    else:
        lines.append("_Chưa có tập nào._")
    lines.extend(["", "## Recent Episode Details", ""])
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
    projects = (
        db.query(DBVideoProject)
        .filter(DBVideoProject.series_id == series_id)
        .order_by(DBVideoProject.episode_number.asc().nullslast(), DBVideoProject.created_at.asc())
        .all()
    )
    renders_by_project = _latest_render_by_project([project.id for project in projects], db)
    path = video_storage.get_series_memory_path(series_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_markdown(series, projects, renders_by_project), encoding="utf-8")
    return path

def ensure_series_memory_file(series_id: str, db: Session) -> Path | None:
    path = video_storage.get_series_memory_path(series_id)
    if path.exists():
        return path
    return sync_series_memory_file(series_id, db)

def read_series_memory_for_prompt(series_id: str, db: Session, *, limit: int = MAX_MEMORY_CONTEXT_CHARS) -> tuple[str, bool]:
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
