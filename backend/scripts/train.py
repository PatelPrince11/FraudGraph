"""Train XGBoost on the time split and write model + metrics.

Three-way split, all by time:
  train period  -> fit trees
  last 15% of train period (validation) -> early stopping + threshold choice
  test period   -> reported metrics, touched exactly once
Picking the threshold on test would be tuning on the exam: optimistic numbers.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score

from app.features import FEATURE_COLS
from app.model import MODEL_DIR, FraudModel

FEATURES = Path(__file__).resolve().parents[2] / "data" / "processed" / "features.parquet"
ALERT_BUDGET = 0.005  # analysts review the top 0.5% of transactions
VAL_FRACTION = 0.15


def split(df: pd.DataFrame):
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    cutoff = train["ts"].quantile(1 - VAL_FRACTION)
    return train[train["ts"] < cutoff], train[train["ts"] >= cutoff], test


def at_threshold(y, scores, thr):
    pred = scores >= thr
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    precision = tp / max(tp + fp, 1); recall = tp / max(tp + fn, 1)
    return {
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(2 * precision * recall / max(precision + recall, 1e-9), 4),
        "false_negative_rate": round(fn / max(tp + fn, 1), 4),
        "alert_rate": round(float(pred.mean()), 5), "tp": tp, "fp": fp, "fn": fn,
    }


def latency(model: FraudModel, sample: pd.DataFrame, n: int = 500):
    """p50/p95 for scoring ONE row (what the API does) + batch throughput."""
    times = []
    for i in range(n):
        row = sample.iloc[[i % len(sample)]]
        t0 = time.perf_counter(); model.score(row); times.append(time.perf_counter() - t0)
    t0 = time.perf_counter(); model.score(sample); batch_s = time.perf_counter() - t0
    return {
        "p50_ms": round(1000 * float(np.percentile(times, 50)), 3),
        "p95_ms": round(1000 * float(np.percentile(times, 95)), 3),
        "batch_rows_per_sec": int(len(sample) / batch_s),
    }


def main(features_path: Path = FEATURES, model_dir: Path = MODEL_DIR):
    df = pd.read_parquet(features_path)
    tr, va, te = split(df)
    print(f"train={len(tr):,} val={len(va):,} test={len(te):,}  "
          f"fraud rate train={tr.is_fraud.mean():.4%} test={te.is_fraud.mean():.4%}")

    clf = xgb.XGBClassifier(
        n_estimators=2000, learning_rate=0.05, max_depth=6, subsample=0.8,
        colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
        eval_metric="aucpr", early_stopping_rounds=100, n_jobs=-1,
    )
    clf.fit(tr[FEATURE_COLS], tr["is_fraud"],
            eval_set=[(va[FEATURE_COLS], va["is_fraud"])], verbose=200)

    va_scores = clf.predict_proba(va[FEATURE_COLS])[:, 1]  # uses best_iteration
    threshold = float(np.quantile(va_scores, 1 - ALERT_BUDGET))

    model_dir.mkdir(parents=True, exist_ok=True)
    # Keep only trees up to the best validation round; later trees were overfitting.
    best = clf.get_booster()[: clf.best_iteration + 1]
    best.save_model(model_dir / "model.json")
    (model_dir / "meta.json").write_text(json.dumps({
        "threshold": threshold, "alert_budget": ALERT_BUDGET,
        "best_iteration": int(clf.best_iteration), "features": FEATURE_COLS,
    }, indent=2))

    model = FraudModel.load(model_dir)
    y, s = te["is_fraud"].to_numpy(), model.score(te)
    metrics = {
        "test_pr_auc": round(average_precision_score(y, s), 4),
        "test_roc_auc": round(roc_auc_score(y, s), 4),
        # A model that can't beat "flag big amounts" isn't learning behaviour.
        "baseline_amount_only_pr_auc": round(average_precision_score(y, te["amt"]), 4),
        "at_threshold": at_threshold(y, s, threshold),
        "latency": latency(model, te.sample(min(5000, len(te)), random_state=0)),
    }
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))

    top = np.argsort(-s)[:1]
    print("\nHighest-risk test transaction explained:")
    print(json.dumps(model.explain(te.iloc[top])[0], indent=2))


if __name__ == "__main__":
    main()
