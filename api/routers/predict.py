"""
api/routers/predict.py — Endpoints de predicción
"""
from fastapi import APIRouter, HTTPException, status

from api.schemas import (
    BatchRequest,
    BatchResponse,
    HealthResponse,
    ModelInfoResponse,
    PredictionResult,
)
from api.services import predictor

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
