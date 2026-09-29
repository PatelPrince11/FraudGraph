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
