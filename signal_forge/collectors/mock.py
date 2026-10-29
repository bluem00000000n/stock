"""
Deterministic Mock Collector for Testing & Offline Execution.
Generates controlled price action scenarios to reliably verify all 25 strategies.
"""

from typing import List, Optional
from signal_forge.collectors.base import BaseCollector
from signal_forge.models.signal import AssetType, Candle, MarketQuote


class MockMarketCollector(BaseCollector):
    def __init__(self, scenario: str = "bullish_breakout"):
        super().__init__(name="mock_collector", is_mock=True)
        self.scenario = scenario

    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        asset_type = AssetType.COIN if "USDT" in symbol else (AssetType.STOCK_KR if symbol.isdigit() else AssetType.STOCK_US)
        return MarketQuote(
            symbol=symbol,
            asset_type=asset_type,
            price=100.0,
            change_24h_pct=4.5,
            volume_24h=1000000.0,
            high_24h=102.0,
            low_24h=95.0,
            funding_rate=-0.0004 if self.scenario == "short_squeeze" else 0.0001,
            open_interest=50000.0,
            source="mock_collector",
            is_mock=True,
        )

    def fetch_klines(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        candles = []
        base_time = 1700000000000

        if self.scenario == "bullish_breakout":
            # 80 flat candles around 100, then last 20 breaking out to 130 on 4x volume
            for i in range(limit):
                t = base_time + i * 3600 * 1000
                if i < limit - 1:
                    p = 100.0 + (i % 3) * 0.5
                    v = 1000.0
                else:
                    p = 125.0  # Sharp breakout above prior 101.5
                    v = 4500.0  # 4.5x volume surge
                candles.append(Candle(timestamp=t, open=p - 0.5, high=p + 1.0, low=p - 1.0, close=p, volume=v))

        elif self.scenario == "pump_exhaustion_short":
            # Sharp parabolic surge to 200, followed by blow-off top and bearish engulfing
            for i in range(limit):
                t = base_time + i * 3600 * 1000
                if i < limit - 5:
                    p = 100.0 + i * 1.5
                    v = 1500.0 + i * 50
                elif i == limit - 5:
                    p = 200.0  # High blow-off
                    v = 10000.0
                else:
                    # Declining price and lower volume
                    p = 200.0 - (i - (limit - 5)) * 6.0
                    v = 3000.0
                candles.append(Candle(timestamp=t, open=p + 1.0, high=p + 2.0, low=p - 2.0, close=p, volume=v))

        elif self.scenario == "vwap_rejection_short":
            # High prices earlier, dropping below VWAP and rejected from underside
            for i in range(limit):
                t = base_time + i * 3600 * 1000
                if i < limit - 10:
                    p = 120.0
                    v = 5000.0
                else:
                    p = 95.0 - (i - (limit - 10)) * 1.0
                    v = 2000.0
                candles.append(Candle(timestamp=t, open=p + 0.5, high=p + 1.0, low=p - 1.0, close=p, volume=v))

        else:
            # Default steadily rising trend
            for i in range(limit):
                t = base_time + i * 3600 * 1000
                p = 100.0 + i * 0.2
                v = 1000.0 + i * 10
                candles.append(Candle(timestamp=t, open=p - 0.2, high=p + 0.5, low=p - 0.5, close=p, volume=v))

        return candles
