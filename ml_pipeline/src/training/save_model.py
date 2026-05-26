"""
training/save_model.py — Paso 5: guardado en Azure Blob Storage + MLflow Registry
=============================================================================
Guarda el modelo en:
  1. Azure Blob Storage → container "models" (producción)
  2. MLflow Model Registry → trazabilidad y versionado
  3. Local /tmp (caché para inferencia inmediata)
"""
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
from sklearn.pipeline import Pipeline

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, save_pickle, now_str

logger = get_logger("save_model")


def run(eval_result: dict, data: dict, config: dict, azure_ctx=None) -> str:
    """
    Serializa el mejor modelo y lo sube a Blob Storage.
    Retorna el blob_name del modelo guardado (para cargarlo en inferencia).
    """
    tmp_dir = Path(config["paths"]["local_tmp"]) / "models"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    best_name     = eval_result["best_name"]
    best_pipeline = eval_result["best_pipeline"]
    best_metrics  = eval_result["best_metrics"]
    feature_cols  = data["feature_cols"]
    scaler_stats  = data["scaler_stats"]

    artifact = {
        "pipeline":       best_pipeline,
        "feature_cols":   feature_cols,
        "scaler_stats":   scaler_stats,
        "best_threshold": best_metrics["best_threshold"],
        "metrics":        best_metrics,
        "model_name":     best_name,
        "target":         config["data"]["target"],
        "saved_at":       now_str(),
        "config_snapshot": {
            "batch_size":  config["inference"]["batch_size"],
            "risk_levels": config["inference"]["risk_levels"],
        }
    }

    # ── Guardar local (temporal) ───────────────────────────────────────────
    local_path = tmp_dir / f"retailcore_{best_name}.pkl"
    save_pickle(artifact, local_path)
    logger.info(f"💾 PKL local (caché): {local_path}")

    # ── Subir a Azure Blob Storage ─────────────────────────────────────────
    containers = config["azure"]["storage"]["containers"]
    blob_name  = f"retailcore_{best_name}.pkl"
    best_blob  = "best_model.pkl"

    if azure_ctx and azure_ctx.blob:
        azure_ctx.blob.upload_pickle(artifact, containers["models"], blob_name)
        azure_ctx.blob.upload_pickle(artifact, containers["models"], best_blob)
        logger.info(f"⬆️  Modelo subido a Blob: {containers['models']}/{blob_name}")
        logger.info(f"⬆️  Alias subido a Blob:  {containers['models']}/{best_blob}")
    else:
        logger.warning("⚠️  Blob Storage no disponible: modelo solo en local")

    # ── Guardar métricas en Azure SQL ──────────────────────────────────────
    if azure_ctx and azure_ctx.sql:
        run_id = mlflow.active_run().info.run_id if mlflow.active_run() else ""
        azure_ctx.sql.insert_model_metrics(best_metrics, best_name, mlflow_run_id=run_id)

    # ── Registrar en MLflow Model Registry ────────────────────────────────
    if config["azure"]["mlflow"]["register_best_model"]:
        try:
            mlflow.sklearn.log_model(
                sk_model=best_pipeline,
                artifact_path="model",
                registered_model_name=config["azure"]["mlflow"]["model_name"],
            )
            logger.info(f"📦 Registrado en MLflow: {config['azure']['mlflow']['model_name']}")
        except Exception as e:
            logger.warning(f"MLflow Registry no disponible: {e}")

    mlflow.log_artifact(str(local_path), artifact_path="model_pkl")
    logger.info("✅ Guardado completado")

    return best_blob   # blob_name del modelo canónico
