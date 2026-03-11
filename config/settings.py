from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    finnhub_api_key: str = Field(default="", alias="FINNHUB_API_KEY")

    # Database
    db_path: str = "data/headlines.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Analysis
    claude_model: str = "claude-3-haiku-20240307"
    max_concurrent_analyses: int = 3
    analysis_rate_limit: int = 30  # per minute
    min_classifier_score: float = 0.33
    analysis_enabled: bool = True

    # Polling intervals (seconds)
    rss_default_poll_interval: int = 30
    api_poll_interval: int = 60
    twitter_poll_interval: int = 60

    # Twitter
    twitter_enabled: bool = False  # Off by default until configured

    # Market context
    market_context_enabled: bool = True
    market_context_refresh_interval: int = 120  # seconds (2 min)

    # Move tracking
    move_tracking_enabled: bool = True
    move_tracker_poll_interval: int = 60  # seconds

    # Paths
    feeds_config: str = "config/feeds.yaml"
    twitter_config: str = "config/twitter_accounts.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
