"""
US Stock Market Data Collector (NYSE & NASDAQ).
Collects public market data from unauthenticated endpoints with zero API keys.
Uses high-reliability public endpoints (Naver Global / Yahoo Chart) with fallback.
Strictly read-only observation.
"""

from datetime import datetime, timezone
from typing import List, Optional
import requests
from signal_forge.collectors.base import BaseCollector
from signal_forge.config import config
from signal_forge.models.signal import AssetType, Candle, MarketQuote
from signal_forge.observability.logger import get_logger

logger = get_logger("us_stock_collector")


def _resolve_us_symbol_code(symbol: str) -> str:
    s = symbol.upper().strip()
    if "." in s:
        return s
    if s in ("SPY", "DIA", "VTI", "VOO", "IVV"):
        return s
    return f"{s}.O"


class USStockCollector(BaseCollector):
    def __init__(self, is_mock: bool = False):
        super().__init__(name="us_stocks", is_mock=is_mock)
        self.headers = {"User-Agent": config.user_agent}
        self.timeout = config.scraper_timeout_sec

    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetches quote for US stock ticker (e.g. 'AAPL', 'NVDA')."""
        if self.is_mock:
            return self._mock_quote(symbol)

        symbol = symbol.upper()
        naver_code = _resolve_us_symbol_code(symbol)

        # 1. Primary: Naver Public Global Stock Endpoint
        try:
            url = f"https://api.stock.naver.com/stock/{naver_code}/basic"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                price = float(str(data.get("closePrice") or 0).replace(",", ""))
                change_pct = float(str(data.get("fluctuationsRatio") or 0).replace(",", ""))
                high_price = float(str(data.get("highPrice", price)).replace(",", "")) if "highPrice" in data else price
                low_price = float(str(data.get("lowPrice", price)).replace(",", "")) if "lowPrice" in data else price
                volume = float(str(data.get("accumulatedTradingVolume") or data.get("volume", 0)).replace(",", ""))

                self.last_collected_at = datetime.now(timezone.utc).isoformat()
                self.is_healthy = True

                return MarketQuote(
                    symbol=symbol,
                    asset_type=AssetType.STOCK_US,
                    price=price,
                    change_24h_pct=round(change_pct, 2),
                    volume_24h=volume,
                    high_24h=high_price,
                    low_24h=low_price,
                    source="naver_global_public",
                    is_mock=False,
                )
        except Exception as e:
            logger.debug(f"Naver US quote failed for {symbol}: {e}")

        # 2. Secondary fallback: Yahoo Public Chart
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                meta = data["chart"]["result"][0]["meta"]
                price = float(meta.get("regularMarketPrice", 0.0))
                prev_close = float(meta.get("chartPreviousClose", price))
                change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else 0.0

                self.last_collected_at = datetime.now(timezone.utc).isoformat()
                self.is_healthy = True

                return MarketQuote(
                    symbol=symbol,
                    asset_type=AssetType.STOCK_US,
                    price=price,
                    change_24h_pct=round(change_pct, 2),
                    volume_24h=float(meta.get("regularMarketVolume", 0.0)),
                    high_24h=float(meta.get("regularMarketDayHigh", price)),
                    low_24h=float(meta.get("regularMarketDayLow", price)),
                    source="yahoo_public_chart",
                    is_mock=False,
                )
        except Exception as e:
            logger.warning(f"Live US quote failed for {symbol}: {e}. Falling back to mock quote.")

        return self._mock_quote(symbol)

    def fetch_klines(
        self, symbol: str, timeframe: str = "1d", limit: int = 100
    ) -> List[Candle]:
        """Fetches candlestick bars for US stock ticker."""
        if self.is_mock:
            return self._mock_klines(symbol, limit)

        symbol = symbol.upper()
        naver_code = _resolve_us_symbol_code(symbol)

        # 1. Primary: Naver Public Global Stock Prices Endpoint
        try:
            url = f"https://api.stock.naver.com/stock/{naver_code}/price?page=1&pageSize={limit}"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    candles = []
                    # Reversed because data is descending (newest first)
                    for item in reversed(data):
                        c = float(str(item.get("closePrice", 0)).replace(",", ""))
                        o = float(str(item.get("openPrice", c)).replace(",", ""))
                        h = float(str(item.get("highPrice", max(o, c))).replace(",", ""))
                        l = float(str(item.get("lowPrice", min(o, c))).replace(",", ""))
                        # Parse traded date
                        dt_str = item.get("localTradedAt", "")
                        try:
                            dt = datetime.fromisoformat(dt_str)
                            ts = int(dt.timestamp() * 1000)
                        except Exception:
                            ts = int(datetime.now(timezone.utc).timestamp() * 1000)

                        candles.append(Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=1000000.0))

                    if candles:
                        self.last_collected_at = datetime.now(timezone.utc).isoformat()
                        return candles[-limit:]
        except Exception as e:
            logger.debug(f"Naver US klines failed for {symbol}: {e}")

        # 2. Secondary fallback: Yahoo Public Chart
        rng = "1y" if limit > 60 else "3mo"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={rng}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                res = data["chart"]["result"][0]
                timestamps = res["timestamp"]
                indicators = res["indicators"]["quote"][0]

                candles = []
                for i in range(len(timestamps)):
                    o = indicators["open"][i]
                    h = indicators["high"][i]
                    l = indicators["low"][i]
                    c = indicators["close"][i]
                    v = indicators["volume"][i]
                    if o is not None and c is not None:
                        candles.append(
                            Candle(
                                timestamp=int(timestamps[i] * 1000),
                                open=float(o),
                                high=float(h if h is not None else o),
                                low=float(l if l is not None else o),
                                close=float(c),
                                volume=float(v if v is not None else 0.0),
                            )
                        )
                if candles:
                    self.last_collected_at = datetime.now(timezone.utc).isoformat()
                    return candles[-limit:]
        except Exception as e:
            logger.warning(f"Live US klines failed for {symbol}: {e}. Falling back to mock klines.")

        return self._mock_klines(symbol, limit)

    def _mock_quote(self, symbol: str) -> MarketQuote:
        prices = {
            "AAPL": 343.46,
            "MSFT": 529.05,
            "NVDA": 214.13,
            "AMZN": 250.00,
            "GOOGL": 340.59,
            "META": 709.33,
            "TSLA": 354.72,
            "AMD": 528.75,
            "QQQ": 709.80,
            "SPY": 763.25,
        }
        p = prices.get(symbol.upper(), 185.50)
        return MarketQuote(
            symbol=symbol,
            asset_type=AssetType.STOCK_US,
            price=p,
            change_24h_pct=1.85,
            volume_24h=52000000.0,
            high_24h=p * 1.02,
            low_24h=p * 0.98,
            source="us_stock_mock",
            is_mock=True,
        )

    def _mock_klines(self, symbol: str, limit: int = 100) -> List[Candle]:
        import time
        prices = {
            "AAPL": 340.0,
            "MSFT": 525.0,
            "NVDA": 210.0,
            "AMZN": 245.0,
            "GOOGL": 335.0,
            "META": 700.0,
            "TSLA": 350.0,
            "AMD": 520.0,
            "QQQ": 705.0,
            "SPY": 758.0,
        }
        base_price = prices.get(symbol.upper(), 150.0)
        step = base_price * 0.002
        now_ms = int(time.time() * 1000)
        candles = []
        for i in range(limit):
            t = now_ms - (limit - i) * 86400 * 1000
            o = base_price + i * step
            h = o + step * 2.0
            l = o - step * 1.5
            c = o + step * 0.8
            v = 25000000.0 + i * 50000
            candles.append(Candle(timestamp=t, open=o, high=h, low=l, close=c, volume=v))
        return candles
