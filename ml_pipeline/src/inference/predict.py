"""
inference/predict.py — Paso 6: inferencia batch (6:50 AM) con Azure
=============================================================================
- Carga el modelo desde Azure Blob Storage
- Carga los paquetes del día desde Blob Storage
- Inyecta datos AEMET en tiempo real (key desde Key Vault)
- Sube el CSV de resultados a Blob Storage
- Inserta las predicciones en Azure SQL Database

Uso:
    python src/inference/predict.py --city madrid
    python src/inference/predict.py --city barcelona --no-aemet
    python src/inference/predict.py --city madrid --input-blob raw-data/today_packages.csv
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger, load_config, today_str
from src.aemet.aemet_client import get_weather_features

logger = get_logger("inference")


def inject_weather_features(df, weather, feature_cols):
    df = df.copy()
    injected = [f for f in weather if f in feature_cols and f in df.columns]
    for feat in injected:
        df[feat] = weather[feat]
    if injected:
        logger.info(f"   🌤️  Features AEMET inyectadas: {injected}")
    return df


def classify_risk(prob: float, threshold: float, risk_config: dict) -> tuple[str, str]:
    high_th = threshold * risk_config["high"]["threshold_multiplier"]
    if prob >= high_th:
        return "HIGH", risk_config["high"]["action"]
    elif prob >= threshold:
        return "MEDIUM", risk_config["medium"]["action"]
    else:
        return "LOW", risk_config["low"]["action"]


def run(
    config: dict,
    azure_ctx=None,
    city: str = "madrid",
    use_aemet: bool = True,
    input_blob: Optional[str] = None,
    local_input: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Inferencia batch completa.
    Lee datos y modelo desde Azure Blob; escribe resultados a Blob y SQL.
    """
    logger.info("🚀 Iniciando inferencia batch")
    containers = config["azure"]["storage"]["containers"]
    risk_config = config["inference"]["risk_levels"]

    # ── Cargar modelo desde Blob ───────────────────────────────────────────
    artifact = None
    if azure_ctx and azure_ctx.blob:
        try:
            artifact = azure_ctx.blob.download_pickle(containers["models"], "best_model.pkl")
            logger.info(f"⬇️  Modelo cargado desde Blob Storage")
        except Exception as e:
            logger.warning(f"No se pudo cargar modelo desde Blob: {e}")

    if artifact is None:
        local_model = Path(config["paths"]["local_tmp"]) / "models" / "best_model.pkl"
        if not local_model.exists():
            raise FileNotFoundError(
                f"Modelo no encontrado en Blob ni en local ({local_model}). "
                "Ejecuta primero el pipeline de entrenamiento."
            )
        import pickle
        with open(local_model, "rb") as f:
            artifact = pickle.load(f)
        logger.info(f"⬇️  Modelo cargado desde disco local: {local_model}")

    pipeline      = artifact["pipeline"]
    feature_cols  = artifact["feature_cols"]
    threshold     = artifact["best_threshold"]
    scaler_stats  = artifact["scaler_stats"]
    model_version = f"{artifact['model_name']}_{artifact.get('saved_at', 'unknown')}"

    # ── Cargar paquetes del día ────────────────────────────────────────────
    df_raw = None
    blob_name = input_blob or f"today_packages_{today_str()}.csv"

    if azure_ctx and azure_ctx.blob:
        try:
            df_raw = azure_ctx.blob.download_csv(containers["raw_data"], blob_name)
            logger.info(f"⬇️  Paquetes cargados desde Blob: {blob_name}")
        except Exception as e:
            logger.warning(f"No se pudo cargar paquetes desde Blob: {e}")

    if df_raw is None and local_input:
        df_raw = pd.read_csv(local_input)
        logger.info(f"⬇️  Paquetes cargados desde local: {local_input}")

    if df_raw is None:
        raise FileNotFoundError(
            f"No se encontraron paquetes en Blob ({blob_name}) ni en local.\n"
            f"Sube el CSV del día con: az storage blob upload "
            f"--container-name {containers['raw_data']} --name {blob_name} --file today.csv"
        )

    # Convertir booleanos
    bool_cols = df_raw.select_dtypes(include="bool").columns
    df_raw[bool_cols] = df_raw[bool_cols].astype(np.float32)
    logger.info(f"   📦 Paquetes a predecir: {len(df_raw):,}")

    # ── AEMET ──────────────────────────────────────────────────────────────
    if use_aemet:
        aemet_key = azure_ctx.get_aemet_key(config) if azure_ctx else None
        weather = get_weather_features(
            city=city, config=config, scaler_stats=scaler_stats,
            api_key=aemet_key, use_fallback_if_error=True,
        )
        df_raw = inject_weather_features(df_raw, weather, feature_cols)

    # ── Predicción ─────────────────────────────────────────────────────────
    missing = [f for f in feature_cols if f not in df_raw.columns]
    if missing:
        raise ValueError(f"Faltan features: {missing[:5]}...")

    X = df_raw[feature_cols].astype(np.float32).values
    y_prob = pipeline.predict_proba(X)[:, 1]

    risk_levels, actions = zip(*[classify_risk(p, threshold, risk_config) for p in y_prob])

    result_df = df_raw.copy()
    result_df["prob_fallo"] = np.round(y_prob, 4)
    result_df["risk_level"] = list(risk_levels)
    result_df["action"]     = list(actions)
    result_df = result_df.sort_values("prob_fallo", ascending=False).reset_index(drop=True)

    # ── Resumen ────────────────────────────────────────────────────────────
    total  = len(result_df)
    high   = (result_df["risk_level"] == "HIGH").sum()
    medium = (result_df["risk_level"] == "MEDIUM").sum()
    low    = (result_df["risk_level"] == "LOW").sum()

    logger.info(f"\n{'='*55}")
    logger.info(f"  📋 RESUMEN OPERACIONAL — {today_str()}")
    logger.info(f"{'='*55}")
    logger.info(f"  Total paquetes:          {total:>6,}")
    logger.info(f"  🔴 REAGENDAR/SMS (HIGH): {high:>6,}  ({high/total:.1%})")
    logger.info(f"  🟡 CAMBIAR FRANJA (MED): {medium:>6,}  ({medium/total:.1%})")
    logger.info(f"  🟢 ENTREGA NORMAL (LOW): {low:>6,}  ({low/total:.1%})")
    logger.info(f"{'='*55}")

    # ── Subir resultados a Blob ────────────────────────────────────────────
    if azure_ctx and azure_ctx.blob:
        out_blob = f"predictions_{today_str()}.csv"
        azure_ctx.blob.upload_csv(result_df, containers["reports"], out_blob)

        high_risk_df = result_df[result_df["risk_level"].isin(["HIGH", "MEDIUM"])]
        azure_ctx.blob.upload_csv(high_risk_df, containers["reports"], f"high_risk_{today_str()}.csv")
        logger.info(f"⬆️  Resultados subidos a Blob: {containers['reports']}/{out_blob}")

    # ── Insertar en Azure SQL ──────────────────────────────────────────────
    if azure_ctx and azure_ctx.sql:
        azure_ctx.sql.insert_predictions(result_df, city=city, model_version=model_version)

    # ── Guardar local también (backup / debugging) ─────────────────────────
    reports_dir = Path(config["paths"]["local_tmp"]) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    local_out = reports_dir / f"predictions_{today_str()}.csv"
    result_df.to_csv(local_out, index=False)
    logger.info(f"💾 Backup local: {local_out}")

    return result_df


def main():
    parser = argparse.ArgumentParser(description="RetailCore — Inferencia batch")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--city", default="madrid",
                        choices=["madrid", "barcelona", "valencia", "sevilla"])
    parser.add_argument("--no-aemet", action="store_true")
    parser.add_argument("--input-blob", default=None,
                        help="Nombre del blob en raw-data (ej: today_packages.csv)")
    parser.add_argument("--local-input", default=None,
                        help="CSV local como fallback")
    args = parser.parse_args()

    config = load_config(args.config)

    from src.azure.azure_client import AzureContext
    azure_ctx = AzureContext.from_config(config)

    run(
        config=config,
        azure_ctx=azure_ctx,
        city=args.city,
        use_aemet=not args.no_aemet,
        input_blob=args.input_blob,
        local_input=Path(args.local_input) if args.local_input else None,
    )


if __name__ == "__main__":
    main()
