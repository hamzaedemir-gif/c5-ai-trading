import { useEffect, useState } from "react";
import { api, HitRate, Opportunity } from "../api/client";
import { useLiveData } from "../live/LiveDataProvider";
import { OpportunityCard } from "./OpportunityCard";
import { Panel } from "./Panel";

export function OpportunityFeed() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [hr, setHr] = useState<HitRate | null>(null);
  const [explainer, setExplainer] = useState("");
  const [disclaimer, setDisclaimer] = useState("");
  const live = useLiveData();

  useEffect(() => {
    let cancelled = false;
    const refresh = () =>
      api
        .opportunities(12)
        .then((r) => {
          if (cancelled) return;
          setItems(r.items);
          setExplainer(r.label_explainer);
          setDisclaimer(r.disclaimer);
        })
        .catch(() => undefined);
    refresh();
    const id = setInterval(refresh, 20_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Refresh quickly when live data ticks too, so order stays current.
  useEffect(() => {
    if (live.tick === 0) return;
    const t = setTimeout(() => {
      api.opportunities(12).then((r) => setItems(r.items)).catch(() => undefined);
    }, 1500);
    return () => clearTimeout(t);
  }, [live.tick]);

  useEffect(() => {
    api.hitRate().then(setHr).catch(() => undefined);
  }, []);

  return (
    <Panel
      title="Top Opportunities"
      right={
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-mute">{items.length} ranked · refreshes live</span>
          {hr?.overall.win_rate != null ? (
            <span className="text-accent border border-accent/40 rounded px-2 py-0.5">
              Backtest hit-rate: {(hr.overall.win_rate * 100).toFixed(1)}%
              ({hr.overall.n_trades} trades)
            </span>
          ) : (
            <span className="text-mute italic">backtest pending</span>
          )}
        </div>
      }
    >
      <div className="bg-warn/10 border border-warn/30 text-warn text-[11px]
        rounded px-3 py-2 mb-3">
        ⚠ {disclaimer || "Analytics & education only. Probabilities are model estimates, not guarantees. Paper-mode only — no real orders."}
      </div>
      {explainer && (
        <div className="text-[11px] text-mute mb-3">{explainer}</div>
      )}
      {items.length === 0 ? (
        <div className="text-mute text-sm py-10 text-center">
          No opportunities ranked yet. Try{" "}
          <span className="text-accent">/run_paper.py ingest AAPL MSFT TSLA</span>{" "}
          or launch in demo mode.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {items.map((o) => (
            <OpportunityCard key={o.symbol} opp={o} />
          ))}
        </div>
      )}
    </Panel>
  );
}
