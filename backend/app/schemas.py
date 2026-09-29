"""Request/response shapes. FastAPI validates input against these and rejects bad
requests with a 422 before our code runs, and generates /docs from them."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class TransactionIn(BaseModel):
    trans_num: str | None = Field(None, max_length=32)
    cc_num: int
    ts: datetime
    merchant: str
    category: str
    amt: float = Field(gt=0)
    lat: float = Field(ge=-90, le=90)
    long: float = Field(ge=-180, le=180)
    merch_lat: float = Field(ge=-90, le=90)
    merch_long: float = Field(ge=-180, le=180)
    dob: date


class Reason(BaseModel):
    feature: str
    label: str
    value: float | int | str | None
    contribution: float


class RiskOut(BaseModel):
    trans_num: str
    # String, not int: card numbers go up to ~5e18, and JavaScript numbers lose
    # precision above 2^53 (~9e15). The browser would silently show the wrong card.
    cc_num: str
    score: float
    threshold: float
    flagged: bool
    reasons: list[Reason]
    features: dict[str, float | int | str | None]
    history_rows: int
    latency_ms: float
    label_is_fraud: bool | None = None


class GraphNode(BaseModel):
    id: str
    kind: str                      # card | device | ip | merchant
    label: str
    hop: int | None
    seed: bool | None = None
    txn_count: int | None = None
    flagged_txns: int | None = None
    labeled_fraud_txns: int | None = None  # ground truth: demo/eval only, not known at time t
    hub: bool | None = None
    cards_in_window: int | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str
    txn_count: int
    flagged_txns: int


class GraphSummary(BaseModel):
    cards: int
    flagged_cards: int
    labeled_fraud_cards: int
    shared_entities: int
    hubs_not_expanded: int
    truncated: bool
    latency_ms: float


class GraphOut(BaseModel):
    trans_num: str
    window_start: datetime
    window_end: datetime
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: GraphSummary


class TxnRow(BaseModel):
    trans_num: str
    ts: datetime
    cc_num: str
    card_label: str
    amt: float
    category: str
    merchant: str
    score: float | None
    flagged: bool
    label_is_fraud: bool | None


class AlertsOut(BaseModel):
    total: int
    items: list[TxnRow]


class ReplayStatus(BaseModel):
    status: str                    # idle | running | done | stopped
    sim_start: datetime | None = None
    sim_end: datetime | None = None
    sim_clock: datetime | None = None
    speed: float | None = None
    processed: int = 0
    total: int = 0
    flagged: int = 0
    txn_per_sec: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    lag_s: float | None = None
    updated_at: datetime | None = None
