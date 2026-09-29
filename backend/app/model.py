"""Load the trained model, score transactions, and explain each score.

Explanations use XGBoost's built-in TreeSHAP (pred_contribs=True): for each row it
returns one number per feature plus a bias term, and they sum EXACTLY to the model's
raw log-odds output. Positive = pushed toward fraud, negative = pushed toward legit.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from app.features import FEATURE_COLS

from app.config import MODEL_DIR  # noqa: E402  (re-exported for scripts)

# Human-readable labels for the investigation UI.
LABELS = {
    "amt": "Amount", "log_amt": "Amount", "amt_z_card": "Amount vs card's normal",
    "amt_ratio_card": "Amount vs card's average",
    "txn_count_1h": "Transactions in past hour", "txn_count_24h": "Transactions in past 24h",
    "txn_count_7D": "Transactions in past 7 days", "amt_sum_1h": "Spend in past hour",
    "amt_sum_24h": "Spend in past 24h", "amt_sum_7D": "Spend in past 7 days",
    "secs_since_last": "Time since previous transaction",
    "dist_home_km": "Distance from home (km)", "dist_prev_km": "Distance from previous merchant (km)",
    "speed_kmh": "Implied travel speed (km/h)", "is_new_merchant": "First time at this merchant",
    "card_txn_index": "Card history length", "hour": "Hour of day", "dow": "Day of week",
    "age": "Cardholder age", "category": "Merchant category",
}


@dataclass
class FraudModel:
    booster: xgb.Booster
    threshold: float

    @classmethod
    def load(cls, model_dir: Path = MODEL_DIR) -> "FraudModel":
        booster = xgb.Booster()
        booster.load_model(model_dir / "model.json")
        meta = json.loads((model_dir / "meta.json").read_text())
        return cls(booster=booster, threshold=meta["threshold"])

    def _dmatrix(self, feats: pd.DataFrame) -> xgb.DMatrix:
        return xgb.DMatrix(feats[FEATURE_COLS], enable_categorical=True)

    def score(self, feats: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(self._dmatrix(feats))

    def explain(self, feats: pd.DataFrame, top_k: int = 4) -> list[list[dict]]:
        """Top-k features pushing each row toward fraud, with the actual feature value."""
        contribs = self.booster.predict(self._dmatrix(feats), pred_contribs=True)[:, :-1]  # drop bias
        out = []
        for i in range(len(feats)):
            order = np.argsort(-contribs[i])[:top_k]
            out.append([
                {
                    "feature": FEATURE_COLS[j],
                    "label": LABELS[FEATURE_COLS[j]],
                    "value": _jsonable(feats[FEATURE_COLS[j]].iloc[i]),
                    "contribution": round(float(contribs[i, j]), 4),
                }
                for j in order if contribs[i, j] > 0
            ])
        return out


def _jsonable(v):
    if pd.isna(v):
        return None
    v = v.item() if hasattr(v, "item") else v
    return round(v, 3) if isinstance(v, float) else v
