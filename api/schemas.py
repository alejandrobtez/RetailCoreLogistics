"""
api/schemas.py — Modelos Pydantic de entrada y salida de la API
"""
from typing import Optional
from pydantic import BaseModel, Field


class DeliveryRecord(BaseModel):
    delivery_id: str
    date: Optional[str] = Field(
        default=None,
        description="Fecha de la entrega YYYY-MM-DD (default: hoy). Usada para extraer mes y trimestre.",
    )
    hour: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6, description="0=Lunes … 6=Domingo")
    is_holiday: int = Field(ge=0, le=1)
    zone: str = Field(
        description="Ciudad: madrid | barcelona | valencia | sevilla",
        pattern="^(madrid|barcelona|valencia|sevilla)$",
    )
    zone_type: str = Field(
        description="Tipo de zona: residential | offices | historic_center | industrial",
        pattern="^(residential|offices|historic_center|industrial)$",
    )
    recipient_failure_rate: float = Field(ge=0.0, le=1.0)
    num_previous_attempts: int = Field(ge=0)
    driver_quality_score: float = Field(ge=0.0, le=1.0)
    driver_delivery_load: int = Field(ge=0)
    product_type: str = Field(
        description="Tipo de producto: standard | fragile | bulky | high_value | signature_required",
        pattern="^(standard|fragile|bulky|high_value|signature_required)$",
    )
    requires_signature: int = Field(ge=0, le=1)
    is_fragile: int = Field(ge=0, le=1)
    is_bulky: int = Field(ge=0, le=1)
    weight_kg: float = Field(gt=0.0)
    weather_rain: int = Field(ge=0, le=1, default=0)
    weather_wind_speed: float = Field(default=0.0)
    weather_temperature: float = Field(default=15.0)
    is_retry: int = Field(ge=0, le=1)

    model_config = {"json_schema_extra": {"example": {
        "delivery_id": "dlv_00000042",
        "date": "2024-05-28",
        "hour": 10,
        "day_of_week": 0,
        "is_holiday": 0,
        "zone": "madrid",
        "zone_type": "historic_center",
        "recipient_failure_rate": 0.31,
        "num_previous_attempts": 1,
        "driver_quality_score": 0.72,
        "driver_delivery_load": 22,
        "product_type": "fragile",
        "requires_signature": 0,
        "is_fragile": 1,
        "is_bulky": 0,
        "weight_kg": 4.5,
        "weather_rain": 1,
        "weather_wind_speed": 3.2,
        "weather_temperature": 11.0,
        "is_retry": 1,
    }}}


class PredictionResult(BaseModel):
    delivery_id: str
    prob_fallo: float
    risk_level: str = Field(description="HIGH | MEDIUM | LOW")
    action: str = Field(description="REAGENDAR_SMS | CAMBIAR_FRANJA | ENTREGA_NORMAL")
    shap_reason: Optional[str] = Field(
        default=None,
        description="Explicación SHAP (disponible cuando se integre el módulo de explicabilidad)"
    )


class BatchRequest(BaseModel):
    city: str = Field(
        default="madrid",
        description="Ciudad para obtener datos AEMET en tiempo real",
        pattern="^(madrid|barcelona|valencia|sevilla)$",
    )
    use_aemet: bool = Field(
        default=True,
        description="Si True, sobreescribe los campos weather_* con datos AEMET en tiempo real",
    )
    deliveries: list[DeliveryRecord] = Field(min_length=1)

    model_config = {"json_schema_extra": {"example": {
        "city": "madrid",
        "use_aemet": False,
        "deliveries": [DeliveryRecord.model_config["json_schema_extra"]["example"]],
    }}}


class BatchResponse(BaseModel):
    total: int
    high: int
    medium: int
    low: int
    model_name: str
    predictions: list[PredictionResult]


class AlertRequest(BaseModel):
    predictions: list[PredictionResult] = Field(description="Lista de predicciones del batch")
    city: str = Field(default="madrid")


class AlertResult(BaseModel):
    sent: bool
    simulated: bool
    delivery_id: str
    phone: str
    message: str
    timestamp: str
    detail: str


class AlertsResponse(BaseModel):
    total_alerts: int
    real: int
    simulated: int
    logic_app_configured: bool
    alerts: list[AlertResult]


class WeatherResponse(BaseModel):
    city: str
    weather_rain: int = Field(description="0 = sin lluvia, 1 = lluvia")
    weather_rain_mm: float = Field(description="Precipitación en mm")
    weather_wind_speed: float = Field(description="Velocidad del viento en m/s")
    weather_temperature: float = Field(description="Temperatura en °C")
    source: str = Field(description="aemet | fallback")


class SaveDeliveryRequest(BaseModel):
    delivery_id: str
    date: str
    hour: int
    day_of_week: int
    is_holiday: int
    zone: str
    zone_type: str
    product_type: str
    requires_signature: int
    is_fragile: int
    is_bulky: int
    weight_kg: float
    driver_delivery_load: int
    is_retry: int
    weather_rain: int
    weather_wind_speed: float
    weather_temperature: float


class SaveDeliveryResponse(BaseModel):
    saved: bool
    delivery_id: str
    csv_rows: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None
    saved_at: Optional[str] = None


class ModelInfoResponse(BaseModel):
    model_name: str
    saved_at: str
    n_features: int
    feature_cols: list[str]
    best_threshold: float
    metrics: dict
