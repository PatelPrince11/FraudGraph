import { useState } from "react";

import type { CardSummary, Follow, Graph, Risk, TxnRow } from "../api";
import { useApi } from "../useApi";
import ActionBar from "./ActionBar";
import ActivityPanel from "./ActivityPanel";
import CardPanel from "./CardPanel";
import GraphView from "./GraphView";
import LinkedCards from "./LinkedCards";
import LocationMap from "./LocationMap";
import RiskCard from "./RiskCard";

/** Everything about one alert. Fetches once here and hands data to each panel. */
export default function Investigation({ transNum, showTruth, onDecided }: {
  transNum: string; showTruth: boolean; onDecided: () => void;
}) {
  const [follow, setFollow] = useState<Follow>("either");
  const [rounds, setRounds] = useState(2);
  const risk = useApi<Risk>(`/transactions/${transNum}/risk`);
  const history = useApi<TxnRow[]>(`/transactions/${transNum}/history?limit=30`);
  const card = useApi<CardSummary>(`/transactions/${transNum}/card`);
  const graph = useApi<Graph>(`/transactions/${transNum}/graph?follow=${follow}&rounds=${rounds}`);

  return (
    <main className="relative min-h-0 overflow-y-auto">
      <div className="grid gap-4 pb-28 xl:grid-cols-3">
        <div className="xl:col-span-2"><RiskCard risk={risk} history={history.data} showTruth={showTruth} /></div>
        <CardPanel card={card} />
        <div className="h-[330px]"><ActivityPanel rows={history.data} current={transNum} showTruth={showTruth} /></div>
        <div className="h-[330px]"><LocationMap card={card.data} rows={history.data} current={transNum} /></div>
        <div className="h-[330px]"><LinkedCards graph={graph.data} showTruth={showTruth} /></div>
        <div className="h-[520px] xl:col-span-3">
          <GraphView graph={graph} follow={follow} setFollow={setFollow}
            rounds={rounds} setRounds={setRounds} showTruth={showTruth} />
        </div>
      </div>
      {/* Solid strip + fade behind the bar, so scrolled content can't show through below it. */}
      <div className="sticky bottom-0 -mt-28 bg-gradient-to-t from-ink from-60% to-transparent pb-1 pt-6">
        <ActionBar transNum={transNum} risk={risk.data} graph={graph.data} onDecided={onDecided} />
      </div>
    </main>
  );
}
