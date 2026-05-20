"""Signal engine: turns raw data into scored, audited signals."""
from .base import Signal
from .engine import SignalEngine
from .volume import volume_spike_signal
from .earnings import earnings_surprise_signal
from .sentiment import sentiment_shift_signal

__all__ = [
    "Signal", "SignalEngine",
    "volume_spike_signal", "earnings_surprise_signal", "sentiment_shift_signal",
]
