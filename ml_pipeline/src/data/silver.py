"""
data/silver.py — Silver layer: data cleaning and validation
=============================================================================
Recibe el DataFrame crudo de la capa bronze y aplica:
  - Conversión de tipos (bool → float32)
  - Verificación de nulos en columnas críticas
  - Verificación de que el target tiene ambas clases
  - Eliminación de duplicados
Persiste el resultado limpio en la capa silver.
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


def run(df: pd.DataFrame, config: dict, azure_ctx=None) -> pd.DataFrame:
    """
    Limpia y valida el DataFrame bronze.
    Persiste el resultado en la capa silver.
    Retorna el DataFrame limpio listo para feature engineering.
    """
    logger.info("🔧 Silver: iniciando limpieza y validación")
    target = config["data"]["target"]
    containers = config["azure"]["storage"]["containers"]

    rows_before = len(df)

    df = _cast_booleans(df)
    validate_quality(df, target)
    df = df.drop_duplicates()

    rows_after = len(df)
    duplicates_removed = rows_before - rows_after
    failure_rate = df[target].mean()

    logger.info(f"   Filas: {rows_after:,} | Duplicados eliminados: {duplicates_removed}")
    logger.info(f"   Tasa de fallos: {failure_rate:.2%} | Fallos: {df[target].sum():,}")
    logger.info("✅ Validación superada")

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

    mlflow.log_params({
        "silver_rows": rows_after,
        "silver_duplicates_removed": duplicates_removed,
        "silver_failure_rate": round(failure_rate, 4),
        "silver_date": today_str(),
    })

    logger.info("✅ Silver completado")
    return df
