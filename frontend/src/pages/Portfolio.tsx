import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PaperStatus } from "../api/client";
import { ChangePct } from "../components/ChangePct";
import { Panel } from "../components/Panel";
import { PriceCell } from "../components/PriceCell";

export function PortfolioPage() {
  const [data, setData] = useState<PaperStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () =>
    api.paperPortfolio().then(setData).catch(() => undefined);

  useEffect(() => {
    load();
    const id = setInterval(load, 5_000);
    return () => clearInterval(id);
  }, []);

  const sell = async (sym: string) => {
    setBusy(sym);
    try {
      await api.paperSell(sym);
      await load();
    } finally {
      setBusy(null);
    }
  };

  if (!data) return <div className="text-mute p-6">Loading paper portfolio…</div>;
  const pnlPct = ((data.equity - data.starting_capital) / data.starting_capital) * 100;

  return (
    <div className="space-y-4">
      <Panel
        title="Paper Portfolio"
        right={
          <div className="flex items-center gap-3 text-[10px]">
            <span className="px-2 py-0.5 rounded border border-warn/40 text-warn">
              SIMULATED · NO REAL ORDERS
            </span>
            {data.kill_switch && (
              <span className="px-2 py-0.5 rounded border border-danger/60 text-danger">
                KILL SWITCH ACTIVE
              </span>
            )}
          </div>
        }
      >
        <div className="bg-warn/10 border border-warn/30 text-warn text-[11px]
          rounded px-3 py-2 mb-3">
          ⚠ {data.disclaimer}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Stat label="Starting" value={`$${data.starting_capital.toLocaleString()}`} />
          <Stat label="Cash" value={`$${data.cash.toLocaleString()}`} />
          <Stat label="Equity" value={`$${data.equity.toLocaleString()}`} />
          <Stat
            label="P&L"
            value={
              <span className={pnlPct >= 0 ? "text-green" : "text-red"}>
                {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
              </span>
            }
          />
        </div>

        {data.positions.length === 0 ? (
          <div className="text-mute text-sm py-8 text-center">
            No paper positions yet. Tap <span className="text-accent">Paper Buy</span> on a card.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-mute text-[10px] uppercase tracking-wider">
              <tr>
                <th className="text-left py-2">Symbol</th>
                <th className="text-right">Qty</th>
                <th className="text-right">Avg</th>
                <th className="text-right">Last</th>
                <th className="text-right">Stop</th>
                <th className="text-right">Unrealised</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p) => {
                const change = ((p.last_price - p.avg_price) / p.avg_price) * 100;
                return (
                  <tr key={p.symbol} className="border-t border-border/50">
                    <td className="py-2">
                      <Link to={`/stocks/${p.symbol}`} className="ticker font-bold hover:text-accent">
                        {p.symbol}
                      </Link>
                    </td>
                    <td className="text-right">{p.qty}</td>
                    <td className="text-right">${p.avg_price.toFixed(2)}</td>
                    <td className="text-right">
                      <PriceCell value={p.last_price} fmt={(v) => `$${v.toFixed(2)}`} />
                    </td>
                    <td className="text-right text-warn">
                      {p.stop_price ? `$${p.stop_price.toFixed(2)}` : "—"}
                    </td>
                    <td className="text-right">
                      <span className={p.unrealized_pnl >= 0 ? "text-green" : "text-red"}>
                        ${p.unrealized_pnl.toFixed(2)}
                      </span>{" "}
                      <ChangePct value={change} />
                    </td>
                    <td className="text-right">
                      <button
                        onClick={() => sell(p.symbol)}
                        disabled={busy === p.symbol}
                        className="text-[10px] border border-danger/40 text-danger
                          px-2 py-1 rounded hover:bg-danger/10 disabled:opacity-40"
                      >
                        {busy === p.symbol ? "…" : "Paper Sell"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <div className="text-[10px] text-mute mt-3">
          Realised P&L: <span className={data.realized_pnl >= 0 ? "text-green" : "text-red"}>
            ${data.realized_pnl.toFixed(2)}
          </span>
        </div>
      </Panel>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border border-border rounded p-3 bg-panel2/60">
      <div className="text-[10px] text-mute uppercase tracking-wider">{label}</div>
      <div className="text-lg font-bold mt-1">{value}</div>
    </div>
  );
}
