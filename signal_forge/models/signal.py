"""
Core domain models for market data, signals, and alerts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
from datetime import datetime, timezone


class AssetType(str, Enum):
    COIN = "COIN"
    STOCK_KR = "STOCK_KR"
    STOCK_US = "STOCK_US"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class AlertTier(str, Enum):
    INFO = "INFO"
    WATCH = "WATCH"
    OPPORTUNITY = "OPPORTUNITY"
    HIGH_CONVICTION = "HIGH_CONVICTION"
    RISK_WARNING = "RISK_WARNING"
    DATA_DEGRADED = "DATA_DEGRADED"


class SignalStatus(str, Enum):
    NEW = "NEW"
    ALERTED = "ALERTED"
    SKIPPED_DEDUP = "SKIPPED_DEDUP"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"


@dataclass
class Candle:
    timestamp: int  # Milliseconds UTC
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketQuote:
    symbol: str
    asset_type: AssetType
    price: float
    change_24h_pct: float
    volume_24h: float
    high_24h: float
    low_24h: float
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    mark_price: Optional[float] = None
    source: str = "binance_public"
    is_mock: bool = False
    timestamp: int = field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp() * 1000))


@dataclass
class SignalCandidate:
    asset_type: AssetType
    symbol: str
    direction: Direction
    strategy_id: str
    strategy_name: str
    timeframe: str
    price: float
    trigger_reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    source_url: str = ""
    first_detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_mock: bool = False
    score: float = 50.0
    tier: AlertTier = AlertTier.WATCH
    invalidation_condition: str = ""
    catalyst_summary: str = ""
    risk_notes: List[str] = field(default_factory=list)

    @property
    def signal_id(self) -> str:
        """Deterministic ID based on symbol, strategy, direction, and day/hour window."""
        raw = f"{self.asset_type.value}:{self.symbol}:{self.strategy_id}:{self.direction.value}:{self.first_detected_at[:13]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class Signal(SignalCandidate):
    status: SignalStatus = SignalStatus.NEW
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AlertRecord:
    signal_id: str
    channel: str = "TELEGRAM"
    status: str = "SUCCESS"
    response_msg: str = ""
    sent_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
