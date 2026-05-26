"""
evaluation/evaluate.py — Paso 4: evaluación y selección del mejor modelo
Idéntico a la versión anterior + sube el reporte de comparativa a Blob Storage.
"""
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, classification_report,
    confusion_matrix, f1_score, roc_auc_score,
)

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.utils import get_logger

logger = get_logger("evaluation")


def _evaluate_single(name, pipeline, X_test, y_test, config):
    th_cfg     = config["evaluation"]["threshold_search"]
    thresholds = np.arange(th_cfg["min"], th_cfg["max"], th_cfg["step"])
    y_prob     = pipeline.predict_proba(X_test)[:, 1]

    roc_auc  = roc_auc_score(y_test, y_prob)
    avg_prec = average_precision_score(y_test, y_prob)

    f1_scores = [f1_score(y_test, (y_prob >= t).astype(int), pos_label=1, zero_division=0)
                 for t in thresholds]
    best_threshold = float(thresholds[np.argmax(f1_scores)])
    y_pred         = (y_prob >= best_threshold).astype(int)
    f1_opt         = float(max(f1_scores))

    cm             = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    recall         = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision      = tp / (tp + fp) if (tp + fp) > 0 else 0.0

    daily              = config["inference"]["batch_size"]
    expected_failures  = int(daily * y_test.mean())
    detected           = int(expected_failures * recall)
    false_alarms       = int((daily - expected_failures) * (fp / max(tn + fp, 1)))

    logger.info(f"   {name:25s} | AUC={roc_auc:.4f} | AP={avg_prec:.4f} | "
                f"F1={f1_opt:.4f} | Recall={recall:.2%} | Threshold={best_threshold:.2f}")

    return dict(
        roc_auc=round(roc_auc, 4), avg_precision=round(avg_prec, 4),
        f1_optimal=round(f1_opt, 4), best_threshold=round(best_threshold, 3),
        recall_fallo=round(recall, 4), precision_fallo=round(precision, 4),
        tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn),
        daily_detected=detected, daily_false_alarms=false_alarms,
    )


def _get_feature_importance(pipeline, feature_cols):
    clf = pipeline.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        return pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    if hasattr(clf, "coef_"):
        return pd.Series(np.abs(clf.coef_[0]), index=feature_cols).sort_values(ascending=False)
    return None


def run(trained_models, data, config, azure_ctx=None):
    logger.info("📊 Evaluando modelos en test set")

    X_test, y_test   = data["X_test"], data["y_test"]
    feature_cols     = data["feature_cols"]
    primary_metric   = config["evaluation"]["primary_metric"]
    containers       = config["azure"]["storage"]["containers"]

    all_metrics = {}
    logger.info(f"   {'Modelo':25s} | {'AUC':>7} | {'AP':>7} | {'F1':>7} | {'Recall':>7}")
    logger.info("   " + "─" * 65)

    for name, pipeline in trained_models.items():
        metrics = _evaluate_single(name, pipeline, X_test, y_test, config)
        all_metrics[name] = metrics
        mlflow.log_metrics({f"{name}__{k}": v for k, v in metrics.items()
                            if isinstance(v, (int, float))})

    best_name     = max(all_metrics, key=lambda k: all_metrics[k][primary_metric])
    best_metrics  = all_metrics[best_name]
    best_pipeline = trained_models[best_name]

    logger.info(f"\n🏆 MEJOR MODELO: {best_name.upper()}")
    logger.info(f"   {primary_metric}: {best_metrics[primary_metric]:.4f}")
    logger.info(f"   Recall fallos: {best_metrics['recall_fallo']:.2%} | "
                f"Detectados/día: ~{best_metrics['daily_detected']:,}")

    y_prob_best = best_pipeline.predict_proba(X_test)[:, 1]
    y_pred_best = (y_prob_best >= best_metrics["best_threshold"]).astype(int)
    logger.info(f"\n{classification_report(y_test, y_pred_best, target_names=['Éxito', 'Fallo'])}")

    fi = _get_feature_importance(best_pipeline, feature_cols)
    if fi is not None:
        logger.info(f"\n  🏅 Top 10 features ({best_name}):")
        for feat, imp in fi.head(10).items():
            logger.info(f"    {feat:<35} {imp:.4f} {'█' * int(imp*150)}")

    comparison_df = pd.DataFrame(all_metrics).T

    # ── Subir reporte a Blob ───────────────────────────────────────────────
    if azure_ctx and azure_ctx.blob:
        azure_ctx.blob.upload_csv(comparison_df, containers["reports"], "model_comparison.csv")
        logger.info(f"⬆️  Comparativa subida a Blob: {containers['reports']}/model_comparison.csv")
    else:
        tmp_dir = Path(config["paths"]["local_tmp"]) / "reports"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        comparison_df.to_csv(tmp_dir / "model_comparison.csv")

    mlflow.log_metrics({
        "best_roc_auc": best_metrics["roc_auc"],
        "best_avg_precision": best_metrics["avg_precision"],
        "best_f1": best_metrics["f1_optimal"],
        "best_recall_fallo": best_metrics["recall_fallo"],
        "best_threshold": best_metrics["best_threshold"],
    })
    mlflow.log_param("best_model_name", best_name)

    logger.info("✅ Evaluación completada")

    return {
        "best_name": best_name,
        "best_pipeline": best_pipeline,
        "best_metrics": best_metrics,
        "all_metrics": all_metrics,
        "feature_importance": fi,
    }
