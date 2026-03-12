from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

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

    def __init__(
        self,
        settings: Settings,
        db: Database,
        ws_manager: WebSocketManager,
        market_context=None,
    ):
        self.settings = settings
        self.db = db
        self.ws_manager = ws_manager
        self.market_context = market_context
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = RateLimiter(
            max_calls=settings.analysis_rate_limit,
            period=60.0,
        )
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_analyses)
        # Cache to avoid duplicate snapshot inserts within the same refresh window
        self._last_snapshot_id: Optional[int] = None
        self._last_snapshot_ts: Optional[str] = None

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
                # Get market context for prompt injection
                context_str = ""
                if self.market_context:
                    context_str = self.market_context.format_for_prompt()

                result = await analyze_headline(
                    client=self.client,
                    model=self.settings.claude_model,
                    source=headline.source,
                    title=headline.title,
                    description=headline.description,
                    market_context=context_str,
                )

                # Update database with analysis result
                await self.db.update_analysis(headline.id, result)

                # Save market snapshot and link to headline
                snapshot_id = await self._save_snapshot(headline.id)

                # Record move tracking baseline (T+0)
                if self.settings.move_tracking_enabled:
                    await self._record_move_baseline(headline.id, snapshot_id)

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
                        "signals": [s.model_dump() for s in result.signals],
                    },
                )

                logger.info(
                    f"Analyzed [{result.sentiment}/{result.impact_score}]: "
                    f"{headline.title[:60]}"
                )

            except Exception as e:
                logger.error(f"Failed to analyze headline {headline.id}: {e}")

    async def _save_snapshot(self, headline_id: int) -> Optional[int]:
        """Save market snapshot and link it to the headline. Reuses cached ID if unchanged."""
        if not self.market_context:
            return None

        snapshot = self.market_context.get_snapshot()
        if not snapshot:
            return None

        snapshot_dict = snapshot.to_dict()
        snapshot_ts = snapshot_dict.get("timestamp")

        # Reuse cached snapshot ID if it's the same refresh cycle
        if self._last_snapshot_ts == snapshot_ts and self._last_snapshot_id:
            snapshot_id = self._last_snapshot_id
        else:
            snapshot_id = await self.db.insert_market_snapshot(snapshot_dict)
            self._last_snapshot_id = snapshot_id
            self._last_snapshot_ts = snapshot_ts

        await self.db.link_headline_snapshot(headline_id, snapshot_id)
        return snapshot_id

    async def _record_move_baseline(self, headline_id: int, snapshot_id: Optional[int]):
        """Record T+0 SPY/VIX prices for post-headline move tracking."""
        try:
            spy_t0 = None
            vix_t0 = None
            if self.market_context:
                snap = self.market_context.get_snapshot()
                if snap:
                    spy_t0 = snap.spy_price
                    vix_t0 = snap.vix_price

            await self.db.insert_move_baseline(
                headline_id=headline_id,
                snapshot_id=snapshot_id,
                analyzed_at=datetime.utcnow().isoformat(),
                spy_t0=spy_t0,
                vix_t0=vix_t0,
            )
        except Exception as e:
            logger.debug(f"Failed to record move baseline for headline {headline_id}: {e}")
