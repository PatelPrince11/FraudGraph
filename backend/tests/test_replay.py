"""Replay: transactions arriving one at a time must get exactly the scores the
offline pipeline gives them, and the database must end up where it started."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import service
from app.db import load_frame, reset_schema, to_rows
from app.features import build_features
from app.main import create_app
from app.model import FraudModel
from app.tables import replay_pending, scores, transactions
from scripts import replay, train
from tests.test_model import synthetic_raw


def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


@pytest.fixture(scope="module")
def world(tmp_path_factory, make_engine):
    tmp = tmp_path_factory.mktemp("replay")
    raw = synthetic_raw(n=2500, n_cards=25, seed=3)
    raw.loc[1, ["cc_num", "trans_date_trans_time"]] = raw.loc[0, ["cc_num", "trans_date_trans_time"]]
    raw["seq"] = range(len(raw))
    ts = pd.to_datetime(raw["trans_date_trans_time"])
    raw["split"] = np.where(ts < ts.quantile(0.8), "train", "test")

    feats = build_features(raw)
    feats_path = tmp / "features.parquet"
    feats.to_parquet(feats_path, index=False)
    train.main(features_path=feats_path, model_dir=tmp / "models")
    model = FraudModel.load(tmp / "models")

    engine = make_engine()
    reset_schema(engine)
    load_frame(engine, to_rows(raw))
    load_frame(engine, replay.offline_scores(model, feats_path, raw["trans_num"]), table=scores)
    return {"engine": engine, "model": model, "feats_path": feats_path, "n": len(raw),
            "n_test": int((raw["split"] == "test").sum())}


def test_prepare_hides_the_future(world):
    e = world["engine"]
    moved = replay.prepare(e)
    assert moved == world["n_test"]
    assert count(e, replay_pending) == moved
    assert count(e, transactions) == world["n"] - moved
    assert count(e, scores) == world["n"] - moved  # future scores removed too


def test_replay_scores_match_offline(world):
    e, model = world["engine"], world["model"]
    first = replay.run(e, model, hours=24 * 20)  # part of the window
    rest = replay.run(e, model)                  # resume: the remainder
    ids = first["trans_nums"] + rest["trans_nums"]
    assert first["processed"] > 0 and rest["status"] == "done"
    assert len(ids) == world["n_test"] and count(e, replay_pending) == 0
    ok, n = replay.verify(e, model, world["feats_path"], ids)
    assert ok == n, f"{n - ok} replayed scores differ from offline"


def test_status_endpoint_reports_the_run(world):
    app = create_app(engine=world["engine"], model=world["model"])
    with TestClient(app) as client:
        body = client.get("/replay/status").json()
    assert body["status"] == "done"
    assert body["processed"] > 0 and body["processed"] == body["total"]


def test_reset_restores_everything(world):
    e, model = world["engine"], world["model"]
    replay.prepare(e)
    replay.run(e, model, hours=24 * 10)  # stop partway
    restored = replay.reset(e, model, world["feats_path"])
    assert restored > 0
    assert count(e, replay_pending) == 0
    assert count(e, transactions) == world["n"]
    assert count(e, scores) == world["n"]


def test_saving_before_scoring_would_leak(world):
    """Why ingest scores FIRST: a saved transaction becomes part of its own history."""
    e, model = world["engine"], world["model"]
    with e.connect() as conn:
        txn = dict(conn.execute(select(transactions).order_by(transactions.c.ts.desc())
                                .limit(1)).mappings().one())
    new = {**txn, "trans_num": "incoming", "seq": None, "ts": txn["ts"] + pd.Timedelta(hours=2)}

    with e.connect() as conn:  # correct order: score, then save
        right = service.ingest(conn, model, new)
        conn.rollback()

    with e.connect() as conn:  # wrong order: save it, then score the incoming event
        conn.execute(transactions.insert(), [{**new, "trans_num": "saved-copy", "seq": 10**9}])
        wrong = service.score(conn, model, new, seq=None)
        conn.rollback()

    r, w = right["features"], wrong["features"]
    assert w["secs_since_last"] == 0 < r["secs_since_last"]      # looks like a burst
    assert w["card_txn_index"] == r["card_txn_index"] + 1          # history too long
    assert wrong["history_rows"] == right["history_rows"] + 1
    # The 1h velocity count does NOT change: windows are [t - 1h, t), and the copy sits
    # exactly at t. Leaks hide in the features you didn't think to check.
    assert w["txn_count_1h"] == r["txn_count_1h"]
