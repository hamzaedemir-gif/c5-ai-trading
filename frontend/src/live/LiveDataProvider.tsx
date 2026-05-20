import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { wsUrl } from "../api/client";

export interface LiveTrade {
  type: "trade";
  symbol: string;
  price: number;
  ts: string;
  last_size: number;
  day_volume: number;
  change_pct: number;
  prev_price: number | null;
}

export interface LiveQuote {
  type: "quote";
  symbol: string;
  ts: string;
  bid: number;
  ask: number;
}

export interface LiveHello {
  type: "hello";
  paper_mode: boolean;
  symbols: string[];
  snapshot: Record<string, Omit<LiveTrade, "type">>;
}

export type LiveMessage = LiveTrade | LiveQuote | LiveHello;

interface LiveDataState {
  connected: boolean;
  paperMode: boolean;
  symbols: string[];
  // Latest trade per symbol.
  latest: Record<string, Omit<LiveTrade, "type">>;
  // Updated counter so subscribers re-render on push.
  tick: number;
}

const Ctx = createContext<LiveDataState>({
  connected: false,
  paperMode: true,
  symbols: [],
  latest: {},
  tick: 0,
});

export function useLiveData() {
  return useContext(Ctx);
}

export function LiveDataProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [paperMode, setPaperMode] = useState(true);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [latest, setLatest] = useState<Record<string, Omit<LiveTrade, "type">>>({});
  const [tick, setTick] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number>(1000);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectRef.current = 1000;
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          setTimeout(connect, reconnectRef.current);
          reconnectRef.current = Math.min(reconnectRef.current * 2, 30_000);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as LiveMessage;
          if (msg.type === "hello") {
            setPaperMode(msg.paper_mode);
            setSymbols(msg.symbols);
            setLatest(msg.snapshot || {});
            setTick((t) => t + 1);
          } else if (msg.type === "trade") {
            setLatest((prev) => ({ ...prev, [msg.symbol]: { ...msg } }));
            setTick((t) => t + 1);
          }
          // quotes ignored for the dashboard; reserve for future UI
        } catch {
          /* ignore */
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return (
    <Ctx.Provider value={{ connected, paperMode, symbols, latest, tick }}>
      {children}
    </Ctx.Provider>
  );
}
