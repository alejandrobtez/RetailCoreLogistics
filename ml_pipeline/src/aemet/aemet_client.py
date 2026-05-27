"""
aemet/aemet_client.py — Integración con API AEMET en tiempo real
=============================================================================
Responsabilidades:
  - Obtener la predicción meteorológica horaria para el día de hoy
  - Transformar los datos climáticos al mismo espacio de features del modelo
  - Aplicar el mismo escalado que se usó en entrenamiento
  - Exponer una función que devuelve un dict {feature: valor_escalado}

Documentación AEMET OpenData: https://opendata.aemet.es/openapi/
API Key: variable de entorno AEMET_API_KEY
=============================================================================
"""
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, load_config

logger = get_logger("aemet")


class AEMETClient:
    """
    Cliente para la API de AEMET OpenData.

    Uso:
        client = AEMETClient(api_key="TU_API_KEY")
        weather = client.get_today_weather(city="madrid")
        # → {"weather_rain": 0.0, "weather_wind_speed": 3.2, "weather_temperature": 18.5, ...}
    """

    BASE_URL = "https://opendata.aemet.es/opendata/api"  # CORRECTO: /opendata/api (no /openapi/api)
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # segundos entre reintentos

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("AEMET_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API Key de AEMET no encontrada. "
                "Defínela como variable de entorno: export AEMET_API_KEY='tu_clave'"
            )
        self.session = requests.Session()
        self.session.headers.update({"api_key": self.api_key})

    # -------------------------------------------------------------------------
    # PETICIÓN HTTP con reintentos
    # -------------------------------------------------------------------------
    def _get(self, url: str) -> dict:
        """Realiza GET con reintentos ante errores temporales."""
        for attempt in range(1, self.RETRY_ATTEMPTS + 1):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Intento {attempt}/{self.RETRY_ATTEMPTS} fallido: {e}")
                if attempt < self.RETRY_ATTEMPTS:
                    time.sleep(self.RETRY_DELAY)
        raise ConnectionError(f"No se pudo conectar con AEMET tras {self.RETRY_ATTEMPTS} intentos")

    # -------------------------------------------------------------------------
    # OBTENER DATOS REALES DE LA ESTACIÓN
    # -------------------------------------------------------------------------
    def get_station_observations(self, station_id: str) -> list[dict]:
        """
        Obtiene observaciones de la última hora para una estación.
        AEMET devuelve primero la URL de datos, luego hay que hacer otra petición.
        """
        # Paso 1: obtener la URL de los datos
        endpoint = f"{self.BASE_URL}/observacion/convencional/datos/estacion/{station_id}"
        meta = self._get(endpoint)

        if meta.get("estado") != 200:
            raise ValueError(f"AEMET devolvió estado {meta.get('estado')}: {meta.get('descripcion')}")

        # Paso 2: obtener los datos reales desde la URL proporcionada
        data_url = meta["datos"]
        data = self._get(data_url)

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"AEMET no devolvió observaciones para estación {station_id}")

        return data

    # -------------------------------------------------------------------------
    # OBTENER PREDICCIÓN DIARIA (para las próximas horas)
    # -------------------------------------------------------------------------
    def get_daily_forecast(self, municipality_code: str) -> dict:
        """
        Obtiene la predicción horaria para un municipio.
        Códigos municipio AEMET: Madrid=28079, Barcelona=08019, Valencia=46250, Sevilla=41091
        """
        endpoint = f"{self.BASE_URL}/prediccion/especifica/municipio/horaria/{municipality_code}"
        meta = self._get(endpoint)

        if meta.get("estado") != 200:
            raise ValueError(f"Error AEMET predicción: {meta.get('descripcion')}")

        data = self._get(meta["datos"])
        return data

    # -------------------------------------------------------------------------
    # EXTRAER VARIABLES RELEVANTES PARA EL MODELO
    # -------------------------------------------------------------------------
    def _parse_observations(self, observations: list[dict]) -> dict:
        """
        Extrae las variables meteorológicas de interés de las observaciones AEMET.
        Devuelve valores en unidades originales (sin escalar).
        """
        latest = observations[-1]  # la observación más reciente

        def safe_float(key: str, default: float = 0.0) -> float:
            val = latest.get(key, default)
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        return {
            "weather_rain_raw": safe_float("prec"),           # mm
            "weather_wind_speed_raw": safe_float("vv"),       # m/s
            "weather_temperature_raw": safe_float("ta"),      # °C
        }

    # -------------------------------------------------------------------------
    # INTERFAZ PÚBLICA PRINCIPAL
    # -------------------------------------------------------------------------
    def get_today_weather(
        self,
        city: str,
        config: dict,
        scaler_stats: Optional[dict] = None
    ) -> dict:
        """
        Devuelve las features meteorológicas para una ciudad, listas para usar
        directamente en el modelo (en el mismo espacio escalado del training).

        Args:
            city: 'madrid', 'barcelona', 'valencia', 'sevilla'
            config: configuración del pipeline (config.yaml)
            scaler_stats: dict con mean y std de cada feature del training
                          Si None, devuelve valores sin escalar (útil para debug)

        Returns:
            dict con keys: weather_rain, weather_wind_speed, weather_temperature,
                           strong_wind, adverse_weather, temp_category
        """
        stations = config["aemet"]["stations"]
        thresholds = config["aemet"]["thresholds"]

        if city not in stations:
            raise ValueError(f"Ciudad '{city}' no configurada. Disponibles: {list(stations.keys())}")

        station_id = stations[city]
        logger.info(f"🌤️  Obteniendo datos AEMET: {city} (estación {station_id})")

        observations = self.get_station_observations(station_id)
        raw = self._parse_observations(observations)

        rain = raw["weather_rain_raw"]
        wind = raw["weather_wind_speed_raw"]
        temp = raw["weather_temperature_raw"]

        logger.info(f"   🌧️  Lluvia: {rain} mm | 💨 Viento: {wind} m/s | 🌡️  Temp: {temp}°C")

        # Features derivadas (igual que en el preprocessing del training)
        strong_wind = 1.0 if wind > thresholds["strong_wind_ms"] else 0.0
        adverse_weather = 1.0 if rain > thresholds["adverse_weather_rain_mm"] else 0.0
        temp_category = (
            0.0 if temp < 5 else
            1.0 if temp < 15 else
            2.0 if temp < 25 else
            3.0
        )

        features = {
            "weather_rain": rain,
            "weather_wind_speed": wind,
            "weather_temperature": temp,
            "strong_wind": strong_wind,
            "adverse_weather": adverse_weather,
            "temp_category": temp_category,
        }

        # Escalar al mismo espacio del training si tenemos las estadísticas
        if scaler_stats:
            features = self._scale_features(features, scaler_stats)
            logger.info("   ✅ Features meteorológicas escaladas al espacio del training")
        else:
            logger.warning("   ⚠️  scaler_stats no proporcionado: features SIN escalar")

        return features

    def _scale_features(self, features: dict, scaler_stats: dict) -> dict:
        """
        Aplica la misma normalización (z-score) que se usó en el training.
        scaler_stats = {"feature_name": {"mean": X, "std": Y}, ...}
        """
        scaled = {}
        for feat, value in features.items():
            if feat in scaler_stats:
                mean = scaler_stats[feat]["mean"]
                std = scaler_stats[feat]["std"]
                scaled[feat] = (value - mean) / std if std > 0 else 0.0
            else:
                scaled[feat] = value  # si no está en el scaler, pasar sin tocar
        return scaled


