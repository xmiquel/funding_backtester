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
    and a ``backend/pyproject.toml`` file. This avoids confusion when
    ``pyproject.toml`` lives in a subdirectory (e.g. ``backend/``) rather
    than at the root.

    Raises:
        FileNotFoundError: if the repo root cannot be determined.

    Returns:
        Absolute :class:`Path` to the repository root directory.
    """
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").is_dir() and (parent / "backend" / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Could not find repo root (looking for .git/ + backend/pyproject.toml)")


def duckdb_path() -> Path:
    """Return the canonical path to the project's DuckDB database.

    The canonical location is ``<repo_root>/data/ticks.duckdb``.
    """
    return _find_repo_root() / "data" / "ticks.duckdb"
