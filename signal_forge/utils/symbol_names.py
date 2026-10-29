"""
Symbol Name & Ticker Resolver.
Provides human-friendly Korean and English names for stock codes and crypto tickers.
"""

from typing import Dict

SYMBOL_NAMES: Dict[str, str] = {
    # Korean Stocks (KRX)
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "005380": "현대차",
    "035420": "NAVER",
    "035720": "카카오",
    "068270": "셀트리온",
    "000270": "기아",
    "005490": "POSCO홀딩스",
    "105560": "KB금융",
    "055550": "신한지주",
    "012330": "현대모비스",
    "028260": "삼성물산",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "032830": "삼성생명",
    "011200": "HMM",
    "086520": "에코프로",
    "247540": "에코프로비엠",
    "096770": "SK이노베이션",

    # Upbit Crypto (KRW Pairs)
    "KRW-BTC": "비트코인",
    "KRW-ETH": "이더리움",
    "KRW-SOL": "솔라나",
    "KRW-XRP": "리플",
    "KRW-DOGE": "도지코인",
    "KRW-ADA": "에이다",
    "KRW-AVAX": "아발란체",
    "KRW-SUI": "수이",
    "KRW-DOT": "폴카닷",
    "KRW-LINK": "체인링크",
    "KRW-NEAR": "니어프로토콜",
    "KRW-SHIB": "시바이누",

    # Binance Crypto (USDT Pairs fallback)
    "BTCUSDT": "비트코인",
    "ETHUSDT": "이더리움",
    "SOLUSDT": "솔라나",
    "XRPUSDT": "리플",
    "DOGEUSDT": "도지코인",
    "ADAUSDT": "에이다",

    # US Stocks
    "AAPL": "애플",
    "NVDA": "엔비디아",
    "MSFT": "마이크로소프트",
    "AMZN": "아마존",
    "GOOGL": "구글",
    "META": "메타",
    "TSLA": "테슬라",
    "AMD": "AMD",
    "QQQ": "인베스코 QQQ",
    "SPY": "SPDR S&P 500",
}


def get_symbol_name(symbol: str) -> str:
    """Returns human-friendly name for a given ticker or stock code."""
    s = symbol.strip().upper()
    return SYMBOL_NAMES.get(s, "")


def format_symbol_display(symbol: str) -> str:
    """Formats symbol display with code/ticker and name (e.g., '068270 (셀트리온)', 'KRW-BTC (비트코인)').
    Omits redundant direction tags since the system operates strictly LONG ONLY.
    """
    name = get_symbol_name(symbol)
    if name:
        return f"{symbol} ({name})"
    return symbol
