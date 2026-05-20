import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, StockDetail as StockDetailT } from "../api/client";
import { ChangePct, ConfBar } from "../components/ChangePct";
import { NewsFeed } from "../components/NewsFeed";
import { Panel } from "../components/Panel";
import { PriceCell } from "../components/PriceCell";
import { StockChart } from "../components/StockChart";
import { useLiveData } from "../live/LiveDataProvider";

export function StockDetail() {
  const { symbol = "" } = useParams();
  const sym = symbol.toUpperCase();
  const [data, setData] = useState<StockDetailT | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"intraday" | "daily">("intraday");
  const live = useLiveData();

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    setData(null);
    api
      .stock(sym)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e));
      });
    const id = setInterval(() => {
      api
        .stock(sym)
        .then((d) => {
          if (!cancelled) setData(d);
        })
        .catch(() => undefined);
    }, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sym]);

  if (err) return <div className="text-red p-6">Error: {err}</div>;
  if (!data) return <div className="text-mute p-6">Loading {sym}…</div>;

  const livePrice = live.latest[sym]?.price ?? data.quote?.price ?? null;
  const liveChange = live.latest[sym]?.change_pct ?? null;
  const bars = mode === "intraday" ? data.intraday : data.daily;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-4">
        <Link to="/" className="text-mute hover:text-accent text-sm">
          ← Dashboard
        </Link>
        <div className="ticker text-2xl font-bold text-accent">{sym}</div>
        <div className="text-2xl">
          <PriceCell value={livePrice ?? undefined} fmt={(v) => `$${v.toFixed(2)}`} />
        </div>
        <ChangePct value={liveChange} />
        {data.quote && (
          <span className="text-mute text-xs ml-auto">
            last: {new Date(data.quote.ts).toLocaleString()} ({data.quote.source})
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Panel
            title="Price Chart"
            right={
              <div className="flex gap-1">
                {(["intraday", "daily"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`text-[10px] uppercase px-2 py-0.5 rounded border ${
                      mode === m
                        ? "border-accent text-accent bg-accent/10"
                        : "border-border text-mute hover:text-text"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            }
          >
            {bars.length === 0 ? (
              <div className="text-mute py-10 text-center">No {mode} bars yet.</div>
            ) : (
              <StockChart bars={bars} mode={mode} />
            )}
          </Panel>

          <SignalBreakdown data={data} />
        </div>

        <div className="space-y-4">
          <NewsFeed symbol={sym} />
        </div>
      </div>
    </div>
  );
}

function SignalBreakdown({ data }: { data: StockDetailT }) {
  const sig = data.signal;
  return (
    <Panel title="Signal Breakdown">
      {!sig ? (
        <div className="text-mute text-sm">No signal data yet for this symbol.</div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <span className="text-mute text-xs uppercase">Aggregate</span>
            <ConfBar value={sig.confidence} />
            <span
              className={`text-xs font-bold uppercase px-2 py-0.5 rounded border ${
                sig.direction === "long"
                  ? "border-green/40 text-green bg-green/5"
                  : sig.direction === "short"
                  ? "border-red/40 text-red bg-red/5"
                  : "border-mute/40 text-mute"
              }`}
            >
              {sig.direction}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {sig.reasons.map((r) => (
              <div
                key={r.type}
                className="border border-border rounded p-3 bg-panel2/60"
              >
                <div className="text-xs text-mute uppercase tracking-wider mb-1">
                  {r.type.replace(/_/g, " ")}
                </div>
                <ConfBar value={r.confidence} />
                <div className="text-xs text-mute mt-2 break-all">
                  dir: <span className="text-text">{r.direction}</span>
                </div>
                <details className="mt-2 text-[10px] text-mute">
                  <summary className="cursor-pointer text-accent">inputs</summary>
                  <pre className="mt-1 overflow-auto max-h-32">
                    {JSON.stringify(r.inputs, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
          {data.audit_log.length > 0 && (
            <details className="text-xs text-mute">
              <summary className="cursor-pointer text-accent">recent audit log ({data.audit_log.length})</summary>
              <ul className="mt-2 space-y-1 max-h-48 overflow-auto">
                {data.audit_log.map((a) => (
                  <li key={a.id} className="border-l border-border pl-2">
                    <span className="text-accent2">{a.ts}</span> · {a.signal_type} ·
                    conf {a.confidence.toFixed(2)} · {a.direction}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </Panel>
  );
}
