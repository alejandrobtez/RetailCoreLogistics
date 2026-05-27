"""
data/silver.py — Silver layer: data cleaning and validation
=============================================================================
Recibe el DataFrame crudo de la capa bronze y aplica (en orden):
  1. Conversión de tipos (bool → float32)
  2. Eliminación de duplicados (filas exactas + delivery_id repetidos)
  3. Validación de nulos en columnas críticas
  4. Validación de rangos físicos por columna
  5. Consistencia meteorológica (combinaciones imposibles)
Persiste el resultado limpio como silver/deliveries_clean_YYYYMMDD.csv.
"""
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, today_str

logger = get_logger("silver")

CRITICAL_COLS = [
    "delivery_failed",
    "recipient_failure_rate",
    "driver_quality_score",
    "weather_rain",
    "weather_wind_speed",
    "weather_temperature",
]

# (min_inclusive, max_inclusive) — None means no bound
RANGE_RULES: dict[str, tuple] = {
    "weather_temperature":    (-20.0,  50.0),
    "weather_wind_speed":     (  0.0,  None),
    "weather_rain":           (  0.0,  None),
    "recipient_failure_rate": (  0.0,   1.0),
    "driver_quality_score":   (  0.0,   1.0),
    "weight_kg":              (  0.001, None),
    "hour":                   (  0,    23),
    "num_previous_attempts":  (  0,    None),
}

# Meteorological hard limits (physically impossible values)
_WIND_HARD_LIMIT   = 40.0   # m/s — above Beaufort 12 (hurricane)
_TEMP_HARD_LIMIT   = 45.0   # °C  — above Spanish historical maximum
_RAIN_HARD_LIMIT   = 200.0  # mm/h — above world-record hourly rainfall


def _cast_booleans(df: pd.DataFrame) -> pd.DataFrame:
    bool_cols = df.select_dtypes(include="bool").columns
    if len(bool_cols):
        df = df.copy()
        df[bool_cols] = df[bool_cols].astype(np.float32)
    return df


def validate_quality(df: pd.DataFrame, target: str) -> None:
    """Valida nulos en columnas críticas y que el target tenga ambas clases."""
    null_counts = df[CRITICAL_COLS].isnull().sum()
    critical_nulls = null_counts[null_counts > 0]
    if not critical_nulls.empty:
        raise ValueError(f"Nulos en columnas críticas:\n{critical_nulls}")
    if df[target].nunique() < 2:
        raise ValueError(f"El target '{target}' solo tiene una clase.")


def _drop_duplicates(df: pd.DataFrame) -> tuple:
    """
    Elimina filas exactamente duplicadas y delivery_id repetidos.
    Retorna (df_clean, n_row_dups, n_id_dups).
    """
    n_before = len(df)
    df = df.drop_duplicates()
    n_row_dups = n_before - len(df)

    n_id_dups = 0
    if "delivery_id" in df.columns:
        mask_dup_id = df["delivery_id"].duplicated(keep="first")
        n_id_dups = int(mask_dup_id.sum())
        if n_id_dups:
            logger.warning(f"   delivery_id duplicados detectados: {n_id_dups} — se conserva primera ocurrencia")
            df = df[~mask_dup_id].copy()

    return df, n_row_dups, n_id_dups


def _validate_ranges(df: pd.DataFrame) -> tuple:
    """
    Elimina filas con valores fuera de rango físico.
    Retorna (df_clean, n_dropped, report_dict).
    """
    mask_keep = pd.Series(True, index=df.index)
    report: dict[str, int] = {}

    for col, (lo, hi) in RANGE_RULES.items():
        if col not in df.columns:
            continue
        col_mask = pd.Series(True, index=df.index)
        if lo is not None:
            col_mask &= df[col] >= lo
        if hi is not None:
            col_mask &= df[col] <= hi
        n_bad = int((~col_mask).sum())
        if n_bad:
            report[col] = n_bad
            logger.warning(f"   Rango inválido en '{col}': {n_bad} filas fuera de [{lo}, {hi}]")
        mask_keep &= col_mask

    n_dropped = int((~mask_keep).sum())
    return df[mask_keep].copy(), n_dropped, report


