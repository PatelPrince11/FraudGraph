"""Replay the test period as if transactions were arriving live.

    python -m scripts.replay --hours 6 --speed 300   # 6 simulated hours at 300x (~72 s)
    python -m scripts.replay --hours 24 --speed 0    # benchmark: as fast as possible
    python -m scripts.replay --reset                 # put everything back

How it works:
  1. prepare: every transaction from the start time onward is moved out of
     `transactions` into `replay_pending`, and its score is deleted. The database now
     looks the way it did at that moment: the future hasn't happened yet.
  2. run: pending transactions are taken in (time, file order). Each one is scored
     from the card's history, then saved with its score, in one database transaction.
     With --speed > 0 the loop waits so simulated time passes `speed` times faster
     than real time; if scoring can't keep up, it falls behind and reports the lag.
  3. The dashboard polls /replay/status and the alert queue fills in live.

Running it again resumes from where the last run stopped. --reset moves everything
still pending back into `transactions` and rescores it from the offline features.
"""
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Engine, delete, func, insert, select

from app import service
from app.db import get_engine, load_frame
from app.features import FEATURE_COLS
from app.model import FraudModel
from app.tables import COLUMNS, metadata, replay_pending, replay_state
from app.tables import scores as S
from app.tables import transactions as T

P = replay_pending
FEATURES = Path(__file__).resolve().parents[2] / "data" / "processed" / "features.parquet"


def ensure_tables(engine: Engine) -> None:
    metadata.create_all(engine, tables=[P, replay_state])  # no-op if they exist


def pending_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(P)).scalar_one()


def prepare(engine: Engine, start: datetime | None = None) -> int:
    """Move every transaction at or after `start` into replay_pending. Returns how many."""
    ensure_tables(engine)
    with engine.begin() as conn:  # all or nothing: rows are never in neither table
        if start is None:  # default: the first transaction of the test period
            start = conn.execute(select(func.min(T.c.ts)).where(T.c.split == "test")).scalar_one()
        future = T.c.ts >= start
        conn.execute(insert(P).from_select(COLUMNS, select(*[T.c[c] for c in COLUMNS]).where(future)))
        # Scores first: the subquery needs the rows still in `transactions`.
        conn.execute(delete(S).where(S.c.trans_num.in_(select(T.c.trans_num).where(future))))
        moved = conn.execute(delete(T).where(future)).rowcount
        conn.execute(delete(replay_state))
    return moved


def _write_state(engine: Engine, **fields) -> None:
    with engine.begin() as conn:
        conn.execute(delete(replay_state))
        conn.execute(insert(replay_state), [{"id": 1, "updated_at": datetime.now(), **fields}])


def run(engine: Engine, model: FraudModel, hours: float | None = None, speed: float = 0.0,
        report_every: float = 1.0, batch: int = 500) -> dict:
    """Ingest pending transactions in order. speed=0 means as fast as possible."""
    with engine.connect() as conn:
        first = conn.execute(select(func.min(P.c.ts))).scalar_one()
    if first is None:
        return {"processed": 0}
    end = first + timedelta(hours=hours) if hours else None
    in_window = (P.c.ts < end) if end else (P.c.ts.isnot(None))
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(P).where(in_window)).scalar_one()

    lat, done_ids, flagged, lag = [], [], 0, 0.0
    status, clock = "running", first
    wall0 = last_report = time.perf_counter()

    def state(status):
        elapsed = time.perf_counter() - wall0
        ms = np.array(lat) * 1000 if lat else np.array([0.0])
        _write_state(engine, status=status, sim_start=first, sim_end=end, sim_clock=clock,
                     speed=speed, processed=len(done_ids), total=total, flagged=flagged,
                     txn_per_sec=round(len(done_ids) / elapsed, 2) if elapsed > 0 else 0.0,
                     p50_ms=round(float(np.percentile(ms, 50)), 1),
                     p95_ms=round(float(np.percentile(ms, 95)), 1), lag_s=round(lag, 2))

    state(status)
    try:
        while True:
            with engine.connect() as conn:
                rows = conn.execute(select(P).where(in_window).order_by(P.c.ts, P.c.seq)
                                    .limit(batch)).mappings().all()
            if not rows:
                status = "done"
                break
            for row in rows:
                txn = dict(row)
                if speed > 0:  # wait until this transaction is "due" in simulated time
                    due = wall0 + (txn["ts"] - first).total_seconds() / speed
                    wait = due - time.perf_counter()
                    if wait > 0:
                        time.sleep(wait)
                    lag = max(0.0, -wait)
                t0 = time.perf_counter()
                with engine.begin() as conn:  # score + save + dequeue: one atomic step
                    result = service.ingest(conn, model, txn)
                    conn.execute(delete(P).where(P.c.trans_num == txn["trans_num"]))
                lat.append(time.perf_counter() - t0)
                done_ids.append(txn["trans_num"])
                flagged += int(result["flagged"])
                clock = txn["ts"]
                if time.perf_counter() - last_report >= report_every:
                    state("running")
                    last_report = time.perf_counter()
    except KeyboardInterrupt:
        status = "stopped"
    state(status)

    elapsed = time.perf_counter() - wall0
    ms = np.array(lat) * 1000 if lat else np.array([0.0])
    sim_hours = (clock - first).total_seconds() / 3600
    return {
        "status": status, "processed": len(done_ids), "total": total, "flagged": flagged,
        "wall_s": round(elapsed, 1), "sim_hours": round(sim_hours, 2),
        "txn_per_sec": round(len(done_ids) / elapsed, 1) if elapsed else 0.0,
        "p50_ms": round(float(np.percentile(ms, 50)), 1),
        "p95_ms": round(float(np.percentile(ms, 95)), 1),
        "max_lag_s": round(lag, 2), "trans_nums": done_ids,
    }


