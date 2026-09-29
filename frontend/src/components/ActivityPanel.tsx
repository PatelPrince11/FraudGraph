import type { TxnRow } from "../api";
import { category, merchantName, money, pct, when } from "../format";
import { DecisionBadge, Panel, Truth } from "./ui";

/** Small icon per spending category group, so the list scans at a glance. */
function CatIcon({ cat }: { cat: string }) {
  const online = cat.endsWith("_net");
  const d = online
    ? "M3 5.5h18v11H3zM8 20h8M12 16.5V20"                        // screen: online purchase
    : cat.startsWith("gas") || cat === "travel"
      ? "M5 20V6a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v14M4 20h12M15 9h2l2 2v6a1.5 1.5 0 0 1-3 0v-3"  // pump
      : "M4 7h16l-1.5 11a2 2 0 0 1-2 1.8H7.5a2 2 0 0 1-2-1.8zM9 7V5a3 3 0 0 1 6 0v2";       // bag
  return (
    <svg viewBox="0 0 24 24" className="size-5 shrink-0 text-muted" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d={d} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function ActivityPanel({ rows, current, showTruth }: {
  rows?: TxnRow[]; current: string; showTruth: boolean;
}) {
  return (
    <Panel title="Account activity" className="h-full" bodyClass="overflow-y-auto">
      <ul className="divide-y divide-line px-5 pb-2">
        {rows?.slice(0, 12).map((t) => (
          <li key={t.trans_num} className={`flex items-center gap-3 py-2.5 ${
            t.trans_num === current ? "-mx-2 rounded-lg bg-raised px-2" : ""}`}>
            <CatIcon cat={t.category} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium tabular-nums">{money(t.amt)}</span>
                <span className="truncate text-xs text-muted">{merchantName(t.merchant)}</span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-faint">
                {category(t.category)} · {when(t.ts)}
                {showTruth && <Truth fraud={t.label_is_fraud} />}
                <DecisionBadge action={t.decision} />
              </div>
            </div>
            <span className={`text-xs font-semibold tabular-nums ${t.flagged ? "text-risk" : "text-faint"}`}>
              {t.score === null ? "–" : t.flagged ? pct(t.score) : "OK"}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
