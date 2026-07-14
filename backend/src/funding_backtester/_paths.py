"""DuckDB path resolution — finds the repo root to build canonical paths.

All paths in this module are derived at import time by walking up from
this file's location until a directory containing the ``.git`` folder
and ``backend/pyproject.toml`` is found. This ensures the canonical
``<repo_root>/data/ticks.duckdb`` always resolves to the same file
regardless of the working directory.
"""

from __future__ import annotations

from pathlib import Path


def _find_repo_root() -> Path:
    """Walk up from this file's directory until the repo root is found.

    The repo root is identified by the presence of both a ``.git`` directory
    and a backend project file. When the code is running from a packaged
    Docker image without the Git metadata, it falls back to the nearest
    directory containing ``pyproject.toml``.

    Raises:
        FileNotFoundError: if the repo root cannot be determined.

    Returns:
        Absolute :class:`Path` to the repository root directory.
    """
    current = Path(__file__).resolve().parent
    fallback_root: Path | None = None
    for parent in [current] + list(current.parents):
        if (parent / ".git").is_dir() and (
            (parent / "backend" / "pyproject.toml").exists() or (parent / "pyproject.toml").exists()
        ):
            return parent
        if fallback_root is None and (parent / "pyproject.toml").exists():
            fallback_root = parent
    if fallback_root is not None:
        return fallback_root
    raise FileNotFoundError("Could not find repo root (looking for .git/ + backend/pyproject.toml)")


def duckdb_path() -> Path:
    """Return the canonical path to the project's DuckDB database.

    The canonical location is ``<repo_root>/data/ticks.duckdb``.
    """
    return _find_repo_root() / "data" / "ticks.duckdb"
