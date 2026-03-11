from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

import yaml

from config.settings import Settings
from src.database import Database
from src.delivery.websocket_manager import WebSocketManager
from src.models import RawHeadline
from src.sources.rss_source import RSSSource

logger = logging.getLogger(__name__)


class SourceManager:
    """Loads source configs and spawns polling tasks."""

    def __init__(self, settings: Settings, ingestion_queue: asyncio.Queue):
        self.settings = settings
        self.ingestion_queue = ingestion_queue
        self.sources: list = []
        self.tasks: list[asyncio.Task] = []

    async def run(self):
        """Load configs and start all source polling loops."""
        self._load_rss_sources()
        logger.info(f"Loaded {len(self.sources)} sources")

        for source in self.sources:
            task = asyncio.create_task(source.poll_loop(self.ingestion_queue))
            self.tasks.append(task)

        # Wait for all tasks (they run forever until cancelled)
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            pass

    def _load_rss_sources(self):
        try:
            with open(self.settings.feeds_config, "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Feeds config not found: {self.settings.feeds_config}")
            return

        for feed in config.get("rss_feeds", []):
            source = RSSSource(
                name=feed["name"],
                url=feed["url"],
                category=feed.get("category", "General"),
                poll_interval=feed.get("poll_interval", self.settings.rss_default_poll_interval),
            )
            self.sources.append(source)
            logger.info(f"  RSS source: {feed['name']} ({feed['url'][:60]}...)")


async def ingestion_consumer(
    ingestion_queue: asyncio.Queue,
    analysis_queue: asyncio.Queue,
    db: Database,
    ws_manager: WebSocketManager,
    settings: Settings,
):
    """Consume raw headlines: deduplicate, classify, store, and broadcast."""
    # Lazy import to avoid circular deps
    try:
        from src.analysis.classifier import is_market_moving
    except ImportError:
        def is_market_moving(title, desc=""):
            return False, 0.0

    logger.info("Ingestion consumer started")

    while True:
        try:
            raw: RawHeadline = await ingestion_queue.get()

            # Compute content hash
            content_hash = hashlib.sha256(
                f"{raw.source}:{raw.title}".encode()
            ).hexdigest()

            # Check exact duplicate
            if await db.hash_exists(content_hash):
                continue

            # Check near-duplicate
            if await db.is_near_duplicate(raw.title, minutes=30):
                continue

            # Classify
            market_moving, score = is_market_moving(raw.title, raw.description or "")

            # Store
            headline = await db.insert_headline(
                content_hash=content_hash,
                source=raw.source,
                source_category=raw.source_category,
                title=raw.title,
                description=raw.description,
                url=raw.url,
                published_at=raw.published_at,
                is_market_moving=market_moving,
                classifier_score=score,
            )

            if headline is None:
                continue  # Insert failed (race condition duplicate)

            # Broadcast to WebSocket clients immediately
            await ws_manager.broadcast(headline.to_ws_dict())

            # Queue for analysis if market-moving
            if market_moving and settings.analysis_enabled:
                await analysis_queue.put(headline)

            logger.debug(f"Ingested: [{raw.source}] {raw.title[:80]}")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ingestion consumer error: {e}", exc_info=True)
