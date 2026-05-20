"""Demo-mode seed data + simulated live ticker.

Lets the dashboard run with zero API keys. See `demo.seed.seed_database`
and `demo.ticker.SimulatedTicker`.
"""
from .seed import DEMO_SYMBOLS, seed_database
from .ticker import SimulatedTicker

__all__ = ["DEMO_SYMBOLS", "seed_database", "SimulatedTicker"]
