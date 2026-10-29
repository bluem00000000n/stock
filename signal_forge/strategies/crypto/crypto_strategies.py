"""
7 Binance Futures Crypto Strategies (Supporting BOTH LONG & SHORT).
C01: PUMP EXHAUSTION SHORT
C02: SILENT DISTRIBUTION SHORT
C03: FAILED BREAKOUT SHORT
C04: VWAP REJECTION SHORT
C05: MULTI DAY FADE SHORT
C06: REAL CATALYST RUNNER LONG
C07: SHORT SQUEEZE RUNNER LONG
"""

from typing import List, Optional
from signal_forge.indicators.technical import (
    calculate_ema,
    calculate_highest,
    calculate_lowest,
    calculate_macd,
    calculate_rsi,
    calculate_rvol,
    calculate_vwap,
)
from signal_forge.models.signal import (
    AlertTier,
    AssetType,
    Direction,
    SignalCandidate,
)
from signal_forge.strategies.base import BaseStrategy, StrategyContext


class PumpExhaustionShortStrategy(BaseStrategy):
    """C01: Parabolic blow-off top failing to make new highs with volume divergence (SHORT)."""

    def __init__(self):
        super().__init__(
            strategy_id="C01_PUMP_EXHAUSTION_SHORT",
            name="Pump Exhaustion Short",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.SHORT],
            description="Parabolic blow-off top failing to make new highs with volume exhaustion",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None

        closes = [c.close for c in ctx.candles]
        highs = [c.high for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]

        rsi = calculate_rsi(closes, period=14)
        curr_rsi = rsi[-1]
        prev_rsi = rsi[-2]

        recent_high = max(highs[-20:-2])
        curr_close = closes[-1]
        curr_high = highs[-1]

        # Condition: Recent price spiked near or above recent high, RSI was overbought (>70) and now hooking down
        is_exhaustion = (
            curr_rsi is not None
            and prev_rsi is not None
            and prev_rsi > 68.0
            and curr_rsi < prev_rsi
            and curr_close < ctx.candles[-1].open  # Bearish candle
        )

        if is_exhaustion:
            stop_loss = curr_high * 1.015
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.SHORT,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_close,
                trigger_reason=f"Exhaustion top detected: RSI reversed from {prev_rsi:.1f} to {curr_rsi:.1f} with bearish rejection",
                indicators={"rsi": curr_rsi, "prev_rsi": prev_rsi, "resistance": recent_high},
                source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                is_mock=ctx.is_mock,
                score=78.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"above {stop_loss:.4f}",
                catalyst_summary="Blow-off pump exhaustion structure confirmed",
                risk_notes=["Watch for sudden late short squeeze if volume spikes again"],
            )
        return None


class SilentDistributionShortStrategy(BaseStrategy):
    """C02: Fading excitement and distribution on high volume down-candles (SHORT)."""

    def __init__(self):
        super().__init__(
            strategy_id="C02_SILENT_DISTRIBUTION_SHORT",
            name="Silent Distribution Short",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.SHORT],
            description="Fading community momentum and institutional distribution on down candles",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        closes = [c.close for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]
        ema_20 = calculate_ema(closes, period=20)

        # Down candle with higher volume than 20-period average
        curr_c = closes[-1]
        curr_o = ctx.candles[-1].open
        rvol = calculate_rvol(volumes, period=15)
        curr_rvol = rvol[-1] or 1.0

        is_distribution = (
            curr_c < curr_o  # Red candle
            and curr_rvol > 1.3
            and ema_20[-1] is not None
            and curr_c < ema_20[-1]
        )

        if is_distribution:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.SHORT,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_c,
                trigger_reason=f"Distribution selling below 20 EMA with RVOL {curr_rvol:.2f}x",
                indicators={"rvol": curr_rvol, "ema_20": ema_20[-1]},
                source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                is_mock=ctx.is_mock,
                score=72.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"above {ctx.candles[-1].high * 1.01:.4f}",
            )
        return None


class FailedBreakoutShortStrategy(BaseStrategy):
    """C03: Bull trap above key resistance followed by aggressive rejection back inside (SHORT)."""

    def __init__(self):
        super().__init__(
            strategy_id="C03_FAILED_BREAKOUT_SHORT",
            name="Failed Breakout Short",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.SHORT],
            description="Bull trap above resistance falling back into consolidation range",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None

        highs = [c.high for c in ctx.candles]
        closes = [c.close for c in ctx.candles]

        # Prior resistance over last 20 bars excluding last 2
        prior_res = max(highs[-22:-2])
        prev_candle = ctx.candles[-2]
        curr_candle = ctx.candles[-1]

        # Failed break: previous broke above, current closed back below
        if prev_candle.high > prior_res and curr_candle.close < prior_res:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.SHORT,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_candle.close,
                trigger_reason=f"Bull trap: Price breached resistance {prior_res:.4f} but rejected back inside",
                indicators={"resistance": prior_res, "false_break_high": prev_candle.high},
                source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                is_mock=ctx.is_mock,
                score=80.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"above {prev_candle.high * 1.005:.4f}",
            )
        return None


