"""Mock C5 confluence-engine stub.

The confluence score is a transparent 10–99 confluence reading (NOT a
statistical probability). The draft returns a simulated value.
"""
from __future__ import annotations

import random


def get_confluence(ticker: str) -> int:
    """Return a simulated confluence score (10–99) for a ticker.

    # TODO: connect to the C5 database/engine — the real source of the live
    #        chart reading and the 10–99 confluence score.
    """
    return random.randint(10, 99)
