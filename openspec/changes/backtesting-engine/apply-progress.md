# Apply Progress: backtesting-engine

## Goal
Close PR1 blockers for the deterministic backtesting core under strict TDD.

## Instructions
- Keep the slice to PR1 core blockers.
- Do not preserve unverifiable historical RED claims.
- Merge with prior apply-progress, do not overwrite it blindly.

## TDD Cycle Evidence

| Task ID | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---------|-----------|-------|------------|-----|-------|-------------|----------|
| Existing PR1 core slice | `backend/tests/test_backtesting_engine.py` | Unit | `uv run pytest tests/test_backtesting_engine.py -q` → 33 passed | Historical RED execution is not claimed; prior tests and GREEN evidence are retained factually | `uv run pytest tests/test_backtesting_engine.py -q` → 33 passed | Deep immutability and blank version scenarios were covered in the prior batch | Validation stayed in `contracts.py`; parameters were frozen recursively |
| R1.1–R1.3 reliability remediation | `backend/tests/test_backtesting_engine.py` | Unit | Existing 33-test safety net passed before edits | Tests were written first; the focused run then produced 8 expected failures before implementation | `uv run pytest tests/test_backtesting_engine.py -q` → 41 passed | Non-finite/type validation, unsupported mutable values, unordered/duplicate indexes, and non-temporal indexes exercise distinct paths | Validation helpers remain in `contracts.py`; index validation remains in `strategy.py`; empty input behavior is preserved |

## Test Summary
- Total tests passing: 41
- Layers used: Unit (1)
- Approval tests: None
- Pure functions created: 3 (`_validate_decimal`, `_freeze_parameter_value`, `_validate_temporal_index`)

## Accomplished
- ✅ Hardened `BacktestMetadata.parameters` against post-construction mutation by freezing nested mappings, lists, tuples, and sets recursively.
- ✅ Added validation coverage for whitespace-only `strategy_version` / `schema_version` values and whitespace-only metadata `schema_version`.
- ✅ Extended `backend/tests/test_backtesting_engine.py` with behavioral coverage for deep immutability and blank version contracts.
- ✅ Preserved the honest progress record by removing the uncaptured RED claim from this batch.
- ✅ Added factual strict-TDD coverage for non-finite Decimal/type normalization, unsupported mutable parameters, and strict temporal index validation.
- ✅ Normalized the new contract and strategy validation failures to `BacktestValidationError` and preserved empty-series behavior.

## Next Steps
- Verification reran cleanly (`uv run pytest tests/test_backtesting_engine.py -q` → 41 passed; `uv run ruff check src/funding_backtester/backtesting tests/test_backtesting_engine.py` clean; `uv run mypy src/funding_backtester/backtesting` clean). PR2 execution/persistence remains out of scope.

## Relevant Files
- `backend/src/funding_backtester/backtesting/contracts.py`
- `backend/tests/test_backtesting_engine.py`
- `backend/src/funding_backtester/backtesting/strategy.py`
