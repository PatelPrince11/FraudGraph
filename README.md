# FraudGraph — Fraud Investigation Engine

Scores card transactions for fraud using behavioural features, explains every alert,
and (coming) links accounts, devices, IPs and merchants in a relationship graph.

## How data flows

    data/raw/*.csv
      -> scripts/build_features.py   (uses app/features.py)
      -> data/processed/features.parquet
      -> scripts/train.py            (uses app/model.py)
      -> data/models/model.json + meta.json + metrics.json
      -> [next] FastAPI -> React dashboard

## Setup

    cd backend
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    pytest -q

## Run

    python -m scripts.build_features
    python -m scripts.train

Always run commands from `backend/`.

## Data notes

- Dataset: Sparkov simulated credit card transactions (Kaggle). Simulated, so scores run high.
- `unix_time` is offset ~7 years from `trans_date_trans_time`; only the latter is used.
- Merchant names all start with `fraud_`; merchant ID is not a model feature.
