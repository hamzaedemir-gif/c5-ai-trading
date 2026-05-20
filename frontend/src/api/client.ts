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
  demo_mode: boolean;
  symbols: string[];
  live_symbols: number;
  stream_connected: boolean;
}

export interface OutcomeRange {
  horizon_days: number;
  expected_pct: number;
  upside_pct: number;
  downside_pct: number;
  volatility_pct: number;
  basis: string;
}

export interface OppReason {
  type: string;
  label: string;
  confidence: number;
  direction: "long" | "short" | "flat";
  summary: string;
}

export interface Opportunity {
  symbol: string;
  price: number | null;
  ts: string | null;
  probability: number;
  direction: "long" | "short" | "flat";
  reasons: OppReason[];
  outcome_range: OutcomeRange;
  disclaimer: string;
}

export interface PaperPosition {
  symbol: string;
  qty: number;
  avg_price: number;
  stop_price: number | null;
  last_price: number;
  market_value: number;
  unrealized_pnl: number;
  opened_at: string;
}

export interface PaperStatus {
  mode: "paper";
  starting_capital: number;
  cash: number;
  equity: number;
  realized_pnl: number;
  kill_switch: boolean;
  positions: PaperPosition[];
  disclaimer: string;
}

export interface PaperBuyResult {
  approved: boolean;
  reason: string;
  symbol: string;
  qty: number;
  price: number;
  stop_price: number | null;
  notional: number;
  trade_id: number | null;
  mode: "paper";
  disclaimer: string;
}

export interface HitRate {
  overall: {
    n_trades: number;
    win_rate: number | null;
    total_pnl: number;
    max_drawdown_pct: number;
    avg_sharpe: number;
    source: string;
  };
  per_symbol: Array<Record<string, unknown>>;
  disclaimer: string;
}

export interface DisclaimerInfo {
  text: string;
  paper_mode: boolean;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  health: () => get<Health>("/healthz"),
  disclaimer: () => get<DisclaimerInfo>("/disclaimer"),
  candidates: (topN = 20, minConf = 0) =>
    get<{ items: Candidate[] }>(`/candidates?top_n=${topN}&min_confidence=${minConf}`),
  opportunities: (topN = 12, horizon = 5) =>
    get<{ items: Opportunity[]; label_explainer: string; disclaimer: string }>(
      `/opportunities?top_n=${topN}&horizon_days=${horizon}`,
    ),
  hitRate: () => get<HitRate>("/performance/hit-rate"),
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
  paperPortfolio: () => get<PaperStatus>("/paper/portfolio"),
  paperBuy: (symbol: string, price?: number) =>
    postJSON<PaperBuyResult>("/paper/buy", { symbol, price }),
  paperSell: (symbol: string, price?: number) =>
    postJSON<{ closed: boolean; reason?: string; realized_pnl?: number }>(
      "/paper/sell", { symbol, price },
    ),
};

export function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws`;
}
