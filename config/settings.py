from __future__ import annotations

from dotenv import dotenv_values
from pydantic_settings import BaseSettings
from pydantic import Field


def _load_env_file() -> dict:
    """Load .env file values, which should win over empty shell env vars."""
    vals = dotenv_values(".env")
    return {k: v for k, v in vals.items() if v}


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    finnhub_api_key: str = ""

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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def __init__(self, **kwargs):
        # Merge .env file values explicitly so they override empty shell env vars
        env_vals = _load_env_file()
        # Convert UPPER_CASE env names to lower_case field names
        lower_env = {k.lower(): v for k, v in env_vals.items()}
        merged = {**lower_env, **{k: v for k, v in kwargs.items() if v}}
        super().__init__(**merged)
