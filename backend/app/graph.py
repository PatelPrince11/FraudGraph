"""Relationship graph around one transaction: which other cards share devices/IPs
with this card, and do those cards also have alerts?

Expansion, one "round" at a time:
  cards -> devices/IPs they used -> other cards that used those devices/IPs
Three rules keep the graph honest and small:
  1. TIME WINDOW [t - days, t]: an investigator at time t can't see the future.
     Same leakage rule as features.py, applied to the graph.
  2. HUBS: a public IP used by 300 cards connects everyone to everyone. Entities used
     by more than hub_limit cards in the window are shown but NOT expanded.
  3. CAP: stop adding cards at max_cards; the response says it was truncated.

FOLLOW: by default only devices/IPs that carried at least one FLAGGED transaction are
expanded ("follow the suspicious activity"). follow="all" expands every entity;
scripts/eval_graph.py compares the two.

Merchants are never expanded (every popular merchant is a hub). They appear only as
leaves when 3+ cards in the graph have FLAGGED charges there. Weak signal: in Sparkov,
fraud merchants are close to random, so some overlap happens by chance.
"""
import time
from datetime import timedelta

import networkx as nx
from sqlalchemy import Connection, distinct, func, select

from app.tables import scores as S
from app.tables import transactions as T
from app.tables import txn_entities as E

HUB_LIMIT = 25
MAX_CARDS = 60
MIN_MERCHANT_CARDS = 3  # with 2, random overlap (birthday problem) made most of them noise


class NotFound(Exception):
    pass


def card_node(cc) -> str:
    return f"card:{cc}"


def mask(cc) -> str:
    return f"•••• {str(cc)[-4:]}"  # never show full card numbers in a UI


def investigate(conn: Connection, trans_num: str, days: int = 30, rounds: int = 2,
                follow: str = "flagged", hub_limit: int = HUB_LIMIT,
                max_cards: int = MAX_CARDS) -> dict:
    t0 = time.perf_counter()
    seed = conn.execute(select(T.c.cc_num, T.c.ts, T.c.merchant)
                        .where(T.c.trans_num == trans_num)).first()
    if seed is None:
        raise NotFound(trans_num)
    start, end = seed.ts - timedelta(days=days), seed.ts
    in_window = E.c.ts.between(start, end)
    flagged_sum = func.coalesce(func.sum(S.c.flagged), 0)

    G = nx.Graph()
    G.add_node(card_node(seed.cc_num), kind="card", cc_num=seed.cc_num)
    cards, frontier = {seed.cc_num}, {seed.cc_num}
    seen, hubs, truncated = set(), set(), False

    def usage(condition):
        """(card, entity) pairs in the window, with how many txns and how many flagged."""
        stmt = (select(E.c.cc_num, E.c.kind, E.c.entity,
                       func.count().label("n"), flagged_sum.label("flagged"))
                .select_from(E.outerjoin(S, S.c.trans_num == E.c.trans_num))
                .where(in_window, condition)
                .group_by(E.c.cc_num, E.c.kind, E.c.entity))
        return conn.execute(stmt).all()

    def add_edge(r):
        ent = f"{r.kind}:{r.entity}"
        if ent not in G:
            G.add_node(ent, kind=r.kind)
        G.add_edge(card_node(r.cc_num), ent, kind=f"uses_{r.kind}",
                   txn_count=int(r.n), flagged_txns=int(r.flagged))

    for _ in range(rounds):
        if not frontier:
            break
        rows = usage(E.c.cc_num.in_(frontier))
        for r in rows:
            add_edge(r)
        new = {r.entity for r in rows
               if follow == "all" or r.flagged > 0} - seen
        seen |= new
        frontier = set()
        if not new:
            break

        # Degree check BEFORE expanding: how many distinct cards used each entity?
        degree = dict(conn.execute(
            select(E.c.entity, func.count(distinct(E.c.cc_num)))
            .where(in_window, E.c.entity.in_(new)).group_by(E.c.entity)).all())
        for r in rows:
            if r.entity in degree:
                G.nodes[f"{r.kind}:{r.entity}"]["cards_in_window"] = int(degree[r.entity])
        new_hubs = {e for e, d in degree.items() if d > hub_limit}
        hubs |= new_hubs

        for r in usage(E.c.entity.in_(new - new_hubs)):
            if r.cc_num not in cards:
                if len(cards) >= max_cards:
                    truncated = True
                    continue
                cards.add(r.cc_num)
                frontier.add(r.cc_num)
                G.add_node(card_node(r.cc_num), kind="card", cc_num=r.cc_num)
            add_edge(r)

    # How many cards used each device/IP in the window, for entities we didn't expand
    # too (the UI would otherwise show blanks). One query for all of them.
    missing = [n.split(":", 1)[1] for n, a in G.nodes(data=True)
               if a["kind"] in ("device", "ip") and "cards_in_window" not in a]
    if missing:
        for entity, kind, d in conn.execute(
                select(E.c.entity, E.c.kind, func.count(distinct(E.c.cc_num)))
                .where(in_window, E.c.entity.in_(missing))
                .group_by(E.c.entity, E.c.kind)).all():
            G.nodes[f"{kind}:{entity}"]["cards_in_window"] = int(d)

    # Card-level facts in the window.
    stats = conn.execute(
        select(T.c.cc_num, func.count().label("n"), flagged_sum.label("flagged"),
               func.coalesce(func.sum(T.c.is_fraud), 0).label("fraud"))
        .select_from(T.outerjoin(S, S.c.trans_num == T.c.trans_num))
        .where(T.c.cc_num.in_(cards), T.c.ts.between(start, end))
        .group_by(T.c.cc_num)).all()
    for r in stats:
        G.nodes[card_node(r.cc_num)].update(
            txn_count=int(r.n), flagged_txns=int(r.flagged), labeled_fraud_txns=int(r.fraud))

    # Merchants where MIN_MERCHANT_CARDS+ graph cards had flagged charges.
    rows = conn.execute(
        select(T.c.cc_num, T.c.merchant, func.count().label("n"))
        .select_from(T.join(S, S.c.trans_num == T.c.trans_num))
        .where(S.c.flagged == 1, T.c.cc_num.in_(cards), T.c.ts.between(start, end))
        .group_by(T.c.cc_num, T.c.merchant)).all()
    by_merchant: dict[str, list] = {}
    for r in rows:
        by_merchant.setdefault(r.merchant, []).append(r)
    for merchant, rs in by_merchant.items():
        if len(rs) >= MIN_MERCHANT_CARDS:
            G.add_node(f"merchant:{merchant}", kind="merchant")
            for r in rs:
                G.add_edge(card_node(r.cc_num), f"merchant:{merchant}", kind="flagged_at",
                           txn_count=int(r.n), flagged_txns=int(r.n))

    return _to_json(G, seed, trans_num, start, end, hubs, truncated, t0)


