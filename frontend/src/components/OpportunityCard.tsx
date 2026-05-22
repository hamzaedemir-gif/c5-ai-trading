import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Opportunity } from "../api/client";
import { useLiveData } from "../live/LiveDataProvider";
import { ChangePct } from "./ChangePct";
import { PriceCell } from "./PriceCell";

export function OpportunityCard({ opp }: { opp: Opportunity }) {
  const navigate = useNavigate();
  const live = useLiveData();
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const livePrice = live.latest[opp.symbol]?.price ?? opp.price ?? null;
  const liveChange = live.latest[opp.symbol]?.change_pct ?? null;
  const probPct = Math.round(opp.probability * 100);
  const probTone =
    opp.probability >= 0.75 ? "accent" :
    opp.probability >= 0.5  ? "warn" : "mute";

  const handleBuy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setBusy(true);
    try {
      const r = await api.paperBuy(opp.symbol, livePrice ?? undefined);
      setToast(
        r.approved
          ? `Paper bought ${r.qty} ${r.symbol} @ $${r.price.toFixed(2)} (stop $${r.stop_price?.toFixed(2)})`
          : `Rejected: ${r.reason}`,
      );
    } catch (err) {
      setToast(`Error: ${err}`);
    } finally {
      setBusy(false);
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <div
      onClick={() => navigate(`/stocks/${opp.symbol}`)}
      className="bg-panel border border-border rounded-lg p-4 cursor-pointer
        hover:border-accent/60 hover:shadow-glow transition-all
        flex flex-col gap-3 min-h-[260px]"
    >
      {/* header: ticker + live price */}
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="ticker text-xl font-bold text-text">{opp.symbol}</div>
          <div className="text-[10px] text-mute uppercase tracking-wider">
            {dirLabel(opp.direction)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold">
            <PriceCell value={livePrice ?? undefined} fmt={(v) => `$${v.toFixed(2)}`} />
          </div>
          <div className="text-xs"><ChangePct value={liveChange} /></div>
        </div>
      </div>

      {/* probability — clearly labelled as estimate */}
      <div>
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-wider text-mute">
            Estimated probability
          </span>
          <span className={`text-2xl font-bold ${probColor(probTone)}`}>
            {probPct}%
          </span>
        </div>
        <div className="h-1.5 bg-panel2 rounded overflow-hidden mt-1">
          <div className={`h-full ${probBar(probTone)}`} style={{ width: `${probPct}%` }} />
        </div>
        <div className="text-[9px] text-mute mt-1 italic">
          model estimate — not a guarantee
        </div>
      </div>

      {/* outcome range — upside AND downside equal weight */}
      <div className="grid grid-cols-2 gap-2">
        <div className="border border-green/30 bg-green/5 rounded p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-mute">
            Potential upside ({opp.outcome_range.horizon_days}d)
          </div>
          <div className="text-green text-base font-bold mt-0.5">
            +{opp.outcome_range.upside_pct.toFixed(2)}%
          </div>
        </div>
        <div className="border border-red/30 bg-red/5 rounded p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-mute">
            Potential downside ({opp.outcome_range.horizon_days}d)
          </div>
          <div className="text-red text-base font-bold mt-0.5">
            {opp.outcome_range.downside_pct.toFixed(2)}%
          </div>
        </div>
      </div>
      <div className="text-[9px] text-mute -mt-1">
        1-sigma envelope · vol {opp.outcome_range.volatility_pct.toFixed(2)}%/day
      </div>

      {/* why flagged */}
      <div className="flex flex-wrap gap-1">
        {opp.reasons.slice(0, 3).map((r) => (
          <span
            key={r.type}
            className={`text-[10px] px-2 py-0.5 rounded border ${
              r.direction === "long"
                ? "border-green/40 text-green bg-green/5"
                : r.direction === "short"
                ? "border-red/40 text-red bg-red/5"
                : "border-mute/40 text-mute"
            }`}
            title={r.summary}
          >
            {r.label} · {Math.round(r.confidence * 100)}%
          </span>
        ))}
      </div>

      {/* paper buy button */}
      <div className="mt-auto flex items-center gap-2">
        <button
          onClick={handleBuy}
          disabled={busy}
          className="flex-1 text-xs uppercase tracking-widest font-bold
            border border-accent/60 text-accent bg-accent/10 rounded
            py-2 hover:bg-accent/20 disabled:opacity-40 transition-colors"
        >
          {busy ? "…" : "Paper Buy"}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); navigate(`/stocks/${opp.symbol}`); }}
          className="text-xs uppercase tracking-widest text-mute border
            border-border rounded px-3 py-2 hover:text-accent hover:border-accent"
        >
          Details
        </button>
      </div>

      {toast && (
        <div className="absolute mt-[230px] z-10 bg-panel2 border border-accent
          text-accent text-xs px-3 py-1 rounded shadow-glow">
          {toast}
        </div>
      )}
    </div>
  );
}

function probColor(t: "accent" | "warn" | "mute"): string {
  return t === "accent" ? "text-accent" : t === "warn" ? "text-warn" : "text-mute";
}
function probBar(t: "accent" | "warn" | "mute"): string {
  return t === "accent" ? "bg-accent" : t === "warn" ? "bg-warn" : "bg-mute";
}
function dirLabel(d: string): string {
  if (d === "long")  return "Bullish setup";
  if (d === "short") return "Bearish setup";
  return "Neutral";
}
