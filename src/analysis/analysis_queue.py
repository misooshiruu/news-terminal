from __future__ import annotations

import asyncio
import logging
import time

import anthropic

from config.settings import Settings
from src.analysis.claude_analyzer import analyze_headline
from src.database import Database
from src.delivery.websocket_manager import WebSocketManager
from src.models import Headline

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple async rate limiter: max N calls per period (seconds)."""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            self.calls = [t for t in self.calls if now - t < self.period]
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            self.calls.append(time.monotonic())


class AnalysisConsumer:
    """Reads headlines from the analysis queue and processes them with Claude."""

    def __init__(self, settings: Settings, db: Database, ws_manager: WebSocketManager):
        self.settings = settings
        self.db = db
        self.ws_manager = ws_manager
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = RateLimiter(
            max_calls=settings.analysis_rate_limit,
            period=60.0,
        )
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_analyses)

    async def run(self, queue: asyncio.Queue):
        """Main consumer loop."""
        logger.info(
            f"Analysis consumer started (model={self.settings.claude_model}, "
            f"rate_limit={self.settings.analysis_rate_limit}/min)"
        )

        while True:
            try:
                headline: Headline = await queue.get()
                asyncio.create_task(self._process(headline))
                queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Analysis consumer error: {e}", exc_info=True)

    async def _process(self, headline: Headline):
        """Analyze a single headline with rate limiting and concurrency control."""
        async with self.semaphore:
            await self.rate_limiter.acquire()

            try:
                result = await analyze_headline(
                    client=self.client,
                    model=self.settings.claude_model,
                    source=headline.source,
                    title=headline.title,
                    description=headline.description,
                )

                # Update database
                await self.db.update_analysis(headline.id, result)

                # Broadcast analysis update to WebSocket clients
                await self.ws_manager.broadcast_analysis_update(
                    headline.id,
                    {
                        "sentiment": result.sentiment,
                        "impact_score": result.impact_score,
                        "categories": result.categories,
                        "tickers": result.tickers,
                        "asset_classes": result.asset_classes,
                        "summary": result.summary,
                    },
                )

                logger.info(
                    f"Analyzed [{result.sentiment}/{result.impact_score}]: "
                    f"{headline.title[:60]}"
                )

            except Exception as e:
                logger.error(f"Failed to analyze headline {headline.id}: {e}")
