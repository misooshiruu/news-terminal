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

### Milestone 5.5: Market Context + Calibration — Done
Live market data injection into Claude's analysis prompt (SPY, VIX, DXY, gold, oil, BTC via Finnhub). Post-headline move tracking at T+5m, T+15m, T+1hr for impact score calibration. Calibration dashboard page with per-impact-level avg moves and sentiment direction accuracy. Market ticker bar in header. Headline timestamps fixed to ET.

### Milestone 5.6: Directional Signals + Enhanced Calibration — Done
Replaced generic bullish/bearish/neutral sentiment with per-asset directional signals (1-5 per headline). Each signal has ticker, direction (up/down), magnitude (1-2), and explanation. Frontend renders colored signal tags (green ↑, red ↓) with hover tooltips showing full ticker name + rationale. Ticker name lookup table (~120 entries). Calibration page enhanced with signal-level accuracy tracking for verifiable tickers (SPY/VIX). JS-based tooltips replace CSS `::after` to avoid scroll-container clipping.

## Current Milestone Notes
Milestones 1-5.6 complete. Signal calibration data will accumulate as new headlines with directional signals complete their 1-hour tracking cycle during market hours.

Next up: Milestone 6 (Twitter) and Milestone 7 (Finnhub + hardening).

## Out of Scope
- Mobile app
- User authentication / multi-user
- Historical backtesting
- Trade execution
- Paid data feeds (Bloomberg, Refinitiv)
- Email/SMS notifications (dashboard only)
