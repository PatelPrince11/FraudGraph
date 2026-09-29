"""End-to-end smoke test on tiny synthetic data with an injected fraud pattern:
fraud = bursts of large night-time transactions far from home."""
import numpy as np
import pandas as pd
import xgboost as xgb

from app.features import CATEGORIES, FEATURE_COLS, build_features
from app.model import FraudModel
from scripts import train


def synthetic_raw(n=6000, n_cards=60, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.Timestamp("2019-01-01") + pd.to_timedelta(rng.integers(0, 540 * 86400, n), unit="s")
    fraud = rng.random(n) < 0.03
    far = np.where(fraud, 8.0, 0.1)
    lat, lon = 45.0, -100.0
    return pd.DataFrame({
        "trans_date_trans_time": ts.astype(str), "cc_num": rng.integers(0, n_cards, n),
        "merchant": rng.integers(0, 50, n).astype(str),
        "category": rng.choice(CATEGORIES, n),
        # Rounded to cents like real data. Postgres stores amt as NUMERIC(12,2), so
        # unrounded amounts would make online features differ from offline ones.
        "amt": np.round(np.where(fraud, rng.uniform(300, 1200, n), rng.exponential(50, n)), 2),
        "lat": lat, "long": lon,
        "merch_lat": lat + rng.normal(0, 1, n) * far, "merch_long": lon + rng.normal(0, 1, n) * far,
        "dob": "1980-01-01", "trans_num": [f"t{i}" for i in range(n)],
        "is_fraud": fraud.astype(int),
    })


def test_train_end_to_end(tmp_path):
    raw = synthetic_raw()
    feats = build_features(raw)
    cutoff = feats["ts"].quantile(0.75)
    feats["split"] = np.where(feats["ts"] < cutoff, "train", "test")
    path = tmp_path / "features.parquet"
    feats.to_parquet(path, index=False)

    train.main(features_path=path, model_dir=tmp_path / "models")

    model = FraudModel.load(tmp_path / "models")
    te = feats[feats.split == "test"]
    scores = model.score(te)
    assert scores[te.is_fraud == 1].mean() > scores[te.is_fraud == 0].mean()

    # TreeSHAP contributions + bias must sum to the raw log-odds output.
    dm = xgb.DMatrix(te[FEATURE_COLS].head(20), enable_categorical=True)
    contribs = model.booster.predict(dm, pred_contribs=True)
    margin = model.booster.predict(dm, output_margin=True)
    np.testing.assert_allclose(contribs.sum(axis=1), margin, rtol=1e-4, atol=1e-4)

    reasons = model.explain(te[te.is_fraud == 1].head(1))[0]
    assert reasons and all(r["contribution"] > 0 for r in reasons)


def test_explanations_merge_transforms_of_the_same_input(tmp_path):
    raw = synthetic_raw()
    feats = build_features(raw)
    feats["split"] = np.where(feats["ts"] < feats["ts"].quantile(0.75), "train", "test")
    feats.to_parquet(tmp_path / "f.parquet", index=False)
    train.main(features_path=tmp_path / "f.parquet", model_dir=tmp_path / "models")
    model = FraudModel.load(tmp_path / "models")

    rows = feats[feats.is_fraud == 1].head(30)
    for reasons in model.explain(rows, top_k=len(FEATURE_COLS)):
        names = [r["feature"] for r in reasons]
        assert "log_amt" not in names                     # folded into amt
        assert len(names) == len(set(names))              # no reason twice

    # Merging keeps the total exact: positive + negative parts still sum to the margin.
    dm = xgb.DMatrix(rows[FEATURE_COLS], enable_categorical=True)
    raw_c = model.booster.predict(dm, pred_contribs=True)
    merged = raw_c.copy()
    a, b = FEATURE_COLS.index("amt"), FEATURE_COLS.index("log_amt")
    merged[:, a] += merged[:, b]; merged[:, b] = 0
    np.testing.assert_allclose(merged.sum(axis=1), raw_c.sum(axis=1), rtol=1e-5, atol=1e-5)