# =============================================================================
# FUNCIÓN DE FALLBACK: datos sintéticos si la API no está disponible
# (útil para desarrollo/testing sin API key real)
# =============================================================================
def get_fallback_weather(city: str, config: dict) -> dict:
    """
    Devuelve features meteorológicas sintéticas (valores medios del training).
    Se usa como fallback cuando la API AEMET no está disponible.
    """
    logger.warning(f"⚠️  Usando datos meteorológicos de FALLBACK para {city}")
    # Valores normalizados ~0 equivalen a la media del training (ya escalado)
    return {
        "weather_rain": 0.0,
        "weather_wind_speed": 0.0,
        "weather_temperature": 0.0,
        "strong_wind": 0.0,
        "adverse_weather": 0.0,
        "temp_category": 0.0,
    }


# =============================================================================
# FUNCIÓN PRINCIPAL para el pipeline
# =============================================================================
def get_weather_features(
    city: str,
    config: dict,
    scaler_stats: Optional[dict] = None,
    api_key: Optional[str] = None,
    use_fallback_if_error: bool = True,
) -> dict:
    """
    Punto de entrada único para obtener features meteorológicas.
    Intenta la API real; si falla y use_fallback_if_error=True, usa fallback.
    """
    try:
        client = AEMETClient(api_key=api_key)
        return client.get_today_weather(city=city, config=config, scaler_stats=scaler_stats)
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos AEMET: {e}")
        if use_fallback_if_error:
            return get_fallback_weather(city, config)
        raise
