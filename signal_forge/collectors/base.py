"""
Base Collector Interface.
All collectors implement timeout, retry, quality metadata, and zero external API keys.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from signal_forge.models.signal import Candle, MarketQuote
from signal_forge.observability.logger import get_logger

logger = get_logger("collector")


class BaseCollector(ABC):
    def __init__(self, name: str, is_mock: bool = False):
        self.name = name
        self.is_mock = is_mock
        self.last_collected_at: Optional[str] = None
        self.is_healthy: bool = True
        self.last_error: Optional[str] = None

    @abstractmethod
    def fetch_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Fetch current market quote for symbol."""
        pass

    @abstractmethod
    def fetch_klines(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ) -> List[Candle]:
        """Fetch historical candlestick data."""
        pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "is_mock": self.is_mock,
            "is_healthy": self.is_healthy,
            "last_collected_at": self.last_collected_at,
            "last_error": self.last_error,
        }
