#!/usr/bin/env python3
"""Generate and review the experimental TADA 3B Vietnamese corpus."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import config
from backend.backends import get_tts_backend_for_engine
from backend.backends.hume_backend import resolve_tada_aligner
from backend.database import ProfileSample as DBProfileSample
from backend.database import session as db_session
from backend.services import generation, profiles, tada_vietnamese

def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

def _safe_name(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in safe.split("-") if part) or "profile"

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Voice profile id or name with Vietnamese reference audio")
    parser.add_argument("--data-dir", default="data", help="Voicebox data directory containing voicebox.db")
    parser.add_argument("--output-dir", default=None, help="Evaluation artifact directory")
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--limit", type=int, default=None, help="Generate only the first N corpus items")
    parser.add_argument("--require-cached", action="store_true", help="Fail if tada-3b-ml is not already cached")
    parser.add_argument("--set-review", choices=["accepted", "rejected", "pending"], help="Only update review-state.json")
    parser.add_argument("--notes", default="", help="Review notes saved with --set-review")
    parser.add_argument("--reviewer", default="", help="Reviewer name saved with --set-review")
    parser.add_argument("--run-id", default=None, help="Run id associated with --set-review")
    return parser.parse_args()

def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)
        handle.write("\n")

def _init_db(data_dir: str):
    config.set_data_dir(data_dir)
    db_session.init_db()
    return db_session.SessionLocal()

def _resolve_profile(profile_ref: str, db):
    row = profiles.get_profile_orm_by_name_or_id(profile_ref, db)
    if row is None:
        raise RuntimeError(f"Voice profile not found: {profile_ref}")

    samples = db.query(DBProfileSample).filter_by(profile_id=row.id).all()
    if not samples:
        raise RuntimeError(f"Profile '{row.name}' has no reference samples")
    missing_transcript = [sample.id for sample in samples if not (sample.reference_text or "").strip()]
    if missing_transcript:
        raise RuntimeError(
            "Vietnamese TADA evaluation requires accurate reference transcripts; "
            f"missing transcript for samples: {', '.join(missing_transcript)}"
        )
    return row, samples

async def _run_generation(args: argparse.Namespace) -> tuple[Path, str]:
    db = _init_db(args.data_dir)
    try:
        profile, samples = _resolve_profile(args.profile, db)
    finally:
        db.close()

    tada_backend = get_tts_backend_for_engine("tada")
    if args.require_cached and not tada_backend._is_model_cached("3B"):
        raise RuntimeError("tada-3b-ml is not cached. Download it first or omit --require-cached.")

    selection = resolve_tada_aligner("vi")
    output_root = tada_vietnamese.get_evaluation_root(args.output_dir)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / f"run-{run_id}-{_safe_name(profile.name)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    corpus = tada_vietnamese.TADA_VIETNAMESE_CORPUS
    if args.limit is not None:
        corpus = corpus[: max(args.limit, 0)]

    samples_meta = []
    for index, item in enumerate(corpus, start=1):
        filename = f"{index:02d}_{item['id']}_tada-3b_vi_{selection.strategy}.wav"
        output_path = run_dir / filename
        print(f"[{index}/{len(corpus)}] {item['id']} -> {output_path}", flush=True)
        wav_bytes = await generation.generate_audio_sync(
            profile_id=profile.id,
            text=item["text"],
            language="vi",
            engine="tada",
            model_size="3B",
            seed=args.seed,
            normalize=True,
            allow_experimental_tada_vietnamese=True,
        )
        output_path.write_bytes(wav_bytes)
        samples_meta.append(
            {
                "id": item["id"],
                "category": item["category"],
                "text": item["text"],
                "audio_file": output_path.name,
                "review": {entry["field"]: None for entry in tada_vietnamese.REVIEW_RUBRIC},
                "notes": "",
            }
        )

    metadata = {
        "run_id": run_id,
        "status": "pending",
        "engine": "tada",
        "model_size": "3B",
        "model_name": "tada-3b-ml",
        "language": "vi",
        "aligner_strategy": selection.strategy,
        "corpus_version": tada_vietnamese.CORPUS_VERSION,
        "seed": args.seed,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "language": profile.language,
            "sample_count": len(samples),
        },
        "rubric": tada_vietnamese.REVIEW_RUBRIC,
        "samples": samples_meta,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(run_dir / "metadata.json", metadata)
    tada_vietnamese.write_review_state(status="pending", run_id=run_id, root=output_root)
    return run_dir, run_id

async def _main() -> int:
    args = _parse_args()
    output_root = tada_vietnamese.get_evaluation_root(args.output_dir)

    if args.set_review:
        path = tada_vietnamese.write_review_state(
            status=args.set_review,
            notes=args.notes,
            reviewer=args.reviewer,
            run_id=args.run_id,
            root=output_root,
        )
        print(f"Updated review state: {path}")
        return 0

    if not args.profile:
        raise RuntimeError("--profile is required unless --set-review is used")

    run_dir, run_id = await _run_generation(args)
    print(f"Evaluation run complete: {run_dir}")
    print("Listen to the WAV files, edit metadata.json if useful, then mark the review:")
    print(f"  {Path(__file__).name} --set-review accepted --run-id {run_id}")
    print(f"  {Path(__file__).name} --set-review rejected --notes 'reason' --run-id {run_id}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
