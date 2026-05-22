import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Mover } from "../api/client";
import { useLiveData } from "../live/LiveDataProvider";
import { ChangePct } from "./ChangePct";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";

type Kind = "gainers" | "losers" | "high_volume";
const TITLE: Record<Kind, string> = {
  gainers: "Top Gainers",
  losers: "Top Losers",
  high_volume: "High Volume Movers",
};

export function MoversBoard() {
  const [data, setData] = useState<Record<Kind, Mover[]>>({
    gainers: [],
    losers: [],
    high_volume: [],
  });

  useEffect(() => {
    let cancelled = false;
    const refresh = () =>
      api
        .movers()
        .then((r) => {
          if (!cancelled) setData(r);
        })
        .catch(() => undefined);
    refresh();
    const id = setInterval(refresh, 20_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <MoverCard kind="gainers" rows={data.gainers} />
      <MoverCard kind="losers" rows={data.losers} />
      <MoverCard kind="high_volume" rows={data.high_volume} />
    </div>
  );
}

function MoverCard({ kind, rows }: { kind: Kind; rows: Mover[] }) {
  const live = useLiveData();
  return (
    <Panel title={TITLE[kind]}>
      {rows.length === 0 ? (
        <div className="text-mute text-sm py-4 text-center">no data</div>
      ) : (
        <ul className="divide-y divide-border/60">
          {rows.slice(0, 6).map((r) => {
            const livePrice = live.latest[r.symbol]?.price ?? r.price;
            return (
              <li key={r.symbol}>
                <Link
                  to={`/stocks/${r.symbol}`}
                  className="grid grid-cols-12 items-center gap-2 py-2 hover:bg-accent/5"
                >
                  <div className="col-span-3 ticker font-bold">{r.symbol}</div>
                  <div className="col-span-4 text-right">
                    <PriceCell value={livePrice} fmt={(v) => `$${v.toFixed(2)}`} />
                  </div>
                  <div className="col-span-3 text-right">
                    {kind === "high_volume" ? (
                      <span className="text-accent2 text-xs">×{r.volume_ratio.toFixed(1)}</span>
                    ) : (
                      <ChangePct value={r.change_pct} />
                    )}
                  </div>
                  <div className="col-span-2 text-right text-mute text-[10px]">
                    {fmtVol(r.volume)}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}

function fmtVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}
