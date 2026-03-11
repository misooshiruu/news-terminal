from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import aiohttp
import feedparser
from dateutil import parser as dateparser

from src.models import RawHeadline
from src.sources.base import BaseSource

logger = logging.getLogger(__name__)


class RSSSource(BaseSource):
    def __init__(self, name: str, url: str, category: str = "General", poll_interval: int = 60):
        super().__init__(name=name, poll_interval=poll_interval)
        self.url = url
        self.category = category
        self._seen_ids: set[str] = set()
        self._max_seen = 500  # Rolling window

    async def fetch(self) -> list[RawHeadline]:
        headlines: list[RawHeadline] = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "MarketTerminal/1.0"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"RSS '{self.name}' returned status {resp.status}")
                        return []
                    text = await resp.text()
        except Exception as e:
            logger.warning(f"RSS '{self.name}' request failed: {e}")
            return []

        feed = feedparser.parse(text)

        for entry in feed.entries:
            entry_id = self._get_entry_id(entry)
            if entry_id in self._seen_ids:
                continue

            self._seen_ids.add(entry_id)

            # Parse published date
            published = self._parse_date(entry)

            title = (entry.get("title") or "").strip()
            if not title:
                continue

            description = (entry.get("summary") or entry.get("description") or "").strip()
            # Strip HTML tags from description
            if description:
                import re
                description = re.sub(r"<[^>]+>", "", description).strip()
                if len(description) > 500:
                    description = description[:500] + "..."

            url = entry.get("link") or entry.get("id") or ""

            headlines.append(RawHeadline(
                source=f"rss_{self.name}",
                source_category="rss",
                title=title,
                description=description if description else None,
                url=url if url else None,
                published_at=published,
            ))

        # Trim seen IDs set
        if len(self._seen_ids) > self._max_seen:
            excess = len(self._seen_ids) - self._max_seen
            # Remove oldest (arbitrary since it's a set, but prevents unbounded growth)
            for _ in range(excess):
                self._seen_ids.pop()

        return headlines

    @staticmethod
    def _get_entry_id(entry) -> str:
        return entry.get("id") or entry.get("link") or entry.get("title", "")

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for field in ("published", "updated", "created"):
            val = entry.get(field)
            if val:
                try:
                    return dateparser.parse(val)
                except (ValueError, TypeError):
                    continue
        # feedparser also provides *_parsed as time tuples
        for field in ("published_parsed", "updated_parsed"):
            val = entry.get(field)
            if val:
                try:
                    return datetime(*val[:6])
                except (ValueError, TypeError):
                    continue
        return None
