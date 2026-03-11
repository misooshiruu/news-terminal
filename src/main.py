from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from src.database import Database
from src.delivery.routes import router
from src.delivery.websocket_manager import WebSocketManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()

    # Ensure data directory exists
    os.makedirs(os.path.dirname(settings.db_path) or "data", exist_ok=True)

    # Initialize database
    db = await Database.create(settings.db_path)
    app.state.db = db
    app.state.settings = settings

    # WebSocket manager
    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager

    # Ingestion queue (sources put headlines here)
    ingestion_queue = asyncio.Queue()
    app.state.ingestion_queue = ingestion_queue

    # Analysis queue (headlines needing Claude analysis go here)
    analysis_queue = asyncio.Queue()
    app.state.analysis_queue = analysis_queue

    # Background tasks list (so we can cancel on shutdown)
    tasks: list[asyncio.Task] = []

    # Import and start source manager (Milestone 2 will populate this)
    try:
        from src.sources.source_manager import SourceManager
        source_manager = SourceManager(settings, ingestion_queue)
        tasks.append(asyncio.create_task(source_manager.run()))
        logger.info("Source manager started")
    except ImportError:
        logger.warning("Source manager not yet implemented, skipping")

    # Import and start ingestion consumer (Milestone 2)
    try:
        from src.sources.source_manager import ingestion_consumer
        tasks.append(asyncio.create_task(
            ingestion_consumer(ingestion_queue, analysis_queue, db, ws_manager, settings)
        ))
        logger.info("Ingestion consumer started")
    except ImportError:
        logger.warning("Ingestion consumer not yet implemented, skipping")

    # Market context provider (fetches live SPY, VIX, etc. from Finnhub)
    market_context = None
    if settings.market_context_enabled and settings.finnhub_api_key:
        try:
            from src.market_data.market_context import MarketContextProvider
            market_context = MarketContextProvider(settings)
            await market_context.start()
            tasks.append(asyncio.create_task(market_context.run()))
            app.state.market_context = market_context
            logger.info("Market context provider started")
        except ImportError:
            logger.warning("Market context provider not available, skipping")

    # Move tracker (records post-headline market moves for calibration)
    move_tracker = None
    if settings.move_tracking_enabled and settings.finnhub_api_key:
        try:
            from src.market_data.move_tracker import MoveTracker
            move_tracker = MoveTracker(settings, db, market_context)
            tasks.append(asyncio.create_task(move_tracker.run()))
            app.state.move_tracker = move_tracker
            logger.info("Move tracker started")
        except ImportError:
            logger.warning("Move tracker not available, skipping")

    # Import and start analysis consumer (Milestone 4)
    if settings.analysis_enabled and settings.anthropic_api_key:
        try:
            from src.analysis.analysis_queue import AnalysisConsumer
            analysis_consumer = AnalysisConsumer(
                settings, db, ws_manager,
                market_context=market_context,
            )
            tasks.append(asyncio.create_task(
                analysis_consumer.run(analysis_queue)
            ))
            logger.info("Analysis consumer started")
        except ImportError:
            logger.warning("Analysis consumer not yet implemented, skipping")

    logger.info(f"Market Terminal started on http://{settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if market_context:
        await market_context.stop()
    await db.close()
    logger.info("Shutdown complete")


app = FastAPI(title="Market News Terminal", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory="frontend"), name="static")
