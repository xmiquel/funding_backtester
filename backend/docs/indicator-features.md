# Capa de features de indicadores

Capa acotada y persistida de features de indicadores derivadas de OHLCV para backtesting centrado en vectorbt y búsqueda reutilizable de reglas con IA/genética. El pipeline lee los marts de OHLCV de dbt desde DuckDB, valida las solicitudes de features contra un catálogo versionado, calcula con `pandas-ta-classic` + metadatos de TA-Lib, escribe `indicator_feature_stage` y materializa `indicator_features` mediante dbt.

---

## Contrato del mart de features

### Columnas de `indicator_features`

Todas las columnas son `NOT NULL` salvo que se indique lo contrario. El mart se materializa como tabla (full refresh).

| Columna | Tipo | Descripción |
|--------|------|-------------|
| `datetime` | `TIMESTAMP` | Límite del bucket para el valor de la feature |
| `symbol` | `VARCHAR` | Símbolo del contrato de futuros |
| `timeframe` | `VARCHAR` | Bucket de agregación de OHLCV (por ejemplo `15s`, `1m`) |
| `source_model` | `VARCHAR` | Nombre del modelo dbt de OHLCV de origen (por ejemplo `ohlcv_15s`) |
| `feature_name` | `VARCHAR` | Nombre del indicador del catálogo acotado |
| `feature_id` | `VARCHAR` | Identidad determinista SHA-256 para la feature parametrizada |
| `parameter_hash` | `VARCHAR` | Hash SHA-256 del JSON canónico de parámetros |
| `parameter_json` | `VARCHAR` | Serialización JSON canónica de los parámetros del indicador |
| `output_name` | `VARCHAR` | Nombre de la columna de salida única (por ejemplo `sma`, `bbands_lower`, `macd_signal`) |
| `value` | `DOUBLE` | Valor del indicador calculado (puede ser `NULL` si el lookback es insuficiente) |
| `computed_at` | `TIMESTAMP` | Marca de tiempo determinista derivada de `max(datetime)` de los datos de origen — la misma entrada siempre produce el mismo valor |
| `computation_version` | `VARCHAR` | Cadena de versión del cálculo de la capa de indicadores (actualmente `indicator-layer-v1`) |
| `pandas_ta_classic_version` | `VARCHAR` | Versión instalada de `pandas_ta_classic` al momento del cálculo |
| `talib_available` | `BOOLEAN` | Indica si TA-Lib era importable al momento del cálculo |
| `talib_version` | `VARCHAR` | Cadena de versión instalada de TA-Lib (nullable, `NULL` cuando `talib_available` es false) |
| `talib_used` | `BOOLEAN` | Indica si para esta feature se usó una ruta de ejecución respaldada por TA-Lib |

### Unicidad

Clave lógica de unicidad:

```
(datetime, symbol, timeframe, source_model, feature_id, output_name)
```

Un test singular de dbt (`analytics/tests/assert_indicator_features_unique.sql`) lo impone en tiempo de build.

### Cómo se identifican las features

Cada feature parametrizada recibe un `feature_id` SHA-256 determinista derivado de la concatenación (separada por `|`):

```
source_model|symbol|timeframe|feature_name|canonical_parameter_json|computation_version
```

`canonical_parameter_json` es JSON compacto (`sort_keys=True`, `separators=(",",":")`). Las mismas entradas siempre producen el mismo `feature_id` — los consumidores pueden referenciar features persistidas sin generar parámetros libres.

`parameter_json` guarda el mismo JSON canónico; `parameter_hash` es su digest hexadecimal SHA-256.

### Cómo consultar

```sql
-- Todas las features de un símbolo
SELECT datetime, feature_name, output_name, value
FROM indicator_features
WHERE symbol = 'ES'
ORDER BY datetime;

-- Una feature específica
SELECT datetime, value
FROM indicator_features
WHERE symbol = 'ES'
  AND feature_name = 'rsi'
  AND output_name = 'rsi'
ORDER BY datetime;

-- Features con metadatos
SELECT feature_name, parameter_json, talib_available, talib_used
FROM indicator_features
WHERE symbol = 'MNQ'
LIMIT 5;
```

### Catálogo acotado

| Indicador | Librería | Parámetros | Salidas | Lookback mínimo |
|---------|---------|------------|---------|-------------|
| `sma` | `pandas_ta_classic` | `length: 20` | `sma` | 20 |
| `ema` | `pandas_ta_classic` | `length: 21` | `ema` | 21 |
| `rsi` | `pandas_ta_classic` | `length: 14` | `rsi` | 14 |
| `macd` | `talib` (delegado por `pandas-ta-classic`) | `fastperiod: 12, slowperiod: 26, signalperiod: 9` | `macd`, `macd_signal`, `macd_hist` | 34 |
| `atr` | `pandas_ta_classic` | `length: 14` | `atr` | 14 |
| `bbands` | `pandas_ta_classic` | `length: 20, std: 2` | `bbands_lower`, `bbands_middle`, `bbands_upper` | 20 |

