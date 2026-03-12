from __future__ import annotations

import json
import logging
import re
from typing import Optional

import anthropic

from src.models import AnalysisResult, DirectionalSignal

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a financial market analyst AI. You analyze news headlines and provide structured market impact assessments with per-asset directional signals.

Respond ONLY with valid JSON in this exact format:
{
  "sentiment": "bullish" | "bearish" | "neutral",
  "impact_score": 1-5,
  "categories": ["category1", "category2"],
  "asset_classes": ["class1", "class2"],
  "summary": "One sentence analysis",
  "signals": [
    {"ticker": "CL", "direction": "down", "magnitude": 2, "explanation": "SPR release floods crude supply"},
    {"ticker": "XLE", "direction": "down", "magnitude": 1, "explanation": "Energy sector follows crude lower"},
    {"ticker": "UAL", "direction": "up", "magnitude": 1, "explanation": "Lower fuel costs benefit airlines"}
  ]
}

Rules for signals:
- Include 1-5 signals for the most directly impacted assets
- ticker: standard symbol (SPY, QQQ, CL, GC, DX, BTC, XLE, UAL, TLT, etc). Use futures symbols for commodities.
- direction: "up" or "down"
- magnitude: 1 (slight move) or 2 (significant move)
- explanation: concise reason (under 15 words)
- Order by magnitude descending (strongest impact first)

Sentiment: derive from overall market direction. If most signals are down or the primary signal is bearish for broad markets, use "bearish". Vice versa for "bullish". Mixed or minor = "neutral".

Categories (use 1-3): Energy, Bonds, Equities, FX, Commodities, Crypto, Geopolitics, Trade, Monetary Policy, Fiscal Policy, Regulation, Earnings, M&A, Tech, Real Estate, Labor, Politics

Asset classes (use 1-3): Equities, Fixed Income, Commodities, FX, Crypto, Derivatives

Impact score guide:
1 = Minimal, routine news
2 = Minor, may move individual stocks
3 = Moderate, sector-level impact
4 = Significant, broad market movement expected
5 = Major, systemic/crisis level

When market context is provided, factor it into your impact assessment:
- High VIX (>25) means fear is already elevated, so bearish news may have less marginal impact (partially priced in)
- If SPY is already down significantly, further bearish news may have diminishing impact
- Upcoming Fed meetings or CPI releases heighten sensitivity to monetary policy and inflation headlines
- Consider whether the news is likely already reflected in current prices

Be concise. Focus on actionable market implications. Do not speculate beyond what the headline states."""

ANALYSIS_USER_TEMPLATE = """Analyze this headline for market impact:

Source: {source}
Headline: {title}
{description_line}
{market_context}"""


async def analyze_headline(
    client: anthropic.AsyncAnthropic,
    model: str,
    source: str,
    title: str,
    description: Optional[str] = None,
    market_context: str = "",
) -> AnalysisResult:
    """Call Claude to analyze a single headline. Returns AnalysisResult."""

    description_line = f"Details: {description}" if description else ""
    user_content = ANALYSIS_USER_TEMPLATE.format(
        source=source,
        title=title,
        description_line=description_line,
        market_context=market_context,
    ).strip()

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=500,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        text = response.content[0].text.strip()
        return _parse_response(text)

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return AnalysisResult()
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return AnalysisResult()


def _parse_response(text: str) -> AnalysisResult:
    """Parse Claude's JSON response into an AnalysisResult."""
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response (handle nested braces)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning(f"Could not parse analysis response: {text[:200]}")
                return AnalysisResult()
        else:
            logger.warning(f"No JSON found in analysis response: {text[:200]}")
            return AnalysisResult()

    # Validate and normalize sentiment
    sentiment = data.get("sentiment", "neutral").lower()
    if sentiment not in ("bullish", "bearish", "neutral"):
        sentiment = "neutral"

    # Validate impact score
    impact = data.get("impact_score", 1)
    try:
        impact = max(1, min(5, int(impact)))
    except (ValueError, TypeError):
        impact = 1

    # Parse directional signals
    raw_signals = data.get("signals", [])
    signals = []
    for s in raw_signals[:5]:  # cap at 5 signals
        if not isinstance(s, dict):
            continue
        direction = s.get("direction", "").lower()
        if direction not in ("up", "down"):
            continue
        magnitude = s.get("magnitude", 1)
        try:
            magnitude = max(1, min(2, int(magnitude)))
        except (ValueError, TypeError):
            magnitude = 1
        signals.append(DirectionalSignal(
            ticker=str(s.get("ticker", "")).upper()[:10],
            direction=direction,
            magnitude=magnitude,
            explanation=str(s.get("explanation", ""))[:100],
        ))

    # Derive tickers from signals (replaces old separate tickers field)
    tickers = [s.ticker for s in signals] if signals else data.get("tickers", [])[:10]

    return AnalysisResult(
        sentiment=sentiment,
        impact_score=impact,
        categories=data.get("categories", [])[:3],
        tickers=tickers,
        asset_classes=data.get("asset_classes", [])[:3],
        summary=str(data.get("summary", ""))[:200],
        signals=signals,
    )
