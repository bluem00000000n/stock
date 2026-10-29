"""
Upbit Spot Market Data Collector (KRW Market).
Connects to official public unauthenticated Upbit REST API (https://api.upbit.com/v1).
100% Zero Paid API Keys required.
Provides real-time Korean Won (KRW) price quotes, 24h change, volume, and OHLCV candles
for seamless multi-asset compounding alongside Korean and US equities.
"""

from datetime import datetime, timezone
from typing import List, Optional
import requests
from signal_forge.collectors.base import BaseCollector
from signal_forge.config import config
from signal_forge.models.signal import AssetType, Candle, MarketQuote
from signal_forge.observability.logger import get_logger
from signal_forge.observability.retry import retry_with_backoff

logger = get_logger("upbit_collector")


def normalize_upbit_symbol(symbol: str) -> str:
    """Normalizes symbol to Upbit KRW pair format (e.g., 'KRW-BTC', 'KRW-SOL')."""
    s = symbol.upper().strip()
    if s.startswith("KRW-"):
        return s
    if s.endswith("USDT"):
        s = s[:-4]
    if s.startswith("KRW"):
        s = s[3:]
    return f"KRW-{s}"


class UpbitCollector(BaseCollector):
    def __init__(self, base_url: str = "https://api.upbit.com/v1", is_mock: bool = False):
        super().__init__(name="upbit_krw", is_mock=is_mock)
        self.base_url = base_url.rstrip("/")
        self.timeout = config.scraper_timeout_sec
        self.headers = {"User-Agent": config.user_agent, "Accept": "application/json"}

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetches real-time trade price and 24h metrics from Upbit in KRW."""
        market_code = normalize_upbit_symbol(symbol)
        if self.is_mock:
            return self._mock_quote(market_code)

        url = f"{self.base_url}/ticker?markets={market_code}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"[UPBIT] Ticker fetch HTTP {resp.status_code} for {market_code}")
                return None
            items = resp.json()
            if not items or not isinstance(items, list):
                return None
            data = items[0]

            price = float(data.get("trade_price", 0.0))
            change_rate = float(data.get("signed_change_rate", 0.0)) * 100.0
            volume_24h = float(data.get("acc_trade_volume_24h", 0.0))
            high_24h = float(data.get("high_price", price))
            low_24h = float(data.get("low_price", price))

            self.last_collected_at = datetime.now(timezone.utc).isoformat()
            return MarketQuote(
                symbol=market_code,
                asset_type=AssetType.COIN,
                price=price,
                change_24h_pct=round(change_rate, 2),
                volume_24h=volume_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                funding_rate=0.0,  # Spot exchange (no funding rate)
                open_interest=0.0,
                source="upbit_public_krw",
            )
        except Exception as e:
            logger.error(f"[UPBIT] Failed to fetch quote for {market_code}: {e}")
            return None

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_klines(
        self, symbol: str, timeframe: str = "1h", limit: int = 60
    ) -> List[Candle]:
        """Fetches historical OHLCV candles from Upbit. Returns chronologically ascending candles."""
        market_code = normalize_upbit_symbol(symbol)
        if self.is_mock:
            return self._mock_candles(limit)

        # Map timeframe to Upbit endpoint
        if timeframe in ("1h", "60m"):
            url = f"{self.base_url}/candles/minutes/60?market={market_code}&count={limit}"
        elif timeframe == "15m":
            url = f"{self.base_url}/candles/minutes/15?market={market_code}&count={limit}"
        elif timeframe == "5m":
            url = f"{self.base_url}/candles/minutes/5?market={market_code}&count={limit}"
        elif timeframe in ("1d", "D"):
            url = f"{self.base_url}/candles/days?market={market_code}&count={limit}"
        else:
            url = f"{self.base_url}/candles/minutes/60?market={market_code}&count={limit}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.warning(f"[UPBIT] Candles fetch HTTP {resp.status_code} for {market_code}")
                return []
            raw_candles = resp.json()
            if not isinstance(raw_candles, list):
                return []

            # Upbit returns newest-first; reverse to chronological ascending order
            candles = []
            for c in reversed(raw_candles):
                candles.append(
                    Candle(
                        timestamp=int(c.get("timestamp", 0)),
                        open=float(c.get("opening_price", 0.0)),
                        high=float(c.get("high_price", 0.0)),
                        low=float(c.get("low_price", 0.0)),
                        close=float(c.get("trade_price", 0.0)),
                        volume=float(c.get("candle_acc_trade_volume", 0.0)),
                    )
                )
            return candles
        except Exception as e:
            logger.error(f"[UPBIT] Failed to fetch klines for {market_code}: {e}")
            return []

    def _mock_quote(self, symbol: str) -> MarketQuote:
        price_map = {
            "KRW-BTC": 110_000_000.0,
            "KRW-ETH": 3_250_000.0,
            "KRW-SOL": 140_000.0,
            "KRW-XRP": 850.0,
            "KRW-DOGE": 185.0,
        }
        price = price_map.get(symbol, 100_000.0)
        return MarketQuote(
            symbol=symbol,
            asset_type=AssetType.COIN,
            price=price,
            change_24h_pct=2.5,
            volume_24h=50_000.0,
            high_24h=price * 1.05,
            low_24h=price * 0.95,
            funding_rate=0.0,
            open_interest=0.0,
            source="upbit_mock_krw",
        )

    def _mock_candles(self, count: int) -> List[Candle]:
        candles = []
        base_time = int(datetime.now(timezone.utc).timestamp() * 1000)
        price = 140_000.0
        for i in range(count):
            candles.append(
                Candle(
                    timestamp=base_time - (count - i) * 3600 * 1000,
                    open=price * (1 + (i * 0.002)),
                    high=price * (1 + (i * 0.002) + 0.01),
                    low=price * (1 + (i * 0.002) - 0.01),
                    close=price * (1 + (i * 0.002) + 0.005),
                    volume=100.0 + i * 5,
                )
            )
        return candles
