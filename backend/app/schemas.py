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
    cc_num: int
    score: float
    threshold: float
    flagged: bool
    reasons: list[Reason]
    features: dict[str, float | int | str | None]
    history_rows: int
    latency_ms: float
    label_is_fraud: bool | None = None
