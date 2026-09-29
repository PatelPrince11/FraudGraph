"""Online/offline parity on REAL data: score a random sample of test transactions
through the API code path and compare every feature to the offline parquet.

Also measures the full scoring path (DB query + features + model + SHAP),
which is the latency number you can honestly claim for the service.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app import service
from app.db import get_engine
from app.features import FEATURE_COLS
from app.model import FraudModel

FEATURES = Path(__file__).resolve().parents[2] / "data" / "processed" / "features.parquet"


def compare(offline: pd.Series, online: dict) -> list[str]:
    bad = []
    for c in FEATURE_COLS:
        a, b = offline[c], online[c]
        if c == "category":
            same = (pd.isna(a) and b is None) or str(a) == str(b)
        else:
            same = np.isclose(float(a), float("nan") if b is None else float(b),
                              rtol=1e-6, atol=1e-3, equal_nan=True)  # atol: API rounds to 3dp
        if not same:
            bad.append(f"{c}: offline={a} online={b}")
    return bad


def main(n: int = 300):
    offline = pd.read_parquet(FEATURES)
    sample = offline[offline["split"] == "test"].sample(n, random_state=0)
    engine, model = get_engine(), FraudModel.load()

    mismatches, latencies = 0, []
    with engine.connect() as conn:
        for _, row in sample.iterrows():
            result = service.score_existing(conn, model, row["trans_num"])
            latencies.append(result["latency_ms"])
            bad = compare(row, result["features"])
            if bad:
                mismatches += 1
                print(row["trans_num"], bad)

    print(f"parity: {n - mismatches}/{n} transactions match on all {len(FEATURE_COLS)} features")
    print(f"scoring path latency ms: p50={np.percentile(latencies, 50):.1f} "
          f"p95={np.percentile(latencies, 95):.1f}")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
