# Market News Terminal

A real-time market news aggregator with AI-powered directional signal analysis. Pulls headlines from 12+ RSS feeds, analyzes them with Claude AI for per-asset directional signals, and displays everything in a live-updating Bloomberg-style dark dashboard with hover tooltips and impact calibration tracking.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal)

## What It Does

- **Aggregates** headlines from CNBC, Reuters, WSJ, MarketWatch, Yahoo Finance, BBC, Al Jazeera, ZeroHedge, and more
- **Deduplicates** across sources using hash matching + fuzzy title similarity
- **Filters** non-market-moving news with a keyword pre-classifier (~60-70% filtered out)
- **Analyzes** remaining headlines with Claude AI for **per-asset directional signals** (e.g., `CL ↓↓`, `XLE ↓`, `UAL ↑`), impact score (1-5), category tags, and one-line summaries
- **Injects market context** — live SPY, VIX, DXY, gold, oil, and BTC prices via Finnhub so Claude can factor in current conditions
- **Tracks accuracy** — records SPY/VIX prices at T+0, T+5m, T+15m, T+1hr to calibrate impact scores and signal direction predictions
- **Streams** everything to a WebSocket-powered dashboard in real time

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/misooshiruu/news-terminal.git
cd news-terminal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
FINNHUB_API_KEY=your-finnhub-key-here
```

- [Anthropic API key](https://console.anthropic.com/) — required for headline analysis
- [Finnhub API key](https://finnhub.io/) — required for live market data (free tier works)

### 3. Run

```bash
./run.sh
```

Or manually:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

## Dashboard Features

- **Live feed** — headlines appear in real time via WebSocket
- **Directional signal tags** — per-asset colored tags showing predicted direction and magnitude (green `SPY ↑`, red `CL ↓↓`)
- **Hover tooltips** — hover any signal tag to see the full ticker name and explanation (e.g., "Crude Oil Futures — SPR release floods crude supply")
- **Sentiment borders** — card left borders color-coded by overall sentiment (green/red/yellow)
- **Impact scores** — 1-5 scale with color intensity
- **Category tags** — Energy, Geopolitics, Monetary Policy, Trade, Crypto, etc.
- **Market ticker bar** — live SPY, VIX, DXY, gold, oil, BTC prices in the header
- **Filters** — filter by category, source, impact level, or search for tickers
- **Auto-scroll** — pauses when you scroll up, resumes at top
- **Calibration page** — tracks whether impact scores and signal predictions match actual market moves

## Architecture

```
[RSS Feeds] ──┐                                                     ┌── SQLite
[Finnhub API]─┤── asyncio.Queue ── Dedup ── Pre-filter ── Claude ──┤── WebSocket
[Twitter/X] ──┘                               │              │      └── Move Tracker
                                        (regex classifier)  (+ market context)
```

### Data Sources

| Source | Type | Poll Interval |
|--------|------|--------------|
| CNBC (Top/World/Economy) | RSS | 30s |
| Yahoo Finance | RSS | 60s |
| MarketWatch | RSS | 60s |
| WSJ Markets | RSS | 60s |
| Reuters Business | RSS | 60s |
| Al Jazeera | RSS | 60s |
| Times of Israel | RSS | 60s |
| BBC World | RSS | 60s |
| ZeroHedge | RSS | 90s |
| Seeking Alpha | RSS | 90s |

Sources are configured in `config/feeds.yaml` — add or remove feeds without touching code.

## Project Structure

```
├── config/
│   ├── settings.py           # Pydantic settings (model, intervals, flags)
│   └── feeds.yaml            # RSS + API source config
├── src/
│   ├── main.py               # FastAPI app + async lifespan
│   ├── models.py             # Data models + SQL schema
│   ├── database.py           # aiosqlite CRUD + dedup + calibration queries
│   ├── sources/
│   │   ├── base.py           # Abstract source with poll loop
│   │   ├── rss_source.py     # RSS poller (aiohttp + feedparser)
│   │   └── source_manager.py # Orchestrator + ingestion pipeline
│   ├── market_data/
│   │   ├── market_context.py # Finnhub quote + calendar fetcher
│   │   └── move_tracker.py   # Post-headline SPY/VIX move tracker
│   ├── analysis/
│   │   ├── classifier.py     # Keyword pre-filter
│   │   ├── claude_analyzer.py# Claude API + directional signal prompt
│   │   └── analysis_queue.py # Rate-limited analysis consumer
│   └── delivery/
│       ├── websocket_manager.py
│       └── routes.py         # HTTP + WebSocket + calibration endpoints
├── frontend/
│   ├── index.html
│   ├── calibration.html      # Calibration analytics page
│   ├── css/terminal.css      # Dark Bloomberg-style theme
│   └── js/
│       ├── app.js            # Main application + market ticker bar
│       ├── websocket.js      # WebSocket client with auto-reconnect
│       ├── feed.js           # Card renderer + JS tooltips
│       ├── filters.js        # Category/ticker/impact/source filters
│       ├── calibration.js    # Calibration page renderer
│       └── ticker-names.js   # ~120 ticker symbol → full name mappings
├── data/headlines.db          # SQLite (auto-created)
└── requirements.txt
```

## Configuration

Key settings in `config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `claude_model` | `claude-3-haiku-20240307` | AI model for analysis |
| `analysis_rate_limit` | 30 | Max Claude API calls per minute |
| `max_concurrent_analyses` | 3 | Parallel analysis tasks |
| `min_classifier_score` | 0.33 | Pre-filter threshold (lower = more headlines analyzed) |
| `rss_default_poll_interval` | 30 | Default RSS poll interval in seconds |
| `analysis_enabled` | true | Toggle AI analysis on/off |
| `move_tracking_enabled` | true | Toggle post-headline move tracking |
| `finnhub_poll_interval` | 30 | Market data refresh interval in seconds |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /calibration` | Calibration analytics page |
| `GET /api/headlines` | Paginated headlines with filters |
| `GET /api/stats` | Today's headline and analysis counts |
| `GET /api/sources/status` | Source health status |
| `GET /api/market-context` | Current market snapshot (SPY, VIX, etc.) |
| `GET /api/calibration/summary` | Move tracking summary stats |
| `GET /api/calibration/by-impact` | Avg market move by impact score |
| `GET /api/calibration/by-signals` | Signal direction accuracy for verifiable tickers |
| `GET /api/calibration/by-sentiment` | Overall sentiment prediction accuracy |
| `GET /api/health` | Health check |
| `WS /ws` | Live headline + analysis stream |

## Cost

Using Claude Haiku with the keyword pre-filter, expect roughly **~$0.15/day** at typical news volumes (~500 headlines/day, ~150 analyzed). Finnhub free tier provides 60 API calls/minute which is more than sufficient.

## License

[MIT](LICENSE)
