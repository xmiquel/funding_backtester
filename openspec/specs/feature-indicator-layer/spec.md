# Feature Indicator Layer Specification

## Purpose

Defines bounded, persisted OHLCV-derived indicator features for vectorbt-first backtesting and future reusable AI/genetic rule-search workflows.

## Requirements

### Requirement: Dependency Installation Proof

The system MUST prove local Windows and Linux/Ubuntu CI installation and runtime import of TA-Lib, `pandas-ta-classic`, and vectorbt for Python 3.12+.

#### Scenario: Standard package resolution succeeds

- GIVEN a supported Windows or Linux/Ubuntu environment
- WHEN dependencies are installed through standard package resolution
- THEN proof MUST record package versions, vectorbt import success, and TA-Lib availability.

#### Scenario: TA-Lib wheel resolution fails

- GIVEN TA-Lib Python wheels are documented for Linux, macOS, and Windows across Python 3.9-3.14
- WHEN the resolver cannot install a compatible wheel
- THEN proof MUST document fallback installation of the TA-Lib C library.
- AND Windows MAY use MSI, zip, env vars, or a local Python 3.12 wheel only after standard resolution is tried.

### Requirement: Bounded Feature Parameter Catalog

The system MUST define an explicit bounded parameter catalog for SMA, EMA, RSI, MACD, ATR, and Bollinger Bands. Parameters are part of the feature/search-space contract, not incidental defaults.

#### Scenario: Cataloged feature is requested

- GIVEN OHLCV data and a cataloged indicator/parameter set
- WHEN computation is requested
- THEN feature values MUST be produced for rows with sufficient input history.
- AND the parameter set MUST be persisted exactly as cataloged.

#### Scenario: Free-form parameters are requested

- GIVEN an indicator name or parameter set outside the catalog
- WHEN computation is requested
- THEN the request MUST fail with a deterministic validation error.
- AND no partial feature output MUST be persisted.

### Requirement: Deterministic Feature Identity

The system MUST assign each parameterized feature a deterministic identity derived from source OHLCV model, symbol/timeframe scope, feature name, canonical parameters, and computation version.

#### Scenario: Same feature is recomputed

- GIVEN persisted output for the same source data and feature identity
- WHEN computation is re-run
- THEN results MUST remain logically identical.
- AND duplicate feature rows MUST NOT be created.

#### Scenario: Genetic search references persisted features

- GIVEN a future rule-search workflow references a feature identity
- WHEN it loads persisted features
- THEN it MUST reuse the existing feature without generating free-form parameters.

### Requirement: Reproducibility Metadata

The system MUST store source OHLCV reference, feature identity, canonical parameters, computation timestamp/version, `pandas-ta-classic` version, TA-Lib version/availability, and actual execution backend.

#### Scenario: Feature lineage is inspected

- GIVEN a persisted feature value
- WHEN a consumer requests lineage
- THEN metadata MUST be sufficient to reproduce or reject the computation.

#### Scenario: Formula drift is detected

- GIVEN golden fixture outputs for a supported feature
- WHEN library or backend behavior changes values
- THEN drift MUST be flagged before accepting new output.

### Requirement: Vectorbt Consumer Shape

The system SHALL expose close prices, features, and derived signals as symbol/timeframe/datetime-aligned Pandas Series or DataFrames usable by vectorbt without exposing indicator implementation details.

#### Scenario: Vectorbt reads aligned features

- GIVEN persisted close prices and features for a requested range
- WHEN a vectorbt workflow loads them
- THEN index alignment and column naming SHALL allow direct Series/DataFrame consumption.

### Requirement: Explicit Non-Goals

The system MUST NOT implement genetic search, model training, a full vectorbt strategy, broad library selection, exhaustive indicator catalogs, or unbounded parameter generation in this change.

#### Scenario: Out-of-scope workflow is requested

- GIVEN a request for AI search execution or arbitrary indicator parameters
- WHEN scoped against this capability
- THEN it MUST be rejected as outside this feature indicator layer contract.
