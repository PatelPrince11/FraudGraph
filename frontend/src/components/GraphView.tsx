import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-2d";

import type { Follow, Graph, GraphEdge, GraphNode } from "../api";
import { Panel, Segmented, Status } from "./ui";

type N = NodeObject<GraphNode>;
type L = LinkObject<GraphNode, GraphEdge>;

const COLOR = {
  risk: "#ff3b30", card: "#6b6b73", device: "#5e9bff", ip: "#4fd1c5",
  hub: "#3a3a40", merchant: "#bf5af2", rule: "#ff9f0a", missed: "#ff9f0a",
  label: "#b4b4bb", seedRing: "#e6e6e8",
};

export const FOLLOW_OPTIONS: { value: Follow; label: string }[] = [
  { value: "either", label: "Alerts + device rule" },
  { value: "flagged", label: "Model alerts" },
  { value: "rule", label: "Device rule" },
  { value: "all", label: "All links" },
];

/** Measure a div so the canvas can fill it (the graph library needs pixel sizes). */
function useSize(ref: React.RefObject<HTMLDivElement | null>) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) =>
      setSize({ width: e.contentRect.width, height: e.contentRect.height }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

function nodeColor(n: GraphNode): string {
  if (n.kind === "card") return (n.flagged_txns ?? 0) > 0 ? COLOR.risk : COLOR.card;
  if (n.hub) return COLOR.hub;
  return COLOR[n.kind];
}

function nodeRadius(n: GraphNode): number {
  if (n.kind !== "card") return 4;
  return 5 + Math.min(6, Math.sqrt(n.flagged_txns ?? 0) * 1.5);
}

/** Card = circle, device = square, IP = diamond, merchant = triangle. */
function tracePath(ctx: CanvasRenderingContext2D, n: N, r: number) {
  const x = n.x ?? 0, y = n.y ?? 0;
  ctx.beginPath();
  if (n.kind === "card") ctx.arc(x, y, r, 0, 2 * Math.PI);
  else if (n.kind === "device") ctx.rect(x - r, y - r, 2 * r, 2 * r);
  else if (n.kind === "ip") {
    ctx.moveTo(x, y - r * 1.3); ctx.lineTo(x + r * 1.3, y);
    ctx.lineTo(x, y + r * 1.3); ctx.lineTo(x - r * 1.3, y); ctx.closePath();
  } else {
    ctx.moveTo(x, y - r * 1.3); ctx.lineTo(x + r * 1.2, y + r); ctx.lineTo(x - r * 1.2, y + r); ctx.closePath();
  }
}

export default function GraphView({ graph, follow, setFollow, rounds, setRounds, showTruth }: {
  graph: { data?: Graph; error?: string; loading: boolean };
  follow: Follow; setFollow: (f: Follow) => void;
  rounds: number; setRounds: (r: number) => void;
  showTruth: boolean;
}) {
  const data = graph.data;
  const [picked, setPicked] = useState<GraphNode | null>(null);
  const [showLeaves, setShowLeaves] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { width, height } = useSize(box);
  const fg = useRef<ForceGraphMethods<N, L> | undefined>(undefined);

  // The library MUTATES node objects (adds x, y, vx, vy), so hand it copies,
  // and only make new copies when the data actually changes.
  //
  // By default, drop devices/IPs that touch only ONE card in this graph: they link
  // nothing to anything, and every card brings 3-8 of them. Hubs and rule-hit devices stay.
  const graphData = useMemo(() => {
    const nodes = data?.nodes ?? [];
    const edges = data?.edges ?? [];
    const degree = new Map<string, number>();
    for (const e of edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const keep = new Set(nodes.filter((n) =>
      showLeaves || n.kind === "card" || n.kind === "merchant" || n.hub || n.rule_hit
      || (degree.get(n.id) ?? 0) >= 2,
    ).map((n) => n.id));
    return {
      nodes: nodes.filter((n) => keep.has(n.id)).map((n) => ({ ...n })) as N[],
      links: edges.filter((e) => keep.has(e.source) && keep.has(e.target)).map((e) => ({ ...e })) as L[],
      hidden: nodes.length - keep.size,
    };
  }, [data, showLeaves]);

  // Spread the layout: default d3 forces pack nodes so tightly that labels overlap.
  useEffect(() => {
    const g = fg.current;
    if (!g) return;
    g.d3Force("charge")?.strength(-90);
    g.d3Force("link")?.distance(35);
    g.d3ReheatSimulation();
  }, [graphData]);

  useEffect(() => setPicked(null), [data]);

  const draw = (n: N, ctx: CanvasRenderingContext2D, scale: number) => {
    const r = nodeRadius(n);
    if (n.kind === "card" && (n.flagged_txns ?? 0) > 0) { // soft glow on alerted cards
      ctx.shadowColor = COLOR.risk; ctx.shadowBlur = 12;
    }
    tracePath(ctx, n, r);
    ctx.fillStyle = nodeColor(n);
    ctx.fill();
    ctx.shadowBlur = 0;

    const ring = (color: string, dash: number[] = [], gap = 2.5) => {
      tracePath(ctx, n, r + gap / scale);
      ctx.setLineDash(dash.map((d) => d / scale));
      ctx.lineWidth = 1.5 / scale;
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if (n.seed) ring(COLOR.seedRing, [], 3);
    if (n.hub) ring("#8b8b93", [2, 2]);
    if (n.rule_hit) ring(COLOR.rule, [], 2.5);
    // "Missed by the model": fraud per the label, but zero flagged charges.
    if (showTruth && n.kind === "card" && (n.labeled_fraud_txns ?? 0) > 0 && (n.flagged_txns ?? 0) === 0)
      ring(COLOR.missed, [3, 2], 4);

    const important = n.kind === "card" && (n.seed || (n.flagged_txns ?? 0) > 0);
    if (important || n.rule_hit || scale > 2.5) {
      ctx.font = `${(n.kind === "card" ? 10 : 8.5) / scale}px Inter, ui-sans-serif, system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = COLOR.label;
      const text = n.kind === "card" ? n.label : n.rule_hit ? `${n.max_cards_24h} cards / 24h` : n.label.slice(0, 16);
      ctx.fillText(text, n.x ?? 0, (n.y ?? 0) + r + 4 / scale);
    }
  };

  const s = data?.summary;
  return (
    <Panel title="Relationship graph" className="h-full"
      right={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Segmented value={follow} onChange={setFollow} options={FOLLOW_OPTIONS} />
          <Segmented value={rounds} onChange={setRounds} options={[
            { value: 1, label: "1 hop" }, { value: 2, label: "2" }, { value: 3, label: "3" }]} />
        </div>
      }>
      <div className="flex h-full flex-col">
        {s && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-5 pb-3 text-xs text-muted">
            <span><b className="text-fg">{s.cards}</b> cards</span>
            <span><b className="text-risk">{s.flagged_cards}</b> with alerts</span>
            <span><b className="text-fg">{s.shared_entities}</b> shared devices/IPs</span>
            <span><b className="text-warn">{s.rule_devices}</b> devices on 3+ cards in 24h</span>
            <span><b className="text-fg">{s.hubs_not_expanded}</b> hubs not expanded</span>
            {showTruth && <span><b className="text-fg">{s.labeled_fraud_cards}</b> labeled fraud</span>}
            {s.truncated && <span className="text-warn">truncated at card limit</span>}
            <label className="ml-auto flex cursor-pointer items-center gap-1.5">
              <input type="checkbox" className="accent-risk" checked={showLeaves}
                onChange={(e) => setShowLeaves(e.target.checked)} />
              show {graphData.hidden} single-card devices/IPs
            </label>
            <span className="text-faint">last 30 days · {s.latency_ms.toFixed(0)} ms</span>
          </div>
        )}
        <div ref={box} className="relative min-h-0 flex-1 overflow-hidden rounded-b-2xl border-t border-line bg-[#111114]">
          <Status loading={graph.loading} error={graph.error} />
          {data && width > 0 && (
            <ForceGraph2D<GraphNode, GraphEdge>
              ref={fg}
              graphData={graphData}
              width={width}
              height={height}
              backgroundColor="rgba(0,0,0,0)"
              nodeId="id"
              nodeCanvasObject={draw}
              nodePointerAreaPaint={(n, color, ctx) => {
                tracePath(ctx, n, nodeRadius(n) + 2);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              linkColor={(l) => (l.flagged_txns > 0 ? "rgba(255,59,48,0.6)" : "rgba(139,139,147,0.28)")}
              linkWidth={(l) => (l.flagged_txns > 0 ? 1.6 : 0.8)}
              onNodeClick={(n) => setPicked(n)}
              onBackgroundClick={() => setPicked(null)}
              cooldownTicks={120}
              onEngineStop={() => fg.current?.zoomToFit(400, 50)}
            />
          )}
          <Legend showTruth={showTruth} />
          {picked && <NodeCard node={picked} showTruth={showTruth} />}
        </div>
      </div>
    </Panel>
  );
}

function Legend({ showTruth }: { showTruth: boolean }) {
  const item = (swatch: string, label: string) => (
    <span className="flex items-center gap-2"><span className={swatch} />{label}</span>
  );
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 grid gap-1 rounded-xl border border-line bg-panel/90 p-3 text-[11px] text-muted backdrop-blur">
      {item("size-2.5 rounded-full bg-risk", "card with alerts")}
      {item("size-2.5 rounded-full bg-[#6b6b73]", "card, no alerts")}
      {item("size-2.5 bg-device", "device")}
      {item("size-2.5 rotate-45 bg-ip", "IP address")}
      {item("size-2.5 bg-device outline-2 outline-offset-1 outline-warn", "device used by 3+ cards in 24h")}
      {item("size-2.5 rounded-sm bg-[#3a3a40] outline-1 outline-dashed outline-muted", "hub, 25+ cards (not expanded)")}
      {item("size-0 border-x-[5px] border-b-[9px] border-x-transparent border-b-merchant", "merchant, 3+ alerted cards (weak)")}
      {showTruth && item("size-2.5 rounded-full outline-2 outline-dashed outline-warn", "fraud the model missed")}
    </div>
  );
}

function NodeCard({ node, showTruth }: { node: GraphNode; showTruth: boolean }) {
  const rows: [string, string | number | null][] =
    node.kind === "card"
      ? [["Transactions (30d)", node.txn_count], ["Alerted transactions", node.flagged_txns],
         ...(showTruth ? [["Labeled fraud", node.labeled_fraud_txns] as [string, number | null]] : []),
         ["Hops from seed", node.hop]]
      : node.kind === "merchant"
        ? [["Hops from seed", node.hop]]
        : [["Cards using it (30d)", node.cards_in_window],
           ...(node.kind === "device" ? [["Most cards in 24h", node.max_cards_24h] as [string, number | null]] : []),
           ["Hub", node.hub ? "yes, not expanded" : "no"], ["Hops from seed", node.hop]];
  return (
    <div className="absolute right-3 top-3 w-64 rounded-xl border border-line bg-panel/95 p-4 text-xs shadow-2xl backdrop-blur">
      <div className="mb-1 text-[10px] uppercase tracking-[0.14em] text-faint">{node.kind}</div>
      <div className="mb-3 break-all font-mono text-sm">{node.label}</div>
      {node.rule_hit && (
        <p className="mb-2 rounded-lg bg-warn/10 px-2 py-1.5 text-warn">
          Used by {node.max_cards_24h} different cards within 24 hours
        </p>
      )}
      <dl className="grid gap-1.5">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd>{v ?? "n/a"}</dd></div>
        ))}
      </dl>
    </div>
  );
}
