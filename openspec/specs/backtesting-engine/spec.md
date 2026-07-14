# backtesting-engine Specification

## Purpose

Provide a narrow offline backtesting engine for reproducible research. The capability is limited to a moving-average crossover strategy, next-bar open execution, explicit cost/slippage inputs, and persisted DuckDB outputs.

## Requirements

### Requirement: Offline deterministic execution

The system MUST run without HTTP execution, frontend UI, genetic optimization, or a broad strategy catalog. It MUST produce identical outputs when given the same data snapshot, code version, and configuration.

#### Scenario: Same inputs, same results

- GIVEN the same OHLCV snapshot, strategy parameters, and cost/slippage values
- WHEN the run is executed twice
- THEN the summary metrics and trade ledger contents are identical
- AND no network access is required

#### Scenario: Unsupported execution mode

- GIVEN a request to run via HTTP or select an unsupported strategy
- WHEN validation runs
- THEN the system rejects the request with a deterministic error

### Requirement: Moving-average crossover and next-bar open fills

The system MUST evaluate moving-average crossover signals on bar close and MUST execute fills on the next bar open.

#### Scenario: Bullish crossover entry

- GIVEN the fast average crosses above the slow average on bar N
- WHEN bar N+1 opens
- THEN a long entry is recorded at the open price of bar N+1

#### Scenario: Missing next bar

- GIVEN a signal occurs on the final available bar
- WHEN no next bar exists
- THEN the system MUST not create a fill and MUST report the condition

### Requirement: Explicit costs and slippage

The system MUST apply configurable transaction cost and slippage values to every fill. These values MUST be part of the run inputs and persisted outputs.

#### Scenario: Non-zero costs

- GIVEN configured commission and slippage values
- WHEN a trade is filled
- THEN the net trade result reflects those values

#### Scenario: Invalid values

- GIVEN a negative cost or slippage setting
- WHEN validation runs
- THEN the system rejects the configuration

### Requirement: Versioned DuckDB persistence

The system MUST persist a versioned run summary and trade ledger in DuckDB. Each run MUST include a run identifier, schema version, strategy version, and linkage to its trade rows.

#### Scenario: Successful run persistence

- GIVEN a completed backtest
- WHEN results are saved
- THEN one run summary row and the related trade rows are stored in DuckDB
- AND each trade row references the run identifier

#### Scenario: Read after rerun

- GIVEN the same run executed again
- WHEN results are persisted
- THEN a separate versioned run record exists
- AND prior records remain readable

### Requirement: Reproducibility metadata

The system MUST persist reproducibility metadata including input data snapshot identity, parameter set, and code or strategy revision reference.

#### Scenario: Auditable run

- GIVEN a persisted run
- WHEN it is inspected later
- THEN the metadata is sufficient to reproduce the same inputs and configuration

#### Scenario: Missing metadata

- GIVEN required snapshot or version information is absent
- WHEN persistence is attempted
- THEN the system rejects the run or marks it incomplete deterministically
