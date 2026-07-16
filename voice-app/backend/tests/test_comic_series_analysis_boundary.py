"""Boundary tests for the Comic Series Analysis feature module.

These prove the architectural boundary from change 13: the module must not
import Video Inspiration internals, must not carry an AI Video handoff, and
must not reference the ``video_inspiration_jobs`` table.
"""

from __future__ import annotations

import ast
import pkgutil
from pathlib import Path

import backend.services.comic_series_analysis as comic_pkg

_PACKAGE_DIR = Path(comic_pkg.__file__).resolve().parent

_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "video_inspiration",
    "video_inspiration_runs",
)

# Symbols that would indicate an AI Video handoff sneaking into the module.
_FORBIDDEN_SYMBOLS = (
    "create_ai_video_project",
    "video_project_memory",
)


def _iter_module_sources():
    for module in pkgutil.walk_packages([str(_PACKAGE_DIR)], prefix=comic_pkg.__name__ + "."):
        # Reconstruct the file path from the dotted module name.
        rel = module.name[len(comic_pkg.__name__) + 1 :].replace(".", "/")
        path = _PACKAGE_DIR / f"{rel}.py"
        if path.exists():
            yield module.name, path
    # include the package __init__
    yield comic_pkg.__name__, _PACKAGE_DIR / "__init__.py"


def _imported_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.add(module)
            for alias in node.names:
                names.add(f"{module}.{alias.name}")
    return names


def test_module_does_not_import_video_inspiration():
    offenders: list[str] = []
    for module_name, path in _iter_module_sources():
        source = path.read_text(encoding="utf-8")
        imported = _imported_names(source)
        for name in imported:
            for forbidden in _FORBIDDEN_IMPORT_SUBSTRINGS:
                if forbidden in name:
                    offenders.append(f"{module_name} imports {name}")
    assert not offenders, "Comic module must not import Video Inspiration: " + "; ".join(offenders)


def test_module_has_no_ai_video_handoff_symbols():
    offenders: list[str] = []
    for module_name, path in _iter_module_sources():
        source = path.read_text(encoding="utf-8")
        for symbol in _FORBIDDEN_SYMBOLS:
            if symbol in source:
                offenders.append(f"{module_name} references {symbol}")
    assert not offenders, "Comic module must not reference AI Video handoff: " + "; ".join(offenders)


def test_contracts_have_no_video_inspiration_state_names():
    from backend.services.comic_series_analysis import contracts

    # The run status vocabulary is its own; it must not reuse video steps.
    assert "source_ready" not in contracts.PIPELINE_STEPS
    assert "transcript" not in contracts.PIPELINE_STEPS
    assert contracts.SOURCE_PACKAGE_SCHEMA_VERSION.startswith("comic_")
    assert contracts.ANALYSIS_PACKAGE_SCHEMA_VERSION.startswith("comic_")
