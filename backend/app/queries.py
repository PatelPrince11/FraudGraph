"""Read-only queries behind the dashboard: the alert queue and a card's recent history."""
from sqlalchemy import Connection, and_, func, or_, select

from app.graph import mask
from app.tables import scores as S
from app.tables import transactions as T


def _row(r) -> dict:
    return {
        "trans_num": r.trans_num, "ts": r.ts, "cc_num": str(r.cc_num),
        "card_label": mask(r.cc_num), "amt": float(r.amt), "category": r.category,
        "merchant": r.merchant, "score": None if r.score is None else round(float(r.score), 6),
        "flagged": bool(r.flagged), "label_is_fraud": None if r.is_fraud is None else bool(r.is_fraud),
    }


COLS = (T.c.trans_num, T.c.ts, T.c.cc_num, T.c.amt, T.c.category, T.c.merchant,
        T.c.is_fraud, S.c.score, S.c.flagged)


def alerts(conn: Connection, split: str = "test", sort: str = "score",
           limit: int = 50, offset: int = 0) -> dict:
    """Flagged transactions: the analyst's work queue.

    Default split is 'test': train-period scores are in-sample, so showing them
    in a demo would make the model look better than it is.
    """
    base = (select(*COLS).select_from(S.join(T, T.c.trans_num == S.c.trans_num))
            .where(S.c.flagged == 1, T.c.split == split))
    order = (S.c.score.desc(), T.c.ts.desc()) if sort == "score" else (T.c.ts.desc(),)
    rows = conn.execute(base.order_by(*order).limit(limit).offset(offset)).all()
    total = conn.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    return {"total": total, "items": [_row(r) for r in rows]}


def card_history(conn: Connection, trans_num: str, limit: int = 15) -> list[dict] | None:
    """The card's most recent transactions up to and INCLUDING this one (never after it)."""
    seed = conn.execute(select(T.c.cc_num, T.c.ts, T.c.seq)
                        .where(T.c.trans_num == trans_num)).first()
    if seed is None:
        return None
    not_after = or_(T.c.ts < seed.ts, and_(T.c.ts == seed.ts, T.c.seq <= seed.seq))
    rows = conn.execute(
        select(*COLS).select_from(T.outerjoin(S, S.c.trans_num == T.c.trans_num))
        .where(T.c.cc_num == seed.cc_num, not_after)
        .order_by(T.c.ts.desc(), T.c.seq.desc()).limit(limit)).all()
    return [_row(r) for r in rows]
