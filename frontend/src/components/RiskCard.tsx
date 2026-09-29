import type { Risk, TxnRow } from "../api";
import { featureValue, pct, riskTier, when } from "../format";
import { Panel, Status, Truth } from "./ui";
import TrendChart from "./TrendChart";

// The handful of transaction-level signals an analyst reads first.
const SIGNALS: [string, string][] = [
  ["amt_z_card", "Amount vs card's normal"],
  ["txn_count_24h", "Transactions, previous 24h"],
  ["secs_since_last", "Since previous transaction"],
  ["dist_home_km", "Distance from home"],
];

export default function RiskCard({ risk, history, showTruth }: {
  risk: { data?: Risk; error?: string; loading: boolean };
  history?: TxnRow[];
  showTruth: boolean;
}) {
  const d = risk.data;
  const tier = d ? riskTier(d.score, d.threshold) : null;
  const top = d ? Math.max(...d.reasons.map((r) => r.contribution), 1e-9) : 1;

  return (
    <Panel title="Transaction risk score" className="h-full"
      right={d && <span className="text-xs text-faint">scored in {d.latency_ms.toFixed(0)} ms</span>}>
      <Status loading={risk.loading} error={risk.error} />
      {d && tier && (
        <div className="grid gap-6 px-5 pb-5 lg:grid-cols-[210px_1fr]">
          <div className="flex flex-col justify-between gap-4">
            <div>
              <div className="flex items-baseline gap-1">
                <span className={`text-7xl font-bold leading-none tracking-tighter tabular-nums ${tier.color}`}>
                  {Math.floor(d.score * 100) /* floor: 99.96% must not read as 100 */}
                </span>
                <span className="text-2xl font-semibold text-muted">/100</span>
              </div>
              <div className={`mt-2 text-xl font-semibold ${tier.color}`}>{tier.label}</div>
              <div className="mt-1 text-xs text-muted">
                fraud probability {pct(d.score)} · alert at {pct(d.threshold)}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                d.flagged ? "bg-risk text-white" : "bg-raised text-muted"}`}>
                {d.flagged ? "Flagged" : "Not flagged"}
              </span>
              {showTruth && <Truth fraud={d.label_is_fraud} />}
            </div>
          </div>

          <div className="min-w-0">
            <div className="mb-1 flex items-baseline justify-between text-xs text-faint">
              <span>This card's recent scores</span>
              {history?.length ? <span>{when(history[history.length - 1].ts)} → now</span> : null}
            </div>
            {history && <TrendChart rows={history} threshold={d.threshold} current={d.trans_num} />}
          </div>

          <div className="lg:col-span-2">
            <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
              Why the model flagged it
            </h3>
            <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
              {d.reasons.map((r) => (
                <div key={r.feature}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate">
                      {r.label} <span className="text-muted">
                        {featureValue(r.feature, r.value, d.features.amt as number)}</span>
                    </span>
                    <span className="text-xs tabular-nums text-faint">+{r.contribution.toFixed(2)}</span>
                  </div>
                  <div className="mt-1.5 h-1 rounded-full bg-raised">
                    <div className="h-1 rounded-full bg-risk" style={{ width: `${(100 * r.contribution) / top}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-x-8 border-t border-line pt-2 md:grid-cols-4">
              {SIGNALS.map(([key, label]) => (
                <div key={key} className="py-1.5">
                  <dt className="text-[11px] text-faint">{label}</dt>
                  <dd className="text-sm tabular-nums">{featureValue(key, d.features[key])}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-[11px] text-faint">
              Contributions are SHAP values (log-odds): what the model used, not proof of fraud.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}
