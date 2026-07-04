# Design: DuckDB Path Unification & Multi-Timeframe Rebuild

**Status**: Draft
**Date**: 2026-07-04
**Change**: `fix-duckdb-path`

## Approach

The canonical DuckDB is `./data/ticks.duckdb` (repo root). Instead of hardcoding paths, we derive the absolute path at startup from the repo root directory, resolved via a well-known project marker file (e.g., `pyproject.toml` at the repo root).

## Resolution Strategy

### 1. Project Root Discovery

Add a utility function that finds the repo root by walking up from `__file__` or `cwd` until a marker file (`pyproject.toml` containing `[project] name = "funding_backtester"`) is found.

```python
# backend/src/funding_backtester/_paths.py
from pathlib import Path


def _find_repo_root(marker: str = "pyproject.toml") -> Path:
    """Walk up from this file's directory until marker is found."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / marker).exists():
            return parent
    raise FileNotFoundError(f"Could not find repo root (marker: {marker})")
```

### 2. Config Change

```python
# backend/src/funding_backtester/config.py
class Settings(BaseSettings):
    ...
    duckdb_path: str = str(_find_repo_root() / "data" / "ticks.duckdb")
    ...
```

**Design decision**: use code-based resolution over env vars for the default, so it always works without manual env setup. The env file override still works via pydantic-settings.

### 3. dbt Profiles Change

```yaml
# analytics/profiles.yml
tick_data:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "{{ env_var('DBT_DUCKDB_PATH', '../data/ticks.duckdb') }}"
      schema: main
      threads: 1
```

**Design decision**: use `../data/ticks.duckdb` relative to the `analytics/` directory, which resolves to `./data/ticks.duckdb`. This avoids requiring the env var for local development. The env var still works for CI/override.

### 4. Script Alignment

Check `load_ticks.py` and any other script that references DuckDB. If they hardcode a path, update them to use the same resolution or import from config.

### 5. Rebuild Execution

```bash
cd D:/repos/funding_backtester/analytics
dbt run --full-refresh --profiles-dir .
```

Run from `analytics/` so `../data/ticks.duckdb` resolves correctly.

### 6. Cleanup

```bash
rm backend/data/ticks.duckdb
```

## Verification Plan

| Step | Command | Expected |
|------|---------|----------|
| 1. Config resolves correctly | `uv run python -c "from funding_backtester.config import settings; print(settings.duckdb_path)"` | Absolute path to `<repo>/data/ticks.duckdb` |
| 2. Check DuckDB tables | `uv run python -c "import duckdb; ..."` | All 9 `ohlcv_*` tables visible |
| 3. dbt run | `dbt run --full-refresh` | All models success |
| 4. dbt test | `dbt test` | All tests pass |
| 5. API test | pytest | All existing tests pass |
| 6. Orphan cleanup | `ls backend/data/ticks.duckdb` | File not found |

## Rollback Plan

1. Revert config changes in `config.py`, `profiles.yml`, and scripts
2. Restore `backend/data/ticks.duckdb` from git or recreate empty
3. Old DuckDB at `./data/ticks.duckdb` remains untouched by rollback