Las filas cuyo índice `datetime` queda por debajo de `min_lookback` desde el inicio de los datos del símbolo producen valores `NULL` para todas las columnas de salida.

---

## Prueba de dependencias

### Paquetes requeridos

| Módulo de importación | Paquete PyPI | Propósito |
|---------------|-------------|---------|
| `pandas_ta_classic` | `pandas-ta-classic` | Cálculo de indicadores mediante el accessor de DataFrame (`df.ta.*`) |
| `talib` | `TA-Lib` | Indicadores respaldados por TA-Lib (MACD) y metadatos de rendimiento |
| `vectorbt` | `vectorbt` | Destino consumidor para backtesting |

### Test de verificación

Ejecutá el test de verificación de dependencias para confirmar que las tres importaciones están disponibles y reportan versiones:

```bash
uv run pytest tests/test_indicator_dependencies.py -v
```

El test (`backend/tests/test_indicator_dependencies.py`) verifica:

1. **Resolución de imports**: cada módulo requerido es encontrado por `importlib.util.find_spec()`.
2. **Metadatos de versión**: cada módulo expone `__version__` y no está vacío.

### Verificación manual

```bash
uv run python -c "
import pandas_ta_classic; print('pandas_ta_classic', pandas_ta_classic.__version__)
import talib; print('TA-Lib', talib.__version__)
import vectorbt; print('vectorbt', vectorbt.__version__)
"
```

---

## Instalación de fallback de TA-Lib

TA-Lib Python publica wheels binarios para Linux, macOS y Windows para Python 3.9–3.14. La vía preferida es la resolución estándar de `uv sync`. Cuando falla, el comportamiento de fallback depende de la plataforma.

### CI en Ubuntu (Linux)

CI usa un enfoque primero-resolver: `uv sync --frozen --extra dev` se ejecuta primero con `continue-on-error: true`. Si falla en Ubuntu, el fallback instala la biblioteca C de TA-Lib desde el código fuente y luego reintenta `uv sync`:

```yaml
- name: Instalar dependencias del backend
  id: uv-sync
  continue-on-error: true
  run: uv sync --frozen --extra dev
- name: Instalar fallback de TA-Lib en Ubuntu cuando falle la verificación del resolver
  if: steps.uv-sync.outcome == 'failure' && runner.os == 'Linux'
  run: |
    sudo apt-get update
    sudo apt-get install -y build-essential wget
    wget -q https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
    tar -xzf ta-lib-0.6.4-src.tar.gz
    cd ta-lib-0.6.4
    ./configure --prefix=/usr
    make
    sudo make install
    cd ../backend
    uv sync --frozen --extra dev
```

Este fallback se repite en los tres jobs de CI que instalan dependencias del backend: `quality`, `test` y `dbt-integration`.

### Windows

Si `uv sync` falla en Windows, el step de CI sale con código 1 — no hay fallback automatizado para Windows en CI.

Para desarrollo local en Windows, una vía de recuperación confirmada es:

```powershell
uv sync
# Si TA-Lib falla:
uv pip install D:\repos\ta_lib-0.6.8-cp312-cp312-win_amd64.whl
```

La ruta exacta del wheel depende de tu versión local de Python y de la ubicación del wheel de TA-Lib.

### macOS

`uv sync` es la vía esperada de instalación. No hay un fallback definido en CI para macOS — el wheel debería resolverse mediante la resolución estándar de PyPI.

---

## Punto de entrada de CLI

El script `backend/src/funding_backtester/scripts/build_indicator_features.py` ejecuta el pipeline completo:

```bash
# Calcula SMA, EMA, RSI desde ohlcv_15s y ejecuta dbt build
uv run python -m funding_backtester.scripts.build_indicator_features \
    --source-model ohlcv_15s \
    --timeframe 15s \
    --feature-names sma,ema,rsi

# Solo stage (omite dbt)
uv run python -m funding_backtester.scripts.build_indicator_features \
    --feature-names macd,bbands \
    --skip-dbt
```

## API de Python

```python
from funding_backtester.indicators import (
    build_indicator_feature_stage,
    compute_indicator_series,
    load_features,
)
```

- `build_indicator_feature_stage(db_path, source_model="ohlcv_15s", timeframe="15s", feature_names=["sma"])` — calcula y persiste filas de stage.
- `compute_indicator_series(name, frame, parameters=None)` — devuelve `IndicatorResult` con el frame calculado y metadatos del backend.
- `load_features(db_path, symbol="ES", timeframe="15s")` — devuelve `(close: pd.Series, features: pd.DataFrame)` alineados para vectorbt.
