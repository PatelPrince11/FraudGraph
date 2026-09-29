"""Queries behind the dashboard: alert queue, card history, card summary, decisions."""
from datetime import datetime

from sqlalchemy import Connection, and_, delete, func, insert, or_, select

from app.graph import mask
from app.tables import decisions as D
from app.tables import scores as S
from app.tables import transactions as T

ACTIONS = ("fraud", "escalated", "legit")


def _row(r) -> dict:
    return {
        "trans_num": r.trans_num, "ts": r.ts, "cc_num": str(r.cc_num),
        "card_label": mask(r.cc_num), "amt": float(r.amt), "category": r.category,
        "merchant": r.merchant, "merch_lat": r.merch_lat, "merch_long": r.merch_long,
        "score": None if r.score is None else round(float(r.score), 6),
        "flagged": bool(r.flagged), "label_is_fraud": None if r.is_fraud is None else bool(r.is_fraud),
        "decision": r.action,
    }


COLS = (T.c.trans_num, T.c.ts, T.c.cc_num, T.c.amt, T.c.category, T.c.merchant,
        T.c.merch_lat, T.c.merch_long, T.c.is_fraud, S.c.score, S.c.flagged, D.c.action)


def alerts(conn: Connection, split: str = "test", sort: str = "score", status: str = "all",
           limit: int = 50, offset: int = 0) -> dict:
    """Flagged transactions: the analyst's work queue.

    Default split is 'test': train-period scores are in-sample, so showing them
    in a demo would make the model look better than it is.
    status: all | open (no decision yet) | decided.
    """
    base = (select(*COLS)
            .select_from(S.join(T, T.c.trans_num == S.c.trans_num)
                         .outerjoin(D, D.c.trans_num == S.c.trans_num))
            .where(S.c.flagged == 1, T.c.split == split))
    if status == "open":
        base = base.where(D.c.action.is_(None))
    elif status == "decided":
        base = base.where(D.c.action.isnot(None))
    order = (S.c.score.desc(), T.c.ts.desc()) if sort == "score" else (T.c.ts.desc(),)
    rows = conn.execute(base.order_by(*order).limit(limit).offset(offset)).all()
    total = conn.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    return {"total": total, "items": [_row(r) for r in rows]}


def _seed(conn: Connection, trans_num: str):
    return conn.execute(select(T).where(T.c.trans_num == trans_num)).first()


def _not_after(seed):
    """The seed transaction and everything before it on the same card (never the future)."""
    return and_(T.c.cc_num == seed.cc_num,
                or_(T.c.ts < seed.ts, and_(T.c.ts == seed.ts, T.c.seq <= seed.seq)))


def card_history(conn: Connection, trans_num: str, limit: int = 15) -> list[dict] | None:
    """The card's most recent transactions up to and INCLUDING this one."""
    seed = _seed(conn, trans_num)
    if seed is None:
        return None
    rows = conn.execute(
        select(*COLS).select_from(T.outerjoin(S, S.c.trans_num == T.c.trans_num)
                                  .outerjoin(D, D.c.trans_num == T.c.trans_num))
        .where(_not_after(seed))
        .order_by(T.c.ts.desc(), T.c.seq.desc()).limit(limit)).all()
    return [_row(r) for r in rows]


def card_summary(conn: Connection, trans_num: str) -> dict | None:
    """Who is this card, as of the alert: home, history length, earlier alerts."""
    seed = _seed(conn, trans_num)
    if seed is None:
        return None
    n, first, avg_amt = conn.execute(select(func.count(), func.min(T.c.ts), func.avg(T.c.amt))
                                     .where(_not_after(seed))).one()
    n_alerts = conn.execute(select(func.count()).select_from(
        T.join(S, S.c.trans_num == T.c.trans_num)).where(_not_after(seed), S.c.flagged == 1)
    ).scalar_one()
    age = (seed.ts.date() - seed.dob).days / 365.25
    return {
        "cc_num": str(seed.cc_num), "card_label": mask(seed.cc_num),
        "city": seed.city, "state": seed.state, "home_lat": seed.lat, "home_long": seed.long,
        "age": int(age), "first_seen": first, "txn_count": n, "alert_count": n_alerts,
        "avg_amt": round(float(avg_amt), 2),
    }


def get_decision(conn: Connection, trans_num: str) -> dict:
    row = conn.execute(select(D).where(D.c.trans_num == trans_num)).first()
    return {"trans_num": trans_num, "action": row.action if row else None,
            "decided_at": row.decided_at if row else None}


def set_decision(conn: Connection, trans_num: str, action: str | None) -> dict:
    """Record (or clear, with None) the analyst's decision. Caller commits."""
    conn.execute(delete(D).where(D.c.trans_num == trans_num))
    if action is not None:
        conn.execute(insert(D), [{"trans_num": trans_num, "action": action,
                                  "decided_at": datetime.now()}])
    return get_decision(conn, trans_num)


def exists(conn: Connection, trans_num: str) -> bool:
    return conn.execute(select(T.c.trans_num).where(T.c.trans_num == trans_num)).first() is not None
