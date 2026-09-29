import { useCallback, useEffect, useState } from "react";

import type { ReplayStatus } from "./api";
import AlertList from "./components/AlertList";
import Investigation from "./components/Investigation";
import ReplayBar from "./components/ReplayBar";
import { useApi } from "./useApi";

/** Selected transaction lives in the URL (#<trans_num>) so a view can be linked/refreshed. */
function useSelection(): [string | null, (id: string) => void] {
  const read = () => window.location.hash.slice(1) || null;
  const [id, setId] = useState<string | null>(read);
  useEffect(() => {
    const onHash = () => setId(read());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const select = useCallback((next: string) => {
    window.history.replaceState(null, "", `#${next}`);
    setId(next);
  }, []);
  return [id, select];
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-9 text-risk" fill="none" stroke="currentColor" strokeWidth="2.2">
      <circle cx="16" cy="16" r="12.5" />
      <path d="M8.5 19.5 13 14l3.5 3.5L23.5 10" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19.5 10h4v4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function App() {
  const [selected, select] = useSelection();
  const [showTruth, setShowTruth] = useState(false);
  const [search, setSearch] = useState("");
  const [decisions, setDecisions] = useState(0); // bumps when an analyst saves a decision
  // Replay runs in a separate process; poll its progress every 1.5 s.
  const replay = useApi<ReplayStatus>("/replay/status", { refreshMs: 1500 }).data;
  const live = replay?.status === "running";

  return (
    <div className="flex h-full flex-col">
      <header className="mx-4 mt-4 flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-panel px-5 py-3">
        <Logo />
        <div>
          <h1 className="text-base font-semibold tracking-tight">FraudGraph</h1>
          <p className="text-[11px] text-faint">Transaction risk investigation · Sparkov test period (simulated)</p>
        </div>
        <form className="ml-6 flex min-w-64 flex-1 items-center gap-2 rounded-full border border-line bg-ink px-4 py-2 md:max-w-sm"
          onSubmit={(e) => { e.preventDefault(); if (search.trim()) select(search.trim()); }}>
          <svg viewBox="0 0 24 24" className="size-4 text-faint" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Open a transaction by ID…" aria-label="Transaction ID"
            className="w-full bg-transparent text-sm text-fg placeholder:text-faint focus:outline-none" />
        </form>
        {replay && replay.status !== "idle" && <ReplayBar r={replay} />}
        <label className="ml-auto flex cursor-pointer items-center gap-2 text-xs text-muted"
          title="Confirmed-fraud labels arrive weeks later via chargebacks. An analyst would not have them at alert time.">
          <input type="checkbox" className="accent-risk" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)} />
          Show ground truth (hindsight)
        </label>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[330px_1fr] gap-4 p-4">
        <AlertList selected={selected} onSelect={select} showTruth={showTruth}
          live={live} version={`${replay?.updated_at}-${decisions}`} />
        {selected ? (
          <Investigation key={selected} transNum={selected} showTruth={showTruth}
            onDecided={() => setDecisions((d) => d + 1)} />
        ) : (
          <main className="grid place-items-center text-sm text-faint">Select an alert</main>
        )}
      </div>
    </div>
  );
}
