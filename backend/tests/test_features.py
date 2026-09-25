import pandas as pd

from app.features import CATEGORIES, build_features


def make_txns(rows):
    """rows: (cc_num, timestamp, amt, merch_lat, merch_long, merchant)"""
    return pd.DataFrame([{
        "trans_date_trans_time": ts, "cc_num": cc, "amt": amt,
        "merchant": m, "category": "grocery_pos",
        "lat": 51.05, "long": -114.07, "merch_lat": mlat, "merch_long": mlon,
        "dob": "2000-01-01", "trans_num": f"t{i}", "is_fraud": 0,
    } for i, (cc, ts, amt, mlat, mlon, m) in enumerate(rows)])


BASE = [
    (1, "2020-01-01 10:00:00", 20.0, 51.05, -114.07, "a"),
    (1, "2020-01-01 10:10:00", 30.0, 51.05, -114.07, "b"),
    (1, "2020-01-01 10:20:00", 40.0, 51.05, -114.07, "a"),
    (2, "2020-01-01 10:15:00", 99.0, 51.05, -114.07, "a"),  # other card, must not bleed in
]


def test_velocity_excludes_current_and_other_cards():
    f = build_features(make_txns(BASE))
    card1 = f[f.cc_num == 1]
    assert card1["txn_count_1h"].tolist() == [0, 1, 2]
    assert card1["amt_sum_1h"].tolist() == [0, 20, 50]
    assert f[f.cc_num == 2]["txn_count_1h"].item() == 0


def test_no_future_leakage():
    """Adding a LATER transaction must not change features of EARLIER ones."""
    cols = ["txn_count_1h", "amt_sum_24h", "amt_z_card", "is_new_merchant", "speed_kmh"]
    before = build_features(make_txns(BASE))[cols]
    later = BASE + [(1, "2020-01-01 10:30:00", 5000.0, 40.71, -74.0, "z")]
    after = build_features(make_txns(later))
    after = after[after.trans_num != "t4"].reset_index(drop=True)[cols]
    pd.testing.assert_frame_equal(before, after)


def test_impossible_travel_is_flagged_by_speed():
    rows = [(1, "2020-01-01 10:00:00", 20.0, 51.05, -114.07, "a"),   # Calgary
            (1, "2020-01-01 10:30:00", 20.0, 40.71, -74.00, "b")]    # NYC 30 min later
    f = build_features(make_txns(rows))
    assert f["speed_kmh"].iloc[1] > 3000


def test_new_merchant():
    f = build_features(make_txns(BASE))
    assert f[f.cc_num == 1]["is_new_merchant"].tolist() == [1, 1, 0]


def test_category_codes_stable_for_single_row():
    """A lone 'travel' row must get the same code it gets in a full batch."""
    one = make_txns([BASE[0]]).assign(category="travel")
    f = build_features(one)
    assert f["category"].cat.codes.item() == 13


def test_unknown_category_becomes_missing_not_new_code():
    raw = make_txns(BASE)
    raw.loc[0, "category"] = "crypto_atm"
    f = build_features(raw)
    assert f["category"].isna().sum() == 1
    assert list(f["category"].cat.categories) == CATEGORIES
