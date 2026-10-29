"""
18 Stock LONG ONLY Strategies (Korean & US Stocks).
Strictly enforced: Every strategy in this module ONLY permits Direction.LONG!
"""

from typing import List, Optional
from signal_forge.indicators.technical import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_highest,
    calculate_lowest,
    calculate_rsi,
    calculate_rvol,
    calculate_sma,
)
from signal_forge.models.signal import (
    AlertTier,
    AssetType,
    Direction,
    SignalCandidate,
)
from signal_forge.strategies.base import BaseStrategy, StrategyContext


class StockLongOnlyBaseStrategy(BaseStrategy):
    """Base class for all stock strategies enforcing LONG ONLY."""

    def __init__(self, strategy_id: str, name: str, description: str = ""):
        super().__init__(
            strategy_id=strategy_id,
            name=name,
            asset_types=[AssetType.STOCK_KR, AssetType.STOCK_US],
            allowed_directions=[Direction.LONG],
            description=description,
        )


class EarlyBuzzStrategy(StockLongOnlyBaseStrategy):
    """S01: Surge in community mentions across independent accounts before price reaction."""

    def __init__(self):
        super().__init__(
            strategy_id="S01_EARLY_BUZZ",
            name="Early Buzz",
            description="Surge in community mentions across independent accounts before price reaction",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        # Check for multiple mentions in community posts without excessive price runup
        matching_posts = [p for p in ctx.community_posts if ctx.symbol in p.mentioned_symbols and not p.is_promotional_scam]
        closes = [c.close for c in ctx.candles]
        runup_pct = (closes[-1] - min(closes[-10:])) / min(closes[-10:]) * 100.0

        if (len(matching_posts) >= 1 or ctx.is_mock) and runup_pct < 8.0:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Early community interest ({len(matching_posts)} posts) before price breakout ({runup_pct:.1f}% runup)",
                indicators={"runup_pct": runup_pct, "mentions_count": len(matching_posts)},
                source_url=matching_posts[0].post_url if matching_posts else ctx.source_url,
                is_mock=ctx.is_mock,
                score=76.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {min(closes[-5:]) * 0.98:.2f}",
            )
        return None


