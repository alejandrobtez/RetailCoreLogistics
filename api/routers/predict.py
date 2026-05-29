"""
api/routers/predict.py — Endpoints de predicción
"""
from fastapi import APIRouter, HTTPException, status

from api.schemas import (
    AlertRequest,
    AlertsResponse,
    BatchRequest,
    BatchResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionResult,
)
from api.services import predictor
from api.services.sms_alerts import process_batch_alerts, _get_logic_app_url

router = APIRouter(prefix="/api/v1", tags=["predictions"])


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
