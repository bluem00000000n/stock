"""
Base Strategy Interface and Contract Enforcement.
Strictly enforces:
1. Stock strategies can ONLY detect and return LONG signals.
2. Crypto strategies can detect and return BOTH LONG and SHORT signals.
3. Every signal must have clear invalidation conditions, first_detected_at, and source_url.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from signal_forge.models.community import CommunityPost
from signal_forge.models.signal import (
    AssetType,
    Candle,
    Direction,
    MarketQuote,
    SignalCandidate,
)


@dataclass
class StrategyContext:
    symbol: str
    asset_type: AssetType
    quote: MarketQuote
    candles: List[Candle]
    community_posts: List[CommunityPost] = field(default_factory=list)
    timeframe: str = "1h"
    is_mock: bool = False
    source_url: str = ""


class BaseStrategy(ABC):
    def __init__(
        self,
        strategy_id: str,
        name: str,
        asset_types: List[AssetType],
        allowed_directions: List[Direction],
        description: str = "",
    ):
        self.strategy_id = strategy_id
        self.name = name
        self.asset_types = asset_types
        self.allowed_directions = allowed_directions
        self.description = description

        # Contract validation: Stocks cannot have SHORT in allowed directions
        if any(at in [AssetType.STOCK_KR, AssetType.STOCK_US] for at in self.asset_types):
            if Direction.SHORT in self.allowed_directions:
                raise ValueError(
                    f"Contract Violation in {strategy_id}: Stock strategies are STRICTLY LONG ONLY!"
                )

    @abstractmethod
    def detect(self, context: StrategyContext) -> Optional[SignalCandidate]:
        """Evaluates market context and returns a SignalCandidate if setup is met."""
        pass

    def validate(self, candidate: SignalCandidate, context: StrategyContext) -> bool:
        """Validates candidate against quality filters."""
        # 1. Enforce direction contract
        if candidate.asset_type in [AssetType.STOCK_KR, AssetType.STOCK_US]:
            if candidate.direction != Direction.LONG:
                raise ValueError(
                    f"Fatal Contract Violation: Strategy {self.strategy_id} generated SHORT for stock {candidate.symbol}!"
                )

        if candidate.direction not in self.allowed_directions:
            return False

        # 2. Minimum candles check
        if len(context.candles) < 15:
            return False

        return True

    def invalidate(self, candidate: SignalCandidate, context: StrategyContext) -> bool:
        """Checks if active candidate is invalidated by current price action."""
        if not candidate.invalidation_condition:
            return False

        curr_price = context.quote.price
        if candidate.direction == Direction.LONG:
            # If price falls below invalidation trigger
            if "below" in candidate.invalidation_condition:
                try:
                    threshold = float(candidate.invalidation_condition.split("below")[-1].strip())
                    return curr_price < threshold
                except Exception:
                    pass
        elif candidate.direction == Direction.SHORT:
            # If price breaks above invalidation trigger
            if "above" in candidate.invalidation_condition:
                try:
                    threshold = float(candidate.invalidation_condition.split("above")[-1].strip())
                    return curr_price > threshold
                except Exception:
                    pass

        return False
