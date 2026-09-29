import { useEffect, useState } from "react";

import type { Action, Decision, Graph, Risk } from "../api";
import { when } from "../format";
import { DECISION_LABEL } from "./ui";

/**
 * Suggestion + the analyst's decision. The suggestion is a plain rule over what's on
 * screen (score, linked alerts, device rule), labeled as such. The decision is saved
 * to the database: in a real system those become fresh training labels.
 */
function suggest(risk?: Risk, graph?: Graph): { title: string; detail: string; tone: string } {
  if (!risk) return { title: "", detail: "", tone: "" };
  const others = graph ? Math.max(0, graph.summary.flagged_cards - (risk.flagged ? 1 : 0)) : 0;
  const rule = graph?.summary.rule_devices ?? 0;
  if (risk.flagged && others > 0)
    return { title: "Escalate", tone: "text-risk",
      detail: `High risk and linked to ${others} other card${others > 1 ? "s" : ""} with alerts.` };
  if (risk.flagged && rule > 0)
    return { title: "Escalate", tone: "text-risk",
      detail: "High risk and uses a device shared by 3+ cards within 24 hours." };
  if (risk.flagged)
    return { title: "Review", tone: "text-warn", detail: "High risk, no linked activity found." };
  if (rule > 0)
    return { title: "Review", tone: "text-warn",
      detail: "Below the alert threshold, but on a device shared by 3+ cards within 24 hours." };
  return { title: "No action needed", tone: "text-ok", detail: "Below the alert threshold." };
}

export default function ActionBar({ transNum, risk, graph, onDecided }: {
  transNum: string; risk?: Risk; graph?: Graph; onDecided: () => void;
}) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setDecision(null);
    fetch(`/api/transactions/${transNum}/decision`, { signal: ctrl.signal })
      .then((r) => r.json()).then(setDecision).catch(() => {});
    return () => ctrl.abort();
  }, [transNum]);

  async function decide(action: Action | null) {
    setBusy(true); setError(null);
    try {
      const r = await fetch(`/api/transactions/${transNum}/decision`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      setDecision(await r.json());
      onDecided();
    } catch (e) {
      setError(`Could not save (${(e as Error).message})`);
    } finally {
      setBusy(false);
    }
  }

  const s = suggest(risk, graph);
  const current = decision?.action;
  const btn = "flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium transition-colors disabled:opacity-50";

  return (
    <section className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-panel/95 px-5 py-4 backdrop-blur">
      <svg viewBox="0 0 24 24" className="size-9 shrink-0 text-risk" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z" strokeLinejoin="round" />
        <path d="M12 8v5M12 16.2v.1" strokeLinecap="round" />
      </svg>
      <div className="min-w-0 flex-1">
        {current ? (
          <>
            <div className="text-base font-semibold">Decision: {DECISION_LABEL[current].text}</div>
            <div className="text-sm text-muted">
              Saved {decision?.decided_at && when(decision.decided_at)} ·{" "}
              <button className="underline decoration-faint underline-offset-2 hover:text-fg"
                onClick={() => decide(null)} disabled={busy}>undo</button>
            </div>
          </>
        ) : (
          <>
            <div className="text-base font-semibold">
              Suggested: <span className={s.tone}>{s.title}</span>
            </div>
            <div className="text-sm text-muted">{s.detail}</div>
          </>
        )}
        {error && <div className="text-xs text-risk">{error}</div>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button disabled={busy} onClick={() => decide("escalated")}
          className={`${btn} ${current === "escalated" ? "bg-warn text-ink" : "bg-risk text-white hover:bg-risk/85"}`}>
          Escalate case <span aria-hidden>›</span>
        </button>
        <button disabled={busy} onClick={() => decide("fraud")}
          className={`${btn} border ${current === "fraud" ? "border-risk bg-risk-deep/50 text-risk" : "border-line hover:bg-raised"}`}>
          <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="8.5" /><path d="m6 6 12 12" />
          </svg>
          Confirm fraud
        </button>
        <button disabled={busy} onClick={() => decide("legit")}
          className={`${btn} border ${current === "legit" ? "border-ok bg-ok/10 text-ok" : "border-line hover:bg-raised"}`}>
          <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="m5 12.5 4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Mark legitimate
        </button>
      </div>
    </section>
  );
}
