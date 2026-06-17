"""Tests for the ticker universe and rotating scanner."""
from c5.universe import BUILTIN_UNIVERSE, _filter_symbols, rotate_chunk


def test_filter_keeps_common_stock_only():
    raw = [
        {"symbol": "AAPL", "type": "Common Stock"},
        {"symbol": "BRK.A", "type": "Common Stock"},   # has a dot -> rejected
        {"symbol": "SPY", "type": "ETP"},               # not common stock -> rejected
        {"symbol": "NVDA", "type": "Common Stock"},
        {"symbol": "TOOLONG", "type": "Common Stock"},  # >5 chars -> rejected
        {"symbol": "AAPL", "type": "Common Stock"},      # duplicate -> deduped
        {"symbol": "", "type": "Common Stock"},          # empty -> rejected
    ]
    out = _filter_symbols(raw)
    assert out == ["AAPL", "NVDA"]


def test_filter_handles_missing_type():
    # Some payloads omit type; a valid plain symbol should still pass.
    out = _filter_symbols([{"symbol": "MSFT"}])
    assert out == ["MSFT"]


def test_builtin_universe_nonempty_and_clean():
    assert len(BUILTIN_UNIVERSE) > 100
    assert "AAPL" in BUILTIN_UNIVERSE and "SPY" in BUILTIN_UNIVERSE


def test_rotate_chunk_basic():
    uni = ["A", "B", "C", "D", "E"]
    chunk, cur = rotate_chunk(uni, 0, 2)
    assert chunk == ["A", "B"] and cur == 2
    chunk, cur = rotate_chunk(uni, cur, 2)
    assert chunk == ["C", "D"] and cur == 4


def test_rotate_chunk_wraps_around():
    uni = ["A", "B", "C", "D", "E"]
    chunk, cur = rotate_chunk(uni, 4, 3)   # wraps E -> A, B
    assert chunk == ["E", "A", "B"] and cur == 2


def test_rotate_chunk_full_sweep_covers_everything():
    uni = [f"S{i}" for i in range(23)]
    seen = set()
    cur = 0
    for _ in range(23):          # enough cycles of size 5 to cover all
        chunk, cur = rotate_chunk(uni, cur, 5)
        seen.update(chunk)
    assert seen == set(uni)


def test_rotate_chunk_empty():
    assert rotate_chunk([], 0, 5) == ([], 0)
