"""Engine creation and bulk loading."""
import io

import pandas as pd
from sqlalchemy import Engine, create_engine, insert

from app.config import DATABASE_URL
from app.tables import COLUMNS, metadata, transactions


def get_engine(url: str = DATABASE_URL) -> Engine:
    # pool_pre_ping: test a pooled connection before use, so a restarted DB
    # doesn't hand the API a dead connection.
    return create_engine(url, pool_pre_ping=True)


def to_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw Sparkov frame -> table-shaped frame. `seq` must already be set."""
    df = raw.rename(columns={"trans_date_trans_time": "ts"})
    df["ts"] = pd.to_datetime(df["ts"])
    df["dob"] = pd.to_datetime(df["dob"]).dt.date
    return df.reindex(columns=COLUMNS)  # missing optional columns -> NaN/NULL


def reset_schema(engine: Engine) -> None:
    metadata.drop_all(engine)
    metadata.create_all(engine)


def load_frame(engine: Engine, rows: pd.DataFrame, chunk: int = 200_000) -> None:
    """Postgres: COPY (streams CSV straight into the table, ~50x faster than INSERTs).
    Anything else (SQLite in tests): plain batched INSERTs."""
    if engine.dialect.name != "postgresql":
        with engine.begin() as conn:
            conn.execute(insert(transactions), rows.astype(object).where(rows.notna(), None)
                         .to_dict("records"))
        return

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cols = ", ".join('"' + c + '"' for c in COLUMNS)  # quoted: "first"/"last" are SQL words
        sql = f"COPY transactions ({cols}) FROM STDIN WITH (FORMAT csv)"
        for start in range(0, len(rows), chunk):
            buf = io.StringIO()
            rows.iloc[start:start + chunk].to_csv(buf, index=False, header=False)
            with cur.copy(sql) as copy:
                copy.write(buf.getvalue())
        raw.commit()
    finally:
        raw.close()