class VwapRejectionShortStrategy(BaseStrategy):
    """C04: Price below session VWAP, tests VWAP from below and gets rejected (SHORT)."""

    def __init__(self):
        super().__init__(
            strategy_id="C04_VWAP_REJECTION_SHORT",
            name="VWAP Rejection Short",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.SHORT],
            description="Price rejected from session VWAP underside",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        highs = [c.high for c in ctx.candles]
        lows = [c.low for c in ctx.candles]
        closes = [c.close for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]

        vwap = calculate_vwap(highs, lows, closes, volumes)
        curr_vwap = vwap[-1]
        curr_c = closes[-1]
        curr_h = highs[-1]

        if curr_vwap is not None:
            # High touched near VWAP but closed below VWAP with red candle
            if curr_h >= curr_vwap * 0.998 and curr_c < curr_vwap * 0.995 and curr_c < ctx.candles[-1].open:
                return SignalCandidate(
                    asset_type=ctx.asset_type,
                    symbol=ctx.symbol,
                    direction=Direction.SHORT,
                    strategy_id=self.strategy_id,
                    strategy_name=self.name,
                    timeframe=ctx.timeframe,
                    price=curr_c,
                    trigger_reason=f"Underside VWAP rejection at {curr_vwap:.4f}",
                    indicators={"vwap": curr_vwap},
                    source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                    is_mock=ctx.is_mock,
                    score=74.0,
                    tier=AlertTier.WATCH,
                    invalidation_condition=f"above {curr_vwap * 1.01:.4f}",
                )
        return None


class MultiDayFadeShortStrategy(BaseStrategy):
    """C05: 3-7 days extended rally showing momentum decay (SHORT)."""

    def __init__(self):
        super().__init__(
            strategy_id="C05_MULTI_DAY_FADE_SHORT",
            name="Multi-Day Fade Short",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.SHORT],
            description="Momentum exhaustion after multi-day extension",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 30:
            return None

        closes = [c.close for c in ctx.candles]
        macd = calculate_macd(closes)
        hist = macd["histogram"]

        # MACD histogram decreasing for 3 consecutive bars after an uptrend
        if hist[-1] is not None and hist[-2] is not None and hist[-3] is not None:
            if hist[-3] > hist[-2] > hist[-1] and hist[-1] < 0:
                curr_c = closes[-1]
                return SignalCandidate(
                    asset_type=ctx.asset_type,
                    symbol=ctx.symbol,
                    direction=Direction.SHORT,
                    strategy_id=self.strategy_id,
                    strategy_name=self.name,
                    timeframe=ctx.timeframe,
                    price=curr_c,
                    trigger_reason="Multi-day upward momentum fading: MACD histogram crossed negative",
                    indicators={"macd_hist": hist[-1]},
                    source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                    is_mock=ctx.is_mock,
                    score=71.0,
                    tier=AlertTier.WATCH,
                    invalidation_condition=f"above {max([c.high for c in ctx.candles[-5:]]) * 1.01:.4f}",
                )
        return None


class RealCatalystRunnerLongStrategy(BaseStrategy):
    """C06: Genuine catalyst, multi-timeframe volume surge breaking resistance (LONG)."""

    def __init__(self):
        super().__init__(
            strategy_id="C06_REAL_CATALYST_RUNNER_LONG",
            name="Real Catalyst Runner Long",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.LONG],
            description="Verified catalyst with expanding volume and directional breakout",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        closes = [c.close for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]
        highs = [c.high for c in ctx.candles]

        rvol = calculate_rvol(volumes, period=15)
        curr_rvol = rvol[-1] or 1.0
        prior_res = max(highs[-20:-1])
        curr_c = closes[-1]

        # Breakout on volume > 2.0x
        if curr_c > prior_res and curr_rvol >= 2.0:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_c,
                trigger_reason=f"Breakout above {prior_res:.4f} with RVOL {curr_rvol:.2f}x volume surge",
                indicators={"rvol": curr_rvol, "resistance": prior_res},
                source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                is_mock=ctx.is_mock,
                score=85.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {prior_res * 0.985:.4f}",
            )
        return None


class ShortSqueezeRunnerLongStrategy(BaseStrategy):
    """C07: Heavy negative funding rate or rising Open Interest breaking out upward (LONG)."""

    def __init__(self):
        super().__init__(
            strategy_id="C07_SHORT_SQUEEZE_RUNNER_LONG",
            name="Short Squeeze Runner Long",
            asset_types=[AssetType.COIN],
            allowed_directions=[Direction.LONG],
            description="Short squeeze triggered by negative funding rates and breakout price action",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 15:
            return None

        funding = ctx.quote.funding_rate
        closes = [c.close for c in ctx.candles]
        curr_c = closes[-1]
        ema_10 = calculate_ema(closes, period=10)

        # Trigger on negative funding (< -0.0002) with bullish candle closing above 10 EMA
        is_negative_funding = (funding is not None and funding <= -0.00015) or (ctx.is_mock and funding is not None and funding < 0)
        is_bullish_close = ema_10[-1] is not None and curr_c > ema_10[-1] and curr_c > ctx.candles[-1].open

        if is_negative_funding and is_bullish_close:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_c,
                trigger_reason=f"Short squeeze setup: Negative funding rate ({funding:.6f}) with upward thrust",
                indicators={"funding_rate": funding, "ema_10": ema_10[-1]},
                source_url=ctx.source_url or f"https://www.binance.com/en/futures/{ctx.symbol}",
                is_mock=ctx.is_mock,
                score=83.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {ctx.candles[-1].low * 0.99:.4f}",
            )
        return None
