from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from config.settings import Settings
from src.database import Database
from src.market_data.market_context import fetch_ticker_prices

logger = logging.getLogger(__name__)

# SPY/VIX checkpoints: (checkpoint_name, timedelta_offset)
MOVE_CHECKPOINTS = [
    ("t5", timedelta(minutes=5)),
    ("t15", timedelta(minutes=15)),
    ("t60", timedelta(hours=1)),
    ("t4h", timedelta(hours=4)),
]

# Per-signal checkpoints (only T+1hr and T+4hr — shorter intervals
# are too noisy for individual stocks and create too many API calls)
SIGNAL_CHECKPOINTS = [
    ("t60", timedelta(hours=1)),
    ("t4h", timedelta(hours=4)),
]


class MoveTracker:
    """Background task that tracks actual market moves after headline analysis.

    For each analyzed headline, records SPY/VIX prices at T+5min, T+15min,
    T+1hr, and T+4hr. Also tracks per-signal ticker prices at T+1hr and T+4hr
    to calibrate directional signal accuracy.
    """

    def __init__(self, settings: Settings, db: Database, market_context=None):
        self.settings = settings
        self.db = db
        self.market_context = market_context
        self.poll_interval = settings.move_tracker_poll_interval

    async def run(self):
        """Background loop — checks pending moves periodically."""
        logger.info(f"Move tracker started (poll every {self.poll_interval}s)")
        # Wait a bit before first check so the system can warm up
        await asyncio.sleep(30)

        while True:
            try:
                if self._is_market_hours():
                    await self._check_pending_moves()
                    await self._check_pending_signal_moves()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Move tracker error: {e}")
            await asyncio.sleep(self.poll_interval)

    def _is_market_hours(self) -> bool:
        """Check if US market is currently open (approximate)."""
        try:
            now_utc = datetime.now(timezone.utc)
            month = now_utc.month
            et_offset = -4 if 3 <= month <= 11 else -5
            et_hour = (now_utc.hour + et_offset) % 24
            weekday = now_utc.weekday()

            # Only track during extended hours (pre-market through after-hours)
            # 4:00 AM - 8:00 PM ET, weekdays only
            if weekday >= 5:
                return False
            return 4 <= et_hour < 20
        except Exception:
            return True  # Default to tracking if time check fails

    async def _check_pending_moves(self):
        """Check which headlines need SPY/VIX move tracking updates."""
        pending = await self.db.get_pending_move_checks()
        if not pending:
            return

        now = datetime.utcnow()
        spy_price, vix_price = self._get_current_prices()
        updates = 0

        for move in pending:
            try:
                analyzed_at = datetime.fromisoformat(move["analyzed_at"])

                for checkpoint_name, offset in MOVE_CHECKPOINTS:
                    checked_col = f"checked_{checkpoint_name}_at"
                    # Skip if already checked
                    if move.get(checked_col) is not None:
                        continue

                    # Check if enough time has elapsed
                    if now >= analyzed_at + offset:
                        await self.db.update_move_checkpoint(
                            move_id=move["id"],
                            checkpoint=checkpoint_name,
                            spy_price=spy_price,
                            vix_price=vix_price,
                        )
                        updates += 1

            except Exception as e:
                logger.debug(f"Error checking move {move['id']}: {e}")

        if updates > 0:
            logger.info(f"Move tracker: updated {updates} SPY/VIX checkpoints")

    async def _check_pending_signal_moves(self):
        """Check which per-signal moves need price updates."""
        pending = await self.db.get_pending_signal_moves()
        if not pending:
            return

        now = datetime.utcnow()

        # Figure out which tickers need price fetches this cycle
        tickers_needed = set()
        actionable = []

        for move in pending:
            try:
                analyzed_at = datetime.fromisoformat(move["analyzed_at"])
                for checkpoint_name, offset in SIGNAL_CHECKPOINTS:
                    checked_col = f"checked_{checkpoint_name}_at"
                    if move.get(checked_col) is not None:
                        continue
                    if now >= analyzed_at + offset:
                        tickers_needed.add(move["ticker"])
                        actionable.append((move, checkpoint_name, offset))
            except Exception:
                continue

        if not tickers_needed:
            return

        # Batch-fetch all needed ticker prices in one yfinance call
        prices = await fetch_ticker_prices(list(tickers_needed))
        updates = 0

        for move, checkpoint_name, offset in actionable:
            try:
                price = prices.get(move["ticker"])
                await self.db.update_signal_checkpoint(
                    move_id=move["id"],
                    checkpoint=checkpoint_name,
                    price=price,
                )
                updates += 1
            except Exception as e:
                logger.debug(f"Error updating signal move {move['id']}: {e}")

        if updates > 0:
            fetched = sum(1 for p in prices.values() if p is not None)
            logger.info(
                f"Move tracker: updated {updates} signal checkpoints "
                f"({fetched}/{len(tickers_needed)} tickers priced)"
            )

    def _get_current_prices(self) -> tuple[Optional[float], Optional[float]]:
        """Get current SPY and VIX from the cached market snapshot."""
        if self.market_context:
            snap = self.market_context.get_snapshot()
            if snap:
                return snap.spy_price, snap.vix_price
        return None, None
