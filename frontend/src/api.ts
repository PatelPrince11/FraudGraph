// TypeScript mirrors of backend/app/schemas.py. If you change a Pydantic model,
// change the matching type here. (Later we can generate these from /openapi.json.)

export type Reason = { feature: string; label: string; value: number | string | null; contribution: number };

export type Risk = {
  trans_num: string;
  cc_num: string; // string on purpose: card numbers exceed JavaScript's safe integer range
  score: number;
  threshold: number;
  flagged: boolean;
  reasons: Reason[];
  features: Record<string, number | string | null>;
  history_rows: number;
  latency_ms: number;
  label_is_fraud: boolean | null;
};

export type TxnRow = {
  trans_num: string;
  ts: string;
  cc_num: string;
  card_label: string;
  amt: number;
  category: string;
  merchant: string;
  merch_lat: number;
  merch_long: number;
  score: number | null;
  flagged: boolean;
  label_is_fraud: boolean | null;
  decision: Action | null;
};

export type Action = "fraud" | "escalated" | "legit";

export type Decision = { trans_num: string; action: Action | null; decided_at: string | null };

export type CardSummary = {
  cc_num: string;
  card_label: string;
  city: string | null;
  state: string | null;
  home_lat: number;
  home_long: number;
  age: number;
  first_seen: string;
  txn_count: number;
  alert_count: number;
  avg_amt: number;
};

export type Follow = "flagged" | "rule" | "either" | "all";

export type Alerts = { total: number; items: TxnRow[] };

export type GraphNode = {
  id: string;
  kind: "card" | "device" | "ip" | "merchant";
  label: string;
  hop: number | null;
  seed: boolean | null;
  txn_count: number | null;
  flagged_txns: number | null;
  labeled_fraud_txns: number | null;
  hub: boolean | null;
  cards_in_window: number | null;
  rule_hit: boolean | null;
  max_cards_24h: number | null;
};

export type GraphEdge = { source: string; target: string; kind: string; txn_count: number; flagged_txns: number };

export type Graph = {
  trans_num: string;
  window_start: string;
  window_end: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    cards: number;
    flagged_cards: number;
    labeled_fraud_cards: number;
    shared_entities: number;
    hubs_not_expanded: number;
    rule_devices: number;
    truncated: boolean;
    latency_ms: number;
  };
};

export type ReplayStatus = {
  status: "idle" | "running" | "done" | "stopped";
  sim_start: string | null;
  sim_end: string | null;
  sim_clock: string | null;
  speed: number | null;
  processed: number;
  total: number;
  flagged: number;
  txn_per_sec: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  lag_s: number | null;
  updated_at: string | null;
};
