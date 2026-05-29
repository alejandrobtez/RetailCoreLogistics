"""
api/services/predictor.py — Carga del modelo y lógica de predicción
=============================================================================
Singleton: el modelo se carga una vez al arrancar la API y se reutiliza
en todas las peticiones (thread-safe para lectura en FastAPI async workers).
"""
import pickle
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Añadir ml_pipeline al path para reutilizar sus módulos
_ML_PIPELINE = Path(__file__).resolve().parents[2] / "ml_pipeline"
sys.path.insert(0, str(_ML_PIPELINE))

from src.utils import get_logger, load_config
from src.azure.azure_client import AzureContext
from src.data.gold import engineer_features
from src.inference.predict import classify_risk, inject_weather_features

logger = get_logger("api.predictor")

_artifact: Optional[dict] = None
_config: Optional[dict] = None
_azure_ctx: Optional[object] = None

_CONFIG_PATH = _ML_PIPELINE / "configs" / "config.yaml"


def load_model() -> None:
    """Carga el modelo en memoria. Llamar una sola vez al arrancar la API."""
    global _artifact, _config, _azure_ctx

    _config = load_config(str(_CONFIG_PATH))
    _azure_ctx = AzureContext.from_config(_config)

    containers = _config["azure"]["storage"]["containers"]

    if _azure_ctx and _azure_ctx.blob:
        try:
            _artifact = _azure_ctx.blob.download_pickle(containers["models"], "best_model.pkl")
            logger.info("Modelo cargado desde Azure Blob Storage")
            return
        except Exception as e:
            logger.warning(f"Blob no disponible: {e}. Intentando disco local...")

    # Buscar en orden: tmp/ del pipeline → models/ de la raíz del repo
    repo_root = _ML_PIPELINE.parent
    candidate_paths = [
        _ML_PIPELINE / _config["paths"]["local_tmp"] / "models" / "best_model.pkl",
        repo_root / "models" / "best_model.pkl",
    ]
    for local_path in candidate_paths:
        if local_path.exists():
            with open(local_path, "rb") as f:
                _artifact = pickle.load(f)
            logger.info(f"Modelo cargado desde disco local: {local_path}")
            return

    logger.warning(
        "Modelo no encontrado. Arranca el pipeline de entrenamiento antes de usar la API: "
        "cd ml_pipeline && python pipeline.py"
    )


def is_model_loaded() -> bool:
    return _artifact is not None


def get_model_info() -> dict:
    if not _artifact:
        return {}
    return {
        "model_name": _artifact.get("model_name", "unknown"),
        "saved_at": _artifact.get("saved_at", "unknown"),
        "n_features": len(_artifact.get("feature_cols", [])),
        "feature_cols": _artifact.get("feature_cols", []),
        "best_threshold": _artifact.get("best_threshold", 0.5),
        "metrics": _artifact.get("metrics", {}),
    }


def get_raw_weather(city: str) -> dict:
    """
    Obtiene datos meteorológicos crudos (sin escalar) de AEMET para mostrar en el formulario.
    Devuelve: weather_rain (0/1), weather_rain_mm, weather_wind_speed (m/s),
              weather_temperature (°C), source (aemet|fallback).
    """
    if not _config:
        raise RuntimeError("Configuración no disponible.")

    thresholds = _config["aemet"]["thresholds"]
    source = "aemet"

    try:
        from src.aemet.aemet_client import AEMETClient
        aemet_key = _azure_ctx.get_aemet_key(_config) if _azure_ctx else None
        client = AEMETClient(api_key=aemet_key)
        observations = client.get_station_observations(_config["aemet"]["stations"][city])
        raw = client._parse_observations(observations)
        rain_mm = raw["weather_rain_raw"]
        wind_ms = raw["weather_wind_speed_raw"]
        temp_c = raw["weather_temperature_raw"]
    except Exception as e:
        logger.warning(f"AEMET no disponible para {city} ({e}). Usando fallback.")
        source = "fallback"
        rain_mm = 0.0
        wind_ms = 2.0
        temp_c = 18.0

    return {
        "city": city,
        "weather_rain": 1 if rain_mm > thresholds["adverse_weather_rain_mm"] else 0,
        "weather_rain_mm": round(rain_mm, 1),
        "weather_wind_speed": round(wind_ms, 1),
        "weather_temperature": round(temp_c, 1),
        "source": source,
    }


def predict_batch(deliveries: list[dict], city: str, use_aemet: bool) -> list[dict]:
    """
    Ejecuta la inferencia sobre una lista de registros de entrega.

    Args:
        deliveries: lista de dicts con los campos de DeliveryRecord
        city: ciudad para obtener datos AEMET (si use_aemet=True)
        use_aemet: si True, sobreescribe weather_* con datos AEMET en tiempo real

    Returns:
        Lista de dicts con delivery_id, prob_fallo, risk_level, action
    """
    if not _artifact:
        raise RuntimeError("Modelo no cargado. Llama a load_model() primero.")

    pipeline = _artifact["pipeline"]
    feature_cols = _artifact["feature_cols"]
    threshold = _artifact["best_threshold"]
    scaler_stats = _artifact["scaler_stats"]
    risk_config = _config["inference"]["risk_levels"]

    df = pd.DataFrame(deliveries)

    # Rellenar date con hoy si no se proporcionó
    today = date.today().strftime("%Y-%m-%d")
    if "date" not in df.columns:
        df["date"] = today
    else:
        df["date"] = df["date"].fillna(today)

    bool_cols = df.select_dtypes(include="bool").columns
    if len(bool_cols):
        df[bool_cols] = df[bool_cols].astype(np.float32)

    if use_aemet:
        try:
            from src.aemet.aemet_client import get_weather_features
            aemet_key = _azure_ctx.get_aemet_key(_config) if _azure_ctx else None
            weather = get_weather_features(
                city=city, config=_config, scaler_stats=scaler_stats,
                api_key=aemet_key, use_fallback_if_error=True,
            )
            df = inject_weather_features(df, weather, feature_cols)
            logger.info(f"Datos AEMET inyectados para {city}")
        except Exception as e:
            logger.warning(f"AEMET no disponible ({e}). Usando weather de la petición.")

    # Aplicar el mismo feature engineering que se usó en el entrenamiento
    df = engineer_features(df)

    # OHE columns not present in a small batch mean that category wasn't in the input → fill with 0
    for col in feature_cols:
        if col not in df.columns:
            df[col] = np.float32(0)

    X = df[feature_cols].astype(np.float32).values
    y_prob = pipeline.predict_proba(X)[:, 1]

    results = []
    for i, (record, prob) in enumerate(zip(deliveries, y_prob)):
        level, action = classify_risk(float(prob), threshold, risk_config)
        results.append({
            "delivery_id": record["delivery_id"],
            "prob_fallo": round(float(prob), 4),
            "risk_level": level,
            "action": action,
            "shap_reason": None,
        })

    return results
