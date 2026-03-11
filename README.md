# Market News Terminal

A real-time market news aggregator with AI-powered sentiment analysis. Pulls headlines from 12+ RSS feeds, classifies them with Claude AI, and displays everything in a live-updating dark-themed dashboard.

![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal)

## What It Does

- **Aggregates** headlines from CNBC, Reuters, WSJ, MarketWatch, Yahoo Finance, BBC, Al Jazeera, ZeroHedge, and more
- **Deduplicates** across sources using hash matching + fuzzy title similarity
- **Filters** non-market-moving news with a keyword pre-classifier (~60-70% filtered out)
- **Analyzes** remaining headlines with Claude AI for sentiment (bullish/bearish/neutral), impact score (1-5), ticker extraction, and one-line summaries
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

Edit `.env` and add your [Anthropic API key](https://console.anthropic.com/):

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

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
- **Sentiment badges** — color-coded BULLISH (green), BEARISH (red), NEUTRAL (yellow)
- **Impact scores** — 1-5 scale with color intensity
- **Ticker tags** — extracted symbols (SPY, AAPL, CL, BTC, etc.)
- **Category tags** — Markets, Geopolitics, Economy, Energy, Crypto, etc.
- **Filters** — filter by category, source, impact level, or search for tickers
- **Auto-scroll** — pauses when you scroll up, resumes at bottom

## Architecture

```
[RSS Feeds] ──┐
[Finnhub API]─┤── asyncio.Queue ── Dedup ── Pre-filter ── Analysis Queue ── SQLite + WebSocket
[Twitter/X] ──┘                               │                │
                                        (regex classifier)  (Claude Haiku)
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
│   ├── database.py           # aiosqlite CRUD + dedup
│   ├── sources/
│   │   ├── base.py           # Abstract source with poll loop
│   │   ├── rss_source.py     # RSS poller (aiohttp + feedparser)
│   │   └── source_manager.py # Orchestrator + ingestion pipeline
│   ├── analysis/
│   │   ├── classifier.py     # Keyword pre-filter
│   │   ├── claude_analyzer.py# Claude API integration
│   │   └── analysis_queue.py # Rate-limited analysis consumer
│   └── delivery/
│       ├── websocket_manager.py
│       └── routes.py         # HTTP + WebSocket endpoints
├── frontend/
│   ├── index.html
│   ├── css/terminal.css      # Dark Bloomberg-style theme
│   └── js/                   # App, WebSocket, feed renderer, filters
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

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /api/headlines` | Paginated headlines with filters |
| `GET /api/stats` | Today's headline and analysis counts |
| `GET /api/sources/status` | Source health status |
| `GET /api/health` | Health check |
| `WS /ws` | Live headline stream |

## Cost

Using Claude Haiku with the keyword pre-filter, expect roughly **~$0.15/day** at typical news volumes (~500 headlines/day, ~150 analyzed).

## License

[MIT](LICENSE)
