"""
Thread-safe SQLite Database Manager for Signal Forge Alert.
Provides connection pooling, automated schema setup, and signal lifecycle operations.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from signal_forge.config import config
from signal_forge.models.community import CommunityPost
from signal_forge.models.signal import (
    AlertRecord,
    Candle,
    Direction,
    Signal,
    SignalStatus,
)
from signal_forge.observability.logger import get_logger

logger = get_logger("database")


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or config.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Initializes tables and indexes from schema.sql."""
        schema_file = Path(__file__).parent / "schema.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found at {schema_file}")
        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
        logger.debug(f"Database schema initialized at {self.db_path}")

    def save_signal(self, signal: Signal) -> bool:
        """Inserts a new signal candidate or returns False if already exists."""
        sql = """
        INSERT OR IGNORE INTO signals (
            signal_id, asset_type, symbol, direction, strategy_id, strategy_name,
            timeframe, price, trigger_reason, indicators_json, source_url,
            score, tier, invalidation_condition, first_detected_at, created_at,
            status, is_mock
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        try:
            with self.get_connection() as conn:
                cur = conn.execute(
                    sql,
                    (
                        signal.signal_id,
                        signal.asset_type.value,
                        signal.symbol,
                        signal.direction.value,
                        signal.strategy_id,
                        signal.strategy_name,
                        signal.timeframe,
                        signal.price,
                        signal.trigger_reason,
                        json.dumps(signal.indicators),
                        signal.source_url,
                        signal.score,
                        signal.tier.value,
                        signal.invalidation_condition,
                        signal.first_detected_at,
                        signal.created_at,
                        signal.status.value,
                        1 if signal.is_mock else 0,
                    ),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to save signal {signal.signal_id}: {e}")
            return False

    def is_duplicate_signal(
        self, symbol: str, strategy_id: str, direction: Direction, cooldown_minutes: int = 120
    ) -> bool:
        """Checks if a matching signal occurred within the cooldown window or was already alerted.
        
        Strict Deduplication ('한번 보낸 알람은 더이상 보내지 않는다'):
        1. Suppresses if symbol is currently held OPEN in compounding_positions.
        2. Suppresses if this symbol + strategy + direction was already ALERTED.
        3. Suppresses if a matching signal was created within cooldown window.
        """
        with self.get_connection() as conn:
            # 1. Holding position check: never send duplicate entry for a currently open position
            open_cnt = conn.execute(
                "SELECT COUNT(*) FROM compounding_positions WHERE symbol = ? AND status = 'OPEN';",
                (symbol,),
            ).fetchone()[0]
            if open_cnt > 0:
                return True

            # 2. Once alerted, never send again!
            alerted_cnt = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE symbol = ? AND strategy_id = ? AND direction = ? AND status = 'ALERTED';",
                (symbol, strategy_id, direction.value),
            ).fetchone()[0]
            if alerted_cnt > 0:
                return True

            # 3. Cooldown window check for recent NEW signals
            cutoff_dt = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
            cutoff_str = cutoff_dt.isoformat()
            sql = """
            SELECT COUNT(*) as count FROM signals
            WHERE symbol = ? AND strategy_id = ? AND direction = ?
              AND created_at >= ?
              AND status IN ('NEW', 'ALERTED');
            """
            row = conn.execute(sql, (symbol, strategy_id, direction.value, cutoff_str)).fetchone()
            count = row["count"] if row else 0
            return count > 0

    def get_last_signal(
        self, symbol: str, strategy_id: str, direction: Direction
    ) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT * FROM signals
        WHERE symbol = ? AND strategy_id = ? AND direction = ?
        ORDER BY created_at DESC LIMIT 1;
        """
        with self.get_connection() as conn:
            row = conn.execute(sql, (symbol, strategy_id, direction.value)).fetchone()
            return dict(row) if row else None

    def update_signal_status(self, signal_id: str, status: SignalStatus) -> None:
        sql = "UPDATE signals SET status = ? WHERE signal_id = ?;"
        with self.get_connection() as conn:
            conn.execute(sql, (status.value, signal_id))
            conn.commit()

    def save_alert_record(self, alert: AlertRecord) -> None:
        sql = """
        INSERT INTO alert_history (signal_id, channel, status, response_msg, sent_at)
        VALUES (?, ?, ?, ?, ?);
        """
        try:
            with self.get_connection() as conn:
                conn.execute(
                    sql,
                    (
                        alert.signal_id,
                        alert.channel,
                        alert.status,
                        alert.response_msg,
                        alert.sent_at,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError as e:
            logger.warning(f"Could not save alert record ({e}). Creating stub signal for {alert.signal_id} and retrying.")
            stub_sql = """
            INSERT OR IGNORE INTO signals (
                signal_id, asset_type, symbol, direction, strategy_id, strategy_name,
                timeframe, price, trigger_reason, source_url, first_detected_at, created_at, status
            ) VALUES (?, 'COIN', 'UNKNOWN', 'LONG', 'TEST', 'Test Alert', '1h', 0.0, 'Stub', '', datetime('now'), datetime('now'), 'NEW');
            """
            try:
                with self.get_connection() as conn:
                    conn.execute(stub_sql, (alert.signal_id,))
                    conn.execute(
                        sql,
                        (
                            alert.signal_id,
                            alert.channel,
                            alert.status,
                            alert.response_msg,
                            alert.sent_at,
                        ),
                    )
                    conn.commit()
            except Exception as inner_e:
                logger.error(f"Failed saving alert record for {alert.signal_id}: {inner_e}")
        except Exception as e:
            logger.error(f"Failed to save alert record: {e}")

    def save_community_post(self, post: CommunityPost) -> bool:
        sql = """
        INSERT OR IGNORE INTO community_posts (
            source_platform, channel_name, post_id, post_url, author, raw_text,
            published_at, collected_at, content_hash, mentioned_symbols,
            has_7d_surge_claim, claimed_direction, claimed_target_price,
            is_promotional_scam, sentiment_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        try:
            with self.get_connection() as conn:
                cur = conn.execute(
                    sql,
                    (
                        post.source_platform,
                        post.channel_name,
                        post.post_id,
                        post.post_url,
                        post.author,
                        post.raw_text,
                        post.published_at,
                        post.collected_at,
                        post.content_hash,
                        ",".join(post.mentioned_symbols),
                        1 if post.has_7d_surge_claim else 0,
                        post.claimed_direction,
                        post.claimed_target_price,
                        1 if post.is_promotional_scam else 0,
                        post.sentiment_score,
                    ),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to save community post: {e}")
            return False

    def cache_candles(
        self, symbol: str, timeframe: str, candles: List[Candle], source: str
    ) -> None:
        sql = """
        INSERT OR REPLACE INTO market_data_cache (
            symbol, timeframe, candle_timestamp, open, high, low, close, volume, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            params = [
                (
                    symbol,
                    timeframe,
                    c.timestamp,
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.volume,
                    source,
                )
                for c in candles
            ]
            conn.executemany(sql, params)
            conn.commit()

    def get_cached_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> List[Candle]:
        sql = """
        SELECT candle_timestamp, open, high, low, close, volume
        FROM market_data_cache
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_timestamp ASC
        LIMIT ?;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (symbol, timeframe, limit)).fetchall()
            return [
                Candle(
                    timestamp=r["candle_timestamp"],
                    open=r["open"],
                    high=r["high"],
                    low=r["low"],
                    close=r["close"],
                    volume=r["volume"],
                )
                for r in rows
            ]

    def record_execution_log(self, task_name: str, status: str, message: str) -> None:
        sql = """
        INSERT INTO execution_logs (task_name, status, message, created_at)
        VALUES (?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            conn.execute(
                sql,
                (
                    task_name,
                    status,
                    message,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def record_signal_outcome(
        self,
        signal_id: str,
        evaluation_timeframe: str,
        entry_price: float,
        evaluated_price: float,
        return_pct: float,
        mfe_pct: float,
        mae_pct: float,
        hit_target: bool,
    ) -> None:
        sql = """
        INSERT OR REPLACE INTO signal_outcomes (
            signal_id, evaluation_timeframe, entry_price, evaluated_price,
            return_pct, max_favorable_excursion_pct, max_adverse_excursion_pct,
            hit_target, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            conn.execute(
                sql,
                (
                    signal_id,
                    evaluation_timeframe,
                    entry_price,
                    evaluated_price,
                    return_pct,
                    mfe_pct,
                    mae_pct,
                    1 if hit_target else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_performance_summary(self) -> Dict[str, Any]:
        """Calculates win rate, sample counts, and average return for verified signals."""
        sql = """
        SELECT 
            COUNT(*) as total_outcomes,
            SUM(hit_target) as total_hits,
            AVG(return_pct) as avg_return,
            AVG(max_favorable_excursion_pct) as avg_mfe,
            AVG(max_adverse_excursion_pct) as avg_mae
        FROM signal_outcomes;
        """
        with self.get_connection() as conn:
            row = conn.execute(sql).fetchone()
            total = row["total_outcomes"] or 0
            hits = row["total_hits"] or 0
            win_rate = (hits / total * 100.0) if total > 0 else 0.0
            return {
                "total_evaluated_samples": total,
                "hit_count": hits,
                "win_rate_pct": round(win_rate, 2),
                "avg_return_pct": round(row["avg_return"] or 0.0, 2),
                "avg_mfe_pct": round(row["avg_mfe"] or 0.0, 2),
                "avg_mae_pct": round(row["avg_mae"] or 0.0, 2),
            }

    def get_or_create_compounding_portfolio(
        self, mode: str = "ULTRA", initial_capital_krw: float = 1_000_000.0
    ) -> Dict[str, Any]:
        """Gets active compounding portfolio or creates one with initial capital."""
        sql = "SELECT * FROM compounding_portfolio WHERE mode = ? ORDER BY id DESC LIMIT 1;"
        with self.get_connection() as conn:
            row = conn.execute(sql, (mode,)).fetchone()
            if row:
                return dict(row)

            now_iso = datetime.now(timezone.utc).isoformat()
            insert_sql = """
            INSERT INTO compounding_portfolio (
                mode, initial_capital_krw, current_cash_krw, equity_krw, peak_equity_krw,
                max_drawdown_pct, total_trades, winning_trades, losing_trades,
                total_net_pnl_krw, total_fee_krw, started_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0.0, 0, 0, 0, 0.0, 0.0, ?, ?);
            """
            cur = conn.execute(
                insert_sql,
                (mode, initial_capital_krw, initial_capital_krw, initial_capital_krw, initial_capital_krw, now_iso, now_iso),
            )
            conn.commit()
            new_row = conn.execute("SELECT * FROM compounding_portfolio WHERE id = ?;", (cur.lastrowid,)).fetchone()
            return dict(new_row)

    def update_compounding_portfolio(
        self,
        mode: str,
        current_cash_krw: float,
        equity_krw: float,
        peak_equity_krw: float,
        max_drawdown_pct: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        total_net_pnl_krw: float,
        total_fee_krw: float,
    ) -> None:
        sql = """
        UPDATE compounding_portfolio SET
            current_cash_krw = ?,
            equity_krw = ?,
            peak_equity_krw = ?,
            max_drawdown_pct = ?,
            total_trades = ?,
            winning_trades = ?,
            losing_trades = ?,
            total_net_pnl_krw = ?,
            total_fee_krw = ?,
            updated_at = ?
        WHERE mode = ?;
        """
        with self.get_connection() as conn:
            conn.execute(
                sql,
                (
                    current_cash_krw,
                    equity_krw,
                    peak_equity_krw,
                    max_drawdown_pct,
                    total_trades,
                    winning_trades,
                    losing_trades,
                    total_net_pnl_krw,
                    total_fee_krw,
                    datetime.now(timezone.utc).isoformat(),
                    mode,
                ),
            )
            conn.commit()

    def get_open_compounding_positions(self) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM compounding_positions WHERE status = 'OPEN' ORDER BY entry_time ASC;"
        with self.get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    def save_compounding_position(self, pos: Dict[str, Any]) -> bool:
        sql = """
        INSERT INTO compounding_positions (
            position_id, symbol, asset_type, direction, strategy_id, strategy_name,
            signal_id, entry_price, current_price, quantity, invested_krw,
            stop_loss_price, target_price, trailing_stop_price, highest_price, lowest_price,
            unrealized_pnl_pct, unrealized_pnl_krw, status, entry_time, fee_krw
        ) VALUES (
            :position_id, :symbol, :asset_type, :direction, :strategy_id, :strategy_name,
            :signal_id, :entry_price, :current_price, :quantity, :invested_krw,
            :stop_loss_price, :target_price, :trailing_stop_price, :highest_price, :lowest_price,
            :unrealized_pnl_pct, :unrealized_pnl_krw, :status, :entry_time, :fee_krw
        );
        """
        with self.get_connection() as conn:
            conn.execute(sql, pos)
            conn.commit()
            return True

    def update_compounding_position_mark(
        self,
        position_id: str,
        current_price: float,
        highest_price: float,
        lowest_price: float,
        trailing_stop_price: float,
        unrealized_pnl_pct: float,
        unrealized_pnl_krw: float,
    ) -> None:
        sql = """
        UPDATE compounding_positions SET
            current_price = ?,
            highest_price = ?,
            lowest_price = ?,
            trailing_stop_price = ?,
            unrealized_pnl_pct = ?,
            unrealized_pnl_krw = ?
        WHERE position_id = ?;
        """
        with self.get_connection() as conn:
            conn.execute(
                sql,
                (
                    current_price,
                    highest_price,
                    lowest_price,
                    trailing_stop_price,
                    unrealized_pnl_pct,
                    unrealized_pnl_krw,
                    position_id,
                ),
            )
            conn.commit()

    def close_compounding_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        realized_pnl_krw: float,
        realized_pnl_pct: float,
        fee_krw: float,
    ) -> None:
        sql = """
        UPDATE compounding_positions SET
            status = 'CLOSED',
            exit_time = ?,
            exit_price = ?,
            exit_reason = ?,
            realized_pnl_krw = ?,
            realized_pnl_pct = ?,
            fee_krw = fee_krw + ?
        WHERE position_id = ?;
        """
        with self.get_connection() as conn:
            conn.execute(
                sql,
                (
                    datetime.now(timezone.utc).isoformat(),
                    exit_price,
                    exit_reason,
                    realized_pnl_krw,
                    realized_pnl_pct,
                    fee_krw,
                    position_id,
                ),
            )
            conn.commit()

    def record_compounding_trade(self, trade: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM compounding_trades;").fetchone()[0]
            trade_num = cnt + 1
            params = dict(trade)
            params["trade_num"] = trade_num
            sql = """
            INSERT INTO compounding_trades (
                trade_num, position_id, symbol, asset_type, direction,
                strategy_id, strategy_name, entry_time, exit_time, entry_price, exit_price,
                quantity, invested_krw, exit_value_krw, gross_pnl_pct, fee_krw,
                net_pnl_krw, net_return_pct, portfolio_ending_balance, exit_reason
            ) VALUES (
                :trade_num, :position_id, :symbol, :asset_type, :direction,
                :strategy_id, :strategy_name, :entry_time, :exit_time, :entry_price, :exit_price,
                :quantity, :invested_krw, :exit_value_krw, :gross_pnl_pct, :fee_krw,
                :net_pnl_krw, :net_return_pct, :portfolio_ending_balance, :exit_reason
            );
            """
            cur = conn.execute(sql, params)
            conn.commit()
            return trade_num

    def get_compounding_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM compounding_trades ORDER BY trade_num DESC LIMIT ?;"
        with self.get_connection() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]


# Default global instance
db = DatabaseManager()

