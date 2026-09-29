import { useEffect, useRef, useState } from "react";

import type { Alerts } from "../api";
import { category, money, pct, when } from "../format";
import { useApi } from "../useApi";
import { DecisionBadge, Panel, Segmented, Status, Truth } from "./ui";

const PAGE = 50;

export default function AlertList({ selected, onSelect, showTruth, live, version }: {
  selected: string | null; onSelect: (id: string) => void; showTruth: boolean;
  live: boolean; version?: string | null;
}) {
  const [sort, setSort] = useState<"score" | "recent">("score");
  const [status, setStatus] = useState<"all" | "open">("all");
  const [page, setPage] = useState(0);
  // Refetch whenever the replay reports progress or a decision is saved (`version`).
  const { data, error, loading } = useApi<Alerts>(
    `/alerts?sort=${sort}&status=${status}&limit=${PAGE}&offset=${page * PAGE}`, { refreshKey: version });

  // A live feed reads newest-first.
  useEffect(() => {
    if (live) { setSort("recent"); setPage(0); }
  }, [live]);

  // Open the top alert on first load so the screen is never empty.
  useEffect(() => {
    if (!selected && data?.items.length) onSelect(data.items[0].trans_num);
  }, [data, selected, onSelect]);

  // Highlight alerts that appeared since the previous refresh.
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  useEffect(() => { seen.current = null; }, [sort, page, status]);
  useEffect(() => {
    if (!data) return;
    const ids = data.items.map((a) => a.trans_num);
    if (seen.current === null) { seen.current = new Set(ids); setFresh(new Set()); return; }
    const added = ids.filter((id) => !seen.current!.has(id));
    added.forEach((id) => seen.current!.add(id));
    if (added.length) setFresh(new Set(added));
  }, [data]);

  const pages = data ? Math.ceil(data.total / PAGE) : 0;

  return (
    <Panel title={<span>Alerts <span className="font-normal text-muted">· {data?.total.toLocaleString() ?? "…"}</span></span>}
      className="h-full"
      right={<Segmented value={status} onChange={(v) => { setStatus(v); setPage(0); }}
        options={[{ value: "all", label: "All" }, { value: "open", label: "Open" }]} />}>
      <div className="flex h-full flex-col">
        <div className="px-5 pb-3">
          <Segmented value={sort} onChange={(v) => { setSort(v); setPage(0); }}
            options={[{ value: "score", label: "Top risk" }, { value: "recent", label: "Newest" }]} />
        </div>
        <Status loading={loading} error={error} />
        {data && data.total === 0 && (
          <p className="px-5 py-3 text-sm text-faint">
            {live ? "No alerts yet. Waiting for transactions…" : "No alerts."}
          </p>
        )}
        <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2">
          {data?.items.map((a) => (
            <li key={a.trans_num}>
              <button onClick={() => onSelect(a.trans_num)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors duration-700 ${
                  a.trans_num === selected ? "bg-raised ring-1 ring-risk/50"
                    : fresh.has(a.trans_num) ? "bg-warn/10" : "hover:bg-raised/60"}`}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-[11px] text-faint">{a.card_label}</span>
                    <span className="font-semibold tabular-nums">{money(a.amt)}</span>
                  </div>
                  <div className="flex items-center gap-1.5 truncate text-[11px] text-muted">
                    {category(a.category)} · {when(a.ts)}
                  </div>
                  {(a.decision || showTruth) && (
                    <div className="mt-1 flex gap-1.5">
                      <DecisionBadge action={a.decision} />
                      {showTruth && <Truth fraud={a.label_is_fraud} />}
                    </div>
                  )}
                </div>
                <span className="text-sm font-semibold tabular-nums text-risk">
                  {a.score === null ? "–" : pct(a.score)}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {pages > 1 && (
          <footer className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}
              className="hover:text-fg disabled:opacity-30">← Prev</button>
            <span>Page {page + 1} of {pages}</span>
            <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}
              className="hover:text-fg disabled:opacity-30">Next →</button>
          </footer>
        )}
      </div>
    </Panel>
  );
}
