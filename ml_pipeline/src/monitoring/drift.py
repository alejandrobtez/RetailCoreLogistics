"""
monitoring/drift.py — Monitorización de data drift y degradación del modelo
=============================================================================
Detecta cuándo el modelo empieza a volverse obsoleto comparando la distribución
de los datos de hoy con los del training (usando PSI - Population Stability Index).

PSI < 0.1  → Sin drift significativo
PSI 0.1-0.2 → Drift moderado (vigilar)
PSI > 0.2  → Drift severo (reentrenar)
=============================================================================
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger

logger = get_logger("monitoring")


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """
    Calcula el Population Stability Index entre distribución esperada (training)
    y actual (producción). Valores > 0.2 indican drift severo.
    """
    eps = 1e-8
    bins = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    bins[0] -= eps
    bins[-1] += eps

    exp_counts = np.histogram(expected, bins=bins)[0]
    act_counts = np.histogram(actual, bins=bins)[0]

    exp_pct = exp_counts / (len(expected) + eps)
    act_pct = act_counts / (len(actual) + eps)

    exp_pct = np.where(exp_pct == 0, eps, exp_pct)
    act_pct = np.where(act_pct == 0, eps, act_pct)

    psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(psi)


def check_drift(
    train_df: pd.DataFrame,
    current_df: pd.DataFrame,
    feature_cols: list,
    config: dict,
) -> dict:
    """
    Compara distribuciones entre datos de entrenamiento y datos actuales.
    Devuelve un dict con el PSI de cada feature y una alerta global.
    """
    threshold = config["monitoring"]["drift_threshold"]
    min_samples = config["monitoring"]["min_samples_for_drift"]

    if len(current_df) < min_samples:
        logger.warning(f"Muestras insuficientes para análisis de drift: {len(current_df)} < {min_samples}")
        return {"status": "insufficient_data", "details": {}}

    results = {}
    alerts = []

    numeric_cols = [c for c in feature_cols
                    if c in train_df.columns and c in current_df.columns
                    and train_df[c].dtype in [np.float32, np.float64, float]]

    for col in numeric_cols[:20]:  # top 20 features para no sobrecargar
        psi = compute_psi(train_df[col].values, current_df[col].values)
        severity = "OK" if psi < 0.1 else "WARN" if psi < 0.2 else "ALERT"
        results[col] = {"psi": round(psi, 4), "severity": severity}

        if severity == "ALERT":
            alerts.append(col)
            logger.warning(f"   ⚠️  Drift detectado en '{col}': PSI={psi:.4f}")

    overall_psi = np.mean([v["psi"] for v in results.values()])
    status = "OK" if not alerts else "ALERT"

    logger.info(f"   PSI medio: {overall_psi:.4f} | Features con drift: {len(alerts)}")
    if alerts:
        logger.warning(f"   🔴 Features con drift severo: {alerts}")
        logger.warning("   💡 Considera reentrenar el modelo con datos recientes")

    return {
        "status": status,
        "overall_psi": round(overall_psi, 4),
        "features_with_drift": alerts,
        "details": results,
    }
