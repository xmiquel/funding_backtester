"""Tests for the feature discovery API endpoints.

Tests cover:
- GET /api/v1/features/catalog — indicator catalog discovery
- GET /api/v1/features/meta — available symbols/timeframes/source_models
- GET /api/v1/features — query persisted feature rows
"""

from __future__ import annotations

import duckdb
import pytest
from httpx import ASGITransport, AsyncClient

from funding_backtester.main import app

# ---------------------------------------------------------------------------
# Feature Catalog Endpoint
# GET /api/v1/features/catalog
# ---------------------------------------------------------------------------


class TestFeatureCatalogEndpoint:
    """Static catalog of bounded indicators — no DuckDB dependency."""

    @pytest.mark.asyncio
    async def test_catalog_returns_list(self, feature_client):
        """GET /api/v1/features/catalog returns a non-empty list."""
        response = await feature_client.get("/api/v1/features/catalog")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 6, f"Expected at least 6 catalog entries, got {len(data)}"

    @pytest.mark.asyncio
    async def test_catalog_entry_has_required_fields(self, feature_client):
        """Each catalog entry has name, library, parameters, outputs, min_lookback."""
        response = await feature_client.get("/api/v1/features/catalog")
        assert response.status_code == 200
        data = response.json()
        for entry in data:
            assert "name" in entry
            assert "library" in entry
            assert "parameters" in entry
            assert "outputs" in entry
            assert "min_lookback" in entry
            assert isinstance(entry["name"], str)
            assert isinstance(entry["library"], str)
            assert isinstance(entry["parameters"], dict)
            assert isinstance(entry["outputs"], list)
            assert isinstance(entry["min_lookback"], int)

    @pytest.mark.asyncio
    async def test_catalog_includes_known_indicators(self, feature_client):
        """Catalog contains sma, ema, rsi, macd, atr, bbands."""
        response = await feature_client.get("/api/v1/features/catalog")
        assert response.status_code == 200
        names = {entry["name"] for entry in response.json()}
        expected = {"sma", "ema", "rsi", "macd", "atr", "bbands"}
        assert expected.issubset(names), f"Missing indicators: {expected - names}"

    @pytest.mark.asyncio
    async def test_catalog_macd_outputs(self, feature_client):
        """MACD entry has 3 outputs: macd, macd_signal, macd_hist."""
        response = await feature_client.get("/api/v1/features/catalog")
        assert response.status_code == 200
        macd = next(e for e in response.json() if e["name"] == "macd")
        assert macd["outputs"] == ["macd", "macd_signal", "macd_hist"]
        assert macd["min_lookback"] == 34

    @pytest.mark.asyncio
    async def test_catalog_bbands_outputs(self, feature_client):
        """BBands entry has 3 outputs: bbands_lower, bbands_middle, bbands_upper."""
        response = await feature_client.get("/api/v1/features/catalog")
        assert response.status_code == 200
        bbands = next(e for e in response.json() if e["name"] == "bbands")
        assert bbands["outputs"] == ["bbands_lower", "bbands_middle", "bbands_upper"]
        assert bbands["parameters"] == {"length": 20, "std": 2}


# ---------------------------------------------------------------------------
# Feature Metadata Endpoint
# GET /api/v1/features/meta
# ---------------------------------------------------------------------------


