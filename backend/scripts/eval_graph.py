"""Measure the graph query against the generated rings.

For each ring (2+ cards), start from one of its test-period online fraud charges,
as an analyst would after an alert, and check what the graph finds:
  reachable recall = ring cards found / ring cards that used ring devices/IPs
                     inside the window (the ones findable at time t, no future)
  precision        = found cards with ANY labeled fraud in the window / all found cards
Plus graph query latency.

HONEST SCOPE: the rings were planted by make_graph_overlay.py, so this validates
the query logic (time window, hub handling, expansion) on data with a known answer.
It is NOT evidence about real-world fraud rings. Say that when you cite it.
"""
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.db import get_engine
from app.graph import investigate
from app.tables import overlay_rings as R
from app.tables import transactions as T
from app.tables import txn_entities as E


def evaluate(conn, online_fraud, days, rounds, follow):
    results = []
    for ring_id, grp in online_fraud[online_fraud["split"] == "test"].groupby("ring_id"):
        seed = grp.sort_values("ts").iloc[len(grp) // 2]  # middle of the ring's activity
        g = investigate(conn, seed["trans_num"], days=days, rounds=rounds, follow=follow)

        found = {int(n["id"].split(":")[1]) for n in g["nodes"] if n["kind"] == "card"}
        window = online_fraud[(online_fraud["ring_id"] == ring_id)
                              & online_fraud["ts"].between(seed["ts"] - timedelta(days=days),
                                                           seed["ts"])]
        reachable = set(window["cc_num"])
        fraud_found = sum(n["labeled_fraud_txns"] > 0 for n in g["nodes"] if n["kind"] == "card")
        results.append({
            "reachable": len(reachable),
            "recall": len(found & reachable) / len(reachable),
            "precision": fraud_found / len(found),
            "cards_found": len(found),
            "latency_ms": g["summary"]["latency_ms"],
        })
    return pd.DataFrame(results)


def report(r: pd.DataFrame, follow: str):
    multi = r[r["reachable"] >= 2]  # rings where there was actually someone else to find
    print(f"\nfollow={follow}: rings evaluated={len(r)} (2+ reachable cards: {len(multi)})")
    print(f"  reachable recall  mean={multi['recall'].mean():.3f}  "
          f"(whole ring found in {(multi['recall'] == 1).mean():.0%} of rings)")
    print(f"  precision         mean={r['precision'].mean():.3f}  "
          f"median cards per graph={r['cards_found'].median():.0f}")
    print(f"  latency ms        p50={np.percentile(r['latency_ms'], 50):.1f}  "
          f"p95={np.percentile(r['latency_ms'], 95):.1f}")


def main(days: int = 30, rounds: int = 2):
    engine = get_engine()
    with engine.connect() as conn:
        rings = pd.read_sql(select(R).where(R.c.ring_size >= 2), conn)
        online_fraud = pd.read_sql(
            select(T.c.trans_num, T.c.cc_num, T.c.ts, T.c.split)
            .join(E, (E.c.trans_num == T.c.trans_num) & (E.c.kind == "device"))
            .where(T.c.is_fraud == 1), conn)
        online_fraud = online_fraud.merge(rings, on="cc_num")

        for follow in ("all", "flagged"):
            report(evaluate(conn, online_fraud, days, rounds, follow), follow)


if __name__ == "__main__":
    main()
