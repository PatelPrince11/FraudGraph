import type { ReactNode } from "react";

export function Panel({ title, right, children, className = "" }: {
  title: string; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-lg border border-slate-200 bg-white ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        {right}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

export function Status({ loading, error }: { loading: boolean; error?: string }) {
  if (error) return <p className="p-4 text-sm text-red-700">Request failed: {error}</p>;
  if (loading) return <p className="p-4 text-sm text-slate-400">Loading…</p>;
  return null;
}

/** Ground-truth label. Only rendered when the "show ground truth" toggle is on. */
export function Truth({ fraud }: { fraud: boolean | null }) {
  if (fraud === null) return null;
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
      fraud ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
      {fraud ? "fraud" : "legit"}
    </span>
  );
}

export function Segmented<T extends string | number>({ value, options, onChange }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-slate-200 p-0.5 text-xs">
      {options.map((o) => (
        <button key={String(o.value)} onClick={() => onChange(o.value)}
          className={`whitespace-nowrap rounded px-2 py-1 ${o.value === value
            ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
