"""Opportunity ranking with realistic, two-sided outcome ranges.

The "outcome range" is deliberately framed both ways: every card shows an
estimated upside AND downside derived from recent realised volatility and
the signal's confidence. Confidence itself is labelled in the UI as an
*estimated probability*, never a guarantee.

This module reuses the existing SignalEngine for scoring; it adds only:
  - per-symbol volatility estimation from stored bars
  - the upside/downside scaling
  - a hit-rate stat that comes straight from the backtester's results
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional

from backtest import Backtester
from data import latest_quote
from data.db import Database
from signals import SignalEngine


@dataclass
class OutcomeRange:
    horizon_days: int
    expected_pct: float        # midpoint, direction-aware
    upside_pct: float          # +X% (potential gain at +1 std)
    downside_pct: float        # -Y% (potential loss at -1 std)
    volatility_pct: float      # daily vol used to derive the range
    basis: str = "trailing realised volatility, 1-sigma move"


def _daily_returns(bars: List[dict]) -> List[float]:
    closes = [b.get("close") for b in bars if b.get("close")]
    rets: List[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev:
            rets.append((closes[i] - prev) / prev)
    return rets


def _stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def estimate_outcome_range(bars: List[dict], direction: str,
                           confidence: float, horizon_days: int = 5) -> OutcomeRange:
    """Symmetric 1-sigma range, then nudged by the signal direction.

    The midpoint is the confidence-weighted directional move, but the +/-
    range is always shown as the full 1-sigma swing in BOTH directions so
    the user sees real downside even on a high-confidence long.
    """
    rets = _daily_returns(bars)
    daily_vol = _stdev(rets)
    if daily_vol == 0:
        daily_vol = 0.01  # 1% floor so we never show zero risk
    # 1-sigma move over the horizon: sigma * sqrt(N)
    sigma_n = daily_vol * math.sqrt(horizon_days)

    # Midpoint shifts in the signal direction but is capped at ~half a sigma
    # so even a "high confidence" call doesn't claim more than the noise floor.
    dir_sign = 1.0 if direction == "long" else (-1.0 if direction == "short" else 0.0)
    expected = dir_sign * confidence * sigma_n * 0.5

    upside_pct = (expected + sigma_n) * 100.0
    downside_pct = (expected - sigma_n) * 100.0

    # Force both sides to remain visible regardless of direction.
    # If both come out positive (or both negative) due to a strong skew,
    # widen so downside is at least -0.5*sigma and upside at least +0.5*sigma.
    half = sigma_n * 50.0  # in percent
    if upside_pct < half:
        upside_pct = half
    if downside_pct > -half:
        downside_pct = -half

    return OutcomeRange(
        horizon_days=horizon_days,
        expected_pct=round(expected * 100.0, 3),
        upside_pct=round(upside_pct, 3),
        downside_pct=round(downside_pct, 3),
        volatility_pct=round(daily_vol * 100.0, 3),
    )


def list_opportunities(db: Database, symbols: Iterable[str],
                       *, top_n: int = 20,
                       min_confidence: float = 0.0,
                       horizon_days: int = 5) -> List[dict]:
    engine = SignalEngine(db, persist=False)
    out: List[dict] = []
    for sym in symbols:
        sigs = engine.evaluate(sym)
        agg = engine.aggregate(sigs)
        if agg.confidence < min_confidence:
            continue
        bars_desc = list(db.fetch_prices(sym, limit=200))
        bars = [dict(r) for r in reversed(bars_desc)]
        outcome = estimate_outcome_range(bars, agg.direction, agg.confidence,
                                         horizon_days=horizon_days)
        quote = latest_quote(db, sym) or {}
        reasons = [
            {
                "type": s.signal_type,
                "label": _reason_label(s.signal_type),
                "confidence": s.confidence,
                "direction": s.direction,
                "summary": _reason_summary(s.signal_type, s.inputs),
            }
            for s in sigs if s.confidence > 0.1
        ]
        if not reasons:
            reasons = [{
                "type": s.signal_type,
                "label": _reason_label(s.signal_type),
                "confidence": s.confidence,
                "direction": s.direction,
                "summary": "below detection threshold",
            } for s in sigs[:1]]
        out.append({
            "symbol": sym,
            "price": quote.get("price"),
            "ts": quote.get("ts"),
            "probability": agg.confidence,         # 0..1 estimated probability
            "direction": agg.direction,
            "reasons": reasons,
            "outcome_range": outcome.__dict__,
            "disclaimer": (
                "Confidence is an estimated probability, not a guarantee. "
                "Outcome range is a 1-sigma envelope from trailing volatility "
                "and includes equal downside risk."
            ),
        })
    out.sort(key=lambda r: r["probability"], reverse=True)
    return out[:top_n]


def _reason_label(t: str) -> str:
    return {
        "volume_spike": "Unusual volume",
        "earnings_surprise": "Earnings surprise",
        "sentiment_shift": "Sentiment shift",
    }.get(t, t.replace("_", " ").title())


def _reason_summary(t: str, inputs: dict) -> str:
    if t == "volume_spike":
        z = inputs.get("z_score")
        if isinstance(z, (int, float)):
            return f"volume z-score {z:+.2f}"
        return "volume above baseline"
    if t == "earnings_surprise":
        s = inputs.get("surprise_pct")
        if isinstance(s, (int, float)):
            return f"EPS surprise {s*100:+.1f}%"
        return "earnings beat/miss"
    if t == "sentiment_shift":
        shift = inputs.get("shift")
        if isinstance(shift, (int, float)):
            return f"sentiment shift {shift:+.2f}"
        return "social mood change"
    return ""


# ---- backtest-derived hit rate ----------------------------------------------

def compute_hit_rate(db: Database, symbols: Iterable[str],
                     *, starting_capital: float = 10_000.0) -> dict:
    """Run the existing Backtester on stored bars; return aggregated stats.

    All numbers come from real replays; nothing is hard-coded or padded.
    """
    per_symbol: List[dict] = []
    total_trades = 0
    total_wins = 0
    total_pnl = 0.0
    drawdowns: List[float] = []
    sharpes: List[float] = []
    for sym in symbols:
        rows = list(db.fetch_prices(sym, limit=5000))
        if len(rows) < 60:
            per_symbol.append({"symbol": sym, "skipped": True,
                               "reason": "insufficient_history"})
            continue
        bars = [dict(r) for r in reversed(rows)]
        bt = Backtester(starting_capital=starting_capital)
        res = bt.run(sym, bars)
        m = res.metrics
        per_symbol.append({
            "symbol": sym, "skipped": False,
            "n_trades": m.n_trades, "win_rate": m.win_rate,
            "total_pnl": m.total_pnl, "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe": m.sharpe,
        })
        total_trades += m.n_trades
        total_wins += m.n_wins
        total_pnl += m.total_pnl
        if m.max_drawdown_pct:
            drawdowns.append(m.max_drawdown_pct)
        if m.sharpe:
            sharpes.append(m.sharpe)

    overall_win_rate: Optional[float] = (
        round(total_wins / total_trades, 4) if total_trades else None
    )
    return {
        "overall": {
            "n_trades": total_trades,
            "win_rate": overall_win_rate,
            "total_pnl": round(total_pnl, 2),
            "max_drawdown_pct": round(max(drawdowns), 4) if drawdowns else 0.0,
            "avg_sharpe": round(sum(sharpes) / len(sharpes), 4) if sharpes else 0.0,
            "source": "backtest replay of stored bars (no hardcoded numbers)",
        },
        "per_symbol": per_symbol,
        "disclaimer": (
            "Backtest results are historical only and do not guarantee "
            "future performance. Trades shown are simulated."
        ),
    }
