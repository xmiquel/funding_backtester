# Apply Progress: backtesting-engine

## Goal

Implement the autonomous PR2 execution slice on top of the PR1 deterministic contracts and moving-average strategy core.

## Instructions

- Technical artifacts, code, tests, and documentation remain in English.
- PR2 is limited to pure next-bar-open execution, fills, deterministic run identity, reproducibility metadata, and explicit costs/slippage.
- DuckDB, marts, CLI, dbt, and frontend remain out of scope.
- The repository tracker branch was refreshed from origin and contains PR1 through `origin/feat/backtesting-engine-core`; local PR2 was rebased onto `origin/feat/backtesting-engine` without publishing changes.

## Cumulative Prior Progress

- [x] PR1 reliability remediation: normalized validation errors and rejected non-finite Decimal values.
- [x] PR1 reliability remediation: recursively froze supported metadata containers and rejected unsupported mutable values.
- [x] PR1 reliability remediation: validated temporal indexes as DatetimeIndex, strictly increasing, and unique.
- [x] PR1 behavioral test evidence: focused suite reached 41 passed.
- [x] PR2 gatekeeper remediation: canonicalized `frozenset` metadata values deterministically and accepted already-frozen metadata values consistently.
- [x] PR2 reliability remediation: rejected bytes, non-string metadata keys, key collisions, and non-finite float metadata values with `BacktestValidationError`.
- [x] PR2 reliability remediation: validated non-empty, aligned, numeric, finite, non-negative open prices before signal execution.
- [x] PR2 reliability remediation: documented and tested the behavior of positions left open at the final bar.
- [x] PR2 reliability remediation: documented execution inputs, price units, fill timing, costs, results, and unfilled signals in the public slice modules.

## TDD Cycle Evidence

| Task ID | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| Existing PR1 core slice | `backend/tests/test_backtesting_engine.py` | Unit | `uv run pytest tests/test_backtesting_engine.py -q` | Historical RED execution not claimed | 33 passed | Deep immutability and blank versions | Recursive parameter freezing |
| R1.1–R1.3 reliability remediation | `backend/tests/test_backtesting_engine.py` | Unit | Existing safety net | Tests written first; 8 expected failures | 41 passed | Non-finite/type validation, unsupported mutable values, unordered/duplicate/non-temporal indexes | Helpers kept localized |
| PR2.1–PR2.4 execution slice | `backend/tests/test_backtesting_engine.py` | Unit | 41 passed before modifying existing test file | Tests written first; import failed because `engine.py` did not exist | `uv run pytest tests/test_backtesting_engine.py -q` → 44 passed | Fill timing/costs, missing next bar, repeated identical run | Decimal arithmetic, canonical payload hashing, immutable result tuples |
| PR2 gatekeeper remediation | `backend/tests/test_backtesting_engine.py` | Unit | 44 passed before modifying test file | Test written first; failed with unsupported `frozenset` metadata | `uv run pytest tests/test_backtesting_engine.py -q` → 45 passed | Reordered string frozensets produce the same run identity | Canonical frozenset sorting uses JSON-stable keys; set/frozenset freezing is consistent |
| PR2 reliability remediation | `backend/tests/test_backtesting_engine.py` | Unit | 45 passed before modifying test file | Tests written first; invalid metadata and open-price cases failed | `uv run pytest tests/test_backtesting_engine.py -q` → 59 passed | Bytes, non-finite floats, nested/non-string keys, empty/misaligned/invalid prices, and final open position | Centralized boundary validation and explicit public docstrings |

## Accomplished

- [x] Added deterministic `execute_next_bar_open` pure execution boundary.
- [x] Added next-bar-open buy/sell fills, missing-next-bar reporting, and long-only trade assembly.
- [x] Added deterministic `run_id` derived from canonical configuration and reproducibility metadata.
- [x] Added immutable run summary, fill, trade, and result contracts carrying cost/version/linkage fields.
- [x] Added behavioral tests for fill timing, cost/slippage math, missing final bar, and repeat determinism.
- [x] Added behavioral coverage proving reordered `frozenset` metadata produces a deterministic run identity.
- [x] Added behavioral coverage proving unsupported metadata cannot reach JSON hashing as a raw `TypeError` or ambiguous key collision.
- [x] Added deterministic open-price validation for empty, incompatible-index, non-numeric, non-finite, and negative inputs.
- [x] Documented one-unit Decimal price/cost semantics, next-bar fills, unfilled final-bar signals, and non-synthetic final position handling.

## Verification

- `uv run pytest tests/test_backtesting_engine.py -q` → 59 passed.
- `uv run ruff check src/funding_backtester/backtesting tests/test_backtesting_engine.py` → clean.
- `uv run mypy src/funding_backtester/backtesting` → clean.
- `git diff --check` → clean.

## Next Steps

- Run SDD verify for the PR2 execution slice.
- Keep DuckDB persistence, marts, CLI, dbt, and frontend for later slices.

## Relevant Files

- `backend/src/funding_backtester/backtesting/contracts.py` — immutable run, fill, trade, and result contracts.
- `backend/src/funding_backtester/backtesting/engine.py` — deterministic next-bar-open execution and Decimal cost math.
- `backend/src/funding_backtester/backtesting/__init__.py` — public exports.
- `backend/tests/test_backtesting_engine.py` — focused behavioral and regression tests.
- `openspec/changes/backtesting-engine/tasks.md` — PR2 slice task status.
