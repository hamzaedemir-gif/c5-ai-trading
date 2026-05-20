const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status}`);
  }
  return res.json();
}

export interface Reason {
  type: string;
  confidence: number;
  direction: "long" | "short" | "flat";
  inputs: Record<string, unknown>;
}

export interface Candidate {
  symbol: string;
  price: number | null;
  ts: string | null;
  confidence: number;
  direction: "long" | "short" | "flat";
  reasons: Reason[];
  aggregate_inputs: Record<string, unknown>;
}

export interface Mover {
  symbol: string;
  price: number;
  change_pct: number;
  volume: number;
  avg_volume: number;
  volume_ratio: number;
  ts: string;
}

export interface NewsItem {
  id: number;
  symbol: string | null;
  headline: string;
  url: string | null;
  summary: string | null;
  published_at: string;
  source: string;
}

export interface StockDetail {
  symbol: string;
  quote: { symbol: string; price: number; volume: number; ts: string; source: string } | null;
  intraday: Array<{ ts: string; open: number; high: number; low: number; close: number; volume: number }>;
  daily: Array<{ date: string; open: number; high: number; low: number; close: number; volume: number }>;
  news: NewsItem[];
  signal: Candidate | null;
  audit_log: Array<{
    id: number;
    ts: string;
    symbol: string;
    signal_type: string;
    confidence: number;
    direction: string;
    inputs: Record<string, unknown>;
    notes: string | null;
  }>;
}

export interface Health {
  ok: boolean;
  paper_mode: boolean;
  symbols: string[];
  live_symbols: number;
  stream_connected: boolean;
}

export interface DisclaimerInfo {
  text: string;
  paper_mode: boolean;
}

export const api = {
  health: () => get<Health>("/healthz"),
  disclaimer: () => get<DisclaimerInfo>("/disclaimer"),
  candidates: (topN = 20, minConf = 0) =>
    get<{ items: Candidate[] }>(`/candidates?top_n=${topN}&min_confidence=${minConf}`),
  movers: (lookback = 60) =>
    get<{ gainers: Mover[]; losers: Mover[]; high_volume: Mover[] }>(
      `/movers?lookback=${lookback}`,
    ),
  news: (symbol?: string, limit = 50) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (symbol) q.set("symbol", symbol);
    return get<{ items: NewsItem[] }>(`/news?${q}`);
  },
  search: (q: string) =>
    get<{ items: string[] }>(`/search?q=${encodeURIComponent(q)}`),
  stock: (symbol: string) => get<StockDetail>(`/stocks/${symbol}`),
};

export function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws`;
}
