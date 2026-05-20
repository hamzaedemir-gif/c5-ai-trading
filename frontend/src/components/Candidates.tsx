import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Candidate } from "../api/client";
import { useLiveData } from "../live/LiveDataProvider";
import { ChangePct, ConfBar } from "./ChangePct";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";

export function Candidates() {
  const [rows, setRows] = useState<Candidate[]>([]);
  const live = useLiveData();

  useEffect(() => {
    let cancelled = false;
    const refresh = () =>
      api
        .candidates(15)
        .then((r) => {
          if (!cancelled) setRows(r.items);
        })
        .catch(() => undefined);
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <Panel title="Top Candidates" right={<span className="text-mute text-xs">{rows.length} ranked</span>}>
      {rows.length === 0 && (
        <div className="text-mute text-sm py-6 text-center">
          No candidates yet. Ingest price data for your watchlist:
          <pre className="mt-2 text-xs text-accent">python run_paper.py ingest AAPL MSFT TSLA</pre>
        </div>
      )}
      <div className="space-y-1">
        {rows.map((c) => {
          const livePrice = live.latest[c.symbol]?.price ?? c.price ?? null;
          const liveChange = live.latest[c.symbol]?.change_pct ?? null;
          return (
            <Link
              key={c.symbol}
              to={`/stocks/${c.symbol}`}
              className="grid grid-cols-12 items-center gap-3 px-3 py-2 rounded
                hover:bg-accent/5 hover:border-accent/30 border border-transparent"
            >
              <div className="col-span-2 ticker font-bold text-text">{c.symbol}</div>
              <div className="col-span-2 text-right">
                <PriceCell value={livePrice ?? undefined} fmt={(v) => `$${v.toFixed(2)}`} />
              </div>
              <div className="col-span-2 text-right">
                <ChangePct value={liveChange ?? null} />
              </div>
              <div className="col-span-3">
                <ConfBar value={c.confidence} />
              </div>
              <div className="col-span-3 flex flex-wrap justify-end gap-1">
                {c.reasons
                  .filter((r) => r.confidence > 0.1)
                  .map((r) => (
                    <span
                      key={r.type}
                      title={`${r.type} · ${r.direction} · ${(r.confidence * 100).toFixed(0)}%`}
                      className={`text-[10px] px-2 py-0.5 rounded border ${
                        r.direction === "long"
                          ? "border-green/40 text-green bg-green/5"
                          : r.direction === "short"
                          ? "border-red/40 text-red bg-red/5"
                          : "border-mute/40 text-mute"
                      }`}
                    >
                      {labelFor(r.type)}
                    </span>
                  ))}
                {c.reasons.every((r) => r.confidence <= 0.1) && (
                  <span className="text-[10px] text-mute">no strong signals</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </Panel>
  );
}

function labelFor(type: string): string {
  switch (type) {
    case "volume_spike": return "VOLUME";
    case "earnings_surprise": return "EARNINGS";
    case "sentiment_shift": return "SENTIMENT";
    default: return type.toUpperCase();
  }
}
