"""
api/routers/predict.py — Endpoints de predicción
"""
import csv
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from api.schemas import (
    AlertRequest,
    AlertsResponse,
    BatchRequest,
    BatchResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionResult,
    SaveDeliveryRequest,
    SaveDeliveryResponse,
    WeatherResponse,
)
from api.services import predictor
from api.services.sms_alerts import process_batch_alerts, _get_logic_app_url

router = APIRouter(prefix="/api/v1", tags=["predictions"])

_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "deliveries_synthetic.csv"
_CSV_COLUMNS = [
    "delivery_id", "date", "hour", "day_of_week", "is_holiday",
    "zone", "zone_type", "recipient_id", "recipient_failure_rate",
    "num_previous_attempts", "driver_id", "driver_quality_score", "driver_delivery_load",
    "product_type", "requires_signature", "is_fragile", "is_bulky", "weight_kg",
    "weather_rain", "weather_wind_speed", "weather_temperature", "is_retry", "delivery_failed",
]


@router.get("/health", response_model=HealthResponse)
def health():
    loaded = predictor.is_model_loaded()
    info = predictor.get_model_info()
    return HealthResponse(
        status="ok" if loaded else "degraded",
        model_loaded=loaded,
        model_name=info.get("model_name"),
        saved_at=info.get("saved_at"),
    )


@router.get("/model/info", response_model=ModelInfoResponse)
def model_info():
    if not predictor.is_model_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no disponible. Ejecuta primero el pipeline de entrenamiento.",
        )
    return ModelInfoResponse(**predictor.get_model_info())


@router.get("/weather/{city}", response_model=WeatherResponse)
def get_weather(city: str):
    """Devuelve datos meteorológicos actuales de AEMET para una ciudad (valores crudos, sin escalar)."""
    valid_cities = {"madrid", "barcelona", "valencia", "sevilla"}
    if city not in valid_cities:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ciudad no válida. Opciones: {sorted(valid_cities)}",
        )
    try:
        return WeatherResponse(**predictor.get_raw_weather(city))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/predict", response_model=BatchResponse)
def predict(request: BatchRequest):
    if not predictor.is_model_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no disponible. Ejecuta primero el pipeline de entrenamiento.",
        )

    deliveries_dicts = [d.model_dump() for d in request.deliveries]

    try:
        predictions = predictor.predict_batch(
            deliveries=deliveries_dicts,
            city=request.city,
            use_aemet=request.use_aemet,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    results = [PredictionResult(**p) for p in predictions]
    high = sum(1 for r in results if r.risk_level == "HIGH")
    medium = sum(1 for r in results if r.risk_level == "MEDIUM")
    low = sum(1 for r in results if r.risk_level == "LOW")

    return BatchResponse(
        total=len(results),
        high=high,
        medium=medium,
        low=low,
        model_name=predictor.get_model_info().get("model_name", "unknown"),
        predictions=results,
    )


@router.post("/deliveries/save", response_model=SaveDeliveryResponse)
def save_delivery(req: SaveDeliveryRequest):
    """Añade una entrega manual al CSV de datos sintéticos."""
    row = {
        "delivery_id": req.delivery_id,
        "date": req.date,
        "hour": req.hour,
        "day_of_week": req.day_of_week,
        "is_holiday": req.is_holiday,
        "zone": req.zone,
        "zone_type": req.zone_type,
        "recipient_id": f"RCP-MANUAL-{uuid.uuid4().hex[:6].upper()}",
        "recipient_failure_rate": 0.2,
        "num_previous_attempts": 1 if req.is_retry else 0,
        "driver_id": f"DRV-MANUAL-{uuid.uuid4().hex[:6].upper()}",
        "driver_quality_score": 0.75,
        "driver_delivery_load": req.driver_delivery_load,
        "product_type": req.product_type,
        "requires_signature": req.requires_signature,
        "is_fragile": req.is_fragile,
        "is_bulky": req.is_bulky,
        "weight_kg": req.weight_kg,
        "weather_rain": req.weather_rain,
        "weather_wind_speed": req.weather_wind_speed,
        "weather_temperature": req.weather_temperature,
        "is_retry": req.is_retry,
        "delivery_failed": "",
    }
    write_header = not _CSV_PATH.exists()
    with open(_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    total_rows = sum(1 for _ in open(_CSV_PATH, encoding="utf-8")) - 1  # -1 header
    return SaveDeliveryResponse(saved=True, delivery_id=req.delivery_id, csv_rows=total_rows)


@router.post("/alerts/send", response_model=AlertsResponse)
async def send_alerts(request: AlertRequest):
    """
    Envía SMS via Azure Logic Apps a todas las entregas con riesgo HIGH (prob >= 0.70).
    Si LOGIC_APP_SMS_URL no está configurada, simula el envío para demo.
    """
    predictions_dicts = [
        {**p.model_dump(), "zone": request.city}
        for p in request.predictions
    ]
    alerts = await process_batch_alerts(predictions_dicts)

    real      = sum(1 for a in alerts if not a["simulated"])
    simulated = sum(1 for a in alerts if a["simulated"])

    return AlertsResponse(
        total_alerts=len(alerts),
        real=real,
        simulated=simulated,
        logic_app_configured=_get_logic_app_url() is not None,
        alerts=[dict(a) for a in alerts],
    )
