import { useEffect, useState } from "react";

import type { Alerts } from "../api";
import { category, money, pct, when } from "../format";
import { useApi } from "../useApi";
import { Panel, Segmented, Status, Truth } from "./ui";

const PAGE = 50;

export default function AlertList({ selected, onSelect, showTruth }: {
  selected: string | null; onSelect: (id: string) => void; showTruth: boolean;
}) {
  const [sort, setSort] = useState<"score" | "recent">("score");
  const [page, setPage] = useState(0);
  const { data, error, loading } = useApi<Alerts>(
    `/alerts?sort=${sort}&limit=${PAGE}&offset=${page * PAGE}`);

  // Open the top alert on first load so the screen is never empty.
  useEffect(() => {
    if (!selected && data?.items.length) onSelect(data.items[0].trans_num);
  }, [data, selected, onSelect]);

  const pages = data ? Math.ceil(data.total / PAGE) : 0;

  return (
    <Panel
      title={data ? `Alerts · ${data.total.toLocaleString()}` : "Alerts"}
      className="h-full"
      right={<Segmented value={sort} onChange={(v) => { setSort(v); setPage(0); }}
        options={[{ value: "score", label: "Top risk" }, { value: "recent", label: "Newest" }]} />}
    >
      <div className="flex h-full flex-col">
        <Status loading={loading} error={error} />
        <ul className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto">
          {data?.items.map((a) => (
            <li key={a.trans_num}>
              <button onClick={() => onSelect(a.trans_num)}
                className={`flex w-full items-center gap-3 px-4 py-2.5 text-left ${
                  a.trans_num === selected ? "bg-slate-100" : "hover:bg-slate-50"}`}>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <span className="font-mono text-xs text-slate-500">{a.card_label}</span>
                    <span className="font-semibold tabular-nums">{money(a.amt)}</span>
                    {showTruth && <Truth fraud={a.label_is_fraud} />}
                  </div>
                  <div className="truncate text-xs text-slate-500">
                    {category(a.category)} · {when(a.ts)}
                  </div>
                </div>
                <span className="text-sm font-semibold tabular-nums text-[var(--color-risk)]">
                  {a.score === null ? "–" : pct(a.score)}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {pages > 1 && (
          <footer className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}
              className="disabled:opacity-30">← Prev</button>
            <span>Page {page + 1} of {pages}</span>
            <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}
              className="disabled:opacity-30">Next →</button>
          </footer>
        )}
      </div>
    </Panel>
  );
}
