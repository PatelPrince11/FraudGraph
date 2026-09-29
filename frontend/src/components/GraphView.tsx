import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-2d";

import type { Graph, GraphEdge, GraphNode } from "../api";
import { useApi } from "../useApi";
import { Panel, Segmented, Status } from "./ui";

type N = NodeObject<GraphNode>;
type L = LinkObject<GraphNode, GraphEdge>;

const COLOR = {
  risk: "#dc2626", card: "#94a3b8", device: "#2563eb", ip: "#0d9488",
  hub: "#cbd5e1", merchant: "#7c3aed", missed: "#d97706", ink: "#0f172a",
};

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

export default function GraphView({ transNum, showTruth }: { transNum: string; showTruth: boolean }) {
  const [follow, setFollow] = useState<"flagged" | "all">("flagged");
  const [rounds, setRounds] = useState(2);
  const [picked, setPicked] = useState<GraphNode | null>(null);
  const { data, error, loading } = useApi<Graph>(
    `/transactions/${transNum}/graph?follow=${follow}&rounds=${rounds}`);

  const box = useRef<HTMLDivElement>(null);
  const { width, height } = useSize(box);
  const fg = useRef<ForceGraphMethods<N, L> | undefined>(undefined);

  // The library MUTATES node objects (adds x, y, vx, vy), so hand it copies,
  // and only make new copies when the data actually changes.
  const graphData = useMemo(() => ({
    nodes: (data?.nodes ?? []).map((n) => ({ ...n })) as N[],
    links: (data?.edges ?? []).map((e) => ({ ...e })) as L[],
  }), [data]);

  useEffect(() => setPicked(null), [transNum, follow, rounds]);

  const draw = (n: N, ctx: CanvasRenderingContext2D, scale: number) => {
    const r = nodeRadius(n);
    tracePath(ctx, n, r);
    ctx.fillStyle = nodeColor(n);
    ctx.fill();

    const ring = (color: string, dash: number[] = []) => {
      tracePath(ctx, n, r + 2.5 / scale);
      ctx.setLineDash(dash.map((d) => d / scale));
      ctx.lineWidth = 1.5 / scale;
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if (n.seed) ring(COLOR.ink);
    if (n.hub) ring("#64748b", [2, 2]);
    // "Missed by the model": fraud per the label, but zero flagged charges.
    if (showTruth && n.kind === "card" && (n.labeled_fraud_txns ?? 0) > 0 && (n.flagged_txns ?? 0) === 0)
      ring(COLOR.missed, [3, 2]);

    // Label the cards that matter; everything else only once you zoom in.
    const important = n.kind === "card" && (n.seed || (n.flagged_txns ?? 0) > 0);
    if (important || scale > 2.5) {
      ctx.font = `${(n.kind === "card" ? 10 : 8) / scale}px ui-sans-serif, system-ui`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#334155";
      ctx.fillText(n.kind === "card" ? n.label : n.label.slice(0, 16), n.x ?? 0, (n.y ?? 0) + r + 3 / scale);
    }
  };

  const s = data?.summary;
  return (
    <Panel title="Relationship graph" className="h-full"
      right={
        <div className="flex items-center gap-2">
          <Segmented value={follow} onChange={setFollow} options={[
            { value: "flagged", label: "Follow flagged links" }, { value: "all", label: "Follow all" }]} />
          <Segmented value={rounds} onChange={setRounds} options={[
            { value: 1, label: "1 hop" }, { value: 2, label: "2" }, { value: 3, label: "3" }]} />
        </div>
      }>
      <div className="flex h-full flex-col">
        {s && (
          <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-slate-100 px-4 py-2 text-xs text-slate-600">
            <span><b className="text-slate-900">{s.cards}</b> cards</span>
            <span><b className="text-[var(--color-risk)]">{s.flagged_cards}</b> with alerts</span>
            <span><b className="text-slate-900">{s.shared_entities}</b> shared devices/IPs</span>
            <span><b className="text-slate-900">{s.hubs_not_expanded}</b> hubs not expanded</span>
            {showTruth && <span><b className="text-slate-900">{s.labeled_fraud_cards}</b> labeled fraud</span>}
            {s.truncated && <span className="text-amber-700">truncated at card limit</span>}
            <span className="ml-auto text-slate-400">last 30 days · {s.latency_ms.toFixed(0)} ms</span>
          </div>
        )}
        <div ref={box} className="relative min-h-0 flex-1">
          <Status loading={loading} error={error} />
          {data && width > 0 && (
            <ForceGraph2D<GraphNode, GraphEdge>
              ref={fg}
              graphData={graphData}
              width={width}
              height={height}
              nodeId="id"
              nodeCanvasObject={draw}
              nodePointerAreaPaint={(n, color, ctx) => {
                tracePath(ctx, n, nodeRadius(n) + 2);
                ctx.fillStyle = color;
                ctx.fill();
              }}
              linkColor={(l) => (l.flagged_txns > 0 ? "rgba(220,38,38,0.55)" : "rgba(100,116,139,0.3)")}
              linkWidth={(l) => (l.flagged_txns > 0 ? 1.6 : 0.8)}
              onNodeClick={(n) => setPicked(n)}
              onBackgroundClick={() => setPicked(null)}
              cooldownTicks={120}
              onEngineStop={() => fg.current?.zoomToFit(400, 40)}
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
    <span className="flex items-center gap-1.5"><span className={swatch} />{label}</span>
  );
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 grid gap-1 rounded-md bg-white/90 p-2 text-[11px] text-slate-600 shadow-sm">
      {item("size-2.5 rounded-full bg-red-600", "card with alerts")}
      {item("size-2.5 rounded-full bg-slate-400", "card, no alerts")}
      {item("size-2.5 bg-blue-600", "device")}
      {item("size-2.5 rotate-45 bg-teal-600", "IP address")}
      {item("size-2.5 rounded-sm bg-slate-300 outline-1 outline-dashed outline-slate-500", "hub, 25+ cards (not expanded)")}
      {item("size-0 border-x-[5px] border-b-[9px] border-x-transparent border-b-violet-600", "merchant, 3+ alerted cards (weak)")}
      {showTruth && item("size-2.5 rounded-full outline-2 outline-dashed outline-amber-600", "fraud the model missed")}
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
        : [["Cards using it (30d)", node.cards_in_window], ["Hub", node.hub ? "yes, not expanded" : "no"],
           ["Hops from seed", node.hop]];
  return (
    <div className="absolute right-3 top-3 w-60 rounded-md border border-slate-200 bg-white p-3 text-xs shadow">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-slate-400">{node.kind}</div>
      <div className="mb-2 break-all font-mono text-sm">{node.label}</div>
      <dl className="grid gap-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between"><dt className="text-slate-500">{k}</dt><dd>{v ?? "n/a"}</dd></div>
        ))}
      </dl>
    </div>
  );
}
