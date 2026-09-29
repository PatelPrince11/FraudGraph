import { useCallback, useEffect, useState } from "react";

import AlertList from "./components/AlertList";
import GraphView from "./components/GraphView";
import HistoryTable from "./components/HistoryTable";
import RiskPanel from "./components/RiskPanel";

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

export default function App() {
  const [selected, select] = useSelection();
  const [showTruth, setShowTruth] = useState(false);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-5 py-3">
        <div>
          <h1 className="text-base font-semibold">FraudGraph</h1>
          <p className="text-xs text-slate-500">
            Transaction risk investigation · Sparkov test period (simulated data)
          </p>
        </div>
        <label className="ml-auto flex cursor-pointer items-center gap-2 text-xs text-slate-600"
          title="Confirmed-fraud labels arrive weeks later via chargebacks. An analyst would not have them at alert time.">
          <input type="checkbox" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)} />
          Show ground truth (hindsight)
        </label>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[340px_1fr] gap-3 p-3">
        <AlertList selected={selected} onSelect={select} showTruth={showTruth} />
        {selected ? (
          <main className="grid min-h-0 grid-cols-[minmax(340px,420px)_1fr] grid-rows-[minmax(0,1fr)_minmax(0,1.3fr)] gap-3">
            <RiskPanel transNum={selected} showTruth={showTruth} />
            <HistoryTable transNum={selected} showTruth={showTruth} />
            <div className="col-span-2 min-h-0">
              <GraphView transNum={selected} showTruth={showTruth} />
            </div>
          </main>
        ) : (
          <main className="grid place-items-center text-sm text-slate-400">Select an alert</main>
        )}
      </div>
    </div>
  );
}