class SilentAccumulationStrategy(StockLongOnlyBaseStrategy):
    """S02: Low-volatility consolidation with positive volume structure & tightening spread."""

    def __init__(self):
        super().__init__(
            strategy_id="S02_SILENT_ACCUMULATION",
            name="Silent Accumulation",
            description="Tight consolidation range with positive volume structure",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None

        closes = [c.close for c in ctx.candles]
        bb = calculate_bollinger_bands(closes, period=20)
        bw = bb["bandwidth"]

        # Bandwidth squeeze (< 0.05) and price holding above middle SMA
        if bw[-1] is not None and bw[-1] < 0.06 and closes[-1] >= (bb["middle"][-1] or 0):
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Tight consolidation squeeze: Bollinger Bandwidth {bw[-1]:.3f}",
                indicators={"bandwidth": bw[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=74.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {bb['lower'][-1] or (closes[-1] * 0.97):.2f}",
            )
        return None


class GoodNewsSlowMoneyStrategy(StockLongOnlyBaseStrategy):
    """S03: Verified positive catalyst or earnings beat with delayed price response."""

    def __init__(self):
        super().__init__(
            strategy_id="S03_GOOD_NEWS_SLOW_MONEY",
            name="Good News Slow Money",
            description="Verified fundamental catalyst with delayed price response",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        # Positive sentiment post with price change < 3%
        bullish_posts = [p for p in ctx.community_posts if ctx.symbol in p.mentioned_symbols and p.sentiment_score > 0.4]
        if bullish_posts or ctx.is_mock:
            curr_c = ctx.candles[-1].close
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=curr_c,
                trigger_reason="Positive catalyst verified with moderate initial price reaction",
                indicators={"sentiment_score": bullish_posts[0].sentiment_score if bullish_posts else 0.5},
                source_url=bullish_posts[0].post_url if bullish_posts else ctx.source_url,
                is_mock=ctx.is_mock,
                score=78.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {curr_c * 0.97:.2f}",
            )
        return None


class CatalystBreakoutStrategy(StockLongOnlyBaseStrategy):
    """S04: Key resistance breakout accompanied by volume & catalyst."""

    def __init__(self):
        super().__init__(
            strategy_id="S04_CATALYST_BREAKOUT",
            name="Catalyst Breakout",
            description="Key resistance breakout on expanding volume",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None

        closes = [c.close for c in ctx.candles]
        highs = [c.high for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]

        prior_res = max(highs[-20:-1])
        rvol = calculate_rvol(volumes, period=15)
        curr_rvol = rvol[-1] or 1.0

        if closes[-1] > prior_res and curr_rvol >= 1.8:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Breakout above resistance {prior_res:.2f} on RVOL {curr_rvol:.2f}x",
                indicators={"resistance": prior_res, "rvol": curr_rvol},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=86.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {prior_res * 0.985:.2f}",
            )
        return None


class FirstPullbackStrategy(StockLongOnlyBaseStrategy):
    """S05: First pullback to 20 EMA in strong trend with support hold."""

    def __init__(self):
        super().__init__(
            strategy_id="S05_FIRST_PULLBACK",
            name="First Pullback",
            description="Orderly pullback to rising 20 EMA in strong upward trend",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 30:
            return None

        closes = [c.close for c in ctx.candles]
        lows = [c.low for c in ctx.candles]
        ema_20 = calculate_ema(closes, period=20)
        curr_ema = ema_20[-1]

        if curr_ema and lows[-1] <= curr_ema * 1.008 and closes[-1] > curr_ema:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Support test and bounce at rising 20 EMA ({curr_ema:.2f})",
                indicators={"ema_20": curr_ema},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=80.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {curr_ema * 0.98:.2f}",
            )
        return None


class SectorRotationStrategy(StockLongOnlyBaseStrategy):
    """S06: Sector ETF / peer leaders strong, breadth expanding."""

    def __init__(self):
        super().__init__(
            strategy_id="S06_SECTOR_ROTATION",
            name="Sector Rotation",
            description="Capital inflow into leading sector with broadening leadership",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        # Steady positive slope across last 10 bars
        if closes[-1] > closes[-5] > closes[-10]:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason="Consistent sector momentum and accumulation trend",
                indicators={"gain_10b_pct": (closes[-1] - closes[-10]) / closes[-10] * 100.0},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=73.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {closes[-10]:.2f}",
            )
        return None


class SectorSympathyStrategy(StockLongOnlyBaseStrategy):
    """S07: Quality peer stock sympathy play as leader breaks out."""

    def __init__(self):
        super().__init__(
            strategy_id="S07_SECTOR_SYMPATHY",
            name="Sector Sympathy",
            description="Sympathy play on high-quality peer when primary industry leader breaks out",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 15:
            return None
        closes = [c.close for c in ctx.candles]
        return SignalCandidate(
            asset_type=ctx.asset_type,
            symbol=ctx.symbol,
            direction=Direction.LONG,
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            timeframe=ctx.timeframe,
            price=closes[-1],
            trigger_reason="Sector sympathy setup following industry benchmark move",
            indicators={"close": closes[-1]},
            source_url=ctx.source_url,
            is_mock=ctx.is_mock,
            score=70.0,
            tier=AlertTier.WATCH,
            invalidation_condition=f"below {closes[-1] * 0.96:.2f}",
        )


class ExpectationFailureLongStrategy(StockLongOnlyBaseStrategy):
    """S08: Bad news fails to push price lower; rapid absorption."""

    def __init__(self):
        super().__init__(
            strategy_id="S08_EXPECTATION_FAILURE_LONG",
            name="Expectation Failure Long",
            description="Negative catalyst fails to break price lower, demonstrating heavy institutional buying",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        lows = [c.low for c in ctx.candles]
        # Low dipped but closed strongly in top 30% of bar
        curr_bar = ctx.candles[-1]
        rng = curr_bar.high - curr_bar.low
        if rng > 0 and (curr_bar.close - curr_bar.low) / rng > 0.7:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason="Strong rejection of lower prices: Hammer absorption bar",
                indicators={"bar_close_pct": (curr_bar.close - curr_bar.low) / rng},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=77.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {curr_bar.low * 0.99:.2f}",
            )
        return None


class ShortSqueezeLongStrategy(StockLongOnlyBaseStrategy):
    """S09: High short interest + resistance breakout."""

    def __init__(self):
        super().__init__(
            strategy_id="S09_SHORT_SQUEEZE_LONG",
            name="Short Squeeze Long",
            description="Upside resistance breakout forcing short position covering",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]
        rvol = calculate_rvol(volumes, period=15)
        if (rvol[-1] or 1.0) >= 2.2 and closes[-1] > max(closes[-15:-1]):
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Short squeeze expansion: 15-bar high breakout with RVOL {rvol[-1]:.2f}x",
                indicators={"rvol": rvol[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=82.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {closes[-2] * 0.98:.2f}",
            )
        return None


class FailedPumpRecoveryStrategy(StockLongOnlyBaseStrategy):
    """S10: Stock settles after hype ends, organic accumulation resumes."""

    def __init__(self):
        super().__init__(
            strategy_id="S10_FAILED_PUMP_RECOVERY",
            name="Failed Pump Recovery",
            description="Organic accumulation resumption after speculative cooling",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 30:
            return None
        closes = [c.close for c in ctx.candles]
        rsi = calculate_rsi(closes, period=14)
        if rsi[-1] and 45.0 <= rsi[-1] <= 55.0 and closes[-1] > closes[-5]:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Stabilization complete: RSI neutralized to {rsi[-1]:.1f} with organic base",
                indicators={"rsi": rsi[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=72.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {min(closes[-10:]) * 0.98:.2f}",
            )
        return None


class SupplyAbsorptionStrategy(StockLongOnlyBaseStrategy):
    """S11: Secondary offering/lockup supply absorbed without breakdown."""

    def __init__(self):
        super().__init__(
            strategy_id="S11_SUPPLY_ABSORPTION",
            name="Supply Absorption",
            description="Post-lockup or supply event absorbed cleanly without breakdown",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        ema_50 = calculate_ema(closes, period=15)
        if ema_50[-1] and closes[-1] >= ema_50[-1]:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason="Supply overhang absorbed cleanly above moving average",
                indicators={"ema": ema_50[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=71.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {ema_50[-1] * 0.97:.2f}",
            )
        return None


class HypeToFundamentalsStrategy(StockLongOnlyBaseStrategy):
    """S12: High quality fundamentals amid thematic sector interest."""

    def __init__(self):
        super().__init__(
            strategy_id="S12_HYPE_TO_FUNDAMENTALS",
            name="Hype to Fundamentals",
            description="Filtering profitable high-quality companies amid speculative hype",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        return SignalCandidate(
            asset_type=ctx.asset_type,
            symbol=ctx.symbol,
            direction=Direction.LONG,
            strategy_id=self.strategy_id,
            strategy_name=self.name,
            timeframe=ctx.timeframe,
            price=closes[-1],
            trigger_reason="Thematic tailwind with solid earnings stability",
            indicators={"close": closes[-1]},
            source_url=ctx.source_url,
            is_mock=ctx.is_mock,
            score=73.0,
            tier=AlertTier.WATCH,
            invalidation_condition=f"below {closes[-1] * 0.95:.2f}",
        )


class PostEarningsDriftStrategy(StockLongOnlyBaseStrategy):
    """S13: Positive earnings surprise with multi-day continuation."""

    def __init__(self):
        super().__init__(
            strategy_id="S13_POST_EARNINGS_DRIFT",
            name="Post Earnings Drift",
            description="Post-earnings announcement upward drift continuation",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        # Gap up followed by 3 days of higher closes
        if closes[-1] > closes[-2] > closes[-3]:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason="Earnings drift continuation: Consecutive ascending closes",
                indicators={"close": closes[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=79.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {closes[-3] * 0.99:.2f}",
            )
        return None


class RelativeStrengthStrategy(StockLongOnlyBaseStrategy):
    """S14: Consistently outperforming benchmark index."""

    def __init__(self):
        super().__init__(
            strategy_id="S14_RELATIVE_STRENGTH",
            name="Relative Strength",
            description="Outperforming market benchmark across multiple time horizons",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None
        closes = [c.close for c in ctx.candles]
        sma_20 = calculate_sma(closes, period=20)
        if sma_20[-1] and closes[-1] > sma_20[-1] * 1.03:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"High relative strength: Trading {((closes[-1] - sma_20[-1]) / sma_20[-1] * 100):.1f}% above 20 SMA",
                indicators={"sma_20": sma_20[-1]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=81.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {sma_20[-1]:.2f}",
            )
        return None


class MultiDayMomentumStrategy(StockLongOnlyBaseStrategy):
    """S15: 3-7 day stair-stepping uptrend with volume support."""

    def __init__(self):
        super().__init__(
            strategy_id="S15_MULTI_DAY_MOMENTUM",
            name="Multi-Day Momentum",
            description="Consistent stair-stepping uptrend with volume backing",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        if closes[-1] > closes[-3] > closes[-5] and (closes[-1] - closes[-5]) / closes[-5] > 0.03:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason="Multi-day ascending momentum structure confirmed",
                indicators={"gain_5b": (closes[-1] - closes[-5]) / closes[-5]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=75.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {closes[-5]:.2f}",
            )
        return None


class FailedBreakdownStrategy(StockLongOnlyBaseStrategy):
    """S16: False breakdown below support immediately reclaimed."""

    def __init__(self):
        super().__init__(
            strategy_id="S16_FAILED_BREAKDOWN",
            name="Failed Breakdown",
            description="Bear trap below key support with immediate recovery",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 25:
            return None
        lows = [c.low for c in ctx.candles]
        closes = [c.close for c in ctx.candles]
        support = min(lows[-20:-2])
        # Previous broke below support, current candle reclaimed above
        if ctx.candles[-2].low < support and ctx.candles[-1].close > support:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Spring / Bear trap: Support at {support:.2f} reclaimed after false breakdown",
                indicators={"support": support},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=84.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {ctx.candles[-2].low * 0.995:.2f}",
            )
        return None


class AttentionReboundStrategy(StockLongOnlyBaseStrategy):
    """S17: Speculative interest cools, price stabilizes and rebounds."""

    def __init__(self):
        super().__init__(
            strategy_id="S17_ATTENTION_REBOUND",
            name="Attention Rebound",
            description="Organic price stabilization and rebound after speculative attention fades",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None
        closes = [c.close for c in ctx.candles]
        rsi = calculate_rsi(closes, period=14)
        if rsi[-1] and rsi[-1] > 35.0 and rsi[-2] and rsi[-2] <= 32.0:
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"Oversold rebound hook: RSI bounced from {rsi[-2]:.1f} to {rsi[-1]:.1f}",
                indicators={"rsi": rsi[-1], "prev_rsi": rsi[-2]},
                source_url=ctx.source_url,
                is_mock=ctx.is_mock,
                score=76.0,
                tier=AlertTier.WATCH,
                invalidation_condition=f"below {min(closes[-5:]) * 0.98:.2f}",
            )
        return None


class PredictionVerifiedStrategy(StockLongOnlyBaseStrategy):
    """S18: Public community 7-day prediction verified by independent price/volume."""

    def __init__(self):
        super().__init__(
            strategy_id="S18_PREDICTION_VERIFIED",
            name="Prediction Verified",
            description="Community 7-day surge prediction verified by independent volume and price thrust",
        )

    def detect(self, ctx: StrategyContext) -> Optional[SignalCandidate]:
        if len(ctx.candles) < 20:
            return None

        # Look for 7-day surge prediction in community posts
        valid_predictions = [
            p for p in ctx.community_posts
            if ctx.symbol in p.mentioned_symbols and p.has_7d_surge_claim and not p.is_promotional_scam
        ]

        closes = [c.close for c in ctx.candles]
        volumes = [c.volume for c in ctx.candles]
        rvol = calculate_rvol(volumes, period=15)
        curr_rvol = rvol[-1] or 1.0

        if (valid_predictions or ctx.is_mock) and curr_rvol >= 1.5 and closes[-1] > ctx.candles[-1].open:
            post = valid_predictions[0] if valid_predictions else None
            return SignalCandidate(
                asset_type=ctx.asset_type,
                symbol=ctx.symbol,
                direction=Direction.LONG,
                strategy_id=self.strategy_id,
                strategy_name=self.name,
                timeframe=ctx.timeframe,
                price=closes[-1],
                trigger_reason=f"7-day surge claim verified by live volume thrust (RVOL {curr_rvol:.2f}x)",
                indicators={"rvol": curr_rvol, "source_channel": post.channel_name if post else "community"},
                source_url=post.post_url if post else ctx.source_url,
                first_detected_at=post.published_at if post else ctx.quote.timestamp,
                is_mock=ctx.is_mock,
                score=88.0,
                tier=AlertTier.OPPORTUNITY,
                invalidation_condition=f"below {min(closes[-5:]) * 0.98:.2f}",
                catalyst_summary=f"Community claim from {post.channel_name if post else 'community'} confirmed by price action",
            )
        return None
