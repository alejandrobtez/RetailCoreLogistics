"""
pipeline.py — Orquestador principal del ML Pipeline (Azure Edition)
=============================================================================
Pasos:
  1. Ingesta       → lee CSV desde Azure Blob Storage
  2. Preprocesado  → split, class weights, scaler stats
  3. Entrenamiento → LR, RF, XGBoost
  4. Evaluación    → selecciona el mejor modelo
  5. Guardado      → Blob Storage + Azure SQL + MLflow Registry
  [6. Inferencia   → opcional, o ejecutar predict.py por separado]

Uso:
    python pipeline.py                                      # entrenamiento
    python pipeline.py --infer --city madrid               # + inferencia
    python pipeline.py --config configs/config.yaml        # config custom

MLflow UI:
    mlflow ui --backend-store-uri mlruns   →  http://localhost:5000
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import mlflow

sys.path.append(str(Path(__file__).resolve().parent))

from src.utils import get_logger, load_config
from src.azure.azure_client import AzureContext
from src.ingestion import ingest
from src.preprocessing import preprocess
from src.training import train, save_model
from src.evaluation import evaluate

logger = get_logger("pipeline")


def run_training_pipeline(config: dict, azure_ctx: AzureContext) -> str:
    """
    Ejecuta el pipeline de entrenamiento completo.
    Retorna el blob_name del modelo guardado.
    """
    mlflow_cfg = config["azure"]["mlflow"]
    tracking_uri = mlflow_cfg.get("tracking_uri") or "mlruns"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    with mlflow.start_run(run_name="full_training_pipeline") as run:
        logger.info("=" * 60)
        logger.info("  RETAILCORE ML PIPELINE — ENTRENAMIENTO (Azure)")
        logger.info(f"  MLflow Run ID: {run.info.run_id}")
        logger.info("=" * 60)

        # ── 1. Ingesta ────────────────────────────────────────────────────
        logger.info("\n[1/5] 📥 INGESTA (Azure Blob Storage)")
        df = ingest.run(config, azure_ctx=azure_ctx)

        # ── 2. Preprocesado ───────────────────────────────────────────────
        logger.info("\n[2/5] 🔧 PREPROCESADO")
        data = preprocess.run(df, config, azure_ctx=azure_ctx)

        # ── 3. Entrenamiento ──────────────────────────────────────────────
        logger.info("\n[3/5] 🧠 ENTRENAMIENTO")
        trained_models = train.run(data, config)

        # ── 4. Evaluación ─────────────────────────────────────────────────
        logger.info("\n[4/5] 📊 EVALUACIÓN")
        eval_result = evaluate.run(trained_models, data, config, azure_ctx=azure_ctx)

        # ── 5. Guardado ───────────────────────────────────────────────────
        logger.info("\n[5/5] 💾 GUARDADO (Blob + SQL + MLflow)")
        model_blob = save_model.run(eval_result, data, config, azure_ctx=azure_ctx)

        logger.info("\n" + "=" * 60)
        logger.info("  ✅ PIPELINE COMPLETADO")
        logger.info(f"  Mejor modelo: {eval_result['best_name'].upper()}")
        logger.info(f"  Avg Precision: {eval_result['best_metrics']['avg_precision']:.4f}")
        logger.info(f"  Modelo en Blob: {config['azure']['storage']['containers']['models']}/{model_blob}")
        logger.info(f"  MLflow UI: http://localhost:5000")
        logger.info("=" * 60)

        return model_blob


def main():
    parser = argparse.ArgumentParser(description="RetailCore ML Pipeline (Azure)")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--infer", action="store_true",
                        help="Ejecutar inferencia batch tras el entrenamiento")
    parser.add_argument("--city", default="madrid",
                        choices=["madrid", "barcelona", "valencia", "sevilla"])
    args = parser.parse_args()

    config = load_config(args.config)

    # Inicializar contexto Azure (Blob + SQL + Key Vault)
    azure_ctx = AzureContext.from_config(config)

    # Entrenamiento
    model_blob = run_training_pipeline(config, azure_ctx)

    # Inferencia opcional
    if args.infer:
        from src.inference.predict import run as run_inference
        logger.info(f"\n[6/6] 🚀 INFERENCIA BATCH — ciudad: {args.city}")
        run_inference(config=config, azure_ctx=azure_ctx, city=args.city, use_aemet=True)


if __name__ == "__main__":
    main()
