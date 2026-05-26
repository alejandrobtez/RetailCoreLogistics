"""
pipeline.py — Orquestador principal del ML Pipeline de RetailCore
=============================================================================
Ejecuta todos los pasos en orden:
  1. Ingesta       → carga y valida el dataset
  2. Preprocesado  → split, class weights, scaler stats
  3. Entrenamiento → LR, RF, XGBoost
  4. Evaluación    → selecciona el mejor modelo
  5. Guardado      → .pkl + MLflow Model Registry
  (6. Inferencia   → se ejecuta por separado a las 6:50 AM)

Uso:
    # Entrenamiento completo
    python pipeline.py

    # Con config personalizada
    python pipeline.py --config configs/config.yaml

    # Entrenamiento + inferencia inmediata sobre un CSV del día
    python pipeline.py --infer --infer-input data/raw/today_packages.csv --city madrid

MLflow UI (ejecutar en otra terminal):
    mlflow ui --backend-store-uri mlruns
    → http://localhost:5000
=============================================================================
"""
import argparse
import sys
from pathlib import Path

import mlflow

# Asegurar que src/ esté en el path
sys.path.append(str(Path(__file__).resolve().parent))

from src.utils import get_logger, load_config
from src.ingestion import ingest
from src.preprocessing import preprocess
from src.training import train, save_model
from src.evaluation import evaluate

logger = get_logger("pipeline")


def run_training_pipeline(config: dict) -> Path:
    """
    Ejecuta el pipeline de entrenamiento completo.
    Retorna la ruta al modelo guardado.
    """
    mlflow_cfg = config["mlflow"]
    mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
    mlflow.set_experiment(mlflow_cfg["experiment_name"])

    with mlflow.start_run(run_name="full_training_pipeline") as run:
        logger.info("=" * 60)
        logger.info("  RETAILCORE ML PIPELINE — ENTRENAMIENTO")
        logger.info(f"  MLflow Run ID: {run.info.run_id}")
        logger.info("=" * 60)

        # ── PASO 1: Ingesta ───────────────────────────────────────────────────
        logger.info("\n[1/5] 📥 INGESTA")
        validated_path = ingest.run(config)

        # ── PASO 2: Preprocesado ──────────────────────────────────────────────
        logger.info("\n[2/5] 🔧 PREPROCESADO")
        data = preprocess.run(validated_path, config)

        # ── PASO 3: Entrenamiento ─────────────────────────────────────────────
        logger.info("\n[3/5] 🧠 ENTRENAMIENTO")
        trained_models = train.run(data, config)

        # ── PASO 4: Evaluación ────────────────────────────────────────────────
        logger.info("\n[4/5] 📊 EVALUACIÓN")
        eval_result = evaluate.run(trained_models, data, config)

        # ── PASO 5: Guardado ──────────────────────────────────────────────────
        logger.info("\n[5/5] 💾 GUARDADO")
        model_path = save_model.run(eval_result, data, config)

        logger.info("\n" + "=" * 60)
        logger.info("  ✅ PIPELINE COMPLETADO")
        logger.info(f"  Mejor modelo: {eval_result['best_name'].upper()}")
        logger.info(f"  Avg Precision: {eval_result['best_metrics']['avg_precision']:.4f}")
        logger.info(f"  Modelo guardado: {model_path}")
        logger.info(f"  MLflow UI: http://localhost:5000")
        logger.info("=" * 60)

        return model_path


def run_inference(model_path: Path, input_path: Path, city: str, config: dict):
    """Ejecuta la inferencia batch tras el entrenamiento."""
    from src.inference import predict
    logger.info(f"\n[6/6] 🚀 INFERENCIA BATCH")
    predict.run(
        input_path=input_path,
        model_path=model_path,
        config=config,
        city=city,
        use_aemet=True,
        use_fallback_if_error=True,
    )


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="RetailCore ML Pipeline — Entrenamiento y predicción de fallos de entrega"
    )
    parser.add_argument(
        "--config", default="configs/config.yaml",
        help="Ruta al archivo de configuración (default: configs/config.yaml)"
    )
    parser.add_argument(
        "--infer", action="store_true",
        help="Ejecutar inferencia batch inmediatamente después del entrenamiento"
    )
    parser.add_argument(
        "--infer-input", default=None,
        help="CSV con paquetes del día (requerido si --infer)"
    )
    parser.add_argument(
        "--city", default="madrid",
        choices=["madrid", "barcelona", "valencia", "sevilla"],
        help="Ciudad para datos de AEMET (default: madrid)"
    )

    args = parser.parse_args()
    config = load_config(args.config)

    # Entrenamiento
    model_path = run_training_pipeline(config)

    # Inferencia opcional
    if args.infer:
        if not args.infer_input:
            logger.error("--infer-input es requerido cuando se usa --infer")
            sys.exit(1)
        run_inference(model_path, Path(args.infer_input), args.city, config)


if __name__ == "__main__":
    main()
