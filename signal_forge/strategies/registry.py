"""
Strategy Registry and Catalog Manager.
Holds, discovers, and validates all 25 strategies (18 Stock LONG ONLY + 7 Crypto LONG/SHORT).
"""

from typing import Dict, List, Optional
from signal_forge.models.signal import AssetType, Direction
from signal_forge.strategies.base import BaseStrategy
from signal_forge.strategies.crypto import (
    PumpExhaustionShortStrategy,
    SilentDistributionShortStrategy,
    FailedBreakoutShortStrategy,
    VwapRejectionShortStrategy,
    MultiDayFadeShortStrategy,
    RealCatalystRunnerLongStrategy,
    ShortSqueezeRunnerLongStrategy,
)
from signal_forge.strategies.stocks import (
    EarlyBuzzStrategy,
    SilentAccumulationStrategy,
    GoodNewsSlowMoneyStrategy,
    CatalystBreakoutStrategy,
    FirstPullbackStrategy,
    SectorRotationStrategy,
    SectorSympathyStrategy,
    ExpectationFailureLongStrategy,
    ShortSqueezeLongStrategy,
    FailedPumpRecoveryStrategy,
    SupplyAbsorptionStrategy,
    HypeToFundamentalsStrategy,
    PostEarningsDriftStrategy,
    RelativeStrengthStrategy,
    MultiDayMomentumStrategy,
    FailedBreakdownStrategy,
    AttentionReboundStrategy,
    PredictionVerifiedStrategy,
)


class StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._register_default_strategies()

    def register(self, strategy: BaseStrategy) -> None:
        """Registers a strategy and validates contract rules."""
        # Contract rule validation
        if any(at in [AssetType.STOCK_KR, AssetType.STOCK_US] for at in strategy.asset_types):
            if Direction.SHORT in strategy.allowed_directions:
                raise ValueError(
                    f"Contract Violation in {strategy.strategy_id}: Stock strategies can NEVER allow Direction.SHORT!"
                )

        self._strategies[strategy.strategy_id] = strategy

    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        return self._strategies.get(strategy_id)

    def get_strategies_for_asset(self, asset_type: AssetType) -> List[BaseStrategy]:
        return [
            s for s in self._strategies.values()
            if asset_type in s.asset_types
        ]

    def list_all(self) -> List[BaseStrategy]:
        return list(self._strategies.values())

    def count(self) -> int:
        return len(self._strategies)

    def _register_default_strategies(self) -> None:
        # 18 Stock Strategies (LONG ONLY)
        stock_classes = [
            EarlyBuzzStrategy,
            SilentAccumulationStrategy,
            GoodNewsSlowMoneyStrategy,
            CatalystBreakoutStrategy,
            FirstPullbackStrategy,
            SectorRotationStrategy,
            SectorSympathyStrategy,
            ExpectationFailureLongStrategy,
            ShortSqueezeLongStrategy,
            FailedPumpRecoveryStrategy,
            SupplyAbsorptionStrategy,
            HypeToFundamentalsStrategy,
            PostEarningsDriftStrategy,
            RelativeStrengthStrategy,
            MultiDayMomentumStrategy,
            FailedBreakdownStrategy,
            AttentionReboundStrategy,
            PredictionVerifiedStrategy,
        ]
        for cls in stock_classes:
            self.register(cls())

        # 7 Crypto Strategies (LONG & SHORT)
        crypto_classes = [
            PumpExhaustionShortStrategy,
            SilentDistributionShortStrategy,
            FailedBreakoutShortStrategy,
            VwapRejectionShortStrategy,
            MultiDayFadeShortStrategy,
            RealCatalystRunnerLongStrategy,
            ShortSqueezeRunnerLongStrategy,
        ]
        for cls in crypto_classes:
            self.register(cls())


# Global singleton registry
strategy_registry = StrategyRegistry()
