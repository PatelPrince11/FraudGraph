"""Raw Sparkov CSVs -> one feature table (parquet).

Train and test are concatenated BEFORE feature building so a test transaction's
velocity/history features can see that card's earlier (train-period) transactions.
That's legal: it's the past. The split itself stays time-based (Kaggle files are
already split by date). Never random-split transactions.
"""
import time
from pathlib import Path

import pandas as pd

from app.features import build_features

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "features.parquet"


def main():
    t0 = time.time()
    train = pd.read_csv(RAW / "fraudTrain.csv", index_col=0).assign(split="train")
    test = pd.read_csv(RAW / "fraudTest.csv", index_col=0).assign(split="test")
    feats = build_features(pd.concat([train, test], ignore_index=True))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(OUT, index=False)

    print(f"rows={len(feats):,}  built in {time.time() - t0:.1f}s -> {OUT}")
    print(feats.groupby("split")["is_fraud"].agg(["size", "sum", "mean"]))
    print(feats["ts"].groupby(feats["split"]).agg(["min", "max"]))


if __name__ == "__main__":
    main()
