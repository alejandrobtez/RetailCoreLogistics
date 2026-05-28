"""
data/bronze.py — Bronze layer: raw data ingestion
=============================================================================
Carga el dataset crudo desde Azure Blob Storage o disco local.
Solo valida que existan las columnas requeridas (esquema mínimo).
Sin transformaciones. Persiste una copia en la capa bronze.
"""
import sys
from pathlib import Path

import mlflow
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, today_str

logger = get_logger("bronze")

REQUIRED_COLS = [
    "delivery_failed",
    "recipient_failure_rate",
    "driver_quality_score",
    "weather_rain",
    "weather_wind_speed",
    "weather_temperature",
]


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas requeridas no encontradas: {missing}")


def run(config: dict, azure_ctx=None) -> pd.DataFrame:
    """
    Carga el dataset crudo y lo persiste en la capa bronze.
    Retorna el DataFrame sin ninguna transformación.
    """
    filename = config["data"]["filename"]
    containers = config["azure"]["storage"]["containers"]

    df = None
    if azure_ctx and azure_ctx.blob:
        try:
            df = azure_ctx.blob.download_csv(containers["raw_data"], filename)
            logger.info(f"📥 Bronze: leído desde Blob: {containers['raw_data']}/{filename}")
        except Exception as e:
            logger.warning(f"Blob no disponible: {e}. Intentando disco local...")

    if df is None:
        # Orden de búsqueda: tmp/raw/<filename> → data/raw/<filename> (raíz del proyecto)
        candidate_paths = [
            Path(config["paths"]["local_tmp"]) / "raw" / filename,
            Path(__file__).resolve().parents[3] / "data" / "raw" / filename,
        ]
        local_path = next((p for p in candidate_paths if p.exists()), None)
        if local_path is None:
            searched = "\n  ".join(str(p) for p in candidate_paths)
            raise FileNotFoundError(
                f"Dataset '{filename}' no encontrado en Blob ni en disco.\n"
                f"Rutas buscadas:\n  {searched}"
            )
        df = pd.read_csv(local_path)
        logger.info(f"📥 Bronze: leído desde disco local: {local_path}")

    logger.info(f"   Filas: {len(df):,} | Columnas: {df.shape[1]}")
    validate_schema(df)

    bronze_blob = f"bronze/deliveries_raw_{today_str('%Y%m%d')}.csv"
    if azure_ctx and azure_ctx.blob:
        azure_ctx.blob.upload_csv(df, containers["raw_data"], bronze_blob)
        logger.info(f"⬆️  Bronze guardado en Blob: {containers['raw_data']}/{bronze_blob}")
    else:
        bronze_path = (
            Path(config["paths"]["local_tmp"]) / "bronze"
            / f"deliveries_raw_{today_str('%Y%m%d')}.csv"
        )
        bronze_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(bronze_path, index=False)
        logger.info(f"📂 Bronze guardado en disco: {bronze_path}")

    mlflow.log_params({
        "bronze_rows": len(df),
        "bronze_cols": df.shape[1],
        "bronze_date": today_str(),
        "bronze_source": "blob" if (azure_ctx and azure_ctx.blob) else "local",
    })

    logger.info("✅ Bronze completado")
    return df
