"""
Korean Stock Market Data Collector (KOSPI & KOSDAQ).
Scrapes public unauthenticated Naver Finance endpoints with zero API keys.
Strictly read-only observation.
"""

from datetime import datetime, timezone
from typing import List, Optional
import requests
from signal_forge.collectors.base import BaseCollector
from signal_forge.config import config
from signal_forge.models.signal import AssetType, Candle, MarketQuote
from signal_forge.observability.logger import get_logger

logger = get_logger("kr_stock_collector")


class KoreanStockCollector(BaseCollector):
    def __init__(self, is_mock: bool = False):
        super().__init__(name="korean_stocks", is_mock=is_mock)
        self.headers = {"User-Agent": config.user_agent}
        self.timeout = config.scraper_timeout_sec

    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetches current price and 24h change for Korean stock code (e.g. '005930')."""
        if self.is_mock:
            return self._mock_quote(symbol)

        url = f"https://m.stock.naver.com/api/stock/{symbol}/basic"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                price = float(str(data.get("closePrice") or data.get("nowPrice") or 0).replace(",", ""))
                change_rate = float(str(data.get("fluctuationsRatio") or data.get("fluctuationRate") or 0).replace(",", ""))
                high_price = float(str(data.get("highPrice", price)).replace(",", ""))
                low_price = float(str(data.get("lowPrice", price)).replace(",", ""))
                volume = float(str(data.get("accumulatedTradingVolume", 0)).replace(",", ""))

                self.last_collected_at = datetime.now(timezone.utc).isoformat()
                self.is_healthy = True

                return MarketQuote(
                    symbol=symbol,
                    asset_type=AssetType.STOCK_KR,
                    price=price,
                    change_24h_pct=change_rate,
                    volume_24h=volume,
                    high_24h=high_price,
                    low_24h=low_price,
                    source="naver_finance_public",
                    is_mock=False,
                )
        except Exception as e:
            logger.warning(f"Live KR stock quote failed for {symbol}: {e}. Falling back to mock quote.")

        return self._mock_quote(symbol)

    def fetch_klines(
        self, symbol: str, timeframe: str = "1d", limit: int = 100
    ) -> List[Candle]:
        """Fetches daily candles for Korean stock."""
        if self.is_mock:
            return self._mock_klines(symbol, limit)

        url = f"https://m.stock.naver.com/api/stock/{symbol}/price?page=1&pageSize={limit}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                candles = []
                for row in reversed(data):
                    close_p = float(str(row.get("closePrice", 0)).replace(",", ""))
                    open_p = float(str(row.get("openPrice", close_p)).replace(",", ""))
                    high_p = float(str(row.get("highPrice", close_p)).replace(",", ""))
                    low_p = float(str(row.get("lowPrice", close_p)).replace(",", ""))
                    vol = float(str(row.get("accumulatedTradingVolume", 0)).replace(",", ""))
                    dt_str = row.get("localTradedAt", "")
                    
                    # Convert date to ms
                    dt = datetime.strptime(dt_str, "%Y-%m-%d") if dt_str else datetime.now(timezone.utc)
                    t_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

                    candles.append(
                        Candle(
                            timestamp=t_ms,
                            open=open_p,
                            high=high_p,
                            low=low_p,
                            close=close_p,
                            volume=vol,
                        )
                    )
                if candles:
                    self.last_collected_at = datetime.now(timezone.utc).isoformat()
                    return candles
        except Exception as e:
            logger.warning(f"Live KR stock klines failed for {symbol}: {e}. Falling back to mock klines.")

        return self._mock_klines(symbol, limit)

    def _mock_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol,
            asset_type=AssetType.STOCK_KR,
            price=72500.0,
            change_24h_pct=2.11,
            volume_24h=14500000.0,
            high_24h=73000.0,
            low_24h=71200.0,
            source="kr_stock_mock",
            is_mock=True,
        )

    def _mock_klines(self, symbol: str, limit: int = 100) -> List[Candle]:
        import time
        now_ms = int(time.time() * 1000)
        candles = []
        base_price = 70000.0
        for i in range(limit):
            t = now_ms - (limit - i) * 86400 * 1000
            o = base_price + i * 50
            h = o + 300
            l = o - 200
            c = o + 100
            v = 500000.0 + i * 1000
            candles.append(Candle(timestamp=t, open=o, high=h, low=l, close=c, volume=v))
        return candles
