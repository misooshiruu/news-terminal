from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

import aiosqlite

from src.models import AnalysisResult, Headline, SCHEMA_SQL

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    @classmethod
    async def create(cls, db_path: str) -> Database:
        db = cls(db_path)
        await db._connect()
        await db._init_schema()
        return db

    async def _connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")

    async def _init_schema(self):
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # --- Deduplication ---

    async def hash_exists(self, content_hash: str) -> bool:
        cursor = await self._db.execute(
            "SELECT 1 FROM headlines WHERE content_hash = ?", (content_hash,)
        )
        return await cursor.fetchone() is not None

    async def is_near_duplicate(self, title: str, minutes: int = 30) -> bool:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await self._db.execute(
            "SELECT title FROM headlines WHERE ingested_at > ? ORDER BY ingested_at DESC LIMIT 200",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        title_lower = title.lower()
        for row in rows:
            if SequenceMatcher(None, title_lower, row["title"].lower()).ratio() > 0.85:
                return True
        return False

    # --- Insert ---

    async def insert_headline(
        self,
        content_hash: str,
        source: str,
        source_category: str,
        title: str,
        description: Optional[str],
        url: Optional[str],
        published_at: Optional[datetime],
        is_market_moving: bool,
        classifier_score: float,
    ) -> Optional[Headline]:
        try:
            cursor = await self._db.execute(
                """INSERT INTO headlines
                   (content_hash, source, source_category, title, description, url,
                    published_at, is_market_moving, classifier_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    content_hash,
                    source,
                    source_category,
                    title,
                    description,
                    url,
                    published_at.isoformat() if published_at else None,
                    is_market_moving,
                    classifier_score,
                ),
            )
            await self._db.commit()
            return await self.get_headline(cursor.lastrowid)
        except aiosqlite.IntegrityError:
            return None  # Duplicate hash

    # --- Update analysis ---

    async def update_analysis(self, headline_id: int, result: AnalysisResult):
        await self._db.execute(
            """UPDATE headlines SET
               sentiment = ?, impact_score = ?, categories = ?, tickers = ?,
               asset_classes = ?, analysis_summary = ?, analyzed_at = ?, is_analyzed = 1
               WHERE id = ?""",
            (
                result.sentiment,
                result.impact_score,
                json.dumps(result.categories),
                json.dumps(result.tickers),
                json.dumps(result.asset_classes),
                result.summary,
                datetime.utcnow().isoformat(),
                headline_id,
            ),
        )
        await self._db.commit()

    # --- Queries ---

    async def get_headline(self, headline_id: int) -> Optional[Headline]:
        cursor = await self._db.execute(
            "SELECT * FROM headlines WHERE id = ?", (headline_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_headline(row) if row else None

    async def get_headlines(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        ticker: Optional[str] = None,
        min_impact: Optional[int] = None,
        source_category: Optional[str] = None,
    ) -> list[dict]:
        query = "SELECT * FROM headlines WHERE 1=1"
        params: list = []

        if category:
            query += " AND categories LIKE ?"
            params.append(f'%"{category}"%')
        if sentiment:
            query += " AND sentiment = ?"
            params.append(sentiment)
        if ticker:
            query += " AND tickers LIKE ?"
            params.append(f'%"{ticker}"%')
        if min_impact:
            query += " AND impact_score >= ?"
            params.append(min_impact)
        if source_category:
            query += " AND source_category = ?"
            params.append(source_category)

        query += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_headline(r).to_ws_dict() for r in rows]

    async def get_source_states(self) -> list[dict]:
        cursor = await self._db.execute("SELECT * FROM source_state")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_source_state(
        self, source_name: str, last_seen_id: Optional[str] = None, healthy: bool = True
    ):
        await self._db.execute(
            """INSERT INTO source_state (source_name, last_seen_id, last_poll_at, is_healthy, error_count)
               VALUES (?, ?, ?, ?, 0)
               ON CONFLICT(source_name) DO UPDATE SET
               last_seen_id = COALESCE(?, last_seen_id),
               last_poll_at = ?,
               is_healthy = ?,
               error_count = CASE WHEN ? THEN 0 ELSE error_count + 1 END""",
            (
                source_name,
                last_seen_id,
                datetime.utcnow().isoformat(),
                healthy,
                last_seen_id,
                datetime.utcnow().isoformat(),
                healthy,
                healthy,
            ),
        )
        await self._db.commit()

    async def get_today_stats(self) -> dict:
        today = datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
        cursor = await self._db.execute(
            "SELECT COUNT(*) as total, COALESCE(SUM(is_analyzed), 0) as analyzed FROM headlines WHERE ingested_at >= ?",
            (today,),
        )
        row = await cursor.fetchone()
        return {"total": row["total"] or 0, "analyzed": int(row["analyzed"] or 0)}

    # --- Helpers ---

    @staticmethod
    def _row_to_headline(row) -> Headline:
        return Headline(
            id=row["id"],
            content_hash=row["content_hash"],
            source=row["source"],
            source_category=row["source_category"] or "",
            title=row["title"],
            description=row["description"],
            url=row["url"],
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            ingested_at=datetime.fromisoformat(row["ingested_at"]) if row["ingested_at"] else None,
            sentiment=row["sentiment"],
            impact_score=row["impact_score"],
            categories=json.loads(row["categories"]) if row["categories"] else [],
            tickers=json.loads(row["tickers"]) if row["tickers"] else [],
            asset_classes=json.loads(row["asset_classes"]) if row["asset_classes"] else [],
            analysis_summary=row["analysis_summary"],
            analyzed_at=datetime.fromisoformat(row["analyzed_at"]) if row["analyzed_at"] else None,
            is_analyzed=bool(row["is_analyzed"]),
            is_market_moving=bool(row["is_market_moving"]),
            classifier_score=row["classifier_score"] or 0.0,
        )
