"""FastAPI application factory.

Composes the existing data / signals / risk modules behind a REST + WS API.
Defaults to paper-mode and refuses to start if C5_TRADING_MODE=live.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import load_config
from core import BackgroundScheduler
from data import Ingestor
from data.alpaca_stream import AlpacaStream
from data.db import Database

from .paper_portfolio import PaperPortfolioService
from .routes import router
from .state import AppState
from .ws_manager import WebSocketManager

log = logging.getLogger(__name__)


def create_app(*, db: Database | None = None,
               stream: AlpacaStream | None = None,
               symbols: list[str] | None = None,
               enable_stream: bool = True) -> FastAPI:
    """Build a FastAPI app.

    `db`, `stream`, `symbols` may be injected for tests.
    `enable_stream=False` skips connecting to Alpaca even if keys are set.
    """
    cfg = load_config()
    if cfg.trading_mode.lower() == "live":
        raise RuntimeError(
            "C5_TRADING_MODE=live -- the dashboard backend is paper-only. "
            "Unset C5_TRADING_MODE or set it to 'paper'."
        )

    if db is None:
        db = Database(cfg.db_path)
    if symbols is None:
        symbols = cfg.symbol_list()

    if stream is None and enable_stream and cfg.alpaca_api_key and cfg.alpaca_api_secret:
        stream = AlpacaStream(
            api_key=cfg.alpaca_api_key,
            api_secret=cfg.alpaca_api_secret,
            stream_url=cfg.alpaca_stream_url,
            symbols=symbols,
            db=db,
        )

    paper = PaperPortfolioService(
        db,
        starting_capital=cfg.starting_capital,
        position_pct=cfg.position_pct,
        stop_loss_pct=cfg.stop_loss_pct,
        daily_max_loss_pct=cfg.daily_max_loss_pct,
    )
    state = AppState(db=db, symbols=symbols, stream=stream, paper_mode=True,
                     paper=paper)
    ws_manager = WebSocketManager()

    scheduler = BackgroundScheduler()
    ingestor = Ingestor(db, finnhub_key=cfg.finnhub_api_key,
                        stocktwits_url=cfg.stocktwits_base_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stream_task: asyncio.Task | None = None
        if state.stream is not None:
            async def _broadcaster(event: dict) -> None:
                state.add_event(event)
                # Live tick invalidates short-TTL caches so the next request
                # sees fresh data instead of an 8s-stale snapshot.
                state.cache.invalidate()
                await ws_manager.broadcast(event)

            state.stream.add_listener(_broadcaster)
            stream_task = asyncio.create_task(state.stream.run(),
                                              name="alpaca-stream")
            log.info("Alpaca stream task started")
        else:
            log.warning(
                "No Alpaca stream attached -- set ALPACA_API_KEY/SECRET for "
                "real-time data. REST endpoints still work against SQLite history."
            )

        # Periodic refresh jobs. We run them off the request path so the UI
        # never waits on a slow data provider.
        def _async_blocking(fn, *fargs, **fkwargs):
            async def runner():
                await asyncio.to_thread(fn, *fargs, **fkwargs)
            return runner

        async def refresh_news_and_earnings():
            for sym in state.symbols:
                await asyncio.to_thread(ingestor.ingest_news, sym)
                await asyncio.to_thread(ingestor.ingest_earnings, sym)
                await asyncio.to_thread(ingestor.ingest_sentiment, sym)
            state.cache.invalidate()

        async def refresh_price_backfill():
            # yfinance backfill catches anything Alpaca missed.
            for sym in state.symbols:
                await asyncio.to_thread(ingestor.ingest_prices, sym, "1d", "1m")
            state.cache.invalidate()

        async def refresh_stops():
            if state.paper is not None:
                await asyncio.to_thread(state.paper.apply_stops, state.marks())

        scheduler.add("news_earnings_sentiment", refresh_news_and_earnings,
                      interval_s=300)
        scheduler.add("price_backfill", refresh_price_backfill,
                      interval_s=120, enabled=not state.demo_mode)
        scheduler.add("stop_check", refresh_stops, interval_s=10)
        scheduler.start()
        log.info("Background scheduler started: %d jobs", len(scheduler._jobs))

        try:
            yield
        finally:
            await scheduler.stop()
            if state.stream is not None:
                state.stream.stop()
            if stream_task is not None:
                stream_task.cancel()
                try:
                    await stream_task
                except (asyncio.CancelledError, Exception):
                    pass

    app = FastAPI(title="C5 AI Trading Dashboard", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list() or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.c5 = state
    app.state.ws_manager = ws_manager
    app.include_router(router)
    return app


def main() -> None:
    import uvicorn

    cfg = load_config()
    uvicorn.run("api.app:create_app", host=cfg.api_host, port=cfg.api_port,
                factory=True, reload=False)


if __name__ == "__main__":
    main()
