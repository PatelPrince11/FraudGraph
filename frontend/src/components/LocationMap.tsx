import { geoMercator, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import states from "us-atlas/states-10m.json";

import type { CardSummary, TxnRow } from "../api";
import { km } from "../format";
import { Panel } from "./ui";

const W = 420, H = 250;
// Converted once at module load: TopoJSON (compact, shared borders) -> GeoJSON features.
const topo = states as unknown as Topology<{ states: GeometryCollection }>;
const STATES = feature(topo, topo.objects.states);

/**
 * Home vs where the card was used. The map zooms to the card's own area, so the
 * state outlines give scale. Dashed arcs connect home to flagged transactions.
 */
export default function LocationMap({ card, rows, current }: {
  card?: CardSummary; rows?: TxnRow[]; current: string;
}) {
  const view = useMemo(() => {
    if (!card || !rows?.length) return null;
    const home: [number, number] = [card.home_long, card.home_lat];
    const pts = rows.map((r) => [r.merch_long, r.merch_lat] as [number, number]);
    // Pad the box by ~1 degree so a card that always shops close to home isn't over-zoomed.
    const pad = [[home[0] - 1, home[1] - 1], [home[0] + 1, home[1] + 1]] as [number, number][];
    const proj = geoMercator().fitExtent([[24, 24], [W - 24, H - 24]],
      { type: "MultiPoint", coordinates: [home, ...pts, ...pad] });
    return { home, proj, path: geoPath(proj) };
  }, [card, rows]);

  const cur = rows?.find((r) => r.trans_num === current);
  const dist = card && cur ? km(card.home_lat, card.home_long, cur.merch_lat, cur.merch_long) : null;

  return (
    <Panel title="Location check" className="h-full"
      right={dist !== null && (
        <span className={`text-xs font-medium ${dist > 150 ? "text-risk" : "text-muted"}`}>
          {Math.round(dist)} km from home
        </span>)}>
      {view && card && rows ? (
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full px-3 pb-3" role="img"
          aria-label="Map of the cardholder's home and recent merchant locations">
          <defs>
            <clipPath id="map-clip"><rect width={W} height={H} rx="12" /></clipPath>
          </defs>
          <g clipPath="url(#map-clip)">
            <rect width={W} height={H} fill="#111114" />
            {STATES.features.map((f, i) => (
              <path key={i} d={view.path(f) ?? ""} fill="#1c1c21" stroke="#3d3d45" strokeWidth="1" />
            ))}
            {rows.map((r) => {
              const [x, y] = view.proj([r.merch_long, r.merch_lat])!;
              const [hx, hy] = view.proj(view.home)!;
              const mx = (x + hx) / 2, my = Math.min(y, hy) - 30; // arc control point above
              return (
                <g key={r.trans_num}>
                  {r.flagged && (
                    <path d={`M${hx},${hy} Q${mx},${my} ${x},${y}`} fill="none"
                      stroke="#ff3b30" strokeOpacity="0.55" strokeDasharray="3 3" />
                  )}
                  <circle cx={x} cy={y} r={r.flagged ? 3.5 : 2.5}
                    fill={r.flagged ? "#ff3b30" : "#8b8b93"} fillOpacity={r.flagged ? 1 : 0.6} />
                </g>
              );
            })}
            {(() => {
              const [hx, hy] = view.proj(view.home)!;
              return (
                <g>
                  <circle cx={hx} cy={hy} r="9" fill="#30d158" fillOpacity="0.18" />
                  <circle cx={hx} cy={hy} r="4.5" fill="#30d158" stroke="#0b0b0c" strokeWidth="1.5" />
                  <text x={hx + 10} y={hy + 4} fontSize="11" fill="#e6e6e8">{card.city ?? "Home"}</text>
                  <text x={hx + 10} y={hy + 17} fontSize="10" fill="#30d158">Home</text>
                </g>
              );
            })()}
            {cur && (() => {
              const [x, y] = view.proj([cur.merch_long, cur.merch_lat])!;
              return (
                <g>
                  <circle cx={x} cy={y} r="11" fill="#ff3b30" fillOpacity="0.2" />
                  <circle cx={x} cy={y} r="5" fill="#ff3b30" stroke="#e6e6e8" strokeWidth="1.5" />
                  <text x={x + 10} y={y - 6} fontSize="10" fill="#ff3b30">This transaction</text>
                </g>
              );
            })()}
          </g>
        </svg>
      ) : <p className="px-5 py-3 text-sm text-faint">Loading…</p>}
    </Panel>
  );
}
