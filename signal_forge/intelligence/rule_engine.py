"""
High-Precision Rule-Based NLP & Sentiment Engine.
Requires zero external API keys and runs 100% locally with microsecond latency.
Implements 7-day surge prediction detection, fraud/manipulation filtering, and ticker extraction.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# Korean and English 7-day surge prediction expressions
PATTERNS_7D_SURGE = [
    r"이번\s*주\s*급등",
    r"다음\s*주\s*폭등",
    r"7일\s*이내",
    r"일주일\s*안에",
    r"이번\s*주\s*2배",
    r"곧\s*상한가",
    r"상한가\s*직행",
    r"세력\s*진입",
    r"대형\s*호재\s*임박",
    r"폭등\s*임박",
    r"VIP\s*선공개",
    r"7\s*days?\s*breakout",
    r"next\s*week\s*100%",
    r"10x\s*soon",
    r"massive\s*catalyst\s*incoming",
    r"guaranteed\s*pump",
    r"buy\s*before\s*announcement",
    r"short\s*squeeze\s*incoming",
]

# Fraud, pump-and-dump, and promotional scam indicators
PATTERNS_SCAM_FLAGS = [
    r"수익\s*보장",
    r"원금\s*보장",
    r"100%\s*수익",
    r"VIP\s*리딩방",
    r"선착순\s*\d+명",
    r"비밀\s*호재",
    r"무조건\s*매수",
    r"guaranteed\s*return",
    r"risk[\s-]*free",
    r"pump\s*group",
    r"dm\s*for\s*signals",
    r"telegram\s*link",
]

# Sentiment Lexicon
BULLISH_KEYWORDS = [
    "급등", "호재", "상승", "돌파", "매수", "신고가", "실적개선", "서프라이즈", "반등", "계약체결",
    "breakout", "bullish", "rally", "surge", "beat", "upgrade", "buy", "expansion", "growth"
]

BEARISH_KEYWORDS = [
    "급락", "악재", "하락", "이탈", "매도", "신저가", "실적부진", "어닝쇼크", "폭락", "유상증자",
    "breakdown", "bearish", "crash", "dump", "miss", "downgrade", "sell", "dilution", "warning"
]

# Common Korean Stock Name Mappings
KR_STOCK_NAME_MAP = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "삼성바이오로직스": "207940",
    "현대차": "005380",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "셀트리온": "068270",
    "기아": "000270",
    "POSCO홀딩스": "005490",
}


@dataclass
class TextAnalysisResult:
    raw_text: str
    mentioned_symbols: List[str]
    has_7d_surge_claim: bool
    is_promotional_scam: bool
    sentiment_score: float  # -1.0 to +1.0
    matched_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.85
    summary: str = ""


class RuleBasedIntelligenceEngine:
    def __init__(self):
        self.re_7d = [re.compile(p, re.IGNORECASE) for p in PATTERNS_7D_SURGE]
        self.re_scam = [re.compile(p, re.IGNORECASE) for p in PATTERNS_SCAM_FLAGS]

    def analyze(self, text: str) -> TextAnalysisResult:
        """Analyzes text for surge claims, scam markers, sentiment, and symbols."""
        if not text:
            return TextAnalysisResult(
                raw_text="",
                mentioned_symbols=[],
                has_7d_surge_claim=False,
                is_promotional_scam=False,
                sentiment_score=0.0,
                summary="Empty content",
            )

        # 1. 7-day surge claim detection
        has_7d = False
        matched = []
        for r in self.re_7d:
            if r.search(text):
                has_7d = True
                matched.append(r.pattern)

        # 2. Promotional scam detection
        is_scam = False
        for r in self.re_scam:
            if r.search(text):
                is_scam = True
                matched.append(f"SCAM:{r.pattern}")

        # 3. Sentiment scoring
        text_lower = text.lower()
        bull_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        total_kw = bull_count + bear_count
        if total_kw > 0:
            sentiment = (bull_count - bear_count) / float(total_kw)
        else:
            sentiment = 0.0

        # 4. Symbol extraction
        symbols = self.extract_symbols(text)

        # Summary generation
        summary_parts = []
        if has_7d:
            summary_parts.append("[7D_SURGE_CLAIM]")
        if is_scam:
            summary_parts.append("[PUMP_RISK_WARNING]")
        if sentiment > 0.3:
            summary_parts.append(f"[BULLISH_SENTIMENT: {sentiment:.2f}]")
        elif sentiment < -0.3:
            summary_parts.append(f"[BEARISH_SENTIMENT: {sentiment:.2f}]")
        else:
            summary_parts.append("[NEUTRAL_SENTIMENT]")

        summary = " ".join(summary_parts)

        return TextAnalysisResult(
            raw_text=text[:500],
            mentioned_symbols=symbols,
            has_7d_surge_claim=has_7d,
            is_promotional_scam=is_scam,
            sentiment_score=round(sentiment, 2),
            matched_patterns=matched,
            confidence=0.90 if matched else 0.70,
            summary=summary,
        )

    def extract_symbols(self, text: str) -> List[str]:
        """Extracts crypto symbols, US tickers, and Korean 6-digit stock codes."""
        found: Set[str] = set()

        # 1. Korean 6-digit stock codes
        kr_codes = re.findall(r"\b\d{6}\b", text)
        for c in kr_codes:
            found.add(c)

        # 2. Korean registered company names
        for name, code in KR_STOCK_NAME_MAP.items():
            if name in text:
                found.add(code)

        # 3. US Stock Tickers with $ prefix or standalone uppercase
        us_tickers = re.findall(r"\$([A-Z]{2,5})\b", text)
        for t in us_tickers:
            found.add(t)

        # 4. Binance Crypto pairs ($BTC, BTCUSDT, ETH, SOL)
        crypto_pairs = re.findall(r"\b(BTC|ETH|SOL|BNB|XRP|DOGE|ADA|AVAX|LINK|SUI)(?:USDT)?\b", text, re.IGNORECASE)
        for cp in crypto_pairs:
            found.add(f"{cp.upper()}USDT")

        return sorted(list(found))
