"""
tests/test_pipeline.py — Tests unitarios del ML Pipeline
"""
import sys
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.ingestion.ingest import validate_dataframe
from src.inference.predict import classify_risk, inject_weather_features
from src.monitoring.drift import compute_psi


# =============================================================================
# FIXTURES
# =============================================================================
@pytest.fixture
def sample_df():
    np.random.seed(42)
    n = 200
    return pd.DataFrame({
        "delivery_id": [f"dlv_{i}" for i in range(n)],
        "delivery_failed": np.random.randint(0, 2, n),
        "recipient_failure_rate": np.random.randn(n),
        "driver_quality_score": np.random.randn(n),
        "weather_rain": np.random.randn(n),
        "weather_wind_speed": np.random.randn(n),
        "weather_temperature": np.random.randn(n),
        "is_holiday": np.random.randn(n),
        "num_previous_attempts": np.random.randn(n),
    })


@pytest.fixture
def risk_config():
    return {
        "high": {"threshold_multiplier": 1.3, "action": "REAGENDAR_SMS"},
        "medium": {"threshold_multiplier": 1.0, "action": "CAMBIAR_FRANJA"},
        "low": {"action": "ENTREGA_NORMAL"},
    }


# =============================================================================
# TESTS: INGESTA
# =============================================================================
class TestIngestion:
    def test_validate_ok(self, sample_df):
        validate_dataframe(sample_df)  # No debe lanzar

    def test_validate_missing_col(self, sample_df):
        df = sample_df.drop(columns=["weather_rain"])
        with pytest.raises(ValueError, match="Columnas requeridas"):
            validate_dataframe(df)

    def test_validate_only_one_class(self, sample_df):
        df = sample_df.copy()
        df["delivery_failed"] = 0
        with pytest.raises(ValueError, match="solo tiene una clase"):
            validate_dataframe(df)


# =============================================================================
# TESTS: INFERENCIA
# =============================================================================
class TestInference:
    def test_classify_high_risk(self, risk_config):
        level, action = classify_risk(0.8, threshold=0.5, risk_config=risk_config)
        assert level == "HIGH"
        assert action == "REAGENDAR_SMS"

    def test_classify_medium_risk(self, risk_config):
        level, action = classify_risk(0.55, threshold=0.5, risk_config=risk_config)
        assert level == "MEDIUM"
        assert action == "CAMBIAR_FRANJA"

    def test_classify_low_risk(self, risk_config):
        level, action = classify_risk(0.1, threshold=0.5, risk_config=risk_config)
        assert level == "LOW"
        assert action == "ENTREGA_NORMAL"

    def test_inject_weather(self, sample_df):
        weather = {"weather_rain": 1.5, "weather_wind_speed": -0.3}
        feature_cols = ["weather_rain", "weather_wind_speed", "weather_temperature"]
        df_out = inject_weather_features(sample_df, weather, feature_cols)
        assert (df_out["weather_rain"] == 1.5).all()
        assert (df_out["weather_wind_speed"] == -0.3).all()
        # Columna no en weather: no modificada
        assert not (df_out["weather_temperature"] == 1.5).all()


# =============================================================================
# TESTS: MONITORING
# =============================================================================
class TestMonitoring:
    def test_psi_identical_distributions(self):
        data = np.random.randn(1000)
        psi = compute_psi(data, data)
        assert psi < 0.05, f"PSI con distribuciones idénticas debería ser ~0, got {psi}"

    def test_psi_different_distributions(self):
        expected = np.random.normal(0, 1, 1000)
        actual = np.random.normal(5, 1, 1000)   # media muy diferente
        psi = compute_psi(expected, actual)
        assert psi > 0.2, f"PSI con distribuciones muy distintas debería ser >0.2, got {psi}"

    def test_psi_returns_float(self):
        data = np.random.randn(500)
        result = compute_psi(data, data + 0.1)
        assert isinstance(result, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
