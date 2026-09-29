import type { ReplayStatus } from "../api";
import { when } from "../format";

/** One-line progress readout for scripts/replay.py. */
export default function ReplayBar({ r }: { r: ReplayStatus }) {
  const live = r.status === "running";
  const pct = r.total ? Math.round((100 * r.processed) / r.total) : 0;
  return (
    <div className="flex items-center gap-3 rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-600">
      <span className={`flex items-center gap-1.5 font-semibold ${live ? "text-red-600" : "text-slate-500"}`}>
        <span className={`size-2 rounded-full ${live ? "animate-pulse bg-red-600" : "bg-slate-400"}`} />
        {live ? "LIVE REPLAY" : r.status === "done" ? "Replay finished" : "Replay stopped"}
      </span>
      {r.sim_clock && <span>simulated time <b className="text-slate-900">{when(r.sim_clock)}</b></span>}
      <span className="tabular-nums">
        {r.processed.toLocaleString()} / {r.total.toLocaleString()} txns ({pct}%)
      </span>
      <span className="tabular-nums"><b className="text-red-600">{r.flagged}</b> alerts</span>
      {r.txn_per_sec !== null && (
        <span className="tabular-nums text-slate-400">
          {r.txn_per_sec.toFixed(1)} txn/s · p95 {r.p95_ms?.toFixed(0)} ms
          {(r.lag_s ?? 0) > 1 && <span className="text-amber-700"> · {r.lag_s!.toFixed(0)} s behind</span>}
        </span>
      )}
    </div>
  );
}
