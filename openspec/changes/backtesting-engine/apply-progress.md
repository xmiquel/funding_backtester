# Apply Progress: backtesting-engine

## Goal

Implement Slice 1 PR3A1a — Result / Trade Validation — from `origin/feat/backtesting-engine`.

## Scope

- Worktree: `D:\repos\funding_backtester-pr3a1a-result-trade-validation`
- Branch: `feat/backtesting-engine-pr3a1a-result-trade-validation`
- Base: `origin/feat/backtesting-engine`
- Only `BacktestResult` / `BacktestTrade` contracts and validation are included.
- Public `BacktestFill` field validation remains out of scope for the next slice.
- No commit, push, or PR was created.

## Cumulative Prior Progress

- [x] PR1 reliability remediation: normalized validation errors, froze metadata containers, and validated temporal indexes.
- [x] PR2 execution slice: deterministic next-bar-open execution, fills, run identity, reproducibility metadata, costs, and immutable result contracts.
- [x] PR2 reliability remediation: deterministic frozenset metadata, invalid metadata rejection, open-price validation, and final-position behavior.

## TDD Cycle Evidence

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| PR3A1a.1 | Tests failed during collection because `validate_backtest_result` was absent. | Added one-unit `BacktestTrade.quantity`; focused suite passed. | Kept quantity default-compatible with existing engine construction. |
| PR3A1a.2 | Invalid trade invariant tests failed during collection. | Added independent trade validation for linkage, ordering, finite Decimal values, non-negative economics, quantity, and PnL. | Shared result-level Decimal, timestamp, and text helpers. |
| PR3A1a.3 | Result validation tests failed during collection. | Added result structure, summary, trade collection, and unfilled-signal count validation. | Fill contents are only type-checked; no public `BacktestFill` field validation was added. |
| PR3A1a blocker | Added regression test first; it reproduced raw `TypeError` from `len(None)`. | Validate the collection type before reading its length; `None` and list inputs now raise `BacktestResultValidationError`. | No broader result or fill validation changes. |
| Review follow-up | Added parametrized tests first for malformed signal tuples, invalid sides, and invalid timestamps. | Focused suite passed all three cases without a logic change. | Existing validation already rejected the reviewed malformed values. |

## Accomplished

- [x] Added `BacktestResultValidationError` and `validate_backtest_result`.
- [x] Added one-unit quantity semantics to `BacktestTrade`.
- [x] Exported the result validator and its exception from the backtesting package.
- [x] Added independent behavioral tests for valid results and invalid trade/result invariants.
- [x] Added regression coverage for non-tuple `unfilled_signals` inputs, including `None`.
- [x] Added focused parametrized coverage for malformed signal tuples, invalid sides, and invalid timestamps.
- [x] Applied Ruff formatting to the three review-signaled Python files.
- [x] Updated `tasks.md` with factual PR3A1a completion status.

## Verification

- `uv sync --frozen --extra dev` → completed successfully; 156 packages installed.
- `uv run pytest tests/test_backtesting_engine.py -q` → 73 passed.
- `uv run pytest` → 224 passed, 2 failed in `tests/test_paths.py`; both failures are worktree-layout assumptions (`.git` and `backend/` are expected one directory above the backend root).
- `uv run ruff format src/funding_backtester/backtesting/__init__.py src/funding_backtester/backtesting/contracts.py tests/test_backtesting_engine.py` → reformatted 3 files.
- `uv run ruff format --check src/ tests/` → 47 files already formatted.
- `uv run ruff check src/ tests/` → passed.
- `uv run mypy src/` → passed.

## Next Steps

- Run full `uv run pytest` plus Ruff, mypy, and diff checks before review.
- Keep BacktestFill field validation and persistence work in the next slice.

## Relevant Files

- `backend/src/funding_backtester/backtesting/contracts.py` — result/trade contracts and validation.
- `backend/src/funding_backtester/backtesting/__init__.py` — public exports.
- `backend/tests/test_backtesting_engine.py` — independent result/trade invariant tests.
- `openspec/changes/backtesting-engine/tasks.md` — factual task status.
