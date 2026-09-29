"""API + online/offline parity tests on synthetic data, using SQLite so they run
anywhere (CI included) without a Postgres server. Same SQL, different engine."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from app.db import load_frame, reset_schema, to_rows
from app.features import build_features
from app.main import create_app
from app.model import FraudModel
from app.tables import transactions
from scripts import train
from scripts.check_parity import compare
from tests.test_model import synthetic_raw


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("api")
    raw = synthetic_raw(n=3000, n_cards=30)
    # Force a same-card, same-timestamp tie: the case seq exists for.
    raw.loc[1, ["cc_num", "trans_date_trans_time"]] = raw.loc[0, ["cc_num", "trans_date_trans_time"]]
    raw["seq"] = range(len(raw))
    raw["split"] = np.where(pd.to_datetime(raw["trans_date_trans_time"])
                            < pd.to_datetime(raw["trans_date_trans_time"]).quantile(0.75),
                            "train", "test")

    offline = build_features(raw)  # exactly what build_features.py does
    offline.to_parquet(tmp / "features.parquet", index=False)
    train.main(features_path=tmp / "features.parquet", model_dir=tmp / "models")

    engine = create_engine(f"sqlite:///{tmp / 'test.db'}")
    reset_schema(engine)
    load_frame(engine, to_rows(raw))

    app = create_app(engine=engine, model=FraudModel.load(tmp / "models"))
    with TestClient(app) as client:  # `with` runs the startup/shutdown lifespan
        yield {"client": client, "offline": offline, "engine": engine, "raw": raw}


def test_health(world):
    assert world["client"].get("/health").json() == {"status": "ok"}


def test_online_features_match_offline(world):
    offline = world["offline"]
    tie_rows = offline[offline["trans_num"].isin(["t0", "t1"])]
    sample = pd.concat([offline.sample(80, random_state=1), tie_rows])
    for _, row in sample.iterrows():
        online = world["client"].get(f"/transactions/{row['trans_num']}/risk").json()
        assert compare(row, online["features"]) == [], row["trans_num"]


def test_risk_response_shape(world):
    body = world["client"].get("/transactions/t5/risk").json()
    assert 0 <= body["score"] <= 1
    assert body["flagged"] == (body["score"] >= body["threshold"])
    assert body["label_is_fraud"] in (True, False)
    assert all(r["contribution"] > 0 for r in body["reasons"])


def test_unknown_transaction_is_404(world):
    assert world["client"].get("/transactions/nope/risk").status_code == 404


def test_score_new_transaction_uses_history_and_does_not_store(world):
    raw = world["raw"]
    card = int(raw["cc_num"].iloc[0])
    when = "2020-03-01T12:00:00"
    expected_history = int(((raw["cc_num"] == card)
                            & (pd.to_datetime(raw["trans_date_trans_time"]) <= when)).sum())
    txn = {"cc_num": card, "ts": when, "merchant": "m1", "category": "travel", "amt": 950.0,
           "lat": 45.0, "long": -100.0, "merch_lat": 40.7, "merch_long": -74.0,
           "dob": "1980-01-01"}

    with world["engine"].connect() as conn:
        before = conn.execute(select(func.count()).select_from(transactions)).scalar_one()
    body = world["client"].post("/score", json=txn).json()
    with world["engine"].connect() as conn:
        after = conn.execute(select(func.count()).select_from(transactions)).scalar_one()

    assert body["history_rows"] == expected_history > 0
    assert after == before


def test_invalid_input_rejected(world):
    bad = {"cc_num": 1, "ts": "2020-01-01T00:00:00", "merchant": "m", "category": "travel",
           "amt": -5, "lat": 0, "long": 0, "merch_lat": 0, "merch_long": 0, "dob": "1980-01-01"}
    assert world["client"].post("/score", json=bad).status_code == 422


def test_graph_endpoint(world):
    body = world["client"].get("/transactions/t5/graph?days=30&rounds=2").json()
    seed = [n for n in body["nodes"] if n.get("seed")]
    assert len(seed) == 1 and seed[0]["hop"] == 0 and seed[0]["label"].startswith("••••")
    assert body["summary"]["cards"] >= 1
    assert world["client"].get("/transactions/t5/graph?follow=everything").status_code == 422
    assert world["client"].get("/transactions/nope/graph").status_code == 404
