"""Mock order-execution stub.

NO real orders are ever placed. These return simulated fills so the trading
loop can demonstrate opening and closing positions.
"""
from __future__ import annotations

from typing import Dict

_ORDER_SEQ = 0


def place_order(ticker: str, qty: float, price: float, mode: str) -> Dict[str, object]:
    """Mock order placement (paper or live) — returns a simulated fill.

    # TODO: real execution via the broker (Webull). Keep LIVE execution behind
    #        an explicit confirmation step; default to paper.
    """
    global _ORDER_SEQ
    _ORDER_SEQ += 1
    return {"order_id": _ORDER_SEQ, "status": "filled",
            "ticker": ticker, "qty": qty, "price": price, "mode": mode}


def close_order(order_id: int, price: float, mode: str) -> Dict[str, object]:
    """Mock order close — returns a simulated fill.

    # TODO: real close/flatten via the broker.
    """
    return {"order_id": order_id, "status": "closed", "price": price, "mode": mode}
