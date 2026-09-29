"""Measure the graph query against the generated rings.

For each ring (2+ cards), start from one of its test-period online fraud charges,
as an analyst would after an alert, and check what the graph finds:
  reachable recall = ring cards found / ring cards that used ring devices/IPs
                     inside the window (the ones findable at time t, no future)
  precision        = found cards with ANY labeled fraud in the window / all found cards
  model-missed found = of the reachable ring cards the MODEL never flagged in the
                     window, the share the graph still found. This is what the
                     device rule is for: the model-driven mode can't find these.
Plus graph query latency.

HONEST SCOPE: the rings were planted by make_graph_overlay.py, so this validates
the query logic (time window, hub handling, expansion) on data with a known answer.
It is NOT evidence about real-world fraud rings. Say that when you cite it.
"""
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select, update

from app.db import get_engine
from app.graph import FOLLOW_MODES, investigate
from app.tables import overlay_rings as R
from app.tables import scores as S
from app.tables import transactions as T
from app.tables import txn_entities as E


def flagged_cards(conn, cards, start, end) -> set:
    """Which of these cards had at least one model-flagged transaction in [start, end]."""
    rows = conn.execute(select(T.c.cc_num).join(S, S.c.trans_num == T.c.trans_num)
                        .where(T.c.cc_num.in_(cards), T.c.ts.between(start, end), S.c.flagged == 1)
                        .group_by(T.c.cc_num)).all()
    return {r.cc_num for r in rows}


def evaluate(conn, online_fraud, days, rounds, follow):
    results = []
    for ring_id, grp in online_fraud[online_fraud["split"] == "test"].groupby("ring_id"):
        seed = grp.sort_values("ts").iloc[len(grp) // 2]  # middle of the ring's activity
        start, end = seed["ts"] - timedelta(days=days), seed["ts"]
        g = investigate(conn, seed["trans_num"], days=days, rounds=rounds, follow=follow)

        found = {int(n["id"].split(":")[1]) for n in g["nodes"] if n["kind"] == "card"}
        window = online_fraud[(online_fraud["ring_id"] == ring_id)
                              & online_fraud["ts"].between(start, end)]
        reachable = set(window["cc_num"]) - {seed["cc_num"]}  # others to find
        missed = reachable - flagged_cards(conn, reachable, start, end)
        fraud_found = sum(n["labeled_fraud_txns"] > 0 for n in g["nodes"] if n["kind"] == "card")
        results.append({
            "reachable": len(reachable), "found": len(found & reachable),
            "missed": len(missed), "missed_found": len(found & missed),
            "precision": fraud_found / len(found), "cards_found": len(found),
            "latency_ms": g["summary"]["latency_ms"],
        })
    return pd.DataFrame(results)


def summarize(r: pd.DataFrame, follow: str) -> dict:
    return {
        "follow": follow,
        "recall": r["found"].sum() / max(r["reachable"].sum(), 1),
        "model_missed_found": r["missed_found"].sum() / max(r["missed"].sum(), 1),
        "precision": r["precision"].mean(),
        "cards_per_graph": r["cards_found"].median(),
        "p95_ms": np.percentile(r["latency_ms"], 95),
    }


def main(days: int = 30, rounds: int = 2, blind: float = 0.5):
    engine = get_engine()
    with engine.connect() as conn:
        rings = pd.read_sql(select(R).where(R.c.ring_size >= 2), conn)
        online_fraud = pd.read_sql(
            select(T.c.trans_num, T.c.cc_num, T.c.ts, T.c.split)
            .join(E, (E.c.trans_num == T.c.trans_num) & (E.c.kind == "device"))
            .where(T.c.is_fraud == 1), conn)
        online_fraud = online_fraud.merge(rings, on="cc_num")
        show("Current model", [evaluate(conn, online_fraud, days, rounds, f) for f in FOLLOW_MODES])

        # Stress test: a NEW fraud pattern the model never learned, so it misses some rings
        # entirely. Un-flag every fraud charge of half the rings, evaluate those rings,
        # then ROLL BACK so the database is untouched.
        blind_rings = rings["ring_id"].drop_duplicates().sample(frac=blind, random_state=0)
        blind_cards = rings.loc[rings["ring_id"].isin(blind_rings), "cc_num"].tolist()
        conn.execute(update(S).where(S.c.trans_num.in_(
            select(T.c.trans_num).where(T.c.cc_num.in_(blind_cards), T.c.is_fraud == 1)
        )).values(flagged=0))
        subset = online_fraud[online_fraud["ring_id"].isin(blind_rings)]
        show(f"Model blind to {blind:.0%} of rings (every charge un-flagged; rolled back after)",
             [evaluate(conn, subset, days, rounds, f) for f in FOLLOW_MODES])
        conn.rollback()


def show(title, results):
    r0 = results[0]
    print(f"\n{title}\n  rings: {len(r0)}   other ring cards reachable: {int(r0['reachable'].sum())}"
          f"   never flagged by the model: {int(r0['missed'].sum())}")
    table = pd.DataFrame([summarize(r, f) for r, f in zip(results, FOLLOW_MODES)])
    print(table.to_string(index=False, formatters={
        "recall": "{:.0%}".format, "model_missed_found": "{:.0%}".format,
        "precision": "{:.0%}".format, "cards_per_graph": "{:.0f}".format,
        "p95_ms": "{:.0f}".format}))


if __name__ == "__main__":
    main()
