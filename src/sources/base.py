from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from src.models import RawHeadline

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    def __init__(self, name: str, poll_interval: int = 60):
        self.name = name
        self.poll_interval = poll_interval

    @abstractmethod
    async def fetch(self) -> list[RawHeadline]:
        """Fetch new headlines from this source."""
        ...

    async def poll_loop(self, output_queue: asyncio.Queue):
        """Run the polling loop, putting results onto the queue."""
        logger.info(f"Source '{self.name}' polling every {self.poll_interval}s")
        while True:
            try:
                headlines = await self.fetch()
                for h in headlines:
                    await output_queue.put(h)
                if headlines:
                    logger.debug(f"Source '{self.name}' fetched {len(headlines)} headlines")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Source '{self.name}' fetch error: {e}")
            await asyncio.sleep(self.poll_interval)
