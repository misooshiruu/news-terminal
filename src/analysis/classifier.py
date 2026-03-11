from __future__ import annotations

import re

# Patterns that suggest a headline may be market-moving
MARKET_MOVING_PATTERNS = [
    # Economic data & central banks
    r'\b(GDP|CPI|PPI|NFP|payroll|unemployment|inflation|rate cut|rate hike|FOMC|Fed |'
    r'ECB|BOJ|BOE|interest rate|monetary policy|quantitative|jobless claims)\b',
    # Geopolitics & conflict
    r'\b(war|invasion|sanctions|tariff|embargo|missile|attack|ceasefire|treaty|'
    r'nuclear|military|troops|airstrikes?|drone|escalat|de-escalat|NATO|Iran|'
    r'Israel|Hamas|Hezbollah|Russia|Ukraine|China|Taiwan|strait of hormuz)\b',
    # Market moves
    r'\b(crash|surge|plunge|rally|halt|circuit breaker|margin call|liquidat|'
    r'sell-off|selloff|rout|correction|bear market|bull market|all-time high|'
    r'record high|record low|volatility|VIX)\b',
    # Corporate
    r'\b(earnings|guidance|revenue|profit|loss|bankruptcy|merger|acquisition|'
    r'IPO|buyback|dividend|layoff|restructur)\b',
    # Commodities / Energy
    r'\b(oil|crude|brent|WTI|natural gas|OPEC|barrel|refiner|pipeline|'
    r'gold|silver|copper|lithium|uranium)\b',
    # Crypto
    r'\b(bitcoin|BTC|ethereum|ETH|crypto|SEC approval|spot ETF)\b',
    # FX
    r'\b(dollar|DXY|yuan|renminbi|yen|euro|sterling|forex|currency)\b',
    # Political / Policy
    r'\b(executive order|legislation|bill sign|veto|impeach|election|'
    r'Trump|Biden|Congress|Senate|debt ceiling|shutdown|stimulus|'
    r'trade war|trade deal|trade agreement)\b',
    # Key sectors
    r'\b(semiconductor|chip|AI |artificial intelligence|tech sector|'
    r'real estate|housing|banking crisis|bank fail)\b',
]

# Compile patterns for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in MARKET_MOVING_PATTERNS]


def is_market_moving(title: str, description: str = "") -> tuple[bool, float]:
    """
    Determine if a headline is potentially market-moving.
    Returns (should_analyze, confidence_score).
    Score ranges from 0.0 to 1.0.
    A headline with 1+ pattern match passes (score >= 0.33).
    """
    text = f"{title} {description}"
    matches = sum(1 for p in _compiled_patterns if p.search(text))
    score = min(matches / 3.0, 1.0)  # 3+ matches = max score
    return score >= 0.33, score
