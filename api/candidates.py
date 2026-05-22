"""Ranking helper that turns SignalEngine output into UI-friendly rows."""
from __future__ import annotations

import json
from typing import Iterable, List

from data import latest_quote
from data.db import Database
from signals import SignalEngine


def rank_candidates(db: Database, symbols: Iterable[str],
                    *, top_n: int = 20, min_confidence: float = 0.0) -> List[dict]:
    """Run the signal engine across `symbols`, return ranked rows.

    Each row carries the aggregate score plus the per-signal breakdown so
    the UI can show "why flagged" without a second round-trip.
    """
    engine = SignalEngine(db, persist=False)
    out: List[dict] = []
    for sym in symbols:
        sigs = engine.evaluate(sym)
        agg = engine.aggregate(sigs)
        if agg.confidence < min_confidence:
            continue
        q = latest_quote(db, sym) or {}
        out.append({
            "symbol": sym,
            "price": q.get("price"),
            "ts": q.get("ts"),
            "confidence": agg.confidence,
            "direction": agg.direction,
            "reasons": [
                {
                    "type": s.signal_type,
                    "confidence": s.confidence,
                    "direction": s.direction,
                    "inputs": dict(s.inputs),
                }
                for s in sigs
            ],
            "aggregate_inputs": dict(agg.inputs),
        })
    out.sort(key=lambda r: r["confidence"], reverse=True)
    return out[:top_n]


def list_audit_log(db: Database, symbol: str | None = None,
                   limit: int = 50) -> List[dict]:
    rows = db.fetch_signals(symbol=symbol, limit=limit)
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["inputs"] = json.loads(d.pop("inputs_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["inputs"] = {}
        out.append(d)
    return out
