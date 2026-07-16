"""Pydantic request/response schemas for Comic Series Analysis (task 2.8).

List/polling responses stay lightweight — full source text, page/panel and
asset payloads are only served through dedicated paginated endpoints so a
poll never drags an entire chapter over the wire (task 7.6).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .contracts import DEFAULT_DEVELOPMENT_MODE, error_message


class ComicUrlJobRequest(BaseModel):
    url: str
    reading_mode: str = "auto"
    development_mode: str = DEFAULT_DEVELOPMENT_MODE
    rights_attested: bool = False
    title: str | None = None


class ComicJobSummary(BaseModel):
    """Lightweight job row for lists/polling (no long payloads)."""

    id: str
    source_type: str
    title: str | None = None
    run_status: str
    result_completeness: str
    current_step: str
    progress: float
    reading_mode: str
    development_mode: str
    outcome_code: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    current_source_document_id: str | None = None
    analysis_revision: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class ComicJobListResponse(BaseModel):
    jobs: list[ComicJobSummary]
    total: int
    limit: int
    offset: int


class ComicJobDetailResponse(ComicJobSummary):
    coverage_metrics: dict | None = None
    limitations: list | None = None
    source_url: str | None = None


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int


def job_summary(job) -> ComicJobSummary:
    data = ComicJobSummary.model_validate(job).model_dump()
    # Legacy ingestion rows were marked ready_for_review before any analysis
    # revision existed. Project them as source_ready so the UI never claims an
    # empty job has already been analyzed.
    if data.get("run_status") == "ready_for_review" and int(data.get("analysis_revision") or 0) == 0:
        data["run_status"] = "source_ready"
        data["current_step"] = "panel_analysis"
        data["progress"] = min(float(data.get("progress") or 0), 0.5)
    if data.get("error_code") and not data.get("error_message"):
        data["error_message"] = error_message(data["error_code"])
    return ComicJobSummary(**data)


def job_detail(job) -> ComicJobDetailResponse:
    base = job_summary(job).model_dump()
    return ComicJobDetailResponse(
        **base,
        coverage_metrics=job.coverage_metrics_json,
        limitations=job.limitations_json,
        source_url=job.source_url,
    )


__all__ = [
    "ComicJobDetailResponse",
    "ComicJobListResponse",
    "ComicJobSummary",
    "ComicUrlJobRequest",
    "PaginatedResponse",
    "job_detail",
    "job_summary",
]
