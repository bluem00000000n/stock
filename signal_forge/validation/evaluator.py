"""
Quant Outcome Validator & Post-Signal Performance Evaluator.
Evaluates historical post-signal performance:
- Stock Timeframes: 1D, 3D, 5D, 7D, 20D
- Crypto Timeframes: 1h, 4h, 24h, 3D, 7D, 20D
- Computes MFE (Maximum Favorable Excursion), MAE (Maximum Adverse Excursion),
  directional win-rate, and target achievement.
Strictly non-trading performance observation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from signal_forge.database.db import DatabaseManager, db
from signal_forge.models.signal import Candle
from signal_forge.observability.logger import get_logger

logger = get_logger("quant_evaluator")

# Horizon mapping: timeframe label -> candle count
HORIZON_STEPS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
    "1d": 1,
    "3d": 3,
    "5d": 5,
    "7d": 7,
    "20d": 20,
}


class QuantOutcomeValidator:
    def __init__(self, database: DatabaseManager = db):
        self.db = database

    def evaluate_all_signals(self) -> Dict[str, Any]:
        """Evaluates all historical signals against cached market candles."""
        sql = """
        SELECT signal_id, asset_type, symbol, direction, strategy_id, strategy_name,
               price, timeframe, created_at, status
        FROM signals
        WHERE is_mock = 0
          AND symbol NOT LIKE 'TEST%'
          AND trigger_reason NOT LIKE '%Test alert%'
        ORDER BY created_at ASC;
        """
        with self.db.get_connection() as conn:
            signals = conn.execute(sql).fetchall()

        evaluated_count = 0
        skipped_count = 0

        for sig in signals:
            sig_dict = dict(sig)
            outcomes = self._evaluate_signal(sig_dict)
            if outcomes:
                for o in outcomes:
                    self.db.record_signal_outcome(
                        signal_id=o["signal_id"],
                        evaluation_timeframe=o["evaluation_timeframe"],
                        entry_price=o["entry_price"],
                        evaluated_price=o["evaluated_price"],
                        return_pct=o["return_pct"],
                        mfe_pct=o["mfe_pct"],
                        mae_pct=o["mae_pct"],
                        hit_target=o["hit_target"],
                    )
                evaluated_count += 1
            else:
                skipped_count += 1

        summary = self.get_comprehensive_metrics()
        logger.info(
            f"Quant evaluation completed: {evaluated_count} signals evaluated, "
            f"{skipped_count} skipped. Total outcome records: {summary['total_evaluated_samples']}"
        )
        return summary

    def _evaluate_signal(self, sig: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluates single signal across appropriate time horizons."""
        symbol = sig["symbol"]
        asset_type = sig["asset_type"]
        direction = sig["direction"]
        entry_price = float(sig["price"])
        signal_id = sig["signal_id"]

        tf_candle = "1h" if asset_type == "COIN" else "1d"
        candles = self.db.get_cached_candles(symbol, tf_candle, limit=100)
        if not candles or len(candles) < 2:
            return []

        # Sanity filter: ignore candles from disparate test scenarios (>5x price disparity)
        valid_candles = [
            c for c in candles if 0.2 * entry_price <= c.close <= 5.0 * entry_price
        ]
        if len(valid_candles) < 2:
            return []

        # Target time horizons
        if asset_type == "COIN":
            horizons = ["1h", "4h", "24h", "3d", "7d"]
        else:
            horizons = ["1d", "3d", "5d", "7d", "20d"]

        outcomes = []
        n_candles = len(valid_candles)

        for hz in horizons:
            steps = HORIZON_STEPS.get(hz, 1)
            window = valid_candles[-steps:] if steps <= n_candles else valid_candles
            if not window:
                continue

            highs = [c.high for c in window]
            lows = [c.low for c in window]
            last_close = window[-1].close

            max_h = max(highs)
            min_l = min(lows)

            if direction == "LONG":
                return_pct = round(((last_close - entry_price) / entry_price) * 100.0, 2)
                mfe_pct = round(((max_h - entry_price) / entry_price) * 100.0, 2)
                mae_pct = round(((min_l - entry_price) / entry_price) * 100.0, 2)
                hit_target = mfe_pct >= 2.0
            else:  # SHORT
                return_pct = round(((entry_price - last_close) / entry_price) * 100.0, 2)
                mfe_pct = round(((entry_price - min_l) / entry_price) * 100.0, 2)
                mae_pct = round(((entry_price - max_h) / entry_price) * 100.0, 2)
                hit_target = mfe_pct >= 2.0

            outcomes.append({
                "signal_id": signal_id,
                "evaluation_timeframe": hz,
                "entry_price": entry_price,
                "evaluated_price": last_close,
                "return_pct": return_pct,
                "mfe_pct": mfe_pct,
                "mae_pct": mae_pct,
                "hit_target": hit_target,
            })

        return outcomes

    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Returns deep statistical analysis of outcomes."""
        summary = self.db.get_performance_summary()

        # Breakdown by strategy
        sql_strat = """
        SELECT s.strategy_id, s.strategy_name, s.direction, s.asset_type,
               COUNT(o.id) as sample_count,
               SUM(o.hit_target) as hits,
               AVG(o.return_pct) as avg_return,
               AVG(o.max_favorable_excursion_pct) as avg_mfe,
               AVG(o.max_adverse_excursion_pct) as avg_mae
        FROM signal_outcomes o
        JOIN signals s ON o.signal_id = s.signal_id
        GROUP BY s.strategy_id, s.strategy_name, s.direction, s.asset_type
        ORDER BY hits DESC, avg_return DESC;
        """

        # Breakdown by market
        sql_market = """
        SELECT s.asset_type,
               COUNT(o.id) as sample_count,
               SUM(o.hit_target) as hits,
               AVG(o.return_pct) as avg_return,
               AVG(o.max_favorable_excursion_pct) as avg_mfe,
               AVG(o.max_adverse_excursion_pct) as avg_mae
        FROM signal_outcomes o
        JOIN signals s ON o.signal_id = s.signal_id
        GROUP BY s.asset_type;
        """

        # Breakdown by timeframe
        sql_tf = """
        SELECT evaluation_timeframe,
               COUNT(id) as sample_count,
               SUM(hit_target) as hits,
               AVG(return_pct) as avg_return,
               AVG(max_favorable_excursion_pct) as avg_mfe,
               AVG(max_adverse_excursion_pct) as avg_mae
        FROM signal_outcomes
        GROUP BY evaluation_timeframe
        ORDER BY sample_count DESC;
        """

        with self.db.get_connection() as conn:
            strat_rows = conn.execute(sql_strat).fetchall()
            market_rows = conn.execute(sql_market).fetchall()
            tf_rows = conn.execute(sql_tf).fetchall()

        strategies = []
        for r in strat_rows:
            cnt = r["sample_count"]
            h = r["hits"] or 0
            wr = round((h / cnt * 100.0), 1) if cnt > 0 else 0.0
            strategies.append({
                "strategy_id": r["strategy_id"],
                "strategy_name": r["strategy_name"],
                "direction": r["direction"],
                "asset_type": r["asset_type"],
                "sample_count": cnt,
                "hit_count": h,
                "win_rate_pct": wr,
                "avg_return_pct": round(r["avg_return"] or 0.0, 2),
                "avg_mfe_pct": round(r["avg_mfe"] or 0.0, 2),
                "avg_mae_pct": round(r["avg_mae"] or 0.0, 2),
            })

        markets = {}
        for r in market_rows:
            cnt = r["sample_count"]
            h = r["hits"] or 0
            wr = round((h / cnt * 100.0), 1) if cnt > 0 else 0.0
            markets[r["asset_type"]] = {
                "sample_count": cnt,
                "hit_count": h,
                "win_rate_pct": wr,
                "avg_return_pct": round(r["avg_return"] or 0.0, 2),
                "avg_mfe_pct": round(r["avg_mfe"] or 0.0, 2),
                "avg_mae_pct": round(r["avg_mae"] or 0.0, 2),
            }

        timeframes = {}
        for r in tf_rows:
            cnt = r["sample_count"]
            h = r["hits"] or 0
            wr = round((h / cnt * 100.0), 1) if cnt > 0 else 0.0
            timeframes[r["evaluation_timeframe"]] = {
                "sample_count": cnt,
                "hit_count": h,
                "win_rate_pct": wr,
                "avg_return_pct": round(r["avg_return"] or 0.0, 2),
                "avg_mfe_pct": round(r["avg_mfe"] or 0.0, 2),
                "avg_mae_pct": round(r["avg_mae"] or 0.0, 2),
            }

        return {
            **summary,
            "strategies": strategies,
            "markets": markets,
            "timeframes": timeframes,
        }


# Global default instance
quant_validator = QuantOutcomeValidator()
