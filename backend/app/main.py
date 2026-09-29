"""FastAPI app.

create_app() takes the engine and model as arguments ("dependency injection"), so
tests can pass a SQLite DB and a tiny model instead of the real ones.
Run locally:  uvicorn app.main:app --reload   (from backend/)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError

from app import graph, queries, service
from app.db import get_engine
from app.model import FraudModel
from app.schemas import (AlertsOut, CardSummary, DecisionIn, DecisionOut, GraphOut,
                         ReplayStatus, RiskOut, TransactionIn, TxnRow)
from app.tables import decisions, metadata, replay_state


def create_app(engine: Engine | None = None, model: FraudModel | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load once at startup, not per request: model load is ~100ms+.
        app.state.engine = engine or get_engine()
        app.state.model = model or FraudModel.load()
        # Decisions are new in this version; create the table if this DB predates it.
        metadata.create_all(app.state.engine, tables=[decisions])
        yield
        app.state.engine.dispose()

    app = FastAPI(title="FraudGraph API", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request):
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    # Plain `def` (not async): pandas/XGBoost block the CPU, so FastAPI runs these
    # in a threadpool instead of freezing its event loop.
    @app.get("/transactions/{trans_num}/risk", response_model=RiskOut)
    def risk(trans_num: str, request: Request):
        with request.app.state.engine.connect() as conn:
            try:
                return service.score_existing(conn, request.app.state.model, trans_num)
            except service.NotFound:
                raise HTTPException(404, f"transaction {trans_num} not found")

    @app.post("/score", response_model=RiskOut)
    def score(txn: TransactionIn, request: Request):
        with request.app.state.engine.connect() as conn:
            return service.score(conn, request.app.state.model, txn.model_dump())

    @app.get("/transactions/{trans_num}/graph", response_model=GraphOut)
    def relationship_graph(trans_num: str, request: Request,
                           days: int = Query(30, ge=1, le=90),
                           rounds: int = Query(2, ge=1, le=3),
                           follow: str = Query("either", pattern="^(flagged|rule|either|all)$")):
        with request.app.state.engine.connect() as conn:
            try:
                return graph.investigate(conn, trans_num, days=days, rounds=rounds,
                                         follow=follow)
            except graph.NotFound:
                raise HTTPException(404, f"transaction {trans_num} not found")

    @app.get("/alerts", response_model=AlertsOut)
    def alert_queue(request: Request,
                    split: str = Query("test", pattern="^(train|test)$"),
                    sort: str = Query("score", pattern="^(score|recent)$"),
                    status: str = Query("all", pattern="^(all|open|decided)$"),
                    limit: int = Query(50, ge=1, le=200),
                    offset: int = Query(0, ge=0)):
        with request.app.state.engine.connect() as conn:
            return queries.alerts(conn, split=split, sort=sort, status=status,
                                  limit=limit, offset=offset)

    @app.get("/transactions/{trans_num}/history", response_model=list[TxnRow])
    def history(trans_num: str, request: Request, limit: int = Query(15, ge=1, le=100)):
        with request.app.state.engine.connect() as conn:
            rows = queries.card_history(conn, trans_num, limit=limit)
        if rows is None:
            raise HTTPException(404, f"transaction {trans_num} not found")
        return rows

    @app.get("/transactions/{trans_num}/card", response_model=CardSummary)
    def card(trans_num: str, request: Request):
        with request.app.state.engine.connect() as conn:
            summary = queries.card_summary(conn, trans_num)
        if summary is None:
            raise HTTPException(404, f"transaction {trans_num} not found")
        return summary

    @app.get("/transactions/{trans_num}/decision", response_model=DecisionOut)
    def get_decision(trans_num: str, request: Request):
        with request.app.state.engine.connect() as conn:
            return queries.get_decision(conn, trans_num)

    @app.post("/transactions/{trans_num}/decision", response_model=DecisionOut)
    def set_decision(trans_num: str, body: DecisionIn, request: Request):
        with request.app.state.engine.begin() as conn:  # begin() = commit on success
            if not queries.exists(conn, trans_num):
                raise HTTPException(404, f"transaction {trans_num} not found")
            return queries.set_decision(conn, trans_num, body.action)

    @app.get("/replay/status", response_model=ReplayStatus)
    def replay_status(request: Request):
        """Progress of scripts/replay.py (a separate process), read from its state row."""
        with request.app.state.engine.connect() as conn:
            try:
                row = conn.execute(select(replay_state)).mappings().first()
            except DBAPIError:  # table not created yet: replay has never run
                return {"status": "idle"}
        return {**row} if row else {"status": "idle"}

    return app


app = create_app()
