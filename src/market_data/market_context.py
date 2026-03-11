from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Finnhub symbol map — adjust if free tier doesn't resolve certain symbols
QUOTE_SYMBOLS = {
    "spy": "SPY",
    "vix": "CBOE:VIX",
    "dxy": "FOREXCOM:DXY",
    "gold": "OANDA:XAU_USD",
    "oil": "OANDA:WTICO_USD",
    "btc": "BINANCE:BTCUSDT",
}


class MarketSnapshot:
    """Current market state at a point in time."""

    def __init__(self):
        self.timestamp: datetime = datetime.utcnow()
        self.spy_price: Optional[float] = None
        self.spy_change_pct: Optional[float] = None
        self.vix_price: Optional[float] = None
        self.dxy_price: Optional[float] = None
        self.btc_price: Optional[float] = None
        self.gold_price: Optional[float] = None
        self.oil_price: Optional[float] = None
        self.market_status: str = "unknown"
        self.upcoming_events: list[str] = []

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "spy_price": self.spy_price,
            "spy_change_pct": self.spy_change_pct,
            "vix_price": self.vix_price,
            "dxy_price": self.dxy_price,
            "btc_price": self.btc_price,
            "gold_price": self.gold_price,
            "oil_price": self.oil_price,
            "market_status": self.market_status,
            "upcoming_events": self.upcoming_events,
        }


