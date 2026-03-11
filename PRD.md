# PRD — Market News Terminal

## Vision
A real-time current events alert system that aggregates market-moving news from multiple sources, uses AI to classify sentiment and impact, and displays it in a Bloomberg-terminal-style dark web dashboard. Helps an investor quickly see what's happening and how it might affect markets.

## Milestones

### Milestone 1: Core Infrastructure — Done
Settings, models, database, FastAPI skeleton, health endpoint.

### Milestone 2: RSS Ingestion — Done
RSS pollers for 12 feeds, dedup (hash + fuzzy), ingestion consumer, feeds.yaml config.

### Milestone 3: Frontend V1 — Done
Dark-themed dashboard with WebSocket live feed, headline cards, timestamps, category/impact/source/ticker filters.

### Milestone 4: Claude Analysis — Done
Keyword pre-filter classifier, Claude Haiku integration, analysis queue with rate limiter and concurrency control. Headlines get sentiment (bullish/bearish/neutral), impact score (1-5), category tags, ticker tags, and one-line summary.

### Milestone 5: Filters + Polish — Done
Category/ticker/impact/source filters working. Auto-scroll control, periodic data refresh for analysis updates, fade-in animations. Green/red/yellow color-coded sentiment borders and badges.

### Milestone 6: Twitter/X Integration — Not Started
twscrape-based polling of financial Twitter accounts (@DeItaone, @FirstSquawk, Trump, etc). XRSS Docker fallback. twitter_accounts.yaml config.

### Milestone 7: Finnhub API + Hardening — Not Started
Finnhub news API source, error recovery, graceful source degradation, startup validation script.

## Current Milestone Notes
Milestones 1-5 complete and verified running. 12 RSS sources active, Claude analysis (claude-3-haiku-20240307) producing sentiment/impact/tickers/summaries in real-time. Dashboard fully functional with live WebSocket feed and working filters.

Next up: Milestone 6 (Twitter) and Milestone 7 (Finnhub + hardening).

## Out of Scope
- Mobile app
- User authentication / multi-user
- Historical backtesting
- Trade execution
- Paid data feeds (Bloomberg, Refinitiv)
- Email/SMS notifications (dashboard only)
