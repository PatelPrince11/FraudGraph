"""Graph rules, checked on a tiny hand-built world where we know the right answer."""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.db import load_frame, reset_schema
from app.graph import investigate
from app.tables import scores, transactions, txn_entities
from scripts.make_graph_overlay import generate

T0 = datetime(2020, 6, 1, 12, 0)


def txn(i, cc, when, merchant="m", fraud=0):
    return {"trans_num": f"t{i}", "seq": i, "cc_num": cc, "ts": when, "merchant": merchant,
            "category": "shopping_net", "amt": 10.0, "lat": 0.0, "long": 0.0,
            "merch_lat": 0.0, "merch_long": 0.0, "dob": datetime(1990, 1, 1).date(),
            "is_fraud": fraud, "split": "test"}


@pytest.fixture(scope="module")
def conn(make_engine):
    # Seed card 1. Cards 2 and 6 share device D1 (before t). Card 5 shares device D2 with
    # card 2 only (2 rounds away). Card 3 uses D1 only AFTER t (future). Card 4 shared
    # D3 with card 1 but 40 days ago (outside window). Cards 100-129 share public IP P.
    uses = [  # (cc, when, kind, entity, flagged, merchant)
        (1, T0, "device", "D1", 1, "shop_x"),
        (2, T0 - timedelta(days=2), "device", "D1", 1, "shop_x"),
        (6, T0 - timedelta(days=5), "device", "D1", 1, "shop_x"),
        (2, T0 - timedelta(days=3), "device", "D2", 0, "m"),
        (5, T0 - timedelta(days=4), "device", "D2", 0, "m"),
        (3, T0 + timedelta(days=1), "device", "D1", 1, "m"),
        (1, T0 - timedelta(days=40), "device", "D3", 0, "m"),
        (4, T0 - timedelta(days=40), "device", "D3", 0, "m"),
        (1, T0 - timedelta(days=1), "ip", "P", 0, "m"),
        *[(100 + k, T0 - timedelta(days=1), "ip", "P", 0, "m") for k in range(30)],
    ]
    txns, ents, scs = [], [], []
    for i, (cc, when, kind, ent, flagged, merchant) in enumerate(uses):
        txns.append(txn(i, cc, when, merchant, fraud=flagged))
        ents.append({"trans_num": f"t{i}", "kind": kind, "entity": ent, "cc_num": cc, "ts": when})
        scs.append({"trans_num": f"t{i}", "score": 0.99 if flagged else 0.01, "flagged": flagged})

    engine = make_engine()
    reset_schema(engine)
    load_frame(engine, pd.DataFrame(txns))
    load_frame(engine, pd.DataFrame(ents), table=txn_entities)
    load_frame(engine, pd.DataFrame(scs), table=scores)
    with engine.connect() as c:
        yield c


def cards(g):
    return {int(n["id"].split(":")[1]) for n in g["nodes"] if n["kind"] == "card"}


def test_finds_shared_device_and_respects_window(conn):
    g = investigate(conn, "t0", days=30, rounds=2, follow="all")
    assert 2 in cards(g) and 5 in cards(g)
    assert 3 not in cards(g), "used the device only after t: future leak"
    assert 4 not in cards(g), "link is older than the window"


def test_rounds_limit_depth(conn):
    assert cards(investigate(conn, "t0", days=30, rounds=1, follow="all")) == {1, 2, 6}


def test_follow_flagged_skips_unflagged_links(conn):
    # D2 links card 2 -> card 5, but no flagged charge ever used D2.
    assert cards(investigate(conn, "t0", days=30, rounds=2, follow="flagged")) == {1, 2, 6}


def test_public_ip_is_a_hub_not_expanded(conn):
    g = investigate(conn, "t0", days=30, rounds=2, follow="all")
    hub = next(n for n in g["nodes"] if n["id"] == "ip:P")
    assert hub["hub"] is True and hub["cards_in_window"] == 31
    assert not cards(g) & set(range(100, 130))
    assert g["summary"]["hubs_not_expanded"] == 1


def test_every_entity_gets_a_card_count(conn):
    g = investigate(conn, "t0", days=30, rounds=2, follow="flagged")
    ents = [n for n in g["nodes"] if n["kind"] in ("device", "ip")]
    assert ents and all(n["cards_in_window"] is not None for n in ents)
    assert next(n for n in ents if n["id"] == "device:D1")["cards_in_window"] == 3  # not card 3


def test_common_flagged_merchant_and_masking(conn):
    g = investigate(conn, "t0", days=30, rounds=2)
    ids = {n["id"] for n in g["nodes"]}
    assert "merchant:shop_x" in ids        # flagged charges by cards 1, 2 and 6
    assert "merchant:m" not in ids         # no flagged charges shared there
    seed = next(n for n in g["nodes"] if n.get("seed"))
    assert seed["label"] == "•••• 1" and seed["hop"] == 0


def test_overlay_generator():
    rows = []
    for c in range(40):
        for d in range(30):
            fraud = int(c < 20 and d >= 25)  # 20 compromised cards, fraud at the end
            rows.append({"trans_num": f"{c}-{d}", "cc_num": c,
                         "ts": T0 + timedelta(days=d, hours=c),
                         "category": "shopping_net" if d % 2 else "grocery_pos",
                         "is_fraud": fraud})
    txns = pd.DataFrame(rows)
    ents, rings = generate(txns, seed=1)
    ents2, _ = generate(txns, seed=1)
    pd.testing.assert_frame_equal(ents, ents2)                          # deterministic
    online = set(txns.loc[txns.category.str.endswith("_net"), "trans_num"])
    assert set(ents.trans_num) == online                                # online only
    assert (ents.groupby("trans_num").size() == 2).all()                # one device + one IP
    assert set(rings.cc_num) == set(range(20))                          # every compromised card

    # Inside a multi-card ring, fraud charges from different cards share a device.
    fraud_dev = ents[(ents.kind == "device")
                     & ents.trans_num.isin(txns.loc[txns.is_fraud == 1, "trans_num"])]
    fraud_dev = fraud_dev.merge(rings, on="cc_num")
    shared = fraud_dev[fraud_dev.ring_size > 1].groupby("entity").cc_num.nunique()
    assert (shared >= 2).any()