def _to_json(G, seed, trans_num, start, end, hubs, truncated, t0) -> dict:
    seed_id = card_node(seed.cc_num)
    hops = nx.single_source_shortest_path_length(G, seed_id)
    nodes = []
    for node_id, a in G.nodes(data=True):
        name = node_id.split(":", 1)[1]
        node = {"id": node_id, "kind": a["kind"], "hop": hops.get(node_id),
                "label": mask(a["cc_num"]) if a["kind"] == "card" else name}
        if a["kind"] == "card":
            node.update(seed=node_id == seed_id, txn_count=a.get("txn_count", 0),
                        flagged_txns=a.get("flagged_txns", 0),
                        labeled_fraud_txns=a.get("labeled_fraud_txns", 0))
        elif a["kind"] in ("device", "ip"):
            node.update(hub=name in hubs, cards_in_window=a.get("cards_in_window"))
        nodes.append(node)
    edges = [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]

    card_nodes = [n for n in nodes if n["kind"] == "card"]
    summary = {
        "cards": len(card_nodes),
        "flagged_cards": sum(n["flagged_txns"] > 0 for n in card_nodes),
        "labeled_fraud_cards": sum(n["labeled_fraud_txns"] > 0 for n in card_nodes),
        # device/IP nodes touching 2+ cards IN THIS GRAPH: the actual links
        "shared_entities": sum(1 for n in nodes if n["kind"] in ("device", "ip")
                               and G.degree(n["id"]) >= 2),
        "hubs_not_expanded": len(hubs),
        "truncated": truncated,
        "latency_ms": round(1000 * (time.perf_counter() - t0), 2),
    }
    return {"trans_num": trans_num, "window_start": start, "window_end": end,
            "nodes": nodes, "edges": edges, "summary": summary}
