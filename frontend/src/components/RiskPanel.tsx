import type { Risk } from "../api";
import { featureValue, money, pct } from "../format";
import { useApi } from "../useApi";
import { Panel, Status, Truth } from "./ui";

// The handful of features an analyst reads first, in plain words.
const FACTS: [string, string, (v: number) => string][] = [
  ["amt_z_card", "Amount vs card's normal", (v) => `${v.toFixed(1)} σ`],
  ["txn_count_24h", "Transactions, previous 24h", (v) => String(v)],
  ["amt_sum_24h", "Spend, previous 24h", money],
  ["secs_since_last", "Since previous transaction", (v) => `${(v / 3600).toFixed(1)} h`],
  ["dist_home_km", "Distance from home", (v) => `${Math.round(v)} km`],
  ["speed_kmh", "Implied travel speed", (v) => `${Math.round(v)} km/h`],
];

export default function RiskPanel({ transNum, showTruth }: { transNum: string; showTruth: boolean }) {
  const { data, error, loading } = useApi<Risk>(`/transactions/${transNum}/risk`);
  const top = data ? Math.max(...data.reasons.map((r) => r.contribution), 1e-9) : 1;

  return (
    <Panel title="Risk assessment" className="h-full"
      right={data && <span className="text-xs text-slate-400">scored in {data.latency_ms.toFixed(0)} ms</span>}>
      <Status loading={loading} error={error} />
      {data && (
        <div className="grid h-full gap-5 overflow-y-auto p-4">
          <div className="flex items-end gap-4">
            <div>
              <div className={`text-4xl font-semibold tabular-nums ${
                data.flagged ? "text-[var(--color-risk)]" : "text-slate-800"}`}>
                {pct(data.score)}
              </div>
              <div className="text-xs text-slate-500">
                fraud probability · alert threshold {pct(data.threshold)}
              </div>
            </div>
            <div className="ml-auto flex items-center gap-2">
              {showTruth && <Truth fraud={data.label_is_fraud} />}
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                data.flagged ? "bg-red-600 text-white" : "bg-slate-100 text-slate-600"}`}>
                {data.flagged ? "Flagged" : "Not flagged"}
              </span>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Why the model flagged it
            </h3>
            <ul className="grid gap-2">
              {data.reasons.map((r) => (
                <li key={r.feature} className="grid grid-cols-[1fr_auto] gap-x-3 text-sm">
                  <span>{r.label} <span className="text-slate-500">= {featureValue(
                    r.feature, r.value, data.features.amt as number)}</span></span>
                  <span className="tabular-nums text-xs text-slate-500">+{r.contribution.toFixed(2)}</span>
                  <div className="col-span-2 h-1.5 rounded bg-slate-100">
                    <div className="h-1.5 rounded bg-red-500" style={{ width: `${(100 * r.contribution) / top}%` }} />
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-slate-400">
              Contributions are SHAP values (log-odds): what the model used, not proof of fraud.
            </p>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {FACTS.map(([key, label, fmt]) => {
              const v = data.features[key];
              return (
                <div key={key} className="flex justify-between gap-2 border-b border-slate-100 pb-1">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="tabular-nums">{typeof v === "number" ? fmt(v) : "n/a"}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      )}
    </Panel>
  );
}
