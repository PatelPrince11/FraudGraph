"""Generate SYNTHETIC devices, IPs and fraud rings for the relationship graph.

Why synthetic: no public labelled dataset links cards to devices and IPs. We say so
in the README, and the model never uses these columns, so the model's metrics stay
100% real-data. The graph is an investigation tool on top.

How the fake world works (all numbers are assumptions, tuned to look plausible):
- Only ONLINE transactions (category ends in _net) get a device and an IP.
- Each card owns 1-2 home devices and 1-2 home IPs. Legit online purchases mostly
  use those; 10% of the time a PUBLIC IP (cafe, airport, mobile carrier) that many
  unrelated cards share. Public IPs are the realistic noise that makes graphs hard.
- Compromised cards are grouped into RINGS: cards whose fraud starts around the same
  time. Each ring's attackers use a small pool of devices/IPs, so fraudulent online
  charges on different cards share entities. 20% of compromised cards act alone.
"""
import time

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.db import get_engine, load_frame, reset_tables
from app.tables import overlay_rings, transactions, txn_entities

P_DEVICE_NOISE = 0.05          # legit purchase from a one-off device (new phone, friend's laptop)
P_IP_PUBLIC, P_IP_NOISE = 0.10, 0.05
P_RING_DEVICE, P_RING_IP = 0.80, 0.70   # fraud purchase uses the ring's own device / IP
P_LONE = 0.20
N_PUBLIC_IPS = 200


def _devices(rng, shape):
    return np.char.add("dev-", np.char.mod("%010x", rng.integers(0, 16**10, shape)))


def _ips(rng, shape):
    n = int(np.prod(shape))
    octets = np.column_stack([rng.integers(24, 224, n), rng.integers(0, 256, (n, 3))])
    return np.array([".".join(map(str, o)) for o in octets]).reshape(shape)


def _pick(rng, pool, n_valid):
    """Per row, pick a random column from pool (rows, k) among the first n_valid[i]."""
    col = rng.integers(0, n_valid)
    return pool[np.arange(len(pool)), col]


def assign_rings(txns: pd.DataFrame, rng) -> pd.DataFrame:
    first_fraud = (txns[txns["is_fraud"] == 1].groupby("cc_num")["ts"].min()
                   .sort_values())
    cards = first_fraud.index.to_numpy()
    lone = rng.random(len(cards)) < P_LONE
    ring_of, ring_id = {}, 0
    for c in cards[lone]:
        ring_of[c] = ring_id; ring_id += 1
    grouped = cards[~lone]  # already in order of when their fraud started
    i = 0
    while i < len(grouped):
        size = int(rng.integers(3, 11))
        for c in grouped[i:i + size]:
            ring_of[c] = ring_id
        ring_id += 1; i += size
    rings = pd.DataFrame({"cc_num": list(ring_of), "ring_id": list(ring_of.values())})
    rings["ring_size"] = rings.groupby("ring_id")["cc_num"].transform("size")
    return rings


def generate(txns: pd.DataFrame, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """txns needs: trans_num, cc_num, ts, category, is_fraud. Returns (entities, rings)."""
    rng = np.random.default_rng(seed)
    txns = txns.reset_index(drop=True)
    cards = np.sort(txns["cc_num"].unique())
    n_cards = len(cards)

    home_dev, n_dev = _devices(rng, (n_cards, 2)), rng.integers(1, 3, n_cards)
    home_ip, n_ip = _ips(rng, (n_cards, 2)), rng.integers(1, 3, n_cards)
    public = _ips(rng, N_PUBLIC_IPS)
    public_w = 1 / np.arange(1, N_PUBLIC_IPS + 1); public_w /= public_w.sum()  # few huge, many small

    rings = assign_rings(txns, rng)
    n_rings = int(rings["ring_id"].max()) + 1 if len(rings) else 0
    ring_dev, ring_ndev = _devices(rng, (max(n_rings, 1), 3)), rng.integers(1, 4, max(n_rings, 1))
    ring_ip, ring_nip = _ips(rng, (max(n_rings, 1), 5)), rng.integers(2, 6, max(n_rings, 1))

    online = txns[txns["category"].str.endswith("_net")].reset_index(drop=True)
    m = len(online)
    ci = np.searchsorted(cards, online["cc_num"].to_numpy())

    # Legit behaviour first, for every online transaction.
    device = _pick(rng, home_dev[ci], n_dev[ci])
    u = rng.random(m)
    device = np.where(u < P_DEVICE_NOISE, _devices(rng, m), device)
    ip = _pick(rng, home_ip[ci], n_ip[ci])
    u = rng.random(m)
    ip = np.where(u < P_IP_PUBLIC, rng.choice(public, m, p=public_w), ip)
    ip = np.where((u >= P_IP_PUBLIC) & (u < P_IP_PUBLIC + P_IP_NOISE), _ips(rng, m), ip)

    # Then overwrite fraudulent online transactions with ring behaviour.
    f = (online["is_fraud"] == 1).to_numpy()
    if f.any():
        ring = online.loc[f, "cc_num"].map(rings.set_index("cc_num")["ring_id"]).to_numpy()
        k = int(f.sum())
        dev_f = np.where(rng.random(k) < P_RING_DEVICE,
                         _pick(rng, ring_dev[ring], ring_ndev[ring]), _devices(rng, k))
        u = rng.random(k)
        ip_f = np.where(u < P_RING_IP, _pick(rng, ring_ip[ring], ring_nip[ring]),
                        np.where(u < P_RING_IP + 0.10, rng.choice(public, k, p=public_w),
                                 _ips(rng, k)))
        device[f], ip[f] = dev_f, ip_f

    base = online[["trans_num", "cc_num", "ts"]]
    entities = pd.concat([base.assign(kind="device", entity=device),
                          base.assign(kind="ip", entity=ip)], ignore_index=True)
    return entities, rings


def main():
    t0 = time.time()
    engine = get_engine()
    T = transactions.c
    stmt = select(T.trans_num, T.cc_num, T.ts, T.category, T.is_fraud).order_by(T.seq)
    with engine.connect() as conn:
        txns = pd.read_sql(stmt, conn)

    entities, rings = generate(txns)
    reset_tables(engine, [txn_entities, overlay_rings])
    load_frame(engine, entities, table=txn_entities)
    load_frame(engine, rings, table=overlay_rings)

    sizes = rings.drop_duplicates("ring_id")["ring_size"]
    print(f"online txns={len(entities) // 2:,}  entity rows={len(entities):,}  "
          f"built in {time.time() - t0:.1f}s")
    print(f"compromised cards={len(rings):,}  rings={len(sizes):,} "
          f"(lone={int((sizes == 1).sum())}, groups={int((sizes > 1).sum())}, "
          f"median group size={int(sizes[sizes > 1].median()) if (sizes > 1).any() else 0})")


if __name__ == "__main__":
    main()
