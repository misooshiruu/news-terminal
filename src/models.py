from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RawHeadline(BaseModel):
    """A headline as received from a data source, before processing."""
    source: str
    source_category: str  # "rss", "api", "twitter"
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class DirectionalSignal(BaseModel):
    """A single per-asset directional impact signal."""
    ticker: str          # e.g. "CL", "UAL", "SPY"
    direction: str       # "up" or "down"
    magnitude: int = 1   # 1 = slight, 2 = strong
    explanation: str = "" # e.g. "Lower fuel costs benefit airlines"


class AnalysisResult(BaseModel):
    """Result from Claude analysis."""
    sentiment: str = "neutral"  # bullish, bearish, neutral (kept for card borders + calibration)
    impact_score: int = 1  # 1-5
    categories: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    summary: str = ""
    signals: list[DirectionalSignal] = Field(default_factory=list)


class Headline(BaseModel):
    """A fully processed headline stored in the database."""
    id: int = 0
    content_hash: str = ""
    source: str = ""
    source_category: str = ""
    title: str = ""
    description: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    ingested_at: Optional[datetime] = None

    # Analysis fields
    sentiment: Optional[str] = None
    impact_score: Optional[int] = None
    categories: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    asset_classes: list[str] = Field(default_factory=list)
    signals: list[dict] = Field(default_factory=list)
    analysis_summary: Optional[str] = None
    analyzed_at: Optional[datetime] = None

    is_analyzed: bool = False
    is_market_moving: bool = False
    classifier_score: float = 0.0

    def to_ws_dict(self) -> dict:
        """Serialize for WebSocket broadcast."""
        return {
            "id": self.id,
            "source": self.source,
            "source_category": self.source_category,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "ingested_at": self.ingested_at.isoformat() if self.ingested_at else None,
            "sentiment": self.sentiment,
            "impact_score": self.impact_score,
            "categories": self.categories,
            "tickers": self.tickers,
            "asset_classes": self.asset_classes,
            "signals": self.signals,
            "analysis_summary": self.analysis_summary,
            "is_analyzed": self.is_analyzed,
            "is_market_moving": self.is_market_moving,
            "classifier_score": self.classifier_score,
        }


# SQL schema for database initialization
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS headlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    source_category TEXT,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT,
    published_at TIMESTAMP,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    sentiment TEXT,
    impact_score INTEGER,
    categories TEXT,
    tickers TEXT,
    asset_classes TEXT,
    signals TEXT,
    analysis_summary TEXT,
    analyzed_at TIMESTAMP,

    is_analyzed BOOLEAN DEFAULT 0,
    is_market_moving BOOLEAN DEFAULT 0,
    classifier_score REAL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_headlines_ingested ON headlines(ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_headlines_sentiment ON headlines(sentiment);
CREATE INDEX IF NOT EXISTS idx_headlines_source ON headlines(source);
CREATE INDEX IF NOT EXISTS idx_headlines_hash ON headlines(content_hash);

CREATE TABLE IF NOT EXISTS source_state (
    source_name TEXT PRIMARY KEY,
    last_seen_id TEXT,
    last_poll_at TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    is_healthy BOOLEAN DEFAULT 1
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TIMESTAMP NOT NULL,
    spy_price REAL,
    spy_change_pct REAL,
    vix_price REAL,
    dxy_price REAL,
    btc_price REAL,
    gold_price REAL,
    oil_price REAL,
    market_status TEXT,
    upcoming_events TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time ON market_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS headline_market_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    headline_id INTEGER NOT NULL REFERENCES headlines(id),
    snapshot_id INTEGER REFERENCES market_snapshots(id),
    analyzed_at TIMESTAMP NOT NULL,
    price_spy_t0 REAL,
    price_vix_t0 REAL,
    price_spy_t5 REAL,
    price_vix_t5 REAL,
    checked_t5_at TIMESTAMP,
    price_spy_t15 REAL,
    price_vix_t15 REAL,
    checked_t15_at TIMESTAMP,
    price_spy_t60 REAL,
    price_vix_t60 REAL,
    checked_t60_at TIMESTAMP,
    is_complete BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_moves_headline ON headline_market_moves(headline_id);
CREATE INDEX IF NOT EXISTS idx_moves_complete ON headline_market_moves(is_complete);
CREATE INDEX IF NOT EXISTS idx_moves_analyzed ON headline_market_moves(analyzed_at);

CREATE TABLE IF NOT EXISTS signal_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    headline_id INTEGER NOT NULL REFERENCES headlines(id),
    ticker TEXT NOT NULL,
    yf_symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    magnitude INTEGER DEFAULT 1,
    analyzed_at TIMESTAMP NOT NULL,
    baseline_price REAL,
    price_t60 REAL,
    price_t4h REAL,
    checked_t60_at TIMESTAMP,
    checked_t4h_at TIMESTAMP,
    is_complete BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_signal_moves_headline ON signal_moves(headline_id);
CREATE INDEX IF NOT EXISTS idx_signal_moves_complete ON signal_moves(is_complete);
CREATE INDEX IF NOT EXISTS idx_signal_moves_ticker ON signal_moves(ticker);
"""


# Ticker symbol → yfinance symbol mapping.
# Equities/ETFs use the same symbol; only overrides needed here.
TICKER_TO_YF = {
    # Commodity futures
    "CL": "CL=F",
    "GC": "GC=F",
    "SI": "SI=F",
    "NG": "NG=F",
    "HG": "HG=F",
    "ZW": "ZW=F",
    "ZC": "ZC=F",
    "ZS": "ZS=F",
    "PL": "PL=F",
    # Indices
    "VIX": "^VIX",
    "SPX": "^GSPC",
    # FX
    "DX": "DX-Y.NYB",
    "EURUSD": "EURUSD=X",
    "USDJPY": "USDJPY=X",
    "GBPUSD": "GBPUSD=X",
    "USDCNH": "CNY=X",
    # Crypto
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}


def ticker_to_yf_symbol(ticker: str) -> str:
    """Convert a signal ticker to a yfinance symbol."""
    return TICKER_TO_YF.get(ticker.upper(), ticker.upper())
