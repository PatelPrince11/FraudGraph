"""Leakage-safe behavioral features for card transactions (Sparkov schema).

THE RULE: a feature for transaction t may only use transactions for the same card
that happened strictly BEFORE t. Break it and offline metrics look amazing, then
the model collapses in production because the future isn't available at scoring time.
"""
import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0
VELOCITY_WINDOWS = ("1h", "24h", "7D")

# Fixed category list = fixed integer codes in training AND serving.
# If codes were inferred from whatever data is present, 'travel' could be code 13 in
# training and code 2 at serving time, and the model would silently read garbage.
# Unknown categories become NaN, which XGBoost treats as missing.
CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net", "grocery_pos",
    "health_fitness", "home", "kids_pets", "misc_net", "misc_pos", "personal_care",
    "shopping_net", "shopping_pos", "travel",
]

# Fixed, ordered vocabulary. XGBoost sees category CODES, not strings. If codes were
# inferred per batch, a single-row request at serving time would get code 0 for any
# category -> silent train/serve skew. Unknown categories become NaN (treated as missing).
CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net", "grocery_pos",
    "health_fitness", "home", "kids_pets", "misc_net", "misc_pos", "personal_care",
    "shopping_net", "shopping_pos", "travel",
]

FEATURE_COLS = [
    "amt", "log_amt", "amt_z_card", "amt_ratio_card",
    *[f"txn_count_{w}" for w in VELOCITY_WINDOWS],
    *[f"amt_sum_{w}" for w in VELOCITY_WINDOWS],
    "secs_since_last", "dist_home_km", "dist_prev_km", "speed_kmh",
    "is_new_merchant", "card_txn_index", "hour", "dow", "age", "category",
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance. Vectorized: works on whole columns at once."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _rolling_past(df: pd.DataFrame, window: str, agg: str) -> pd.Series:
    """Per-card time window over [t - window, t). closed='left' excludes the current row.

    Result is indexed by (cc_num, ts), not df's index, so we return raw values.
    Safe only because df is already sorted by (cc_num, ts) -> same row order.
    """
    r = df.groupby("cc_num", sort=False).rolling(window, on="ts", closed="left")["amt"]
    out = getattr(r, agg)()
    return pd.Series(out.to_numpy(), index=df.index)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["trans_date_trans_time"])
    # Stable sort so ties keep file order -> deterministic features.
    df = df.sort_values(["cc_num", "ts"], kind="mergesort").reset_index(drop=True)
    g = df.groupby("cc_num", sort=False)

    # --- Amount: is this amount unusual FOR THIS CARD? (shift() = past only)
    df["log_amt"] = np.log1p(df["amt"])
    past_mean = g["amt"].transform(lambda s: s.shift().expanding().mean())
    past_std = g["amt"].transform(lambda s: s.shift().expanding().std())
    df["amt_z_card"] = (df["amt"] - past_mean) / past_std.replace(0, np.nan)
    df["amt_ratio_card"] = df["amt"] / past_mean

    # --- Velocity: bursts of activity are the classic stolen-card signal
    for w in VELOCITY_WINDOWS:
        df[f"txn_count_{w}"] = _rolling_past(df, w, "count").fillna(0)
        df[f"amt_sum_{w}"] = _rolling_past(df, w, "sum").fillna(0)
    df["secs_since_last"] = g["ts"].diff().dt.total_seconds()

    # --- Location: far from home, or physically impossible travel between txns
    df["dist_home_km"] = haversine_km(df["lat"], df["long"], df["merch_lat"], df["merch_long"])
    df["dist_prev_km"] = haversine_km(g["merch_lat"].shift(), g["merch_long"].shift(),
                                      df["merch_lat"], df["merch_long"])
    hours = (df["secs_since_last"] / 3600).clip(lower=1 / 60)  # floor at 1 min, no div-by-0
    df["speed_kmh"] = df["dist_prev_km"] / hours

    # --- Novelty
    df["is_new_merchant"] = (df.groupby(["cc_num", "merchant"]).cumcount() == 0).astype(int)
    df["card_txn_index"] = g.cumcount()  # how much history we have; low = features are noisy

    # --- Context
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.dayofweek
    df["age"] = (df["ts"] - pd.to_datetime(df["dob"])).dt.days / 365.25
    known = df["category"].where(df["category"].isin(CATEGORIES))
    df["category"] = pd.Categorical(known, categories=CATEGORIES)

    return df
