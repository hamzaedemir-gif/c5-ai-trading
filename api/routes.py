"""REST routes exposed by the dashboard backend."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Body, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from data import compute_movers, latest_quote, list_recent_news, search_symbols

from .candidates import list_audit_log, rank_candidates
from .opportunities import compute_hit_rate, list_opportunities

router = APIRouter()


def _state(request: Request):
    return request.app.state.c5


@router.get("/healthz")
def healthz(request: Request) -> dict:
    s = _state(request)
    snapshot = s.stream.snapshot() if s.stream else {}
    return {
        "ok": True,
        "paper_mode": s.paper_mode,
        "demo_mode": s.demo_mode,
        "symbols": s.symbols,
        "live_symbols": len(snapshot),
        "stream_connected": bool(s.stream and s.stream.latest),
    }


def _cache_get_or(state, key: tuple, ttl: float, fn):
    hit, value = state.cache.get(key)
    if hit:
        return value
    value = fn()
    state.cache.set(key, value, ttl=ttl)
    return value


@router.get("/opportunities")
def opportunities(request: Request,
                  top_n: int = Query(20, ge=1, le=100),
                  min_confidence: float = Query(0.0, ge=0.0, le=1.0),
                  horizon_days: int = Query(5, ge=1, le=30)) -> dict:
    s = _state(request)
    key = ("opportunities", top_n, min_confidence, horizon_days)
    items = _cache_get_or(s, key, 8.0, lambda: list_opportunities(
        s.db, s.symbols, top_n=top_n,
        min_confidence=min_confidence, horizon_days=horizon_days,
    ))
    return {
        "items": items,
        "label_explainer": (
            "Probability is the model's estimated confidence (0..1). "
            "Outcome range shows a 1-sigma move in BOTH directions over the "
            "horizon, derived from trailing realised volatility."
        ),
        "disclaimer": s.disclaimer,
    }


@router.get("/performance/hit-rate")
def performance_hit_rate(request: Request) -> dict:
    s = _state(request)
    return _cache_get_or(s, ("hit_rate",), 60.0,
                         lambda: compute_hit_rate(s.db, s.symbols))


@router.get("/paper/portfolio")
def paper_portfolio(request: Request) -> dict:
    s = _state(request)
    if s.paper is None:
        raise HTTPException(503, "paper portfolio not initialised")
    s.paper.apply_stops(s.marks())
    return s.paper.status(s.marks())


@router.post("/paper/buy")
def paper_buy(request: Request, body: dict = Body(...)) -> dict:
    s = _state(request)
    if s.paper is None:
        raise HTTPException(503, "paper portfolio not initialised")
    sym = str(body.get("symbol", "")).upper()
    if not sym:
        raise HTTPException(422, "symbol required")
    price = body.get("price")
    price = float(price) if price is not None else None
    result = s.paper.paper_buy(sym, current_price=price)
    return {
        "approved": result.approved,
        "reason": result.reason,
        "symbol": result.symbol,
        "qty": result.qty,
        "price": result.price,
        "stop_price": result.stop_price,
        "notional": result.notional,
        "trade_id": result.trade_id,
        "mode": "paper",
        "disclaimer": "Simulated. No real order was placed.",
    }


@router.post("/paper/sell")
def paper_sell(request: Request, body: dict = Body(...)) -> dict:
    s = _state(request)
    if s.paper is None:
        raise HTTPException(503, "paper portfolio not initialised")
    sym = str(body.get("symbol", "")).upper()
    if not sym:
        raise HTTPException(422, "symbol required")
    price = body.get("price")
    price = float(price) if price is not None else None
    return s.paper.paper_sell(sym, current_price=price)


@router.post("/paper/kill-switch")
def paper_kill_switch(request: Request, body: dict = Body(default={})) -> dict:
    s = _state(request)
    if s.paper is None:
        raise HTTPException(503, "paper portfolio not initialised")
    action = str(body.get("action", "trip")).lower()
    if action == "reset":
        s.paper.reset_kill_switch()
    else:
        s.paper.trip_kill_switch(reason=str(body.get("reason", "manual")))
    return {"kill_switch": s.paper.risk.kill_switch}


@router.get("/disclaimer")
def disclaimer(request: Request) -> dict:
    return {"text": _state(request).disclaimer, "paper_mode": _state(request).paper_mode}


@router.get("/candidates")
def candidates(request: Request,
               top_n: int = Query(20, ge=1, le=100),
               min_confidence: float = Query(0.0, ge=0.0, le=1.0)) -> dict:
    s = _state(request)
    key = ("candidates", top_n, min_confidence)
    rows = _cache_get_or(s, key, 8.0, lambda: rank_candidates(
        s.db, s.symbols, top_n=top_n, min_confidence=min_confidence,
    ))
    return {"items": rows}


@router.get("/movers")
def movers(request: Request, lookback: int = Query(60, ge=2, le=500)) -> dict:
    s = _state(request)
    key = ("movers", lookback)
    return _cache_get_or(s, key, 6.0, lambda: compute_movers(
        s.db, s.symbols, lookback_bars=lookback,
    ))


@router.get("/news")
def news(request: Request, symbol: str | None = None,
         limit: int = Query(50, ge=1, le=200)) -> dict:
    s = _state(request)
    key = ("news", symbol or "", limit)
    return _cache_get_or(s, key, 15.0, lambda: {
        "items": list_recent_news(s.db, limit=limit, symbol=symbol),
    })


@router.get("/search")
def search(request: Request, q: str = Query("", min_length=0, max_length=20),
           limit: int = Query(15, ge=1, le=50)) -> dict:
    s = _state(request)
    matches = search_symbols(s.db, q, limit=limit)
    # Always include configured symbols when query matches them as a prefix.
    if q:
        upper = q.upper()
        configured = [sym for sym in s.symbols if sym.startswith(upper)]
        for sym in configured:
            if sym not in matches:
                matches.append(sym)
    return {"items": matches[:limit]}


@router.get("/stocks/{symbol}")
def stock_detail(request: Request, symbol: str,
                 bars: int = Query(390, ge=1, le=5000)) -> dict:
    s = _state(request)
    symbol = symbol.upper()
    rows = list(s.db.fetch_prices(symbol, limit=bars))
    if not rows:
        raise HTTPException(404, f"no price history for {symbol}")
    history = [dict(r) for r in reversed(rows)]
    daily = _to_daily(history)
    quote = latest_quote(s.db, symbol)
    news_items = list_recent_news(s.db, limit=20, symbol=symbol)
    candidate_rows = rank_candidates(s.db, [symbol], top_n=1)
    signal_breakdown = candidate_rows[0] if candidate_rows else None
    audit = list_audit_log(s.db, symbol=symbol, limit=20)
    return {
        "symbol": symbol,
        "quote": quote,
        "intraday": history,
        "daily": daily,
        "news": news_items,
        "signal": signal_breakdown,
        "audit_log": audit,
    }


@router.get("/audit-log")
def audit_log(request: Request, symbol: str | None = None,
              limit: int = Query(100, ge=1, le=500)) -> dict:
    s = _state(request)
    return {"items": list_audit_log(s.db, symbol=symbol, limit=limit)}


def _to_daily(bars: List[dict]) -> List[dict]:
    """Aggregate per-day OHLCV from a list of intraday bars (oldest -> newest)."""
    out: dict[str, dict] = {}
    for b in bars:
        day = (b.get("ts") or "")[:10]
        if not day:
            continue
        agg = out.get(day)
        c = b.get("close")
        h = b.get("high") or c
        l = b.get("low") or c
        v = b.get("volume") or 0
        if agg is None:
            out[day] = {
                "date": day,
                "open": b.get("open") or c,
                "high": h, "low": l, "close": c, "volume": v,
            }
        else:
            if h is not None: agg["high"] = max(agg["high"], h)
            if l is not None: agg["low"] = min(agg["low"], l)
            agg["close"] = c if c is not None else agg["close"]
            agg["volume"] = (agg["volume"] or 0) + v
    return list(out.values())


# ---------- WebSocket --------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    app = websocket.app
    manager = app.state.ws_manager
    s = app.state.c5
    await manager.connect(websocket)
    # send a hello + most recent snapshot so the client can paint immediately
    snapshot = s.stream.snapshot() if s.stream else {}
    try:
        await websocket.send_json({
            "type": "hello",
            "paper_mode": s.paper_mode,
            "demo_mode": s.demo_mode,
            "symbols": s.symbols,
            "snapshot": snapshot,
        })
        while True:
            # Treat any client message as a keepalive; we mostly push.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