def _check_weather_consistency(df: pd.DataFrame) -> tuple:
    """
    Detecta y elimina combinaciones meteorológicas físicamente imposibles:
      - Viento > _WIND_HARD_LIMIT m/s
      - Temperatura > _TEMP_HARD_LIMIT °C
      - Precipitación > _RAIN_HARD_LIMIT mm/h
    Retorna (df_clean, n_dropped).
    """
    mask_ok = pd.Series(True, index=df.index)

    meteo_checks = [
        ("weather_wind_speed",   lambda s: s <= _WIND_HARD_LIMIT,
         f"viento > {_WIND_HARD_LIMIT} m/s"),
        ("weather_temperature",  lambda s: s <= _TEMP_HARD_LIMIT,
         f"temperatura > {_TEMP_HARD_LIMIT} °C"),
        ("weather_rain",         lambda s: s <= _RAIN_HARD_LIMIT,
         f"lluvia > {_RAIN_HARD_LIMIT} mm/h"),
    ]

    for col, predicate, description in meteo_checks:
        if col not in df.columns:
            continue
        col_ok = predicate(df[col])
        n_bad = int((~col_ok).sum())
        if n_bad:
            logger.warning(f"   Meteorología inconsistente ({description}): {n_bad} filas")
        mask_ok &= col_ok

    n_dropped = int((~mask_ok).sum())
    return df[mask_ok].copy(), n_dropped


def run(df: pd.DataFrame, config: dict, azure_ctx=None) -> pd.DataFrame:
    """
    Limpia y valida el DataFrame bronze en 5 pasos.
    Persiste el resultado como silver/deliveries_clean_YYYYMMDD.csv.
    Retorna el DataFrame limpio listo para feature engineering (Gold).
    """
    logger.info("🔧 Silver: iniciando limpieza y validación")
    target = config["data"]["target"]
    containers = config["azure"]["storage"]["containers"]

    rows_in = len(df)
    logger.info(f"   Filas de entrada: {rows_in:,}")

    # ── Paso 1: conversión de tipos ──────────────────────────────────────────
    df = _cast_booleans(df)
    logger.info("   [1/5] Tipos booleanos convertidos a float32")

    # ── Paso 2: eliminación de duplicados ────────────────────────────────────
    df, n_row_dups, n_id_dups = _drop_duplicates(df)
    logger.info(f"   [2/5] Duplicados: {n_row_dups} filas exactas + {n_id_dups} delivery_id repetidos eliminados")

    # ── Paso 3: validación de nulos y clases del target ──────────────────────
    validate_quality(df, target)
    logger.info("   [3/5] Nulos en columnas críticas: OK | Clases del target: OK")

    # ── Paso 4: validación de rangos ─────────────────────────────────────────
    df, n_range_dropped, range_report = _validate_ranges(df)
    if range_report:
        logger.info(f"   [4/5] Rangos inválidos eliminados: {n_range_dropped} filas → {range_report}")
    else:
        logger.info(f"   [4/5] Rangos: todos los valores dentro de límites físicos ✓")

    # ── Paso 5: consistencia meteorológica ───────────────────────────────────
    df, n_meteo_dropped = _check_weather_consistency(df)
    logger.info(f"   [5/5] Meteorología inconsistente eliminada: {n_meteo_dropped} filas")

    # ── Resumen ──────────────────────────────────────────────────────────────
    rows_out = len(df)
    total_dropped = rows_in - rows_out
    failure_rate = df[target].mean()

    logger.info(f"   Filas de salida: {rows_out:,} | Total eliminadas: {total_dropped:,} ({total_dropped/rows_in:.2%})")
    logger.info(f"   Tasa de fallos: {failure_rate:.2%} | Fallos totales: {df[target].sum():,}")

    # ── Persistencia ─────────────────────────────────────────────────────────
    silver_blob = f"silver/deliveries_clean_{today_str('%Y%m%d')}.csv"
    if azure_ctx and azure_ctx.blob:
        azure_ctx.blob.upload_csv(df, containers["raw_data"], silver_blob)
        logger.info(f"⬆️  Silver guardado en Blob: {containers['raw_data']}/{silver_blob}")
    else:
        silver_path = (
            Path(config["paths"]["local_tmp"]) / "silver"
            / f"deliveries_clean_{today_str('%Y%m%d')}.csv"
        )
        silver_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(silver_path, index=False)
        logger.info(f"📂 Silver guardado en disco: {silver_path}")

    # ── MLflow ───────────────────────────────────────────────────────────────
    mlflow.log_params({
        "silver_rows_in":           rows_in,
        "silver_rows_out":          rows_out,
        "silver_dropped_total":     total_dropped,
        "silver_dropped_row_dups":  n_row_dups,
        "silver_dropped_id_dups":   n_id_dups,
        "silver_dropped_ranges":    n_range_dropped,
        "silver_dropped_meteo":     n_meteo_dropped,
        "silver_failure_rate":      round(float(failure_rate), 4),
        "silver_date":              today_str(),
    })

    logger.info("✅ Silver completado")
    return df
