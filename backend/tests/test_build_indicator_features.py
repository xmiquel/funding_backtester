"""Tests for the build_indicator_features CLI script.

Tests use a temporary DuckDB database with the dbt pipeline bootstrapped,
then exercise the CLI entry point at the function level.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
from unittest import mock

import duckdb
import pytest

from funding_backtester.scripts.build_indicator_features import build, main

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DBT_PROJECT = REPO_ROOT / "analytics"


def _build_dbt_database(db_path: pathlib.Path) -> str:
    """Bootstrap DuckDB + dbt for a test database."""
    fixture_dir = pathlib.Path(__file__).parent / "data"
    fixture_abs = fixture_dir.resolve()
    pattern = str(fixture_abs / "*.txt")

    conn = duckdb.connect(str(db_path))
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW raw_ticks AS
        SELECT * FROM read_csv_auto(
            '{pattern}',
            delim=';',
            header=false,
            columns={{
                'raw_timestamp': 'VARCHAR',
                'ask': 'DOUBLE',
                'bid': 'DOUBLE',
                'last': 'DOUBLE',
                'volume': 'BIGINT'
            }},
            filename=true
        )
        """
    )
    conn.close()

    env = os.environ.copy()
    env["DBT_DUCKDB_PATH"] = str(db_path)
    result = subprocess.run(
        ["uv", "run", "dbt", "build"],
        cwd=str(DBT_PROJECT.resolve()),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("--- dbt stdout ---")
        print(result.stdout)
        print("--- dbt stderr ---")
        print(result.stderr)
        pytest.fail(f"dbt build failed (exit {result.returncode})")

    return str(db_path)


class TestBuildFunction:
    """Test the low-level ``build`` function."""

    def test_build_persists_indicator_stage_rows(self, tmp_path: pathlib.Path) -> None:
        """``build()`` writes indicator stage rows."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "build_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

        assert count == 2
        conn = duckdb.connect(str(db_path))
        try:
            stage_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()
        assert stage_rows == 2

    def test_build_skips_dbt_when_flag_is_true(self, tmp_path: pathlib.Path) -> None:
        """build() does not invoke dbt build when skip_dbt=True."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "skip_dbt_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
                skip_dbt=True,
            )

        assert count == 2
        mock_run.assert_not_called()

    def test_build_invokes_dbt_by_default(self, tmp_path: pathlib.Path) -> None:
        """build() invokes dbt build by default (skip_dbt=False)."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "dbt_default_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

        assert count == 2
        mock_run.assert_called_once()

    def test_build_resolves_relative_database_path_for_stage_and_dbt(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build() resolves relative database paths once for stage and dbt."""
        monkeypatch.chdir(tmp_path)
        relative_db_path = pathlib.Path("relative_build.duckdb")
        expected_db_path = (tmp_path / relative_db_path).resolve()

        with (
            mock.patch(
                "funding_backtester.scripts.build_indicator_features.build_indicator_feature_stage"
            ) as mock_stage,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_stage.return_value = 2
            mock_run.return_value.returncode = 0
            count = build(
                database_path=relative_db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir="analytics",
            )

        assert count == 2
        mock_stage.assert_called_once_with(
            expected_db_path,
            source_model="ohlcv_15s",
            timeframe="15s",
            feature_names=("sma",),
        )
        assert mock_run.call_args.kwargs["env"]["DBT_DUCKDB_PATH"] == str(expected_db_path)

    def test_build_rerun_is_idempotent(self, tmp_path: pathlib.Path) -> None:
        """Running build() twice produces the same stage row count."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "idempotent_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            first_count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )
            second_count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

        assert first_count == 2
        assert second_count == 2

    def test_build_rejects_invalid_source_model(self, tmp_path: pathlib.Path) -> None:
        """build() raises ValueError for invalid source_model."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "invalid_source_test.duckdb"))

        with pytest.raises(ValueError, match="Invalid source_model"):
            build(
                database_path=db_path,
                source_model="ohlcv_15s; drop table ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

    def test_build_multiple_features(self, tmp_path: pathlib.Path) -> None:
        """build() persists rows for multiple indicator feature names."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "multi_feature_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            count = build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma", "ema"),
                dbt_project_dir=DBT_PROJECT,
            )

        assert count == 4
        conn = duckdb.connect(str(db_path))
        try:
            stage_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()
        assert stage_rows == 4

    def test_build_rejects_empty_source_without_replacing_existing_stage_rows(
        self, tmp_path: pathlib.Path
    ) -> None:
        """build() fails hard on an empty source_model and keeps prior stage rows."""
        db_path = pathlib.Path(_build_dbt_database(tmp_path / "empty_source_test.duckdb"))

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

        conn = duckdb.connect(str(db_path))
        try:
            conn.execute("DELETE FROM ohlcv_15s")
            before_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()

        with (
            mock.patch("subprocess.run") as mock_run,
            pytest.raises(RuntimeError, match="No rows found in source_model"),
        ):
            build(
                database_path=db_path,
                source_model="ohlcv_15s",
                timeframe="15s",
                feature_names=("sma",),
                dbt_project_dir=DBT_PROJECT,
            )

        conn = duckdb.connect(str(db_path))
        try:
            after_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()

        assert before_rows == 2
        assert after_rows == 2
        mock_run.assert_not_called()


class TestMainFunction:
    """Test the CLI ``main`` entry point via argument parsing."""

    def test_main_defaults_dbt_project_dir_from_repo_root(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() resolves the default dbt project directory from the repo root."""
        db_path = tmp_path / "default_dbt_project.duckdb"
        _build_dbt_database(db_path)
        monkeypatch.chdir(BACKEND_DIR)

        with (
            mock.patch(
                "funding_backtester.scripts.build_indicator_features.build_indicator_feature_stage"
            ) as mock_stage,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_stage.return_value = 2
            mock_run.return_value.returncode = 0
            rc = main(
                argv=[
                    "--duckdb-path",
                    str(db_path),
                    "--source-model",
                    "ohlcv_15s",
                    "--timeframe",
                    "15s",
                    "--feature-names",
                    "sma",
                ]
            )

        assert rc == 0
        assert mock_run.call_args.kwargs["cwd"] == str(DBT_PROJECT.resolve())

    def test_main_defaults_runs_build(self, tmp_path: pathlib.Path) -> None:
        """main() parses default args and runs build against the DuckDB."""
        db_path = tmp_path / "main_test.duckdb"
        _build_dbt_database(db_path)

        rc = main(
            argv=[
                "--duckdb-path",
                str(db_path),
                "--source-model",
                "ohlcv_15s",
                "--timeframe",
                "15s",
                "--feature-names",
                "sma",
                "--dbt-project-dir",
                str(DBT_PROJECT),
            ]
        )

        assert rc == 0
        conn = duckdb.connect(str(db_path))
        try:
            stage_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()
        assert stage_rows == 2

    def test_main_skip_dbt(self, tmp_path: pathlib.Path) -> None:
        """main() with --skip-dbt only stages features without building dbt mart."""
        db_path = tmp_path / "skip_dbt.duckdb"
        _build_dbt_database(db_path)

        rc = main(
            argv=[
                "--duckdb-path",
                str(db_path),
                "--source-model",
                "ohlcv_15s",
                "--timeframe",
                "15s",
                "--feature-names",
                "sma",
                "--skip-dbt",
                "--dbt-project-dir",
                str(DBT_PROJECT),
            ]
        )

        assert rc == 0
        conn = duckdb.connect(str(db_path))
        try:
            stage_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()
        assert stage_rows == 2

    def test_main_multiple_feature_names(self, tmp_path: pathlib.Path) -> None:
        """main() accepts comma-separated --feature-names."""
        db_path = tmp_path / "multi_feature_main.duckdb"
        _build_dbt_database(db_path)

        rc = main(
            argv=[
                "--duckdb-path",
                str(db_path),
                "--source-model",
                "ohlcv_15s",
                "--timeframe",
                "15s",
                "--feature-names",
                "sma,ema,rsi",
                "--dbt-project-dir",
                str(DBT_PROJECT),
            ]
        )

        assert rc == 0
        conn = duckdb.connect(str(db_path))
        try:
            stage_rows = conn.execute("SELECT COUNT(*) FROM indicator_feature_stage").fetchone()[0]
        finally:
            conn.close()
        assert stage_rows == 6

    def test_main_returns_nonzero_on_dbt_failure(self, tmp_path: pathlib.Path) -> None:
        """main() returns nonzero exit code when dbt build fails."""
        db_path = tmp_path / "fake_build_test.duckdb"
        _build_dbt_database(db_path)

        with mock.patch("funding_backtester.scripts.build_indicator_features.build") as mock_build:
            mock_build.side_effect = subprocess.CalledProcessError(1, ["dbt"])
            rc = main(
                argv=[
                    "--duckdb-path",
                    str(db_path),
                    "--source-model",
                    "ohlcv_15s",
                    "--timeframe",
                    "15s",
                    "--feature-names",
                    "sma",
                    "--dbt-project-dir",
                    str(DBT_PROJECT),
                ]
            )

        assert rc != 0
