import type { Graph } from "../api";
import { Panel } from "./ui";

/** The graph as a list: other cards connected to this one, and what connects them. */
export default function LinkedCards({ graph, showTruth }: { graph?: Graph; showTruth: boolean }) {
  if (!graph) return <Panel title="Linked cards" className="h-full"><p className="px-5 text-sm text-faint">Loading…</p></Panel>;
  const seed = graph.nodes.find((n) => n.seed)!;
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  // For each linked card, the devices/IPs it shares with the graph (what put it here).
  const via = new Map<string, Set<string>>();
  for (const e of graph.edges) {
    const [card, ent] = byId.get(e.source)?.kind === "card" ? [e.source, e.target] : [e.target, e.source];
    const k = byId.get(ent)?.kind;
    if (k === "device" || k === "ip") (via.get(card) ?? via.set(card, new Set()).get(card)!).add(k);
  }
  const cards = graph.nodes
    .filter((n) => n.kind === "card" && !n.seed)
    .sort((a, b) => (b.flagged_txns ?? 0) - (a.flagged_txns ?? 0) || (a.hop ?? 9) - (b.hop ?? 9));

  return (
    <Panel title={`Linked cards · ${cards.length}`} className="h-full" bodyClass="overflow-y-auto">
      {cards.length === 0 ? (
        <p className="px-5 pb-5 text-sm text-faint">No other cards share a followed device or IP with {seed.label}.</p>
      ) : (
        <ul className="divide-y divide-line px-5 pb-2">
          {cards.slice(0, 20).map((c) => {
            const alerts = c.flagged_txns ?? 0;
            const missed = showTruth && alerts === 0 && (c.labeled_fraud_txns ?? 0) > 0;
            return (
              <li key={c.id} className="flex items-center gap-3 py-2.5">
                <div className="grid size-9 shrink-0 place-items-center rounded-full border border-line bg-raised">
                  <svg viewBox="0 0 24 24" className="size-4 text-muted" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <rect x="3" y="6" width="18" height="12" rx="2" /><path d="M3 10h18" />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-sm">{c.label}</div>
                  <div className="text-[11px] text-faint">
                    via {[...(via.get(c.id) ?? [])].join(" + ") || "graph"} · {c.hop} hops
                  </div>
                </div>
                <span className={`text-xs font-medium ${alerts ? "text-risk" : missed ? "text-warn" : "text-ok"}`}>
                  {alerts ? `${alerts} alert${alerts > 1 ? "s" : ""}` : missed ? "Missed fraud" : "Normal"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
