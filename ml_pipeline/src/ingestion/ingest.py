"""
ingestion/ingest.py — OBSOLETO
=============================================================================
Supersedido por la arquitectura medallion:
  src/data/bronze.py → carga cruda + validación de esquema
  src/data/silver.py → limpieza y validación de calidad

Conservado por compatibilidad. No se usa en pipeline.py.
"""
import sys
from pathlib import Path

import mlflow
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, today_str

logger = get_logger("ingestion")

REQUIRED_COLS = [
    "delivery_failed", "recipient_failure_rate", "driver_quality_score",
    "weather_rain", "weather_wind_speed", "weather_temperature",
]


def validate_dataframe(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas requeridas no encontradas: {missing}")
    null_counts = df[REQUIRED_COLS].isnull().sum()
    critical_nulls = null_counts[null_counts > 0]
    if not critical_nulls.empty:
        raise ValueError(f"Nulos en columnas críticas:\n{critical_nulls}")
    if df["delivery_failed"].nunique() < 2:
        raise ValueError("El target 'delivery_failed' solo tiene una clase.")
    logger.info("✅ Validación superada")


def run(config: dict, azure_ctx=None) -> pd.DataFrame:
    """
    Carga el dataset desde Azure Blob Storage o disco local.
    Retorna el DataFrame validado (en memoria, no se escribe a disco).
    """
    filename = config["data"]["filename"]
    containers = config["azure"]["storage"]["containers"]

    # ── Intentar Blob Storage ──────────────────────────────────────────────
    df = None
    if azure_ctx and azure_ctx.blob:
        try:
            df = azure_ctx.blob.download_csv(containers["raw_data"], filename)
            logger.info(f"📥 Dataset leído desde Blob Storage: {containers['raw_data']}/{filename}")
        except Exception as e:
            logger.warning(f"No se pudo leer desde Blob: {e}. Intentando disco local...")

    # ── Fallback local ─────────────────────────────────────────────────────
    if df is None:
        local_path = Path(config["paths"]["local_tmp"]) / "raw" / filename
        if not local_path.exists():
            raise FileNotFoundError(
                f"Dataset no encontrado en Blob ni en disco local ({local_path}).\n"
                f"Sube el CSV a Blob Storage: az storage blob upload "
                f"--container-name {containers['raw_data']} --name {filename} --file {filename}"
            )
        df = pd.read_csv(local_path)
        logger.info(f"📥 Dataset leído desde disco local: {local_path}")

    logger.info(f"   Filas: {len(df):,} | Columnas: {df.shape[1]}")

    # ── Validar ────────────────────────────────────────────────────────────
    validate_dataframe(df)

    target = config["data"]["target"]
    failure_rate = df[target].mean()
    logger.info(f"   Tasa de fallos: {failure_rate:.2%} | Fallos: {df[target].sum():,}")

    # ── Log MLflow ─────────────────────────────────────────────────────────
    mlflow.log_params({
        "ingestion_rows": len(df),
        "ingestion_cols": df.shape[1],
        "ingestion_failure_rate": round(failure_rate, 4),
        "ingestion_date": today_str(),
        "ingestion_source": "blob" if (azure_ctx and azure_ctx.blob) else "local",
    })

    return df
