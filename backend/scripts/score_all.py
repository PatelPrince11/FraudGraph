"""Score every stored transaction once and save the results in the `scores` table.

The graph and the dashboard's alert list need "was this transaction flagged?" for
thousands of transactions per request. Recomputing that live would take seconds,
so we batch-score offline (~5s for 1.85M rows) and look it up.

Uses the offline parquet features. That's only valid because check_parity.py proved
offline features == online features.

Caveat: train-period scores are IN-SAMPLE (the model learned from those rows), so
they look better than reality. Only test-period scores are honest evidence.
"""
import time
from pathlib import Path

import pandas as pd

from app.db import get_engine, load_frame, reset_tables
from app.features import FEATURE_COLS
from app.model import FraudModel
from app.tables import scores

FEATURES = Path(__file__).resolve().parents[2] / "data" / "processed" / "features.parquet"


def main():
    t0 = time.time()
    feats = pd.read_parquet(FEATURES, columns=["trans_num", *FEATURE_COLS])
    model = FraudModel.load()
    out = pd.DataFrame({"trans_num": feats["trans_num"], "score": model.score(feats)})
    out["flagged"] = (out["score"] >= model.threshold).astype(int)

    engine = get_engine()
    reset_tables(engine, [scores])
    load_frame(engine, out, table=scores)
    print(f"scored {len(out):,} transactions in {time.time() - t0:.1f}s, "
          f"flagged {out['flagged'].sum():,} ({out['flagged'].mean():.3%})")


if __name__ == "__main__":
    main()
