# Architecture

## System Overview
Real-time market news terminal that aggregates headlines from RSS feeds, financial APIs, and Twitter/X, then uses Claude AI to analyze sentiment and market impact. Delivered via a dark-themed WebSocket-powered web dashboard.

## Pipeline
```
[RSS Feeds] ──┐
[Finnhub API]─┤── asyncio.Queue ── Dedup ── Pre-filter ── Analysis Queue ── SQLite + WebSocket
[Twitter/X] ──┘                               │                │
                                        (regex classifier)  (Claude Haiku)
```

## Project Structure
```
Current Events/
├── config/
│   ├── settings.py           # Pydantic settings
│   ├── feeds.yaml            # RSS + API source config
│   └── twitter_accounts.yaml # Twitter accounts (Milestone 6)
├── src/
│   ├── main.py               # FastAPI app + lifespan
│   ├── models.py             # Pydantic models + SQL schema
│   ├── database.py           # aiosqlite CRUD
│   ├── sources/
│   │   ├── base.py           # Abstract BaseSource
│   │   ├── rss_source.py     # RSS poller
│   │   ├── newsapi_source.py # Finnhub (Milestone 7)
│   │   ├── twitter_source.py # Twitter (Milestone 6)
│   │   └── source_manager.py # Orchestrator + ingestion consumer
│   ├── market_data/
│   │   ├── market_context.py  # Finnhub quote + calendar fetcher
│   │   └── move_tracker.py    # Post-headline SPY/VIX move tracker
│   ├── analysis/
│   │   ├── classifier.py     # Keyword pre-filter
│   │   ├── claude_analyzer.py# Claude API integration (w/ market context)
│   │   └── analysis_queue.py # Async queue + rate limiter + snapshot tracking
│   └── delivery/
│       ├── websocket_manager.py
│       └── routes.py
├── frontend/
│   ├── index.html
│   ├── css/terminal.css
│   ├── calibration.html       # Calibration analytics page
│   └── js/{app,websocket,feed,filters,calibration,ticker-names}.js
├── data/headlines.db          # SQLite (auto-created)
├── .env                       # API keys
├── requirements.txt
└── run.sh
```

## Design Decisions

- **[2026-03-10] Claude Haiku for analysis**
  **Context**: Evaluated Opus ($2-3/day), Sonnet ($0.60/day), Haiku ($0.15/day), Gemini Flash (free). Task is structured classification, not complex reasoning.
  **Consequence**: ~$0.15/day. Configurable in settings.py to upgrade later.

- **[2026-03-10] SQLite with WAL mode**
  **Context**: Single-user system, no need for Postgres. WAL mode enables concurrent reads during writes.
  **Consequence**: Zero external dependencies. DB file in data/ directory.

- **[2026-03-10] Keyword pre-filter before Claude**
  **Context**: ~60-70% of headlines aren't market-moving (lifestyle, sports, etc). Pre-filtering saves API cost.
  **Consequence**: Only market-relevant headlines get analyzed. False negatives possible but acceptable.

- **[2026-03-10] YAML config for data sources**
  **Context**: Adding/removing feeds should not require code changes.
  **Consequence**: Edit feeds.yaml, restart server.

- **[2026-03-11] Model: claude-3-haiku-20240307**
  **Context**: claude-3-5-haiku-20241022 reached end-of-life Feb 2026. claude-sonnet-4-20250514 also available but more expensive.
  **Consequence**: Using older Haiku 3 for now. Can switch to Sonnet 4 via settings.py.

- **[2026-03-11] Preview sandbox requires /tmp mirror**
  **Context**: macOS sandbox blocks Desktop access for preview_start. Project files must be mirrored to /tmp/market-terminal-preview/ for the preview tool.
  **Consequence**: Any source changes need to be synced to /tmp copy before preview restart.

- **[2026-03-11] Market context injection into Claude prompt**
  **Context**: Impact scores based on headline text alone miss market conditions (VIX level, what's priced in, upcoming events).
  **Consequence**: Finnhub quotes (SPY, VIX, DXY, gold, oil, BTC) + economic calendar injected into each analysis prompt. ~3.5 req/min of Finnhub budget.

- **[2026-03-11] Post-headline move tracking for calibration**
  **Context**: No way to know if impact scores are accurate without tracking actual market moves.
  **Consequence**: Records SPY/VIX at T+0, T+5m, T+15m, T+1hr after each analysis. Calibration page shows avg move per impact level and sentiment direction accuracy.

- **[2026-03-12] Per-asset directional signals instead of generic sentiment**
  **Context**: Single bullish/bearish/neutral label too vague for investment decisions — doesn't say what to trade or which direction.
  **Consequence**: Claude now returns 1-5 directional signals per headline (ticker + direction + magnitude + explanation). Frontend renders as colored tags with hover tooltips. Old "sentiment" field kept for card borders and calibration backward compat.

- **[2026-03-12] JS-driven fixed-position tooltips instead of CSS ::after**
  **Context**: Pure CSS tooltips (`::after` pseudo-element with `position: absolute`) were clipped by the scroll container's `overflow-y: auto`.
  **Consequence**: Replaced with a single fixed-position DOM element positioned via JS `getBoundingClientRect()`. Auto-flips below element when near viewport top. Event delegation via `mouseover`/`mouseout` on document.

- **[2026-03-12] Signal-level calibration for verifiable tickers**
  **Context**: Original calibration only tracked overall sentiment (bullish/bearish) vs SPY direction. With directional signals, we can measure per-ticker accuracy.
  **Consequence**: New `/api/calibration/by-signals` endpoint uses `json_each()` to unpack signals and validate SPY/SPX/QQQ/VIX/UVXY predictions against actual T+1hr price movements. Calibration page shows signal accuracy table alongside existing impact + sentiment tables.

## Infrastructure
- **Runtime**: Python 3.9+ with asyncio
- **Server**: uvicorn + FastAPI on port 8000
- **Database**: SQLite at data/headlines.db
- **Env vars**: ANTHROPIC_API_KEY, FINNHUB_API_KEY in .env
- **Start**: `./run.sh` or `uvicorn src.main:app --port 8000`
- **Preview**: Uses /tmp/market-terminal-preview/ mirror with /tmp/mt-venv/
