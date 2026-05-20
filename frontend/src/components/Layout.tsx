import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, DisclaimerInfo } from "../api/client";
import { useLiveData } from "../live/LiveDataProvider";
import { SearchBar } from "./SearchBar";

export function Layout({ children }: { children: React.ReactNode }) {
  const live = useLiveData();
  const [disc, setDisc] = useState<DisclaimerInfo | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.disclaimer().then(setDisc).catch(() => undefined);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-panel/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto px-6 py-3 flex items-center gap-6">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-accent/20 border border-accent text-accent flex items-center justify-center font-bold shadow-glow">
              C5
            </div>
            <div className="leading-tight">
              <div className="text-text font-bold">C5 AI Trading</div>
              <div className="text-mute text-xs">Live Signal Dashboard</div>
            </div>
          </Link>
          <nav className="flex items-center gap-3 text-xs">
            <NavLink to="/">Opportunities</NavLink>
            <NavLink to="/portfolio">Paper Portfolio</NavLink>
          </nav>
          <div className="flex-1 max-w-md">
            <SearchBar onPick={(sym) => navigate(`/stocks/${sym}`)} />
          </div>
          <div className="flex items-center gap-4 text-xs">
            <Pill
              label={live.connected ? "LIVE" : "OFFLINE"}
              tone={live.connected ? "ok" : "bad"}
            />
            <Pill
              label={live.paperMode ? "PAPER MODE" : "LIVE MODE"}
              tone={live.paperMode ? "warn" : "bad"}
            />
            {live.demoMode && (
              <Pill label="DEMO DATA" tone="warn" />
            )}
            <div className="text-mute">
              {live.symbols.length} symbols
            </div>
          </div>
        </div>
      </header>

      {disc && (
        <div className="bg-warn/10 border-b border-warn/30 text-warn text-xs px-6 py-2 text-center">
          ⚠ {disc.text}
        </div>
      )}

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-6 py-6">{children}</main>

      <footer className="border-t border-border text-mute text-xs px-6 py-3 text-center">
        Analytics & education only · No orders are ever routed by this app · Not financial advice
      </footer>
    </div>
  );
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="text-mute hover:text-accent border border-transparent
        hover:border-accent/40 px-2 py-1 rounded"
    >
      {children}
    </Link>
  );
}

function Pill({ label, tone }: { label: string; tone: "ok" | "warn" | "bad" }) {
  const color = {
    ok: "bg-accent/15 text-accent border-accent/40",
    warn: "bg-warn/15 text-warn border-warn/40",
    bad: "bg-danger/15 text-danger border-danger/40",
  }[tone];
  return (
    <span className={`px-2 py-1 rounded border ${color} text-[10px] font-bold`}>
      {label}
    </span>
  );
}
