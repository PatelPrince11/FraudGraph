"""FastAPI app.

create_app() takes the engine and model as arguments ("dependency injection"), so
tests can pass a SQLite DB and a tiny model instead of the real ones.
Run locally:  uvicorn app.main:app --reload   (from backend/)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import Engine, text

from app import service
from app.db import get_engine
from app.model import FraudModel
from app.schemas import RiskOut, TransactionIn


def create_app(engine: Engine | None = None, model: FraudModel | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load once at startup, not per request: model load is ~100ms+.
        app.state.engine = engine or get_engine()
        app.state.model = model or FraudModel.load()
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

    return app


app = create_app()
