from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import evaluate_tada_vietnamese
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.backends.hume_backend import resolve_tada_aligner, tada_prompt_cache_key
from backend.database.models import (
    Base,
    ProfileSample as DBProfileSample,
    VoiceProfile as DBVoiceProfile,
)
from backend.routes import generations as generation_routes
from backend.services import profiles, qwen_vietnamese, tada_vietnamese


def test_tada_vietnamese_gate_requires_accepted_review(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.delenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, raising=False)

    with pytest.raises(ValueError, match="experimental"):
        tada_vietnamese.ensure_tada_vietnamese_allowed(
            engine="tada",
            model_size="3B",
            language="vi",
        )

    tada_vietnamese.write_review_state(status="accepted", root=tmp_path)

    tada_vietnamese.ensure_tada_vietnamese_allowed(
        engine="tada",
        model_size="3B",
        language="vi",
    )

def test_tada_vietnamese_local_bypass_accepts_3b_before_review(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, "1")

    tada_vietnamese.ensure_tada_vietnamese_allowed(
        engine="tada",
        model_size="3B",
        language="vi",
    )

def test_tada_vietnamese_profile_bypass_accepts_vi_profile_without_review(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.delenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, raising=False)

    model_size = tada_vietnamese.normalize_tada_model_size(
        engine="tada",
        language="vi",
        model_size="1.7B",
    )
    assert model_size == "3B"
    assert tada_vietnamese.should_allow_profile_bypass(
        profile=SimpleNamespace(language="vi"),
        engine="tada",
        model_size=model_size,
        language="vi",
    )

    tada_vietnamese.ensure_tada_vietnamese_allowed(
        engine="tada",
        model_size=model_size,
        language="vi",
        allow_evaluation=True,
    )

def test_tada_vietnamese_profile_bypass_is_scoped_to_vietnamese_profiles():
    assert not tada_vietnamese.should_allow_profile_bypass(
        profile=SimpleNamespace(language="en"),
        engine="tada",
        model_size="3B",
        language="vi",
    )
    assert not tada_vietnamese.should_allow_profile_bypass(
        profile=SimpleNamespace(language="vi"),
        engine="tada",
        model_size="1B",
        language="vi",
    )

def test_generation_route_normalizes_stale_vietnamese_model_size_to_qwen_1_7b():
    request = models.GenerationRequest(
        profile_id="profile-1",
        text="Xin chào.",
        language="vi",
        engine="qwen",
        model_size="3B",
    )

    assert generation_routes._resolve_generation_model_size(request, engine="qwen") == "1.7B"

def test_qwen_vietnamese_helper_forces_legacy_tada_profile_to_qwen():
    profile = SimpleNamespace(language="vi")

    assert qwen_vietnamese.resolve_engine(
        profile=profile,
        engine="tada",
        language="vi",
    ) == "qwen"
    assert qwen_vietnamese.normalize_model_size(
        engine="qwen",
        language="vi",
        model_size="3B",
    ) == "1.7B"

