import type { ReplayStatus } from "../api";
import { when } from "../format";

/** One-line progress readout for scripts/replay.py. */
export default function ReplayBar({ r }: { r: ReplayStatus }) {
  const live = r.status === "running";
  const pct = r.total ? Math.round((100 * r.processed) / r.total) : 0;
  return (
    <div className="flex items-center gap-3 rounded-full border border-line bg-panel px-4 py-1.5 text-xs text-muted">
      <span className={`flex items-center gap-1.5 font-semibold ${live ? "text-risk" : "text-muted"}`}>
        <span className={`size-2 rounded-full ${live ? "animate-pulse bg-risk" : "bg-faint"}`} />
        {live ? "LIVE REPLAY" : r.status === "done" ? "Replay finished" : "Replay stopped"}
      </span>
      {r.sim_clock && <span>sim time <b className="font-medium text-fg">{when(r.sim_clock)}</b></span>}
      <span className="tabular-nums">{r.processed.toLocaleString()} / {r.total.toLocaleString()} ({pct}%)</span>
      <span className="tabular-nums"><b className="text-risk">{r.flagged}</b> alerts</span>
      {r.txn_per_sec !== null && (
        <span className="tabular-nums text-faint">
          {r.txn_per_sec.toFixed(1)} txn/s · p95 {r.p95_ms?.toFixed(0)} ms
          {(r.lag_s ?? 0) > 1 && <span className="text-warn"> · {r.lag_s!.toFixed(0)} s behind</span>}
        </span>
      )}
    </div>
  );
}
