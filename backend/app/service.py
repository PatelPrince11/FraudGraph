"""Score one transaction the SAME way training did: rebuild its features from the
card's full history (option 1 from our design discussion).

Offline: build_features(all transactions) -> row t
Online:  build_features(card history before t + t) -> last row
Same function, same prefix of data -> identical features. tests/test_api.py proves it.
"""
import time
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import Connection, and_, or_, select

from app.features import FEATURE_COLS, build_features
from app.model import FraudModel, _jsonable
from app.tables import transactions as T


class NotFound(Exception):
    pass


def fetch_history(conn: Connection, cc_num: int, ts: datetime, seq: int | None) -> pd.DataFrame:
    """Every earlier transaction for this card, in the same order the offline pipeline saw.

    Existing transaction (seq known): strictly before it, ties broken by seq.
    New transaction (seq None): everything up to and including its timestamp,
    because it arrives after anything already stored.
    """
    if seq is None:
        before = T.c.ts <= ts
    else:
        before = or_(T.c.ts < ts, and_(T.c.ts == ts, T.c.seq < seq))
    stmt = (select(T).where(T.c.cc_num == cc_num, before)
            .order_by(T.c.ts, T.c.seq))
    return pd.read_sql(stmt, conn)


def get_transaction(conn: Connection, trans_num: str) -> dict:
    row = conn.execute(select(T).where(T.c.trans_num == trans_num)).mappings().first()
    if row is None:
        raise NotFound(trans_num)
    return dict(row)


def score(conn: Connection, model: FraudModel, txn: dict, seq: int | None = None) -> dict:
    t0 = time.perf_counter()
    ts = pd.Timestamp(txn["ts"])
    if ts.tzinfo is not None:  # stored times are naive; comparing naive vs aware errors
        ts = ts.tz_localize(None)
    ts = ts.to_pydatetime()
    txn = {**txn, "ts": ts, "trans_num": txn.get("trans_num") or uuid.uuid4().hex}

    history = fetch_history(conn, txn["cc_num"], ts, seq)
    new = pd.DataFrame([txn])
    # A card's first transaction has empty history. Empty DataFrames come back with
    # 'object' columns, and concat would turn amt etc. into objects too -> math breaks.
    frame = pd.concat([history, new], ignore_index=True) if len(history) else new
    frame = frame.astype({"cc_num": "int64", "amt": "float64", "lat": "float64",
                          "long": "float64", "merch_lat": "float64", "merch_long": "float64"})
    frame["trans_date_trans_time"] = frame["ts"]
    feats = build_features(frame)
    row = feats[feats["trans_num"] == txn["trans_num"]]

    prob = float(model.score(row)[0])
    return {
        "trans_num": txn["trans_num"],
        "cc_num": str(txn["cc_num"]),
        "score": round(prob, 6),
        "threshold": round(model.threshold, 6),
        "flagged": prob >= model.threshold,
        "reasons": model.explain(row)[0],
        "features": {c: _jsonable(row[c].iloc[0]) for c in FEATURE_COLS},
        "history_rows": len(history),
        "latency_ms": round(1000 * (time.perf_counter() - t0), 2),
    }


def score_existing(conn: Connection, model: FraudModel, trans_num: str) -> dict:
    txn = get_transaction(conn, trans_num)
    result = score(conn, model, txn, seq=txn["seq"])
    label = txn.get("is_fraud")
    result["label_is_fraud"] = None if label is None or np.isnan(label) else bool(label)
    return result
