import { useId } from "react";

import type { TxnRow } from "../api";

const W = 560, H = 170, PAD = { l: 30, r: 10, t: 10, b: 22 };

/**
 * Area chart of the card's recent scores, oldest to newest, placed by TIME (not by
 * index) so a burst of transactions shows up as points bunched together.
 */
export default function TrendChart({ rows, threshold, current }: {
  rows: TxnRow[]; threshold: number; current: string;
}) {
  const gradId = useId();
  const pts = [...rows].reverse().filter((r) => r.score !== null); // API sends newest first
  if (pts.length < 2) return <p className="py-8 text-center text-xs text-faint">Not enough history</p>;

  const t = pts.map((p) => new Date(p.ts).getTime());
  const t0 = t[0], t1 = t[t.length - 1] || t0 + 1;
  const x = (ms: number) => PAD.l + ((ms - t0) / (t1 - t0 || 1)) * (W - PAD.l - PAD.r);
  const y = (s: number) => PAD.t + (1 - s) * (H - PAD.t - PAD.b);
  const xy = pts.map((p, i) => [x(t[i]), y(p.score!)] as const);

  const line = xy.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("");
  const area = `${line}L${xy[xy.length - 1][0]},${y(0)}L${xy[0][0]},${y(0)}Z`;
  const spanH = (t1 - t0) / 3.6e6;
  const tick = (ms: number) => {
    const h = (t1 - ms) / 3.6e6;
    if (h < 0.5) return "now";
    return spanH > 72 ? `-${Math.round(h / 24)}d` : `-${Math.round(h)}h`;
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
      aria-label="Fraud score of this card's recent transactions over time">
      <defs>
        <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#ff3b30" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#ff3b30" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 25, 50, 75, 100].map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v / 100)} y2={y(v / 100)}
            stroke="#2a2a2f" strokeDasharray={v ? "2 4" : undefined} />
          <text x={PAD.l - 8} y={y(v / 100) + 3} textAnchor="end" fontSize="10" fill="#5c5c64">{v}</text>
        </g>
      ))}
      <line x1={PAD.l} x2={W - PAD.r} y1={y(threshold)} y2={y(threshold)} stroke="#ff3b30" strokeOpacity="0.5" strokeDasharray="4 3" />
      <text x={W - PAD.r} y={y(threshold) - 4} textAnchor="end" fontSize="9.5" fill="#ff3b30" fillOpacity="0.8">alert threshold</text>
      <path d={area} fill={`url(#${gradId})`} />
      <path d={line} fill="none" stroke="#ff3b30" strokeWidth="2" strokeLinejoin="round" />
      {xy.map(([a, b], i) => pts[i].trans_num === current ? (
        <g key={i}>
          <circle cx={a} cy={b} r="7" fill="#ff3b30" fillOpacity="0.25" />
          <circle cx={a} cy={b} r="4" fill="#ff3b30" stroke="#e6e6e8" strokeWidth="1.5" />
        </g>
      ) : pts[i].flagged ? <circle key={i} cx={a} cy={b} r="2.5" fill="#ff3b30" /> : null)}
      {[t0, t0 + (t1 - t0) / 2, t1].map((ms, i) => (
        <text key={i} x={x(ms)} y={H - 6} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}
          fontSize="10" fill="#5c5c64">{tick(ms)}</text>
      ))}
    </svg>
  );
}
