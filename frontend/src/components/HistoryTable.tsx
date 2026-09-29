import type { TxnRow } from "../api";
import { category, money, pct, when } from "../format";
import { useApi } from "../useApi";
import { Panel, Status, Truth } from "./ui";

export default function HistoryTable({ transNum, showTruth }: { transNum: string; showTruth: boolean }) {
  const { data, error, loading } = useApi<TxnRow[]>(`/transactions/${transNum}/history?limit=12`);

  return (
    <Panel title={data?.length ? `Card ${data[0].card_label} · recent activity` : "Recent activity"}
      className="h-full">
      <Status loading={loading} error={error} />
      {data && (
        <div className="h-full overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-2 py-2 text-right font-medium">Amount</th>
                <th className="px-2 py-2 font-medium">Category</th>
                <th className="px-2 py-2 font-medium">Merchant</th>
                <th className="px-2 py-2 text-right font-medium">Score</th>
                {showTruth && <th className="px-4 py-2 font-medium">Label</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((t) => (
                <tr key={t.trans_num} className={t.trans_num === transNum ? "bg-amber-50" : ""}>
                  <td className="whitespace-nowrap px-4 py-1.5 tabular-nums text-slate-600">{when(t.ts)}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{money(t.amt)}</td>
                  <td className="px-2 py-1.5">{category(t.category)}</td>
                  <td className="max-w-40 truncate px-2 py-1.5 text-slate-600">{t.merchant.replace(/^fraud_/, "")}</td>
                  <td className={`px-2 py-1.5 text-right tabular-nums ${
                    t.flagged ? "font-semibold text-[var(--color-risk)]" : "text-slate-500"}`}>
                    {t.score === null ? "–" : pct(t.score)}
                  </td>
                  {showTruth && <td className="px-4 py-1.5"><Truth fraud={t.label_is_fraud} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
