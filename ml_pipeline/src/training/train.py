"""
training/train.py — Paso 3: entrenamiento de todos los modelos candidatos
=============================================================================
Responsabilidades:
  - Entrenar LR, RF y XGBoost con los parámetros de config.yaml
  - Loguear hiperparámetros a MLflow
  - Retornar los pipelines entrenados listos para evaluación
"""
import sys
from pathlib import Path
from typing import Generator

import mlflow
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger

logger = get_logger("training")

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost no disponible. Usando GradientBoosting como fallback.")


def _build_logistic_regression(cfg: dict, class_weight: dict, random_state: int) -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            C=cfg.get("C", 0.1),
            max_iter=cfg.get("max_iter", 500),
            class_weight=class_weight,
            random_state=random_state,
            n_jobs=-1,
        ))
    ])


def _build_random_forest(cfg: dict, class_weight: dict, random_state: int) -> Pipeline:
    return Pipeline([
        ("clf", RandomForestClassifier(
            n_estimators=cfg.get("n_estimators", 300),
            max_depth=cfg.get("max_depth", 12),
            min_samples_leaf=cfg.get("min_samples_leaf", 10),
            class_weight=class_weight,
            n_jobs=-1,
            random_state=random_state,
        ))
    ])


def _build_xgboost(cfg: dict, class_weight: dict, random_state: int) -> Pipeline:
    scale_pos_weight = class_weight.get(0, 1.0) / class_weight.get(1, 1.0)
    if XGBOOST_AVAILABLE:
        clf = xgb.XGBClassifier(
            n_estimators=cfg.get("n_estimators", 400),
            max_depth=cfg.get("max_depth", 6),
            learning_rate=cfg.get("learning_rate", 0.05),
            subsample=cfg.get("subsample", 0.8),
            colsample_bytree=cfg.get("colsample_bytree", 0.8),
            scale_pos_weight=scale_pos_weight,
            eval_metric="aucpr",
            random_state=random_state,
            n_jobs=-1,
        )
    else:
        logger.warning("Usando GradientBoostingClassifier como fallback de XGBoost")
        clf = GradientBoostingClassifier(
            n_estimators=cfg.get("n_estimators", 300),
            max_depth=cfg.get("max_depth", 5),
            learning_rate=cfg.get("learning_rate", 0.05),
            subsample=cfg.get("subsample", 0.8),
            random_state=random_state,
        )
    return Pipeline([("clf", clf)])


BUILDERS = {
    "logistic_regression": _build_logistic_regression,
    "random_forest": _build_random_forest,
    "xgboost": _build_xgboost,
}


def _iter_enabled_models(config: dict) -> Generator:
    """Itera sobre los modelos habilitados en config.yaml."""
    candidates = config["models"]["candidates"]
    for name, cfg in candidates.items():
        if cfg.get("enabled", True):
            yield name, cfg


def run(data: dict, config: dict) -> dict[str, Pipeline]:
    """
    Entrena todos los modelos habilitados.
    Retorna un dict {nombre: pipeline_entrenado}.
    """
    logger.info("🧠 Iniciando entrenamiento de modelos")

    X_train = data["X_train"]
    y_train = data["y_train"]
    class_weight = data["class_weight"]
    random_state = config["models"]["random_state"]

    trained_models = {}

    for name, cfg in _iter_enabled_models(config):
        if name not in BUILDERS:
            logger.warning(f"Modelo '{name}' no reconocido, se omite")
            continue

        logger.info(f"   🔄 Entrenando: {name.upper()}")

        pipeline = BUILDERS[name](cfg, class_weight, random_state)
        pipeline.fit(X_train, y_train)

        # Loguear hiperparámetros a MLflow (prefijados con el nombre del modelo)
        mlflow.log_params({f"{name}__{k}": v for k, v in cfg.items() if k != "enabled"})

        trained_models[name] = pipeline
        logger.info(f"   ✅ {name} entrenado")

    logger.info(f"✅ {len(trained_models)} modelos entrenados")
    return trained_models
