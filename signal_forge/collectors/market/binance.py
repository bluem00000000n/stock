"""
Binance USDⓈ-M Futures Market Data Collector.
Connects strictly to official public Binance Futures API (fapi.binance.com).
Zero API key required. Read-only market data collection.
"""

from datetime import datetime, timezone
from typing import List, Optional
import requests
from signal_forge.collectors.base import BaseCollector
from signal_forge.config import config
from signal_forge.models.signal import AssetType, Candle, MarketQuote
from signal_forge.observability.logger import get_logger
from signal_forge.observability.retry import retry_with_backoff

logger = get_logger("binance_collector")


class BinanceFuturesCollector(BaseCollector):
    def __init__(self, base_url: Optional[str] = None, is_mock: bool = False):
        super().__init__(name="binance_futures", is_mock=is_mock)
        self.base_url = (base_url or config.binance_base_url).rstrip("/")
        self.timeout = config.binance_timeout_sec

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetches 24hr ticker, funding rate, and open interest for symbol."""
        if self.is_mock:
            return self._mock_quote(symbol)

        symbol = symbol.upper()
        url = f"{self.base_url}/fapi/v1/ticker/24hr?symbol={symbol}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Optional funding rate lookup
            funding_rate = None
            try:
                f_resp = requests.get(
                    f"{self.base_url}/fapi/v1/fundingRate?symbol={symbol}&limit=1",
                    timeout=self.timeout,
                )
                if f_resp.status_code == 200:
                    f_data = f_resp.json()
                    if f_data:
                        funding_rate = float(f_data[-1]["fundingRate"])
            except Exception:
                pass

            # Optional open interest lookup
            open_interest = None
            try:
                oi_resp = requests.get(
                    f"{self.base_url}/fapi/v1/openInterest?symbol={symbol}",
                    timeout=self.timeout,
                )
                if oi_resp.status_code == 200:
                    oi_data = oi_resp.json()
                    open_interest = float(oi_data.get("openInterest", 0.0))
            except Exception:
                pass

            self.last_collected_at = datetime.now(timezone.utc).isoformat()
            self.is_healthy = True

            return MarketQuote(
                symbol=symbol,
                asset_type=AssetType.COIN,
                price=float(data["lastPrice"]),
                change_24h_pct=float(data["priceChangePercent"]),
                volume_24h=float(data["volume"]),
                high_24h=float(data["highPrice"]),
                low_24h=float(data["lowPrice"]),
                funding_rate=funding_rate,
                open_interest=open_interest,
                source="binance_public_api",
                is_mock=False,
                timestamp=int(data["closeTime"]),
            )
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            logger.error(f"Error fetching Binance quote for {symbol}: {e}")
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_klines(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        """Fetches historical candlestick bars from Binance Futures."""
        if self.is_mock:
            return self._mock_klines(symbol, limit)

        symbol = symbol.upper()
        url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={timeframe}&limit={limit}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            candles: List[Candle] = []
            for item in data:
                candles.append(
                    Candle(
                        timestamp=int(item[0]),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                    )
                )

            self.last_collected_at = datetime.now(timezone.utc).isoformat()
            self.is_healthy = True
            return candles
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            logger.error(f"Error fetching Binance klines for {symbol} ({timeframe}): {e}")
            raise

    def _mock_quote(self, symbol: str) -> MarketQuote:
        price_map = {
            "BTCUSDT": 81400.0,
            "ETHUSDT": 2410.0,
            "SOLUSDT": 104.0,
            "BNBUSDT": 716.0,
            "XRPUSDT": 1.30,
            "DOGEUSDT": 0.08,
            "ADAUSDT": 0.22,
            "LINKUSDT": 12.0,
            "AVAXUSDT": 10.0,
            "SUIUSDT": 1.0,
        }
        p = price_map.get(symbol.upper(), 100.0)
        return MarketQuote(
            symbol=symbol,
            asset_type=AssetType.COIN,
            price=p,
            change_24h_pct=3.45,
            volume_24h=12500000.0,
            high_24h=p * 1.02,
            low_24h=p * 0.98,
            funding_rate=-0.00035,
            open_interest=45000.0,
            source="binance_mock",
            is_mock=True,
        )

    def _mock_klines(self, symbol: str, limit: int = 100) -> List[Candle]:
        import time
        price_map = {
            "BTCUSDT": 81000.0,
            "ETHUSDT": 2400.0,
            "SOLUSDT": 103.0,
            "BNBUSDT": 715.0,
            "XRPUSDT": 1.29,
            "DOGEUSDT": 0.079,
            "ADAUSDT": 0.22,
            "LINKUSDT": 11.9,
            "AVAXUSDT": 9.8,
            "SUIUSDT": 0.98,
        }
        now_ms = int(time.time() * 1000)
        candles = []
        base_price = price_map.get(symbol.upper(), 100.0)
        step = base_price * 0.001
        for i in range(limit):
            t = now_ms - (limit - i) * 3600 * 1000
            o = base_price + (i % 5) * step
            h = o + step * 2.0
            l = o - step * 1.5
            c = o + step * 0.5
            v = 1000.0 + i * 20
            candles.append(Candle(timestamp=t, open=o, high=h, low=l, close=c, volume=v))
        return candles