class TestFeatureMetaEndpoint:
    """Endpoint to discover available symbols/timeframes/source_models."""

    @pytest.mark.asyncio
    async def test_meta_returns_object(self, feature_client):
        """GET /api/v1/features/meta returns an object with symbols, timeframes, source_models."""
        response = await feature_client.get("/api/v1/features/meta")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "symbols" in data
        assert "timeframes" in data
        assert "source_models" in data

    @pytest.mark.asyncio
    async def test_meta_empty_when_no_feature_table(self, feature_client):
        """When no features table exists, meta returns empty arrays (not 500)."""
        response = await feature_client.get("/api/v1/features/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == []
        assert data["timeframes"] == []
        assert data["source_models"] == []

    @pytest.mark.asyncio
    async def test_meta_empty_when_existing_db_has_no_feature_tables(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """An existing DuckDB file without feature tables still returns empty arrays."""
        db_path = str(tmp_path / "empty_features.duckdb")
        duckdb.connect(db_path).close()
        feature_client = _create_client(monkeypatch, db_path)

        response = await feature_client.get("/api/v1/features/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == []
        assert data["timeframes"] == []
        assert data["source_models"] == []

    @pytest.mark.asyncio
    async def test_meta_empty_when_duckdb_file_is_malformed(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """A malformed DuckDB file is treated as an operational failure and returns empty arrays."""
        db_path = tmp_path / "malformed_features.duckdb"
        db_path.write_bytes(b"not a duckdb database")
        feature_client = _create_client(monkeypatch, str(db_path))

        response = await feature_client.get("/api/v1/features/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == []
        assert data["timeframes"] == []
        assert data["source_models"] == []

    @pytest.mark.asyncio
    async def test_meta_returns_data_when_features_exist(self, feature_client_with_stage):
        """After building features, meta returns non-empty lists."""
        response = await feature_client_with_stage.get("/api/v1/features/meta")
        assert response.status_code == 200
        data = response.json()
        assert len(data["symbols"]) > 0
        assert len(data["timeframes"]) > 0
        assert len(data["source_models"]) > 0
        assert "ES" in data["symbols"]
        assert "15s" in data["timeframes"]


# ---------------------------------------------------------------------------
# Feature Data Endpoint
# GET /api/v1/features
# ---------------------------------------------------------------------------


class TestFeatureQueryEndpoint:
    """Query persisted feature rows."""

    @pytest.mark.asyncio
    async def test_missing_symbol_returns_422(self, feature_client):
        """GET /api/v1/features without symbol returns 422."""
        response = await feature_client.get("/api/v1/features")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_result_when_no_features_table(self, feature_client):
        """When no features table exists, returns empty array."""
        response = await feature_client.get("/api/v1/features?symbol=ES")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_empty_result_when_existing_db_has_no_feature_tables(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """An existing DuckDB file without feature tables still returns an empty array."""
        db_path = str(tmp_path / "empty_features.duckdb")
        duckdb.connect(db_path).close()
        feature_client = _create_client(monkeypatch, db_path)

        response = await feature_client.get("/api/v1/features?symbol=ES")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_empty_result_when_duckdb_file_is_malformed(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """A malformed DuckDB file returns empty results, not 500."""
        db_path = tmp_path / "malformed_features.duckdb"
        db_path.write_bytes(b"not a duckdb database")
        feature_client = _create_client(monkeypatch, str(db_path))

        response = await feature_client.get("/api/v1/features?symbol=ES")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_feature_rows(self, feature_client_with_stage):
        """Valid symbol with feature data returns rows."""
        response = await feature_client_with_stage.get("/api/v1/features?symbol=ES")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_feature_row_has_expected_fields(self, feature_client_with_stage):
        """Each feature row has the expected shape from indicator_features."""
        response = await feature_client_with_stage.get("/api/v1/features?symbol=ES")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        row = data[0]
        expected_keys = {
            "datetime",
            "symbol",
            "timeframe",
            "source_model",
            "feature_name",
            "feature_id",
            "parameter_hash",
            "parameter_json",
            "output_name",
            "value",
            "computed_at",
            "computation_version",
            "pandas_ta_classic_version",
            "talib_available",
            "talib_version",
            "talib_used",
        }
        assert expected_keys.issubset(row.keys()), (
            f"Missing keys: {expected_keys - set(row.keys())}"
        )

    @pytest.mark.asyncio
    async def test_feature_filter_by_name(self, feature_client_with_stage):
        """feature_name parameter filters results."""
        response = await feature_client_with_stage.get(
            "/api/v1/features?symbol=ES&feature_name=sma"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        for row in data:
            assert row["feature_name"] == "sma"

    @pytest.mark.asyncio
    async def test_feature_filter_by_timeframe(self, feature_client_with_stage):
        """timeframe parameter filters results."""
        response = await feature_client_with_stage.get("/api/v1/features?symbol=ES&timeframe=15s")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        for row in data:
            assert row["timeframe"] == "15s"

    @pytest.mark.asyncio
    async def test_empty_for_unknown_symbol(self, feature_client_with_stage):
        """Unknown symbol returns empty array."""
        response = await feature_client_with_stage.get("/api/v1/features?symbol=UNKNOWN")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_filter_by_multiple_feature_names(self, feature_client_with_stage):
        """Multiple feature_name params filter correctly."""
        response = await feature_client_with_stage.get(
            "/api/v1/features?symbol=ES&feature_name=rsi&feature_name=sma"
        )
        assert response.status_code == 200
        data = response.json()
        feature_names = {r["feature_name"] for r in data}
        assert "rsi" in feature_names
        assert "sma" in feature_names


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_client(monkeypatch, db_path):
    """Create an API client pointing to the given DuckDB path."""
    monkeypatch.setattr("funding_backtester.config.settings.duckdb_path", db_path)
    import funding_backtester.api.v1.ohlcv as ohlcv_mod

    ohlcv_mod._client = None
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _populate_stage_table(conn):
    """Insert sample feature data into indicator_feature_stage."""
    conn.execute("""
        CREATE TABLE indicator_feature_stage (
            datetime TIMESTAMP NOT NULL,
            symbol VARCHAR NOT NULL,
            timeframe VARCHAR NOT NULL,
            source_model VARCHAR NOT NULL,
            feature_name VARCHAR NOT NULL,
            feature_id VARCHAR NOT NULL,
            parameter_hash VARCHAR NOT NULL,
            parameter_json VARCHAR NOT NULL,
            output_name VARCHAR NOT NULL,
            value DOUBLE,
            computed_at TIMESTAMP NOT NULL,
            computation_version VARCHAR NOT NULL,
            pandas_ta_classic_version VARCHAR NOT NULL,
            talib_available BOOLEAN NOT NULL,
            talib_version VARCHAR,
            talib_used BOOLEAN NOT NULL
        )
    """)
    sample_json = '{"length":14}'
    sma_json = '{"length":20}'
    conn.execute(
        """
        INSERT INTO indicator_feature_stage VALUES
        ('2026-03-15 09:30:00', 'ES', '15s', 'ohlcv_15s',
         'rsi', 'fid-rsi', 'hash-rsi', ?,
         'rsi', 45.5,
         '2026-03-15 09:30:15', 'indicator-layer-v1',
         '1.0.6', true, '0.6.8', false),
        ('2026-03-15 09:30:15', 'ES', '15s', 'ohlcv_15s',
         'rsi', 'fid-rsi', 'hash-rsi', ?,
         'rsi', 46.0,
         '2026-03-15 09:30:15', 'indicator-layer-v1',
         '1.0.6', true, '0.6.8', false),
        ('2026-03-15 09:30:00', 'ES', '15s', 'ohlcv_15s',
         'sma', 'fid-sma', 'hash-sma', ?,
         'sma', 4510.25,
         '2026-03-15 09:30:15', 'indicator-layer-v1',
         '1.0.6', true, '0.6.8', false)
        """,
        [sample_json, sample_json, sma_json],
    )


@pytest.fixture
def feature_db_path(tmp_path: pytest.TempPathFactory) -> str:
    """Create a temporary DuckDB path."""
    return str(tmp_path / "test_features.duckdb")  # type: ignore[arg-type]


@pytest.fixture
def feature_client(feature_db_path: str, monkeypatch: pytest.MonkeyPatch):
    """API client with empty DB (no feature tables)."""
    return _create_client(monkeypatch, feature_db_path)


@pytest.fixture
def feature_client_with_stage(feature_db_path: str, monkeypatch: pytest.MonkeyPatch):
    """API client with a DB that has indicator_feature_stage data."""
    conn = duckdb.connect(feature_db_path)
    _populate_stage_table(conn)
    conn.close()
    return _create_client(monkeypatch, feature_db_path)
