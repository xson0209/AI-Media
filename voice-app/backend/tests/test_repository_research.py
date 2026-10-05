from __future__ import annotations

import base64
import hashlib

import pytest
from PIL import Image

from backend import config
from backend.services import research_repository, research_screenshots, video_source_visuals


def _blob(text: str) -> tuple[str, dict]:
    raw = text.encode()
    sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    return sha, {"type": "file", "encoding": "base64", "size": len(raw), "sha": sha, "content": base64.b64encode(raw).decode()}


def test_collect_repository_pins_every_document_to_resolved_commit():
    commit_sha = "a" * 40
    tree_sha = "b" * 40
    readme_sha, readme = _blob("# Demo\n\nRun python app.py\n")
    app_sha, app = _blob("print('hello')\n")
    responses = {
        "https://api.github.com/repos/acme/demo": {"default_branch": "main", "description": "demo"},
        "https://api.github.com/repos/acme/demo/commits/main": {"sha": commit_sha, "commit": {"tree": {"sha": tree_sha}}},
        f"https://api.github.com/repos/acme/demo/git/trees/{tree_sha}?recursive=1": {"tree": [
            {"path": "README.md", "type": "blob", "size": len(readme["content"]), "sha": readme_sha},
            {"path": "app.py", "type": "blob", "size": len(app["content"]), "sha": app_sha},
        ]},
        f"https://api.github.com/repos/acme/demo/contents/README.md?ref={commit_sha}": readme,
        f"https://api.github.com/repos/acme/demo/contents/app.py?ref={commit_sha}": app,
    }
    result = research_repository.collect_repository("https://github.com/acme/demo", get_json=responses.__getitem__)
    assert result["repository"]["commit_sha"] == commit_sha
    assert {document["commit_sha"] for document in result["documents"]} == {commit_sha}
    assert all(f"/{commit_sha}/" in evidence["url"] for evidence in result["evidence_refs"])
    assert result["coverage"]["executed"] is False


def test_repository_rejects_invalid_url_and_untrusted_blob():
    with pytest.raises(research_repository.RepositoryResearchError):
        research_repository.parse_repository_url("https://github.com:bad-port/acme/demo")
    with pytest.raises(research_repository.RepositoryResearchError):
        research_repository.parse_repository_url("https://github.com/acme/demo/issues/1")

    commit_sha = "a" * 40
    tree_sha = "b" * 40
    responses = {
        "https://api.github.com/repos/acme/demo": {"default_branch": "main"},
        "https://api.github.com/repos/acme/demo/commits/main": {"sha": commit_sha, "commit": {"tree": {"sha": tree_sha}}},
        f"https://api.github.com/repos/acme/demo/git/trees/{tree_sha}?recursive=1": {"tree": [{"path": "README.md", "type": "blob", "size": 1, "sha": "c" * 40}]},
        f"https://api.github.com/repos/acme/demo/contents/README.md?ref={commit_sha}": {"type": "file", "encoding": "base64", "size": 1, "sha": "c" * 40, "content": base64.b64encode(b"x").decode()},
    }
    with pytest.raises(research_repository.RepositoryResearchError):
        research_repository.collect_repository("https://github.com/acme/demo", get_json=responses.__getitem__)


def test_ground_options_rejects_unreferenced_fact():
    study = {"facts": [{"id": "fact-1", "statement": "A", "verification": "documented", "evidence": [{"id": "e-1", "excerpt": "A"}]}]}
    with pytest.raises(research_repository.RepositoryResearchError):
        research_repository.ground_options({"options": [{"title": "x", "fact_ids": ["fact-9"]}]}, study)
    grounded = research_repository.ground_options({"options": [{"title": "x", "fact_ids": ["fact-1"]}]}, study)
    assert grounded["options"][0]["evidence_refs"][0]["id"] == "e-1"


def test_screenshot_keeps_original_when_vision_returns_invalid_region(tmp_path):
    config.set_data_dir(tmp_path)
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (100, 80), "white").save(image_path)

    result = research_screenshots.collect_screenshot(
        "source-1",
        image_path,
        None,
        read_screen=lambda _path, _db: {"summary": "screen", "repository_candidate": "", "regions": [{"label": "bad", "text": "x", "box": [2, 2, 1, 1], "confidence": 1}], "limitations": []},
    )
    assert result["coverage"]["original_saved"] is True
    assert result["visual_assets"][0]["sha256"] == hashlib.sha256(image_path.read_bytes()).hexdigest()
    assert result["evidence_refs"] == []


def test_source_visual_clip_command_uses_original_region_without_text_redraw(tmp_path):
    image = tmp_path / "screen.png"
    Image.new("RGB", (1000, 800), "white").save(image)
    asset = {"id": "screen-1", "width": 1000, "height": 800, "regions": [{"id": "region-1", "box": [0.1, 0.2, 0.4, 0.3]}]}
    command = video_source_visuals.build_clip_command("ffmpeg", image, tmp_path / "out.mp4", asset, {"region_id": "region-1", "motion": "zoom", "highlight": True}, duration=4, resolution=(720, 1280))
    joined = " ".join(command)
    assert "drawbox" in joined
    assert "zoompan" in joined
    assert "-loop 1" in joined
    assert "redraw" not in joined.lower()
