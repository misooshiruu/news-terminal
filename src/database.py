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
        await self._run_migrations()

    async def _run_migrations(self):
        """Run schema migrations for new columns on existing databases."""
        migrations = [
            "ALTER TABLE headlines ADD COLUMN market_context_snapshot_id INTEGER",
            "ALTER TABLE headlines ADD COLUMN signals TEXT",
        ]
        for sql in migrations:
            try:
                await self._db.execute(sql)
                await self._db.commit()
            except Exception:
                pass  # Column already exists

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
        # Derive tickers from signals if signals are present
        tickers = result.tickers
        if result.signals and not tickers:
            tickers = [s.ticker for s in result.signals]

        signals_json = (
            json.dumps([s.model_dump() for s in result.signals])
            if result.signals else None
        )

        await self._db.execute(
            """UPDATE headlines SET
               sentiment = ?, impact_score = ?, categories = ?, tickers = ?,
               asset_classes = ?, signals = ?, analysis_summary = ?,
               analyzed_at = ?, is_analyzed = 1
               WHERE id = ?""",
            (
                result.sentiment,
                result.impact_score,
                json.dumps(result.categories),
                json.dumps(tickers),
                json.dumps(result.asset_classes),
                signals_json,
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

    # --- Market Snapshots ---

    async def insert_market_snapshot(self, snapshot_dict: dict) -> int:
        """Insert a market snapshot and return its ID."""
        cursor = await self._db.execute(
            """INSERT INTO market_snapshots
               (captured_at, spy_price, spy_change_pct, vix_price, dxy_price,
                btc_price, gold_price, oil_price, market_status, upcoming_events)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_dict.get("timestamp", datetime.utcnow().isoformat()),
                snapshot_dict.get("spy_price"),
                snapshot_dict.get("spy_change_pct"),
                snapshot_dict.get("vix_price"),
                snapshot_dict.get("dxy_price"),
                snapshot_dict.get("btc_price"),
                snapshot_dict.get("gold_price"),
                snapshot_dict.get("oil_price"),
                snapshot_dict.get("market_status"),
                json.dumps(snapshot_dict.get("upcoming_events", [])),
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def link_headline_snapshot(self, headline_id: int, snapshot_id: int):
        """Associate a headline with the market snapshot used during its analysis."""
        await self._db.execute(
            "UPDATE headlines SET market_context_snapshot_id = ? WHERE id = ?",
            (snapshot_id, headline_id),
        )
        await self._db.commit()

    # --- Move Tracking ---

    async def insert_move_baseline(
        self, headline_id: int, snapshot_id: Optional[int],
        analyzed_at: str, spy_t0: Optional[float], vix_t0: Optional[float],
    ):
        """Insert the T+0 baseline for market move tracking."""
        await self._db.execute(
            """INSERT INTO headline_market_moves
               (headline_id, snapshot_id, analyzed_at, price_spy_t0, price_vix_t0)
               VALUES (?, ?, ?, ?, ?)""",
            (headline_id, snapshot_id, analyzed_at, spy_t0, vix_t0),
        )
        await self._db.commit()

    async def get_pending_move_checks(self) -> list[dict]:
        """Get headlines that need move tracking updates."""
        cursor = await self._db.execute(
            """SELECT m.id, m.headline_id, m.analyzed_at,
                      m.price_spy_t0, m.price_vix_t0,
                      m.checked_t5_at, m.checked_t15_at, m.checked_t60_at,
                      h.impact_score, h.sentiment
               FROM headline_market_moves m
               JOIN headlines h ON h.id = m.headline_id
               WHERE m.is_complete = 0
               ORDER BY m.analyzed_at ASC
               LIMIT 50"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_move_checkpoint(
        self, move_id: int, checkpoint: str,
        spy_price: Optional[float], vix_price: Optional[float],
    ):
        """Update a specific checkpoint (t5, t15, t60) for a move record."""
        spy_col = f"price_spy_{checkpoint}"
        vix_col = f"price_vix_{checkpoint}"
        checked_col = f"checked_{checkpoint}_at"
        await self._db.execute(
            f"""UPDATE headline_market_moves
                SET {spy_col} = ?, {vix_col} = ?, {checked_col} = ?
                WHERE id = ?""",
            (spy_price, vix_price, datetime.utcnow().isoformat(), move_id),
        )
        # Check if all checkpoints are now filled
        await self._db.execute(
            """UPDATE headline_market_moves SET is_complete = 1
               WHERE id = ? AND checked_t5_at IS NOT NULL
               AND checked_t15_at IS NOT NULL AND checked_t60_at IS NOT NULL""",
            (move_id,),
        )
        await self._db.commit()

    # --- Calibration Queries ---

    async def get_calibration_by_impact(self) -> list[dict]:
        """Aggregate market moves by impact score for calibration view."""
        cursor = await self._db.execute(
            """SELECT
                 h.impact_score,
                 COUNT(*) as sample_count,
                 AVG(ABS(m.price_spy_t5 - m.price_spy_t0) / NULLIF(m.price_spy_t0, 0) * 100) as avg_spy_move_t5_pct,
                 AVG(ABS(m.price_spy_t15 - m.price_spy_t0) / NULLIF(m.price_spy_t0, 0) * 100) as avg_spy_move_t15_pct,
                 AVG(ABS(m.price_spy_t60 - m.price_spy_t0) / NULLIF(m.price_spy_t0, 0) * 100) as avg_spy_move_t60_pct,
                 AVG(ABS(m.price_vix_t60 - m.price_vix_t0)) as avg_vix_move_t60
               FROM headline_market_moves m
               JOIN headlines h ON h.id = m.headline_id
               WHERE m.price_spy_t0 IS NOT NULL AND m.is_complete = 1
               GROUP BY h.impact_score
               ORDER BY h.impact_score"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_calibration_by_sentiment(self) -> list[dict]:
        """Check if sentiment predictions match actual market direction."""
        cursor = await self._db.execute(
            """SELECT
                 h.sentiment,
                 COUNT(*) as sample_count,
                 SUM(CASE WHEN h.sentiment = 'bullish' AND m.price_spy_t60 > m.price_spy_t0 THEN 1
                          WHEN h.sentiment = 'bearish' AND m.price_spy_t60 < m.price_spy_t0 THEN 1
                          ELSE 0 END) as correct_direction,
                 AVG((m.price_spy_t60 - m.price_spy_t0) / NULLIF(m.price_spy_t0, 0) * 100) as avg_spy_return_pct
               FROM headline_market_moves m
               JOIN headlines h ON h.id = m.headline_id
               WHERE m.price_spy_t0 IS NOT NULL AND m.is_complete = 1
                 AND h.sentiment IS NOT NULL
               GROUP BY h.sentiment"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_calibration_by_signals(self) -> list[dict]:
        """Check directional signal accuracy for verifiable tickers (SPY/VIX).

        Uses json_each() to unpack the signals JSON array stored in each
        headline row.  Only signals referencing SPY-family or VIX-family
        tickers are included because those are the assets we actually track
        prices for in headline_market_moves.
        """
        cursor = await self._db.execute(
            """SELECT
                 json_extract(j.value, '$.ticker') as ticker,
                 COUNT(*) as sample_count,
                 SUM(CASE
                     WHEN json_extract(j.value, '$.ticker') IN ('SPY','SPX','QQQ')
                          AND json_extract(j.value, '$.direction') = 'up'
                          AND m.price_spy_t60 > m.price_spy_t0 THEN 1
                     WHEN json_extract(j.value, '$.ticker') IN ('SPY','SPX','QQQ')
                          AND json_extract(j.value, '$.direction') = 'down'
                          AND m.price_spy_t60 < m.price_spy_t0 THEN 1
                     WHEN json_extract(j.value, '$.ticker') IN ('VIX','UVXY')
                          AND json_extract(j.value, '$.direction') = 'up'
                          AND m.price_vix_t60 > m.price_vix_t0 THEN 1
                     WHEN json_extract(j.value, '$.ticker') IN ('VIX','UVXY')
                          AND json_extract(j.value, '$.direction') = 'down'
                          AND m.price_vix_t60 < m.price_vix_t0 THEN 1
                     ELSE 0
                 END) as correct_count,
                 SUM(CASE WHEN json_extract(j.value, '$.direction')='up'
                          THEN 1 ELSE 0 END) as up_predictions,
                 SUM(CASE WHEN json_extract(j.value, '$.direction')='down'
                          THEN 1 ELSE 0 END) as down_predictions,
                 SUM(CASE WHEN json_extract(j.value, '$.magnitude')=2
                          THEN 1 ELSE 0 END) as strong_signals,
                 AVG(CASE
                     WHEN json_extract(j.value, '$.ticker') IN ('SPY','SPX','QQQ')
                         THEN (m.price_spy_t60 - m.price_spy_t0)
                              / NULLIF(m.price_spy_t0, 0) * 100
                     WHEN json_extract(j.value, '$.ticker') IN ('VIX','UVXY')
                         THEN (m.price_vix_t60 - m.price_vix_t0)
                 END) as avg_actual_move
               FROM headline_market_moves m
               JOIN headlines h ON h.id = m.headline_id
               , json_each(h.signals) j
               WHERE m.is_complete = 1
                 AND m.price_spy_t0 IS NOT NULL
                 AND h.signals IS NOT NULL
                 AND h.signals != '[]'
                 AND json_extract(j.value, '$.ticker')
                     IN ('SPY','SPX','QQQ','VIX','UVXY')
               GROUP BY ticker
               ORDER BY sample_count DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_calibration_summary(self) -> dict:
        """Overall calibration stats."""
        cursor = await self._db.execute(
            """SELECT
                 COUNT(*) as total_tracked,
                 SUM(is_complete) as total_complete,
                 MIN(analyzed_at) as earliest,
                 MAX(analyzed_at) as latest
               FROM headline_market_moves"""
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}

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
            signals=json.loads(row["signals"]) if row["signals"] else [],
            analysis_summary=row["analysis_summary"],
            analyzed_at=datetime.fromisoformat(row["analyzed_at"]) if row["analyzed_at"] else None,
            is_analyzed=bool(row["is_analyzed"]),
            is_market_moving=bool(row["is_market_moving"]),
            classifier_score=row["classifier_score"] or 0.0,
        )
