"""
data/gold.py — Gold layer: feature engineering and train/val/test split
=============================================================================
Recibe el DataFrame limpio de la capa silver y produce:
  - Selección de features (excluye IDs y target)
  - Split estratificado 70 / 10 / 20
  - Class weights para manejar el desbalanceo (~23% fallos)
  - Estadísticas del scaler (mean/std por feature)
  - Artefactos subidos a Blob: scaler_stats.pkl, feature_cols.pkl
"""
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, save_pickle

logger = get_logger("gold")


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering aplicado entre Silver y Gold:
      - Encoding cíclico: hour_sin/cos, dow_sin/cos
      - Features de fecha: month, quarter
      - OHE: zone, zone_type, product_type
      - Interacciones: 5 términos de producto entre features clave
    Elimina las columnas originales de las que se derivan los encodings.
    """
    df = df.copy()

    # Encoding cíclico para hora y día de la semana
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"]  = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"]  = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # Features de fecha desde la columna 'date'
    if "date" in df.columns:
        dates = pd.to_datetime(df["date"])
        df["month"]   = dates.dt.month.astype(np.float32)
        df["quarter"] = dates.dt.quarter.astype(np.float32)
        df = df.drop(columns=["date"])

    # OHE para columnas categóricas
    for col in ["zone", "zone_type", "product_type"]:
        if col in df.columns:
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=False, dtype=np.float32)
            df = pd.concat([df, dummies], axis=1)
            df = df.drop(columns=[col])

    # Interacciones no lineales (ayudan a XGBoost a arrancar con mejores features)
    df["load_x_rain"]    = df["driver_delivery_load"] * df["weather_rain"]
    df["fragile_x_bulky"] = df["is_fragile"] * df["is_bulky"]
    df["score_x_rfr"]    = df["driver_quality_score"] * df["recipient_failure_rate"]
    df["score_x_load"]   = df["driver_quality_score"] * df["driver_delivery_load"]
    df["rfr_x_retry"]    = df["recipient_failure_rate"] * df["is_retry"]

    return df


def _compute_scaler_stats(df: pd.DataFrame, feature_cols: list) -> dict:
    return {
        col: {"mean": float(df[col].mean()), "std": float(df[col].std())}
        for col in feature_cols
    }


def run(df: pd.DataFrame, config: dict, azure_ctx=None) -> dict:
    """
    Prepara el DataFrame silver para entrenamiento.
    Persiste scaler_stats.pkl y feature_cols.pkl como artefactos gold.
    Retorna dict con arrays listos para train/val/test.
    """
    logger.info("⚙️  Gold: preparando features para entrenamiento")

    # Feature engineering antes de la selección de columnas
    df = engineer_features(df)
    logger.info(f"   Feature engineering aplicado: {df.shape[1]} columnas totales")

    target = config["data"]["target"]
    exclude_cols = config["data"]["exclude_cols"]
    test_size = config["data"]["test_size"]
    val_size = config["data"]["val_size"]
    random_state = config["data"]["random_state"]
    containers = config["azure"]["storage"]["containers"]

    feature_cols = [c for c in df.columns if c not in exclude_cols]

    # Descartar columnas no numéricas (object/string) que no se pueden castear a float32
    non_numeric = [c for c in feature_cols if df[c].dtype == object]
    if non_numeric:
        logger.warning(f"   Columnas descartadas (no numéricas): {non_numeric}")
        feature_cols = [c for c in feature_cols if c not in non_numeric]

    X = df[feature_cols].astype(np.float32)
    y = df[target].astype(np.float32)

    logger.info(f"   Features: {len(feature_cols)} | Filas: {len(df):,} | Fallos: {y.mean():.2%}")

    scaler_stats = _compute_scaler_stats(X, feature_cols)

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )
    relative_val = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval,
        test_size=relative_val, stratify=y_trainval, random_state=random_state,
    )

    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train.values)
    class_weight = {int(c): float(w) for c, w in zip(classes, weights)}

    logger.info(f"   Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
    logger.info(f"   Class weights: {class_weight}")

    if azure_ctx and azure_ctx.blob:
        azure_ctx.blob.upload_pickle(scaler_stats, containers["processed"], "scaler_stats.pkl")
        azure_ctx.blob.upload_pickle(feature_cols, containers["processed"], "feature_cols.pkl")
        logger.info(f"⬆️  Gold artefactos subidos a Blob: {containers['processed']}/")
    else:
        gold_dir = Path(config["paths"]["local_tmp"]) / "gold"
        gold_dir.mkdir(parents=True, exist_ok=True)
        save_pickle(scaler_stats, gold_dir / "scaler_stats.pkl")
        save_pickle(feature_cols, gold_dir / "feature_cols.pkl")
        logger.info(f"📂 Gold artefactos guardados en disco: {gold_dir}")

    mlflow.log_params({
        "gold_n_features": len(feature_cols),
        "gold_train_size": len(X_train),
        "gold_val_size": len(X_val),
        "gold_test_size": len(X_test),
        "gold_train_failure_rate": round(float(y_train.mean()), 4),
        "gold_class_weight_pos": round(class_weight[1], 4),
    })

    logger.info("✅ Gold completado")

    return {
        "X_train": X_train.values, "X_val": X_val.values, "X_test": X_test.values,
        "y_train": y_train.values, "y_val": y_val.values,  "y_test": y_test.values,
        "feature_cols": feature_cols,
        "class_weight": class_weight,
        "scaler_stats": scaler_stats,
    }
