"""Tests for the DuckDB path resolution module.

Verifies that _find_repo_root correctly locates the project root
and duckdb_path returns a path relative to it.
"""

from __future__ import annotations

import pathlib

from funding_backtester._paths import _find_repo_root, duckdb_path


class TestFindRepoRoot:
    """Verify repo root discovery via .git + backend/pyproject.toml markers."""

    def test_returns_existing_path(self):
        """_find_repo_root returns a path that exists."""
        root = _find_repo_root()
        assert isinstance(root, pathlib.Path)
        assert root.exists(), f"Repo root {root} does not exist"

    def test_contains_git_directory(self):
        """The returned directory contains .git."""
        root = _find_repo_root()
        assert (root / ".git").is_dir(), f".git not found in {root}"

    def test_contains_backend_pyproject_toml(self):
        """The returned directory contains backend/pyproject.toml."""
        root = _find_repo_root()
        p = root / "backend" / "pyproject.toml"
        assert p.exists(), f"backend/pyproject.toml not found in {root}"
        content = p.read_text()
        assert "[project]" in content
        assert 'name = "funding_backtester"' in content


class TestDuckdbPath:
    """Verify duckdb_path() returns the canonical path."""

    def test_duckdb_path_returns_absolute_path(self):
        """duckdb_path returns an absolute Path."""
        result = duckdb_path()
        assert isinstance(result, pathlib.Path)
        assert result.is_absolute(), f"Expected absolute path, got {result}"

    def test_duckdb_path_ends_with_data_ticks_duckdb(self):
        """duckdb_path ends with data/ticks.duckdb."""
        result = duckdb_path()
        assert result.name == "ticks.duckdb"
        assert result.parent.name == "data"
        assert result.suffix == ".duckdb"

    def test_duckdb_path_lives_under_repo_root(self):
        """duckdb_path is a child of the repo root."""
        root = _find_repo_root()
        result = duckdb_path()
        assert str(result).startswith(str(root)), f"Expected {result} to be under repo root {root}"

    def test_duckdb_path_concatenation(self):
        """duckdb_path is exactly <repo_root>/data/ticks.duckdb."""
        root = _find_repo_root()
        expected = root / "data" / "ticks.duckdb"
        assert duckdb_path() == expected, f"Expected {expected}, got {duckdb_path()}"
