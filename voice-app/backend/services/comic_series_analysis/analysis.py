"""Persist reviewable multimodal comic analysis for one source revision.

The orchestrator only records visual conclusions when a vision-capable
adapter receives real image attachments. Structured provider output is
materialized as panels, OCR/dialogue, characters, locations and plot rows,
then projected into ``analysis_package_json`` for the review UI.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ...database import (
    ComicAnalysisJob as DBJob,
    ComicDetectedCharacter as DBCharacter,
    ComicDetectedLocation as DBLocation,
    ComicPanel as DBPanel,
    ComicPlotAnalysis as DBPlot,
    ComicSourceAsset as DBAsset,
    ComicSourcePage as DBPage,
    ComicSpeechBubble as DBBubble,
)
from . import vision_adapters
from .contracts import ANALYSIS_PACKAGE_SCHEMA_VERSION, ComicAnalysisError


def analyze_revision(db: Session, job_id: str) -> DBJob:
    """Analyze the finalized source and create a new immutable review revision."""
    job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if job is None:
        raise ComicAnalysisError("COMIC_ANALYSIS_NOT_FOUND", status_code=404)
    if not job.current_source_document_id:
        raise ComicAnalysisError(
            "COMIC_ANALYSIS_INVALID_STATE",
            "Chưa có source document để phân tích.",
        )

    revision = int(job.analysis_revision or 0) + 1
    job.current_step = "panel_analysis"
    job.run_status = "running"
    job.error_code = None
    job.failure_reason = None
    job.outcome_code = None
    job.progress = max(float(job.progress or 0), 0.55)
    db.commit()
    db.refresh(job)

    pages = (
        db.query(DBPage)
        .filter(DBPage.document_id == job.current_source_document_id)
        .order_by(DBPage.page_order)
        .all()
    )
    assets = (
        db.query(DBAsset)
        .filter(DBAsset.document_id == job.current_source_document_id)
        .order_by(DBAsset.asset_order)
        .all()
    )

    text_evidence, dialogue_count = _persist_text_analysis(db, job, revision, pages)
    job.analysis_schema_version = ANALYSIS_PACKAGE_SCHEMA_VERSION
    job.analysis_package_json = build_analysis_package(db, job.id, revision)
    db.commit()
    db.refresh(job)

    adapter = vision_adapters.get_vision_adapter(db)
    vision_ok = adapter.supports_vision()
    (
        visual_status,
        panel_count,
        payloads,
        char_count,
        location_count,
        visual_dialogue_count,
    ) = _persist_visual_analysis(
        db, job, revision, pages, assets, adapter, vision_ok, text_evidence
    )
    dialogue_count += visual_dialogue_count
    _persist_plot(db, job, revision, text_evidence, payloads)

    coverage = {
        "text_pages": sum(1 for page in pages if page.extracted_text),
        "image_assets": len(assets),
        "panels": panel_count,
        "dialogue": dialogue_count,
        "characters": char_count,
        "locations": location_count,
        "visual_modality": visual_status,
    }
    limitations: list[dict] = []
    if visual_status not in {"completed", "not_applicable"}:
        limitations.append(
            {
                "code": "COMIC_VISION_UNAVAILABLE",
                "detail": "Chưa phân tích đầy đủ hình ảnh; kết quả còn thiếu mô tả visual, nhân vật hoặc bối cảnh.",
            }
        )

    job.analysis_revision = revision
    job.analysis_schema_version = ANALYSIS_PACKAGE_SCHEMA_VERSION
    job.coverage_metrics_json = coverage
    job.limitations_json = limitations
    job.result_completeness = (
        "complete" if visual_status in {"completed", "not_applicable"} and pages else "partial"
    )
    job.current_step = "build_review"
    job.run_status = "ready_for_review"
    job.progress = 1.0
    db.flush()
    job.analysis_package_json = build_analysis_package(db, job.id, revision)
    db.flush()
    return job


def _persist_text_analysis(db, job, revision, pages) -> tuple[list[str], int]:
    evidence_ids: list[str] = []
    count = 0
    for page in pages:
        text = _clean(page.extracted_text)
        if not text:
            continue
        evidence_id = page.evidence_id or f"text-{page.page_order}"
        evidence_ids.append(evidence_id)
        db.add(
            DBBubble(
                job_id=job.id,
                analysis_revision=revision,
                reading_order=page.page_order,
                bubble_type="narration",
                raw_text=text,
                normalized_text=text,
                evidence_ids_json=[evidence_id],
                edit_source="observed",
            )
        )
        count += 1
    db.flush()
    return evidence_ids, count


def _persist_visual_analysis_legacy(
    db,
    job,
    revision,
    pages,
    assets,
    adapter,
    vision_ok,
) -> tuple[str, int, list[dict]]:
    image_pages = [page for page in pages if page.page_kind == "image"]
    payloads: list[dict] = []
    if not image_pages:
        return "not_applicable", 0, payloads

    if not vision_ok:
        for page in image_pages:
            db.add(
                DBPanel(
                    job_id=job.id,
                    analysis_revision=revision,
                    page_id=page.id,
                    asset_id=page.asset_id,
                    reading_order=page.page_order,
                    visual_description=None,
                    evidence_ids_json=[page.evidence_id] if page.evidence_id else None,
                    confidence=None,
                    edit_source="observed",
                    needs_review=True,
                )
            )
        db.flush()
        return "unavailable", len(image_pages), payloads

    from ... import config as core_config

    assets_by_id = {asset.id: asset for asset in assets}
    attachments: list[vision_adapters.Attachment] = []
    for index, page in enumerate(image_pages):
        asset = assets_by_id.get(page.asset_id)
        if asset is None:
            continue
        derivatives = asset.derivatives_json or {}
        # The 1600px preview is sufficient for OCR/visual extraction and keeps
        # multi-image Codex requests small enough to finish reliably. Originals
        # remain immutable and available for review/download.
        stored_path = derivatives.get("preview_path") or derivatives.get("analysis_path") or asset.original_path
        path = core_config.resolve_storage_path(stored_path) if stored_path else None
        if path and path.exists():
            attachments.append(
                vision_adapters.Attachment(
                    attachment_index=index,
                    asset_id=asset.id,
                    path=str(path),
                    page_order=page.page_order,
                )
            )

    if not attachments:
        return _persist_missing_attachment_panels(db, job, revision, image_pages)

    panel_count = 0
    visual_status = "completed"
    completed_batches: list[tuple[vision_adapters.AttachmentManifest, dict]] = []
    for batch in vision_adapters.batch_attachments(attachments):
        vision_adapters.validate_attachments(batch)
        result = adapter.analyze_batch(
            batch,
            "Phân tích panel, chữ/OCR, lời thoại, nhân vật, bối cảnh và diễn biến truyện.",
        )
        if not result.completed or not isinstance(result.payload, dict):
            visual_status = "partial"
            continue
        payload = result.payload
        payloads.append(payload)
        completed_batches.append((batch, payload))

    for batch, payload in completed_batches:
        provider_panels = payload.get("panels")
        panel_items = provider_panels if isinstance(provider_panels, list) else []
        if not panel_items:
            panel_items = [
                {
                    "asset_id": attachment.asset_id,
                    "reading_order": attachment.page_order,
                    "evidence_ids": [attachment.asset_id],
                }
                for attachment in batch.attachments
            ]
        by_asset = {attachment.asset_id: attachment for attachment in batch.attachments}
        known_assets = set(by_asset)
        for index, item in enumerate(panel_items):
            if not isinstance(item, dict):
                continue
            asset_id = _clean(item.get("asset_id"))
            if asset_id not in by_asset:
                asset_id = batch.attachments[min(index, len(batch.attachments) - 1)].asset_id
            attachment = by_asset[asset_id]
            description = _clean(item.get("visual_description"))
            db.add(
                DBPanel(
                    job_id=job.id,
                    analysis_revision=revision,
                    asset_id=asset_id,
                    reading_order=_as_int(item.get("reading_order"), attachment.page_order or index),
                    bounding_box_json=(
                        item.get("bounding_box") if isinstance(item.get("bounding_box"), dict) else None
                    ),
                    visual_description=description,
                    evidence_ids_json=_evidence_ids(item, known_assets, asset_id),
                    confidence=_confidence(item.get("confidence")),
                    edit_source="observed",
                    needs_review=not bool(description),
                )
            )
            panel_count += 1

    if panel_count == 0:
        fallback_status, panel_count, _ = _persist_missing_attachment_panels(
            db, job, revision, image_pages
        )
        visual_status = "partial" if fallback_status == "unavailable" else fallback_status
    db.flush()
    return visual_status, panel_count, payloads


def _persist_visual_analysis(
    db,
    job,
    revision,
    pages,
    assets,
    adapter,
    vision_ok,
    text_evidence,
) -> tuple[str, int, list[dict], int, int, int]:
    image_pages = [page for page in pages if page.page_kind == "image"]
    payloads: list[dict] = []
    if not image_pages:
        return "not_applicable", 0, payloads, 0, 0, 0

    if not vision_ok:
        status, panel_count, _ = _persist_missing_attachment_panels(db, job, revision, image_pages)
        job.analysis_package_json = build_analysis_package(db, job.id, revision)
        db.commit()
        db.refresh(job)
        return status, panel_count, payloads, 0, 0, 0

    from ... import config as core_config

    assets_by_id = {asset.id: asset for asset in assets}
    attachments: list[vision_adapters.Attachment] = []
    for index, page in enumerate(image_pages):
        asset = assets_by_id.get(page.asset_id)
        if asset is None:
            continue
        derivatives = asset.derivatives_json or {}
        stored_path = derivatives.get("preview_path") or derivatives.get("analysis_path") or asset.original_path
        path = core_config.resolve_storage_path(stored_path) if stored_path else None
        if path and path.exists():
            attachments.append(
                vision_adapters.Attachment(
                    attachment_index=index,
                    asset_id=asset.id,
                    path=str(path),
                    page_order=page.page_order,
                )
            )

    if not attachments:
        fallback_status, panel_count, _ = _persist_missing_attachment_panels(
            db, job, revision, image_pages
        )
        job.analysis_package_json = build_analysis_package(db, job.id, revision)
        db.commit()
        db.refresh(job)
        return fallback_status, panel_count, payloads, 0, 0, 0

    panel_count = 0
    char_count = 0
    location_count = 0
    visual_dialogue_count = 0
    visual_status = "completed"
    completed_batch_ids: list[str] = []
    failed_batch_ids: list[str] = []
    batches = vision_adapters.batch_attachments(attachments)
    total_batches = len(batches)
    instruction = "Phân tích panel, chữ/OCR, lời thoại, nhân vật, bối cảnh và diễn biến truyện."

    for batch_index, batch in enumerate(batches):
        batch_completed = False
        batch_failed = False
        for result_batch, result in _analyze_batch_with_split(adapter, batch, instruction):
            if not result.completed or not isinstance(result.payload, dict):
                visual_status = "partial"
                batch_failed = True
                failed_batch_ids.append(result_batch.batch_id)
                panel_count += _persist_fallback_panels_for_attachments(
                    db, job, revision, result_batch.attachments
                )
                continue

            payload = result.payload
            payloads.append(payload)
            completed_batch_ids.append(result_batch.batch_id)
            batch_completed = True
            panel_count += _persist_panels_from_payload(db, job, revision, result_batch, payload)
            char_count += _persist_characters(db, job, revision, [payload], vision_ok)
            location_count += _persist_locations(db, job, revision, [payload], vision_ok)
            visual_dialogue_count += _persist_visual_dialogues(db, job, revision, [payload])
            _persist_plot(db, job, revision, text_evidence, payloads)

        if not batch_completed or batch_failed:
            visual_status = "partial"

        _publish_analysis_checkpoint(
            db,
            job,
            revision,
            progress=0.55 + ((batch_index + 1) / max(total_batches, 1)) * 0.35,
            visual_status=visual_status,
            total_batches=total_batches,
            finished_batches=batch_index + 1,
            completed_batch_ids=completed_batch_ids,
            failed_batch_ids=failed_batch_ids,
        )

    if panel_count == 0:
        fallback_status, panel_count, _ = _persist_missing_attachment_panels(
            db, job, revision, image_pages
        )
        visual_status = "partial" if fallback_status == "unavailable" else fallback_status
        _publish_analysis_checkpoint(
            db,
            job,
            revision,
            progress=0.9,
            visual_status=visual_status,
            total_batches=total_batches,
            finished_batches=total_batches,
            completed_batch_ids=completed_batch_ids,
            failed_batch_ids=failed_batch_ids,
        )
    db.flush()
    return visual_status, panel_count, payloads, char_count, location_count, visual_dialogue_count


def _analyze_batch_with_split(adapter, batch, instruction):
    vision_adapters.validate_attachments(batch)
    result = adapter.analyze_batch(batch, instruction)
    if result.completed or len(batch.attachments) <= 1 or not _should_split_failed_batch(result):
        return [(batch, result)]

    midpoint = max(1, len(batch.attachments) // 2)
    chunks = [batch.attachments[:midpoint], batch.attachments[midpoint:]]
    results = []
    for index, chunk in enumerate(chunks):
        if not chunk:
            continue
        child = vision_adapters.AttachmentManifest(
            batch_id=f"{batch.batch_id}.{index + 1}",
            attachments=chunk,
        )
        results.extend(_analyze_batch_with_split(adapter, child, instruction))
    return results


def _should_split_failed_batch(result) -> bool:
    non_splittable = {
        "CODEX_CLI_NOT_FOUND",
        "CODEX_PATH_INVALID",
        "CODEX_PROVIDER_REJECTED",
        "COMIC_VISION_UNAVAILABLE",
    }
    if result.error_code in non_splittable:
        return False
    return result.error_code in {
        None,
        "CODEX_EXEC_TIMEOUT",
        "CODEX_PROVIDER_TEMPORARY_UNAVAILABLE",
        "COMIC_AI_OUTPUT_INVALID",
    } or result.status in {"partial", "invalid_output", "vision_unavailable"}


def _persist_panels_from_payload(db, job, revision, batch, payload) -> int:
    provider_panels = payload.get("panels")
    panel_items = provider_panels if isinstance(provider_panels, list) else []
    if not panel_items:
        panel_items = [
            {
                "asset_id": attachment.asset_id,
                "reading_order": attachment.page_order,
                "evidence_ids": [attachment.asset_id],
            }
            for attachment in batch.attachments
        ]
    by_asset = {attachment.asset_id: attachment for attachment in batch.attachments}
    known_assets = set(by_asset)
    panel_count = 0
    for index, item in enumerate(panel_items):
        if not isinstance(item, dict):
            continue
        asset_id = _clean(item.get("asset_id"))
        if asset_id not in by_asset:
            asset_id = batch.attachments[min(index, len(batch.attachments) - 1)].asset_id
        attachment = by_asset[asset_id]
        description = _clean(item.get("visual_description"))
        db.add(
            DBPanel(
                job_id=job.id,
                analysis_revision=revision,
                asset_id=asset_id,
                reading_order=_as_int(item.get("reading_order"), attachment.page_order or index),
                bounding_box_json=(
                    item.get("bounding_box") if isinstance(item.get("bounding_box"), dict) else None
                ),
                visual_description=description,
                evidence_ids_json=_evidence_ids(item, known_assets, asset_id),
                confidence=_confidence(item.get("confidence")),
                edit_source="observed",
                needs_review=not bool(description),
            )
        )
        panel_count += 1
    db.flush()
    return panel_count


def _persist_fallback_panels_for_attachments(db, job, revision, attachments) -> int:
    asset_ids = [attachment.asset_id for attachment in attachments]
    existing_asset_ids = {
        value
        for (value,) in (
            db.query(DBPanel.asset_id)
            .filter(DBPanel.job_id == job.id, DBPanel.analysis_revision == revision)
            .filter(DBPanel.asset_id.in_(asset_ids))
            .all()
        )
        if value
    }
    count = 0
    for attachment in attachments:
        if attachment.asset_id in existing_asset_ids:
            continue
        db.add(
            DBPanel(
                job_id=job.id,
                analysis_revision=revision,
                asset_id=attachment.asset_id,
                reading_order=attachment.page_order or attachment.attachment_index,
                evidence_ids_json=[attachment.asset_id],
                edit_source="observed",
                needs_review=True,
            )
        )
        count += 1
    db.flush()
    return count


def _publish_analysis_checkpoint(
    db,
    job,
    revision,
    *,
    progress: float,
    visual_status: str,
    total_batches: int,
    finished_batches: int,
    completed_batch_ids: list[str],
    failed_batch_ids: list[str],
) -> None:
    state = dict(job.step_state_json or {})
    state["visual_analysis"] = {
        "analysis_revision": revision,
        "status": visual_status,
        "total_batches": total_batches,
        "finished_batches": finished_batches,
        "completed_batch_ids": list(completed_batch_ids),
        "failed_batch_ids": list(failed_batch_ids),
    }
    job.step_state_json = state
    job.current_step = "panel_analysis"
    job.progress = max(float(job.progress or 0), min(progress, 0.95))
    job.analysis_schema_version = ANALYSIS_PACKAGE_SCHEMA_VERSION
    db.flush()
    job.analysis_package_json = build_analysis_package(db, job.id, revision)
    db.flush()
    db.commit()
    db.refresh(job)


def _persist_missing_attachment_panels(db, job, revision, image_pages):
    for page in image_pages:
        db.add(
            DBPanel(
                job_id=job.id,
                analysis_revision=revision,
                page_id=page.id,
                asset_id=page.asset_id,
                reading_order=page.page_order,
                evidence_ids_json=[page.evidence_id] if page.evidence_id else None,
                edit_source="observed",
                needs_review=True,
            )
        )
    db.flush()
    return "unavailable", len(image_pages), []


def _persist_characters(db, job, revision, payloads, vision_ok) -> int:
    if not vision_ok:
        return 0
    seen: set[str] = {
        (name or "").casefold()
        for (name,) in (
            db.query(DBCharacter.display_name)
            .filter(DBCharacter.job_id == job.id, DBCharacter.analysis_revision == revision)
            .all()
        )
        if name
    }
    count = 0
    for payload in payloads:
        values = payload.get("characters") if isinstance(payload.get("characters"), list) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            name = _clean(item.get("name") or item.get("display_name"))
            key = (name or "").casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            db.add(
                DBCharacter(
                    job_id=job.id,
                    analysis_revision=revision,
                    display_name=name,
                    aliases_json=_string_list(item.get("aliases")),
                    role=_clean(item.get("role")),
                    face_description=_clean(item.get("face_description")),
                    hair_description=_clean(item.get("hair_description")),
                    body_description=_clean(item.get("body_description")),
                    outfit_description=_clean(item.get("outfit_description")),
                    personality=_clean(item.get("personality")),
                    speech_style=_clean(item.get("speech_style")),
                    evidence_ids_json=_string_list(item.get("evidence_ids")),
                    reference_asset_ids_json=_string_list(item.get("reference_asset_ids")),
                    confidence=_confidence(item.get("confidence")),
                    edit_source="inferred",
                )
            )
            count += 1
    db.flush()
    return count


def _persist_locations(db, job, revision, payloads, vision_ok) -> int:
    if not vision_ok:
        return 0
    seen: set[str] = {
        (name or "").casefold()
        for (name,) in (
            db.query(DBLocation.name)
            .filter(DBLocation.job_id == job.id, DBLocation.analysis_revision == revision)
            .all()
        )
        if name
    }
    count = 0
    for payload in payloads:
        values = payload.get("locations") if isinstance(payload.get("locations"), list) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            name = _clean(item.get("name"))
            key = (name or "").casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            db.add(
                DBLocation(
                    job_id=job.id,
                    analysis_revision=revision,
                    name=name,
                    description=_clean(item.get("description")),
                    world_rules=_clean(item.get("world_rules")),
                    evidence_ids_json=_string_list(item.get("evidence_ids")),
                    confidence=_confidence(item.get("confidence")),
                    edit_source="inferred",
                )
            )
            count += 1
    db.flush()
    return count


def _persist_visual_dialogues(db, job, revision, payloads) -> int:
    characters = db.query(DBCharacter).filter_by(job_id=job.id, analysis_revision=revision).all()
    character_ids = {(item.display_name or "").casefold(): item.id for item in characters}
    count = 0
    for payload in payloads:
        values = payload.get("dialogues") if isinstance(payload.get("dialogues"), list) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            text = _clean(item.get("text") or item.get("normalized_text"))
            if not text:
                continue
            speaker = _clean(item.get("speaker"))
            db.add(
                DBBubble(
                    job_id=job.id,
                    analysis_revision=revision,
                    reading_order=_as_int(item.get("reading_order"), count),
                    bubble_type=_clean(item.get("bubble_type")) or "unknown",
                    bounding_box_json=(
                        item.get("bounding_box") if isinstance(item.get("bounding_box"), dict) else None
                    ),
                    raw_text=_clean(item.get("raw_text")) or text,
                    normalized_text=text,
                    language=_clean(item.get("language")),
                    ocr_confidence=_confidence(item.get("confidence")),
                    speaker_character_id=character_ids.get((speaker or "").casefold()),
                    speaker_confidence=_confidence(item.get("speaker_confidence")),
                    evidence_ids_json=_string_list(item.get("evidence_ids")),
                    edit_source="observed",
                )
            )
            count += 1
    db.flush()
    return count


def _persist_plot_legacy(db, job, revision, text_evidence, payloads) -> None:
    plots = [payload.get("plot") for payload in payloads if isinstance(payload.get("plot"), dict)]
    combined = next((plot for plot in plots if plot), {})
    synopsis = _clean(combined.get("synopsis"))
    end_state = combined.get("end_state") if isinstance(combined.get("end_state"), dict) else None
    if end_state is None and _clean(combined.get("end_state_summary")):
        end_state = {"summary": _clean(combined.get("end_state_summary"))}
    if not synopsis and text_evidence:
        synopsis = "Tóm tắt sơ bộ dựa trên văn bản trích được (cần review)."
    db.add(
        DBPlot(
            job_id=job.id,
            analysis_revision=revision,
            synopsis=synopsis,
            plot_beats_json=combined.get("plot_beats") or [],
            relationships_json=combined.get("relationships") or [],
            end_state_json=end_state,
            canon_candidates_json=combined.get("canon_candidates") or [],
            development_options_json=combined.get("development_options") or [],
            uncertainties_json=(
                combined.get("uncertainties")
                or ([{"code": "NO_VISION", "detail": "Chưa phân tích hình ảnh"}] if not payloads else [])
            ),
            limitations_json=combined.get("limitations") or [],
        )
    )
    db.flush()


def _persist_plot(db, job, revision, text_evidence, payloads) -> None:
    plots = [payload.get("plot") for payload in payloads if isinstance(payload.get("plot"), dict)]
    combined = _combine_plots(plots)
    synopsis = _clean(combined.get("synopsis"))
    end_state = combined.get("end_state") if isinstance(combined.get("end_state"), dict) else None
    if not synopsis and text_evidence:
        synopsis = "Tóm tắt sơ bộ dựa trên văn bản trích được (cần review)."
    values = {
        "synopsis": synopsis,
        "plot_beats_json": combined.get("plot_beats") or [],
        "relationships_json": combined.get("relationships") or [],
        "end_state_json": end_state,
        "canon_candidates_json": combined.get("canon_candidates") or [],
        "development_options_json": combined.get("development_options") or [],
        "uncertainties_json": (
            combined.get("uncertainties")
            or ([{"code": "NO_VISION", "detail": "Chưa phân tích hình ảnh"}] if not payloads else [])
        ),
        "limitations_json": combined.get("limitations") or [],
    }
    plot = db.query(DBPlot).filter_by(job_id=job.id, analysis_revision=revision).first()
    if plot is None:
        db.add(DBPlot(job_id=job.id, analysis_revision=revision, **values))
    else:
        for key, value in values.items():
            setattr(plot, key, value)
    db.flush()


def _combine_plots(plots: list[dict]) -> dict:
    if not plots:
        return {}
    synopses = _unique_strings(plot.get("synopsis") for plot in plots)
    end_state = None
    for plot in plots:
        candidate = plot.get("end_state") if isinstance(plot.get("end_state"), dict) else None
        if candidate is None and _clean(plot.get("end_state_summary")):
            candidate = {"summary": _clean(plot.get("end_state_summary"))}
        if candidate:
            end_state = candidate
    return {
        "synopsis": "\n\n".join(synopses),
        "plot_beats": _unique_strings_from_lists(plot.get("plot_beats") for plot in plots),
        "relationships": _unique_json_items(plot.get("relationships") for plot in plots),
        "end_state": end_state,
        "canon_candidates": _unique_strings_from_lists(plot.get("canon_candidates") for plot in plots),
        "development_options": _unique_strings_from_lists(plot.get("development_options") for plot in plots),
        "uncertainties": _unique_json_items(plot.get("uncertainties") for plot in plots),
        "limitations": _unique_json_items(plot.get("limitations") for plot in plots),
    }


def _unique_strings(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_strings_from_lists(values) -> list[str]:
    flat = []
    for value in values:
        if isinstance(value, list):
            flat.extend(value)
    return _unique_strings(flat)


def _unique_json_items(values) -> list:
    seen: set[str] = set()
    result: list = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            key = str(item)
            if isinstance(item, dict):
                import json

                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def build_analysis_package(db: Session, job_id: str, revision: int) -> dict:
    panels = (
        db.query(DBPanel)
        .filter_by(job_id=job_id, analysis_revision=revision)
        .order_by(DBPanel.reading_order)
        .all()
    )
    bubbles = (
        db.query(DBBubble)
        .filter_by(job_id=job_id, analysis_revision=revision)
        .order_by(DBBubble.reading_order)
        .all()
    )
    characters = db.query(DBCharacter).filter_by(job_id=job_id, analysis_revision=revision).all()
    locations = db.query(DBLocation).filter_by(job_id=job_id, analysis_revision=revision).all()
    plot = db.query(DBPlot).filter_by(job_id=job_id, analysis_revision=revision).first()
    return {
        "analysis_revision": revision,
        "panels": [
            {
                "id": item.id,
                "asset_id": item.asset_id,
                "reading_order": item.reading_order,
                "visual_description": item.visual_description,
                "confidence": item.confidence,
                "evidence_ids": item.evidence_ids_json,
                "needs_review": item.needs_review,
            }
            for item in panels
        ],
        "dialogues": [
            {
                "id": item.id,
                "reading_order": item.reading_order,
                "bubble_type": item.bubble_type,
                "text": item.approved_text or item.normalized_text or item.raw_text,
                "speaker_character_id": item.speaker_character_id,
                "confidence": item.ocr_confidence,
                "evidence_ids": item.evidence_ids_json,
            }
            for item in bubbles
        ],
        "characters": [
            {
                "id": item.id,
                "name": item.display_name,
                "role": item.role,
                "face_description": item.face_description,
                "hair_description": item.hair_description,
                "body_description": item.body_description,
                "outfit_description": item.outfit_description,
                "personality": item.personality,
                "speech_style": item.speech_style,
                "confidence": item.confidence,
                "evidence_ids": item.evidence_ids_json,
            }
            for item in characters
        ],
        "locations": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "world_rules": item.world_rules,
                "confidence": item.confidence,
                "evidence_ids": item.evidence_ids_json,
            }
            for item in locations
        ],
        "plot": {
            "synopsis": plot.synopsis if plot else None,
            "plot_beats": plot.plot_beats_json if plot else [],
            "relationships": plot.relationships_json if plot else [],
            "end_state": plot.end_state_json if plot else None,
            "canon_candidates": plot.canon_candidates_json if plot else [],
            "uncertainties": plot.uncertainties_json if plot else [],
            "limitations": plot.limitations_json if plot else [],
        },
    }


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _confidence(value) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [str(item) for item in value if str(item).strip()]
    return items or None


def _evidence_ids(item: dict, known: set[str], fallback: str) -> list[str]:
    values = [value for value in (_string_list(item.get("evidence_ids")) or []) if value in known]
    return values or [fallback]


__all__ = ["analyze_revision", "build_analysis_package"]
