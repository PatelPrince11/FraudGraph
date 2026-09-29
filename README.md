# FraudGraph — Fraud Investigation Engine

Scores card transactions for fraud using behavioural features, explains every alert,
and (coming) links accounts, devices, IPs and merchants in a relationship graph.

## How data flows

    data/raw/*.csv
      -> scripts/build_features.py   (uses app/features.py)
      -> data/processed/features.parquet
      -> scripts/train.py            (uses app/model.py)
      -> data/models/model.json + meta.json + metrics.json
      -> scripts/load_db.py -> PostgreSQL (card history for online scoring)
      -> app/main.py (FastAPI): rebuilds features from history, scores, explains
      -> scripts/score_all.py -> scores table (every transaction scored once)
      -> scripts/make_graph_overlay.py -> SYNTHETIC devices/IPs/fraud rings
      -> app/graph.py: GET /transactions/{id}/graph (cards linked by shared devices/IPs)
      -> frontend/ (React + Vite): alert queue -> risk + reasons -> card history -> graph

## Setup

    cd backend
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    pytest -q

## Run

    python -m scripts.build_features
    python -m scripts.train
    docker compose up -d db          # from repo root
    cp .env.example .env             # from backend/
    python -m scripts.load_db
    python -m scripts.check_parity   # online features == offline features
    python -m scripts.score_all
    python -m scripts.make_graph_overlay
    python -m scripts.eval_graph     # graph recall/precision/latency on planted rings
    uvicorn app.main:app --reload    # API docs at http://127.0.0.1:8000/docs

Always run backend commands from `backend/`.

Dashboard (second terminal, API must be running):

    cd frontend
    npm install
    npm run dev                      # http://localhost:5173

Vite forwards `/api/*` to FastAPI on port 8000, so the browser sees one origin (no CORS).

## Data notes

- Dataset: Sparkov simulated credit card transactions (Kaggle). Simulated, so scores run high.
- `unix_time` is offset ~7 years from `trans_date_trans_time`; only the latter is used.
- Merchant names all start with `fraud_`; merchant ID is not a model feature.
- Devices, IPs and fraud rings are **synthetic** (Sparkov has none). They live in separate
  tables, cover online (`_net`) transactions only, and are never model inputs. Graph
  metrics validate the query logic on planted rings, not real-world ring detection.
- Train-period scores in the `scores` table are in-sample; only test-period scores are honest.
