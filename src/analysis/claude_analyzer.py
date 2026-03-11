from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from src.models import AnalysisResult

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a financial market analyst AI. You analyze news headlines and provide structured market impact assessments.

Respond ONLY with valid JSON in this exact format:
{
  "sentiment": "bullish" | "bearish" | "neutral",
  "impact_score": 1-5,
  "categories": ["category1", "category2"],
  "tickers": ["TICKER1", "TICKER2"],
  "asset_classes": ["class1", "class2"],
  "summary": "One sentence analysis"
}

Categories (use 1-3): Energy, Bonds, Equities, FX, Commodities, Crypto, Geopolitics, Trade, Monetary Policy, Fiscal Policy, Regulation, Earnings, M&A, Tech, Real Estate, Labor, Politics

Asset classes (use 1-3): Equities, Fixed Income, Commodities, FX, Crypto, Derivatives

Tickers: Use standard symbols (SPY, QQQ, CL, GC, DX, BTC, etc). Only include tickers directly affected. Use futures symbols for commodities.

Impact score guide:
1 = Minimal, routine news
2 = Minor, may move individual stocks
3 = Moderate, sector-level impact
4 = Significant, broad market movement expected
5 = Major, systemic/crisis level

Be concise. Focus on actionable market implications. Do not speculate beyond what the headline states."""

ANALYSIS_USER_TEMPLATE = """Analyze this headline for market impact:

Source: {source}
Headline: {title}
{description_line}"""


async def analyze_headline(
    client: anthropic.AsyncAnthropic,
    model: str,
    source: str,
    title: str,
    description: Optional[str] = None,
) -> AnalysisResult:
    """Call Claude to analyze a single headline. Returns AnalysisResult."""

    description_line = f"Details: {description}" if description else ""
    user_content = ANALYSIS_USER_TEMPLATE.format(
        source=source,
        title=title,
        description_line=description_line,
    ).strip()

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=300,
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
        # Try to extract JSON from the response
        import re
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning(f"Could not parse analysis response: {text[:200]}")
                return AnalysisResult()
        else:
            logger.warning(f"No JSON found in analysis response: {text[:200]}")
            return AnalysisResult()

    # Validate and normalize
    sentiment = data.get("sentiment", "neutral").lower()
    if sentiment not in ("bullish", "bearish", "neutral"):
        sentiment = "neutral"

    impact = data.get("impact_score", 1)
    try:
        impact = max(1, min(5, int(impact)))
    except (ValueError, TypeError):
        impact = 1

    return AnalysisResult(
        sentiment=sentiment,
        impact_score=impact,
        categories=data.get("categories", [])[:3],
        tickers=data.get("tickers", [])[:10],
        asset_classes=data.get("asset_classes", [])[:3],
        summary=str(data.get("summary", ""))[:200],
    )
