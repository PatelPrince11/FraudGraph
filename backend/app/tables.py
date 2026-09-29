"""Database schema (SQLAlchemy Core).

Core = Python objects that describe tables and build SQL. No ORM classes: our
workload is "fetch a card's history as a DataFrame", which is a query, not objects.
"""
from sqlalchemy import (BigInteger, Column, Date, DateTime, Float, Index, MetaData,
                        Numeric, SmallInteger, String, Table)

metadata = MetaData()

transactions = Table(
    "transactions", metadata,
    Column("trans_num", String(32), primary_key=True),
    # seq = row order in the original files. Breaks ties between same-card transactions
    # with identical timestamps exactly the way the offline pipeline did.
    Column("seq", BigInteger, nullable=False, unique=True),
    Column("cc_num", BigInteger, nullable=False),
    Column("ts", DateTime, nullable=False),
    Column("merchant", String(80), nullable=False),
    Column("category", String(20), nullable=False),
    # Money is NUMERIC in the database (exact cents). asdecimal=False hands Python
    # floats to pandas, because numpy math on Decimal objects is slow and awkward.
    Column("amt", Numeric(12, 2, asdecimal=False), nullable=False),
    Column("first", String(40)), Column("last", String(40)),
    Column("city", String(60)), Column("state", String(2)),
    Column("lat", Float, nullable=False), Column("long", Float, nullable=False),
    Column("merch_lat", Float, nullable=False), Column("merch_long", Float, nullable=False),
    Column("dob", Date, nullable=False),
    Column("is_fraud", SmallInteger),  # ground-truth label; never a model input
    Column("split", String(5), nullable=False),
    # THE index for this app: "all of card X's transactions before time T, in order".
    Index("ix_card_history", "cc_num", "ts", "seq"),
)

COLUMNS = [c.name for c in transactions.columns]

# Model output for every stored transaction, written by scripts/score_all.py.
# Separate table because it changes every time the model is retrained; the
# transactions themselves never change.
scores = Table(
    "scores", metadata,
    Column("trans_num", String(32), primary_key=True),
    Column("score", Float, nullable=False),
    Column("flagged", SmallInteger, nullable=False),  # 1 if score >= model threshold
)

# --- SYNTHETIC overlay (scripts/make_graph_overlay.py) -------------------------
# Sparkov has no devices or IPs. These tables add them for ONLINE transactions only
# (categories ending in _net): an in-store card swipe has no customer device or IP.
# Kept apart from `transactions` so real data and generated data never mix, and the
# model never trains on them.
txn_entities = Table(
    "txn_entities", metadata,
    Column("trans_num", String(32), primary_key=True),
    Column("kind", String(6), primary_key=True),       # "device" or "ip"
    Column("entity", String(40), nullable=False),
    # Copied from transactions (denormalized) so graph queries never need a join.
    Column("cc_num", BigInteger, nullable=False),
    Column("ts", DateTime, nullable=False),
    Index("ix_entity_time", "entity", "ts"),            # who else used this device/IP, when?
    Index("ix_entity_card_time", "cc_num", "ts"),       # which devices/IPs did this card use?
)

# Ground truth for the generated fraud rings. Used ONLY by scripts/eval_graph.py
# to measure the graph query. Never read by the API.
overlay_rings = Table(
    "overlay_rings", metadata,
    Column("cc_num", BigInteger, primary_key=True),
    Column("ring_id", BigInteger, nullable=False),
    Column("ring_size", SmallInteger, nullable=False),
)
