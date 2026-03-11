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
│   ├── analysis/
│   │   ├── classifier.py     # Keyword pre-filter
│   │   ├── claude_analyzer.py# Claude API integration
│   │   └── analysis_queue.py # Async queue + rate limiter
│   └── delivery/
│       ├── websocket_manager.py
│       └── routes.py
├── frontend/
│   ├── index.html
│   ├── css/terminal.css
│   └── js/{app,websocket,feed,filters}.js
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

## Infrastructure
- **Runtime**: Python 3.9+ with asyncio
- **Server**: uvicorn + FastAPI on port 8000
- **Database**: SQLite at data/headlines.db
- **Env vars**: ANTHROPIC_API_KEY, FINNHUB_API_KEY in .env
- **Start**: `./run.sh` or `uvicorn src.main:app --port 8000`
- **Preview**: Uses /tmp/market-terminal-preview/ mirror with /tmp/mt-venv/