@pytest.mark.asyncio
async def test_generate_speech_uses_qwen_for_legacy_tada_vietnamese_profile(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.delenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, raising=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    profile = DBVoiceProfile(
        id="profile-1",
        name="Thoai 1 Vietnamese",
        language="vi",
        voice_type="cloned",
        default_engine="tada",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(profile)
    db.commit()

    enqueued: list[str] = []

    def fake_enqueue(generation_id, coro):
        enqueued.append(generation_id)
        close = getattr(coro, "close", None)
        if close:
            close()

    monkeypatch.setattr(generation_routes, "enqueue_generation", fake_enqueue)

    response = await generation_routes.generate_speech(
        models.GenerationRequest(
            profile_id=profile.id,
            text="Xin chào thị trường Việt Nam.",
            language="vi",
            engine="tada",
            model_size="3B",
        ),
        db,
    )

    assert response.status == "generating"
    assert response.engine == "qwen"
    assert response.model_size == "1.7B"
    assert enqueued == [response.id]
    db.close()

@pytest.mark.asyncio
async def test_generate_speech_normalizes_qwen_vietnamese_0_6b_to_1_7b(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    profile = DBVoiceProfile(
        id="profile-1",
        name="Thoai 1 Vietnamese",
        language="vi",
        voice_type="cloned",
        default_engine="qwen",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(profile)
    db.commit()

    enqueued: list[str] = []

    def fake_enqueue(generation_id, coro):
        enqueued.append(generation_id)
        close = getattr(coro, "close", None)
        if close:
            close()

    monkeypatch.setattr(generation_routes, "enqueue_generation", fake_enqueue)

    response = await generation_routes.generate_speech(
        models.GenerationRequest(
            profile_id=profile.id,
            text="Xin chào thị trường Việt Nam.",
            language="vi",
            engine="qwen",
            model_size="0.6B",
        ),
        db,
    )

    assert response.status == "generating"
    assert response.engine == "qwen"
    assert response.model_size == "1.7B"
    assert enqueued == [response.id]
    db.close()

def test_tada_vietnamese_gate_rejects_tada_1b():
    with pytest.raises(ValueError, match="TADA 1B"):
        tada_vietnamese.ensure_tada_vietnamese_allowed(
            engine="tada",
            model_size="1B",
            language="vi",
            allow_evaluation=True,
        )

def test_tada_vietnamese_local_bypass_rejects_1b(monkeypatch):
    monkeypatch.setenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, "1")

    with pytest.raises(ValueError, match="TADA 1B"):
        tada_vietnamese.ensure_tada_vietnamese_allowed(
            engine="tada",
            model_size="1B",
            language="vi",
        )

def test_tada_vietnamese_gate_does_not_fallback_to_english(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.delenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, raising=False)

    with pytest.raises(ValueError, match="experimental"):
        tada_vietnamese.ensure_tada_vietnamese_allowed(
            engine="tada",
            model_size="3B",
            language="vi",
        )

    assert not tada_vietnamese.is_review_accepted(root=tmp_path)


@pytest.mark.asyncio
async def test_tada_vietnamese_status_reports_local_bypass(monkeypatch, tmp_path):
    monkeypatch.setenv(tada_vietnamese.EVAL_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(tada_vietnamese.LOCAL_TEST_BYPASS_ENV, "1")

    from backend.routes.models import get_tada_vietnamese_status

    status = await get_tada_vietnamese_status()

    assert status.accepted is False
    assert status.local_bypass_enabled is True
    assert status.language == "vi"
    assert status.model_size == "3B"


def test_tada_vietnamese_review_state_records_rejection(tmp_path):
    tada_vietnamese.write_review_state(
        status="rejected",
        notes="tone accuracy failed",
        reviewer="qa",
        run_id="run-1",
        root=tmp_path,
    )

    state = tada_vietnamese.load_review_state(tmp_path)
    assert state is not None
    assert state["status"] == "rejected"
    assert state["notes"] == "tone accuracy failed"
    assert state["reviewer"] == "qa"
    assert state["run_id"] == "run-1"

def test_evaluation_workflow_requires_profile_samples_and_transcripts(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    with pytest.raises(RuntimeError, match="Voice profile not found"):
        evaluate_tada_vietnamese._resolve_profile("missing", db)

    profile = DBVoiceProfile(
        id="profile-1",
        name="Vietnamese profile",
        language="vi",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(profile)
    db.commit()

    with pytest.raises(RuntimeError, match="has no reference samples"):
        evaluate_tada_vietnamese._resolve_profile(profile.id, db)

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake-wav")
    sample = DBProfileSample(
        id="sample-1",
        profile_id=profile.id,
        audio_path=str(audio),
        reference_text="",
    )
    db.add(sample)
    db.commit()

    with pytest.raises(RuntimeError, match="requires accurate reference transcripts"):
        evaluate_tada_vietnamese._resolve_profile(profile.id, db)

    db.close()

def test_tada_aligner_resolution_and_cache_key_include_strategy(tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake-wav")

    assert resolve_tada_aligner("vi").strategy == "default-fallback-vi"
    assert resolve_tada_aligner("zh").strategy == "aligner-ch"
    assert resolve_tada_aligner("ja").strategy == "aligner-ja"

    vi_key = tada_prompt_cache_key(str(audio), "xin chào", "vi")
    en_key = tada_prompt_cache_key(str(audio), "xin chào", "en")
    assert vi_key != en_key
    assert "default-fallback-vi" in vi_key

@pytest.mark.asyncio
async def test_create_voice_prompt_for_profile_passes_language(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_local()

    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"fake-wav")

    profile = DBVoiceProfile(
        id="profile-1",
        name="Vietnamese profile",
        language="vi",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sample = DBProfileSample(
        id="sample-1",
        profile_id=profile.id,
        audio_path=str(audio),
        reference_text="Xin chào.",
    )
    db.add(profile)
    db.add(sample)
    db.commit()

    class FakeBackend:
        def __init__(self):
            self.language = None

        async def create_voice_prompt(self, audio_path, reference_text, use_cache=True, language=None):
            self.language = language
            return {"ok": True}, False

    fake_backend = FakeBackend()

    import backend.backends as backends

    monkeypatch.setattr(backends, "get_tts_backend_for_engine", lambda engine_name: fake_backend)
    monkeypatch.setattr(profiles.config, "resolve_storage_path", lambda path: Path(path))

    prompt = await profiles.create_voice_prompt_for_profile(
        profile.id,
        db,
        engine="chatterbox",
        language="vi",
    )

    assert prompt == {"ok": True}
    assert fake_backend.language == "vi"
    db.close()
