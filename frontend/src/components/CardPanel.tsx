import type { CardSummary } from "../api";
import { money, monthYear } from "../format";
import { Panel, Row, Status } from "./ui";

export default function CardPanel({ card }: { card: { data?: CardSummary; error?: string; loading: boolean } }) {
  const c = card.data;
  return (
    <Panel title="Case summary" className="h-full">
      <Status loading={card.loading} error={card.error} />
      {c && (
        <div className="px-5 pb-5">
          <div className="flex items-center gap-4 pb-4">
            <div className="grid size-14 shrink-0 place-items-center rounded-2xl border border-line bg-raised">
              <svg viewBox="0 0 24 24" className="size-7 text-muted" fill="none" stroke="currentColor" strokeWidth="1.6">
                <rect x="2.5" y="5" width="19" height="14" rx="2.5" /><path d="M2.5 9.5h19M6 15h4" />
              </svg>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs text-muted">
                <span className={`size-2 rounded-full ${c.alert_count ? "bg-risk" : "bg-ok"}`} />
                {c.alert_count ? "Card under review" : "No alerts on this card"}
              </div>
              <div className="font-mono text-2xl font-semibold tracking-tight">{c.card_label}</div>
            </div>
          </div>
          <dl className="divide-y divide-line border-t border-line">
            <Row k="Home" v={[c.city, c.state].filter(Boolean).join(", ") || "n/a"} />
            <Row k="Cardholder age" v={`${c.age}`} />
            <Row k="Card history since" v={monthYear(c.first_seen)} />
            <Row k="Transactions to date" v={c.txn_count.toLocaleString()} />
            <Row k="Average purchase" v={money(c.avg_amt)} />
            <Row k="Alerts to date" v={<span className={c.alert_count ? "text-risk" : ""}>{c.alert_count}</span>} />
          </dl>
        </div>
      )}
    </Panel>
  );
}