def offline_scores(model: FraudModel, features_path: Path, trans_nums) -> pd.DataFrame:
    feats = pd.read_parquet(features_path, columns=["trans_num", *FEATURE_COLS])
    feats = feats[feats["trans_num"].isin(set(trans_nums))]
    out = pd.DataFrame({"trans_num": feats["trans_num"], "score": model.score(feats)})
    out["flagged"] = (out["score"] >= model.threshold).astype(int)
    return out


def verify(engine: Engine, model: FraudModel, features_path: Path, trans_nums) -> tuple[int, int]:
    """Do the scores written during replay equal the offline batch scores?"""
    expected = offline_scores(model, features_path, trans_nums).set_index("trans_num")["score"]
    ids, parts = list(trans_nums), []
    with engine.connect() as conn:
        for i in range(0, len(ids), 10_000):  # chunks: databases cap query parameters
            parts.append(pd.read_sql(select(S.c.trans_num, S.c.score)
                                     .where(S.c.trans_num.in_(ids[i:i + 10_000])), conn))
    got = pd.concat(parts).set_index("trans_num")["score"]
    both = expected.index.intersection(got.index)
    match = np.isclose(expected[both], got[both], atol=1e-5)
    return int(match.sum()), len(trans_nums)


def reset(engine: Engine, model: FraudModel, features_path: Path = FEATURES) -> int:
    """Move everything still pending back, and restore its scores."""
    ensure_tables(engine)
    with engine.begin() as conn:
        restored = [r[0] for r in conn.execute(select(P.c.trans_num))]
        conn.execute(insert(T).from_select(COLUMNS, select(*[P.c[c] for c in COLUMNS])))
        conn.execute(delete(P))
        conn.execute(delete(replay_state))
    if restored:
        load_frame(engine, offline_scores(model, features_path, restored), table=S)
    return len(restored)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hours", type=float, default=6, help="simulated hours to replay (default 6)")
    ap.add_argument("--speed", type=float, default=300,
                    help="simulated seconds per real second; 0 = as fast as possible (default 300)")
    ap.add_argument("--start", type=datetime.fromisoformat, default=None,
                    help="replay start, e.g. 2020-07-01 (default: start of the test period)")
    ap.add_argument("--reset", action="store_true", help="put all pending transactions back")
    args = ap.parse_args()

    engine, model = get_engine(), FraudModel.load()
    ensure_tables(engine)

    if args.reset:
        print(f"restored {reset(engine, model):,} transactions and their scores")
        return

    if pending_count(engine) == 0:
        t0 = time.time()
        n = prepare(engine, args.start)
        print(f"prepared: moved {n:,} future transactions to replay_pending ({time.time() - t0:.1f}s)")
    else:
        print(f"resuming: {pending_count(engine):,} transactions still pending")

    print(f"replaying {args.hours:g} simulated hours at "
          f"{'max speed' if args.speed == 0 else f'{args.speed:g}x'}  (Ctrl+C stops safely)")
    s = run(engine, model, hours=args.hours, speed=args.speed)
    if not s["processed"]:
        print("nothing to replay")
        return
    print(f"{s['status']}: {s['processed']:,}/{s['total']:,} transactions, "
          f"{s['sim_hours']:.1f} simulated hours in {s['wall_s']}s")
    print(f"  throughput {s['txn_per_sec']} txn/s   per-transaction p50 {s['p50_ms']} ms  "
          f"p95 {s['p95_ms']} ms   max lag {s['max_lag_s']}s")
    rate = s["processed"] / (s["sim_hours"] * 3600) if s["sim_hours"] else 0
    if rate:
        print(f"  the data arrives at {rate:.2f} txn/s, so this is "
              f"{s['txn_per_sec'] / rate:,.0f}x faster than real time")
    print(f"  alerts raised: {s['flagged']:,}")
    if FEATURES.exists():
        ok, n = verify(engine, model, FEATURES, s["trans_nums"])
        print(f"  replayed scores match offline scores: {ok:,}/{n:,}")


if __name__ == "__main__":
    main()
