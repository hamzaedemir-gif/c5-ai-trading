"""CLI entry point: ingest -> evaluate signals -> risk-gate (paper mode only).

Usage:
    python run_paper.py ingest AAPL MSFT
    python run_paper.py signals AAPL
    python run_paper.py backtest AAPL

In paper mode no orders are ever sent to a brokerage; the decision is
logged in SQLite. Live mode requires C5_TRADING_MODE=live AND explicit
opt-in in this script (intentionally not wired up here).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import List

from config import load_config
from data import Database, Ingestor
from signals import SignalEngine


def cmd_ingest(cfg, symbols: List[str]) -> int:
    with Database(cfg.db_path) as db:
        ing = Ingestor(db, finnhub_key=cfg.finnhub_api_key,
                       stocktwits_url=cfg.stocktwits_base_url)
        results = ing.ingest_all(symbols)
        for sym, r in results.items():
            print(f"{sym}: prices+{r.prices} earnings+{r.earnings} "
                  f"news+{r.news} sentiment+{r.sentiment}")
    return 0


def cmd_signals(cfg, symbols: List[str]) -> int:
    with Database(cfg.db_path) as db:
        engine = SignalEngine(db, persist=True)
        for sym in symbols:
            sigs = engine.evaluate(sym)
            agg = engine.aggregate(sigs)
            print(f"\n=== {sym} ===")
            for s in sigs:
                print(f"  {s.signal_type:18s} conf={s.confidence:.2f} "
                      f"dir={s.direction}")
            print(f"  AGGREGATE         conf={agg.confidence:.2f} "
                  f"dir={agg.direction}")
    return 0


def cmd_backtest(cfg, symbols: List[str]) -> int:
    from backtest import Backtester

    with Database(cfg.db_path) as db:
        for sym in symbols:
            rows = list(db.fetch_prices(sym, limit=5000))
            bars = [dict(r) for r in reversed(rows)]
            if not bars:
                print(f"{sym}: no price history -- run `ingest` first")
                continue
            bt = Backtester(
                starting_capital=cfg.starting_capital,
                position_pct=cfg.position_pct,
                stop_loss_pct=cfg.stop_loss_pct,
                daily_max_loss_pct=cfg.daily_max_loss_pct,
            )
            res = bt.run(sym, bars)
            print(f"\n=== {sym} backtest ===")
            print(json.dumps(res.metrics.as_dict(), indent=2, default=str))
    return 0


def main(argv: List[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("ingest", "signals", "backtest"):
        sp = sub.add_parser(name)
        sp.add_argument("symbols", nargs="+")

    args = parser.parse_args(argv)
    cfg = load_config()

    if cfg.trading_mode.lower() == "live":
        print("REFUSING TO RUN: C5_TRADING_MODE=live. This script is paper-only.",
              file=sys.stderr)
        print("Set C5_TRADING_MODE=paper or unset it.", file=sys.stderr)
        return 2

    if args.cmd == "ingest":
        return cmd_ingest(cfg, args.symbols)
    if args.cmd == "signals":
        return cmd_signals(cfg, args.symbols)
    if args.cmd == "backtest":
        return cmd_backtest(cfg, args.symbols)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
