import type { ReactNode } from "react";

export function Panel({ title, right, children, className = "", bodyClass = "" }: {
  title: ReactNode; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-2xl border border-line bg-panel ${className}`}>
      <header className="flex items-center justify-between gap-3 px-5 pb-2 pt-4">
        <h2 className="text-[15px] font-semibold tracking-tight text-fg">{title}</h2>
        {right}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function Status({ loading, error }: { loading: boolean; error?: string }) {
  if (error) return <p className="px-5 py-3 text-sm text-risk">Request failed: {error}</p>;
  if (loading) return <p className="px-5 py-3 text-sm text-faint">Loading…</p>;
  return null;
}

/** Ground-truth label. Only rendered when the "show ground truth" toggle is on. */
export function Truth({ fraud }: { fraud: boolean | null }) {
  if (fraud === null) return null;
  return (
    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
      fraud ? "bg-risk-deep/60 text-risk" : "bg-ok/10 text-ok"}`}>
      {fraud ? "fraud" : "legit"}
    </span>
  );
}

export const DECISION_LABEL: Record<string, { text: string; cls: string }> = {
  fraud: { text: "Confirmed fraud", cls: "bg-risk-deep/60 text-risk" },
  escalated: { text: "Escalated", cls: "bg-warn/15 text-warn" },
  legit: { text: "Legitimate", cls: "bg-ok/10 text-ok" },
};

export function DecisionBadge({ action }: { action: string | null | undefined }) {
  if (!action) return null;
  const d = DECISION_LABEL[action];
  return <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${d.cls}`}>{d.text}</span>;
}

export function Segmented<T extends string | number>({ value, options, onChange }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-line bg-ink p-0.5 text-xs">
      {options.map((o) => (
        <button key={String(o.value)} onClick={() => onChange(o.value)}
          className={`whitespace-nowrap rounded-full px-3 py-1 transition-colors ${o.value === value
            ? "bg-fg font-medium text-ink" : "text-muted hover:text-fg"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Row({ k, v }: { k: ReactNode; v: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-sm text-muted">{k}</dt>
      <dd className="text-right text-sm text-fg tabular-nums">{v}</dd>
    </div>
  );
}
