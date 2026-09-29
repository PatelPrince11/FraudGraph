"""Load both Sparkov CSVs into PostgreSQL (drops and recreates the table).

seq is assigned from the same concat order build_features.py used, so the
database's tie-breaking matches the offline features exactly.
"""
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from app.db import get_engine, load_frame, reset_schema, to_rows
from app.tables import transactions

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def main():
    t0 = time.time()
    train = pd.read_csv(RAW / "fraudTrain.csv", index_col=0).assign(split="train")
    test = pd.read_csv(RAW / "fraudTest.csv", index_col=0).assign(split="test")
    raw = pd.concat([train, test], ignore_index=True)
    raw["seq"] = range(len(raw))

    engine = get_engine()
    reset_schema(engine)
    load_frame(engine, to_rows(raw))

    with engine.connect() as conn:
        n = conn.execute(select(func.count()).select_from(transactions)).scalar_one()
    print(f"loaded {n:,} rows in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