class MarketContextProvider:
    """Background task that periodically fetches market data from Finnhub."""

    def __init__(self, settings):
        self.settings = settings
        self.api_key = settings.finnhub_api_key
        self.refresh_interval = settings.market_context_refresh_interval
        self._session: Optional[aiohttp.ClientSession] = None
        self._snapshot: Optional[MarketSnapshot] = None
        self._lock = asyncio.Lock()

    async def start(self):
        self._session = aiohttp.ClientSession()

    async def stop(self):
        if self._session:
            await self._session.close()

    async def run(self):
        """Background loop — refreshes snapshot periodically."""
        logger.info(f"Market context provider running (refresh every {self.refresh_interval}s)")
        while True:
            try:
                await self._refresh()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Market context refresh error: {e}")
            await asyncio.sleep(self.refresh_interval)

    async def _refresh(self):
        """Fetch all market data in parallel and build a new snapshot."""
        snapshot = MarketSnapshot()

        # Fetch quotes in parallel
        tasks = {
            key: self._fetch_quote(symbol)
            for key, symbol in QUOTE_SYMBOLS.items()
        }
        tasks["calendar"] = self._fetch_economic_calendar()
        tasks["status"] = self._fetch_market_status()

        results = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )
        result_map = dict(zip(tasks.keys(), results))

        # Process quote results
        for key in QUOTE_SYMBOLS:
            data = result_map.get(key)
            if isinstance(data, dict) and data.get("c"):
                price = data["c"]
                change_pct = data.get("dp")
                if key == "spy":
                    snapshot.spy_price = price
                    snapshot.spy_change_pct = change_pct
                elif key == "vix":
                    snapshot.vix_price = price
                elif key == "dxy":
                    snapshot.dxy_price = price
                elif key == "gold":
                    snapshot.gold_price = price
                elif key == "oil":
                    snapshot.oil_price = price
                elif key == "btc":
                    snapshot.btc_price = price
            elif isinstance(data, Exception):
                logger.debug(f"Failed to fetch {key}: {data}")

        # Calendar
        cal = result_map.get("calendar")
        if isinstance(cal, list):
            snapshot.upcoming_events = cal

        # Market status
        status = result_map.get("status")
        if isinstance(status, str):
            snapshot.market_status = status

        async with self._lock:
            self._snapshot = snapshot

        has_data = any([
            snapshot.spy_price, snapshot.vix_price, snapshot.btc_price,
        ])
        if has_data:
            logger.info(
                f"Market snapshot: SPY={snapshot.spy_price} "
                f"VIX={snapshot.vix_price} BTC={snapshot.btc_price} "
                f"status={snapshot.market_status}"
            )
        else:
            logger.warning("Market snapshot: no quote data received")

    async def _fetch_quote(self, symbol: str) -> dict:
        """Fetch a single quote from Finnhub."""
        url = "https://finnhub.io/api/v1/quote"
        params = {"symbol": symbol, "token": self.api_key}
        async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                text = await resp.text()
                logger.debug(f"Finnhub quote {symbol} returned {resp.status}: {text[:100]}")
                return {}

    async def _fetch_economic_calendar(self) -> list[str]:
        """Fetch upcoming economic events from Finnhub."""
        try:
            now = datetime.utcnow()
            from_date = now.strftime("%Y-%m-%d")
            to_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")
            url = "https://finnhub.io/api/v1/calendar/economic"
            params = {"from": from_date, "to": to_date, "token": self.api_key}
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                events = data.get("economicCalendar", [])
                # Filter for important US events
                important = []
                important_keywords = [
                    "fed", "fomc", "cpi", "ppi", "nonfarm", "payroll", "gdp",
                    "retail sales", "unemployment", "interest rate", "inflation",
                    "consumer confidence", "ism", "pce",
                ]
                for evt in events[:50]:
                    country = evt.get("country", "").upper()
                    event_name = evt.get("event", "").lower()
                    impact = evt.get("impact", "").lower()
                    if country == "US" and (
                        impact in ("high", "medium")
                        or any(kw in event_name for kw in important_keywords)
                    ):
                        date_str = evt.get("time", evt.get("date", ""))[:10]
                        short_name = evt.get("event", "")[:40]
                        important.append(f"{short_name} {date_str}")
                return important[:8]
        except Exception as e:
            logger.debug(f"Economic calendar fetch error: {e}")
            return []

    async def _fetch_market_status(self) -> str:
        """Determine if US market is open based on time."""
        # Simple time-based check (avoids extra API call)
        try:
            from datetime import timezone
            now_utc = datetime.now(timezone.utc)
            # ET is UTC-5 (EST) or UTC-4 (EDT). Approximate with UTC-4 Mar-Nov.
            month = now_utc.month
            et_offset = -4 if 3 <= month <= 11 else -5
            et_hour = (now_utc.hour + et_offset) % 24
            weekday = now_utc.weekday()  # 0=Mon, 6=Sun

            if weekday >= 5:
                return "closed"
            elif et_hour < 4:
                return "closed"
            elif et_hour < 9 or (et_hour == 9 and now_utc.minute < 30):
                return "pre-market"
            elif et_hour < 16:
                return "open"
            elif et_hour < 20:
                return "after-hours"
            else:
                return "closed"
        except Exception:
            return "unknown"

    def get_snapshot(self) -> Optional[MarketSnapshot]:
        """Get the current cached snapshot (non-async, instant)."""
        return self._snapshot

    def snapshot_to_dict(self) -> Optional[dict]:
        """Serialize current snapshot for storage or API response."""
        if self._snapshot:
            return self._snapshot.to_dict()
        return None

    def format_for_prompt(self) -> str:
        """Format current snapshot as text for injection into Claude's prompt."""
        snap = self._snapshot
        if not snap:
            return ""

        parts = []
        if snap.spy_price:
            pct = f" ({'+' if snap.spy_change_pct >= 0 else ''}{snap.spy_change_pct:.2f}%)" if snap.spy_change_pct is not None else ""
            parts.append(f"SPY: ${snap.spy_price:.2f}{pct}")
        if snap.vix_price:
            parts.append(f"VIX: {snap.vix_price:.1f}")
        if snap.dxy_price:
            parts.append(f"DXY: {snap.dxy_price:.1f}")
        if snap.gold_price:
            parts.append(f"Gold: ${snap.gold_price:.0f}")
        if snap.oil_price:
            parts.append(f"Oil: ${snap.oil_price:.2f}")
        if snap.btc_price:
            parts.append(f"BTC: ${snap.btc_price:,.0f}")

        if not parts:
            return ""

        lines = ["=== CURRENT MARKET CONTEXT ==="]
        lines.append(" | ".join(parts))
        if snap.market_status != "unknown":
            lines.append(f"Market: {snap.market_status.replace('-', ' ').title()}")
        if snap.upcoming_events:
            lines.append(f"Upcoming: {', '.join(snap.upcoming_events[:4])}")
        lines.append("=" * 30)

        return "\n".join(lines)
