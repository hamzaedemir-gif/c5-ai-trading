"""Mock broker/data-source connection stubs."""
from __future__ import annotations


def connect_tradingview() -> bool:
    """Mock TradingView connect.

    # TODO: real TradingView connect / execution path (NOT a C5 data source).
    """
    return True


def connect_webull() -> bool:
    """Mock Webull connect.

    # TODO: connect Webull OpenAPI — primary read-only market data and (later)
    #        order execution. Real auth + token handling goes here.
    """
    return True
