"""
Live Compounding Paper Trading & Execution Engine.
Simulates real-world order execution with 1,000,000 KRW initial capital.
Mode: ULTRA (concentrated high-conviction runner strategies with Kelly fractional sizing).
Maintains exact position tracking, trailing stop management, stop-loss discipline, swap executions, and fee deductions in SQLite.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from signal_forge.alerts.telegram import telegram_dispatcher
from signal_forge.config import config
from signal_forge.database.db import DatabaseManager, db
from signal_forge.models.signal import AlertTier, AssetType, Direction, SignalCandidate
from signal_forge.observability.logger import get_logger
from signal_forge.utils.market_calendar import is_market_open
from signal_forge.utils.symbol_names import format_symbol_display

logger = get_logger("compounding_engine")


class LiveCompoundingTrader:
    def __init__(
        self,
        mode: str = "ULTRA",
        initial_capital_krw: float = 1_000_000.0,
        usd_krw_rate: float = 1380.0,
        enforce_market_hours: bool = True,
        database: DatabaseManager = db,
    ):
        self.mode = mode
        self.initial_capital_krw = initial_capital_krw
        self.usd_krw_rate = usd_krw_rate
        self.enforce_market_hours = enforce_market_hours
        self.db = database
        self.dispatcher = telegram_dispatcher

        # Risk & Sizing Parameters (Ultra Mode)
        self.max_concurrent_positions = 2       # Concentrated portfolio (up to 2 runner bets)
        self.target_position_pct = 0.50         # 50% sizing per position (Kelly fractional)
        self.liquidity_order_cap_krw = 500_000_000.0  # 500M KRW realistic liquidity cap
        self.crypto_fee_rate = 0.0005           # 0.05% taker commission per leg (0.10% roundtrip)
        self.stock_fee_rate = 0.0010            # 0.10% commission/tax per leg (0.20% roundtrip)
        self.stop_loss_pct = 5.2                # Strict 5.2% stop-loss threshold

        # Pending alert queues for aggregating simultaneous alerts
        self.pending_entries: List[Dict[str, Any]] = []
        self.pending_exits: List[Dict[str, Any]] = []

        # Ensure portfolio exists in DB & sync equity mark-to-market
        self.portfolio = self.db.get_or_create_compounding_portfolio(
            mode=self.mode, initial_capital_krw=self.initial_capital_krw
        )
        self.sync_portfolio_equity()

    def clear_pending_alerts(self) -> None:
        """Clears pending alert queues."""
        self.pending_entries.clear()
        self.pending_exits.clear()

    def reload_portfolio(self) -> Dict[str, Any]:
        """Refreshes portfolio state from SQLite."""
        self.portfolio = self.db.get_or_create_compounding_portfolio(
            mode=self.mode, initial_capital_krw=self.initial_capital_krw
        )
        return self.portfolio

    def sync_portfolio_equity(self) -> Dict[str, Any]:
        """Recalculates exact portfolio equity from cash + all open positions market value."""
        self.reload_portfolio()
        open_positions = self.db.get_open_compounding_positions()
        open_market_val = sum(
            p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in open_positions
        )
        cash = self.portfolio["current_cash_krw"]
        equity = round(cash + open_market_val, 0)
        peak = round(max(self.portfolio.get("peak_equity_krw", 0.0), equity, self.initial_capital_krw), 0)
        mdd = round(((peak - equity) / peak * 100.0), 2) if peak > 0 else 0.0

        self.db.update_compounding_portfolio(
            mode=self.mode,
            current_cash_krw=round(cash, 0),
            equity_krw=equity,
            peak_equity_krw=peak,
            max_drawdown_pct=mdd,
            total_trades=self.portfolio["total_trades"],
            winning_trades=self.portfolio["winning_trades"],
            losing_trades=self.portfolio["losing_trades"],
            total_net_pnl_krw=self.portfolio["total_net_pnl_krw"],
            total_fee_krw=self.portfolio["total_fee_krw"],
        )
        return self.reload_portfolio()

    def _convert_to_krw_price(self, price: float, asset_type: AssetType, symbol: str = "") -> float:
        if symbol.startswith("KRW-"):
            return price
        if asset_type in (AssetType.COIN, AssetType.STOCK_US):
            return price * self.usd_krw_rate
        return price

    def _format_price(self, price: float, asset_type_str: str, symbol: str = "") -> str:
        """Helper to format price with appropriate currency unit and precision."""
        if asset_type_str == "STOCK_KR" or symbol.startswith("KRW-"):
            if price >= 100:
                return f"{int(round(price)):,}원"
            else:
                return f"{price:,.2f}원"
        if price < 1.0:
            return f"${price:,.4f}"
        if price < 10.0:
            return f"${price:,.3f}"
        return f"${price:,.2f}"

    def process_signal_for_entry(
        self,
        candidate: SignalCandidate,
        current_quotes: Optional[Dict[str, float]] = None,
        immediate: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Evaluates whether an incoming signal qualifies for an Ultra Compounding position.
        
        Handles:
        1. [잔액진입 (신규)]: Entering first position when slots are empty.
        2. [포지션유지 + 잔액진입]: Keeping existing position and adding second position with remaining cash.
        3. [종목교체 (Swap)]: Replacing an underperforming/stagnant position when slots are full.
        """
        self.sync_portfolio_equity()

        # Strict Filter for Ultra Mode:
        # Must be OPPORTUNITY or HIGH_CONVICTION, score >= 75.0, RVOL >= 1.8x
        rvol = candidate.indicators.get("rvol", 1.0)
        if candidate.tier not in (AlertTier.HIGH_CONVICTION, AlertTier.OPPORTUNITY):
            logger.debug(f"[ULTRA] Rejected {candidate.symbol}: tier {candidate.tier.value} below threshold")
            return None
        if candidate.score < 75.0:
            logger.debug(f"[ULTRA] Rejected {candidate.symbol}: score {candidate.score} < 75.0")
            return None
        if isinstance(rvol, (int, float)) and rvol < 1.8:
            logger.debug(f"[ULTRA] Rejected {candidate.symbol}: RVOL {rvol} < 1.8x")
            return None

        # Market operating hours gating (enforce real trading sessions & holidays)
        if self.enforce_market_hours and not candidate.is_mock and not config.use_mock:
            is_open, open_reason = is_market_open(candidate.asset_type)
            if not is_open:
                logger.info(
                    f"[ULTRA] Cannot enter {candidate.symbol} ({candidate.asset_type.value}): "
                    f"Market is closed ({open_reason}). Gated until regular session."
                )
                return None

        # Stock & Spot Crypto LONG ONLY Contract
        is_spot_crypto = candidate.symbol.startswith("KRW-") or config.markets_cfg.get("crypto", {}).get("contract_type") == "spot"
        if (candidate.asset_type in (AssetType.STOCK_KR, AssetType.STOCK_US) or is_spot_crypto) and candidate.direction != Direction.LONG:
            logger.error(f"[ULTRA] Short on {candidate.symbol} strictly forbidden! Suppressed.")
            return None

        # Check existing open positions
        open_positions = self.db.get_open_compounding_positions()
        for pos in open_positions:
            if pos["symbol"] == candidate.symbol:
                logger.info(f"[ULTRA] Already holding position in {candidate.symbol}. Skipping.")
                return None

        # Update quotes if provided
        if current_quotes:
            for p in open_positions:
                sym = p["symbol"]
                if sym in current_quotes and current_quotes[sym] > 0:
                    cp = current_quotes[sym]
                    ep = p["entry_price"]
                    pnl_pct = ((cp - ep) / ep * 100.0) if p["direction"] == "LONG" else ((ep - cp) / ep * 100.0)
                    pnl_krw = p["invested_krw"] * (pnl_pct / 100.0)
                    self.db.update_compounding_position_mark(
                        position_id=p["position_id"],
                        current_price=cp,
                        highest_price=max(p["highest_price"], cp),
                        lowest_price=min(p["lowest_price"], cp),
                        trailing_stop_price=p["trailing_stop_price"],
                        unrealized_pnl_pct=round(pnl_pct, 2),
                        unrealized_pnl_krw=round(pnl_krw, 0),
                    )
            open_positions = self.db.get_open_compounding_positions()
            self.sync_portfolio_equity()

        cash_before = self.portfolio["current_cash_krw"]
        open_val_before = sum(p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in open_positions)
        equity_before = cash_before + open_val_before
        swapped_trade: Optional[Dict[str, Any]] = None
        entry_mode: str = ""

        # Entry Mode Determination
        n_open = len(open_positions)
        if n_open < self.max_concurrent_positions and cash_before >= 100_000.0:
            if n_open == 0:
                entry_mode = "잔액진입 (신규)"
            else:
                entry_mode = "포지션유지 + 잔액진입"
        else:
            # Slots are full OR cash is insufficient -> Evaluate SWAP (종목교체)
            # Candidate must have high conviction for replacement
            if candidate.score < 80.0 and candidate.tier != AlertTier.HIGH_CONVICTION:
                logger.info(
                    f"[ULTRA] Max positions ({self.max_concurrent_positions}) reached & candidate score {candidate.score} < 80.0. "
                    f"Cannot swap. Skipping {candidate.symbol}."
                )
                return None

            if not open_positions:
                logger.warning(f"[ULTRA] Available cash ({cash_before:,.0f} KRW) insufficient and no position to swap.")
                return None

            # Filter swappable positions: A position in a closed market CANNOT be sold/swapped!
            swappable_positions = []
            for p in open_positions:
                p_asset = AssetType(p["asset_type"])
                is_open, closed_reason = is_market_open(p_asset)
                if not self.enforce_market_hours or is_open or config.use_mock:
                    swappable_positions.append(p)
                else:
                    logger.info(
                        f"[ULTRA SWAP] Position {p['symbol']} cannot be swapped out: {p['asset_type']} market is currently closed ({closed_reason})."
                    )

            if not swappable_positions:
                logger.info(
                    f"[ULTRA] Cannot swap for {candidate.symbol}: All open positions are in closed markets (휴장 중 매도 불가)."
                )
                return None

            # Find worst performing or stagnant position among open-market swappable positions
            worst_pos = min(swappable_positions, key=lambda x: x.get("unrealized_pnl_pct", 0.0))
            worst_pnl = worst_pos.get("unrealized_pnl_pct", 0.0)

            # Do not swap out strong runners (>= +10%)
            if worst_pnl >= 10.0:
                logger.info(
                    f"[ULTRA] Swappable positions are active runners (lowest PnL {worst_pnl:+.2f}% >= +10.0%). "
                    f"Swap skipped to protect runner profits."
                )
                return None

            # Execute SWAP exit of worst_pos
            exit_price = worst_pos.get("current_price") or worst_pos["entry_price"]
            swapped_trade = self._execute_exit(
                worst_pos,
                exit_price=exit_price,
                exit_reason=f"종목 교체 청산 (Swap ➡️ {candidate.symbol})",
                gross_pnl_pct=worst_pnl,
                immediate=False,
            )
            # Remove from pending exits so it is bundled into the single swap notification
            self.pending_exits = [
                x for x in self.pending_exits if x["trade"]["position_id"] != worst_pos["position_id"]
            ]
            entry_mode = "종목교체 (Swap)"

            # Refresh open positions and cash balance after swap
            self.sync_portfolio_equity()
            open_positions = self.db.get_open_compounding_positions()
            cash_before = self.portfolio["current_cash_krw"]
            open_val_before = sum(p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in open_positions)
            equity_before = cash_before + open_val_before

        # Sizing Calculation
        target_allocation = min(equity_before * self.target_position_pct, cash_before, self.liquidity_order_cap_krw)
        if target_allocation < 100_000.0:
            logger.warning(f"[ULTRA] Available cash ({cash_before:,.0f} KRW) insufficient for new entry")
            return None

        entry_price = candidate.price
        price_krw = self._convert_to_krw_price(entry_price, candidate.asset_type, candidate.symbol)

        is_stock = candidate.asset_type in (AssetType.STOCK_KR, AssetType.STOCK_US)
        if is_stock:
            # 주식은 소수점 거래 불가: 온전한 주당(1주) 단위 정수로만 매수 체결
            quantity = float(int(target_allocation // price_krw))
            if quantity < 1.0:
                logger.warning(
                    f"[ULTRA] Allocated cash ({target_allocation:,.0f} KRW) insufficient to buy 1 share of {candidate.symbol} @ {price_krw:,.0f} KRW"
                )
                return None
            actual_invested_krw = round(quantity * price_krw, 0)
            fee_rate = self.stock_fee_rate
            entry_fee_krw = round(actual_invested_krw * fee_rate, 0)
            total_deducted_krw = actual_invested_krw + entry_fee_krw
        else:
            # 코인은 소수점 거래 기본 (Upbit Spot Crypto)
            fee_rate = self.crypto_fee_rate
            entry_fee_krw = round(target_allocation * fee_rate, 0)
            actual_invested_krw = target_allocation - entry_fee_krw
            quantity = round(actual_invested_krw / price_krw, 4)
            total_deducted_krw = target_allocation

        # Stop loss & Profit target calculation
        is_krw_denominated = candidate.symbol.startswith("KRW-") or candidate.asset_type == AssetType.STOCK_KR
        if candidate.direction == Direction.LONG:
            if is_krw_denominated:
                if entry_price >= 100:
                    stop_loss_price = float(round(entry_price * (1.0 - (self.stop_loss_pct / 100.0))))
                    target_price = float(round(entry_price * 1.35))
                else:
                    stop_loss_price = round(entry_price * (1.0 - (self.stop_loss_pct / 100.0)), 2)
                    target_price = round(entry_price * 1.35, 2)
            else:
                stop_loss_price = round(entry_price * (1.0 - (self.stop_loss_pct / 100.0)), 4 if entry_price < 10 else 2)
                target_price = round(entry_price * 1.35, 4 if entry_price < 10 else 2)
        else:
            stop_loss_price = round(entry_price * (1.0 + (self.stop_loss_pct / 100.0)), 4 if entry_price < 10 else 2)
            target_price = round(entry_price * 0.70, 4 if entry_price < 10 else 2)

        pos_id = f"pos_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        position_record = {
            "position_id": pos_id,
            "symbol": candidate.symbol,
            "asset_type": candidate.asset_type.value,
            "direction": candidate.direction.value,
            "strategy_id": candidate.strategy_id,
            "strategy_name": candidate.strategy_name,
            "signal_id": candidate.signal_id,
            "entry_price": entry_price,
            "current_price": entry_price,
            "quantity": quantity,
            "invested_krw": actual_invested_krw,
            "stop_loss_price": stop_loss_price,
            "target_price": target_price,
            "trailing_stop_price": stop_loss_price,
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "unrealized_pnl_pct": 0.0,
            "unrealized_pnl_krw": 0.0,
            "status": "OPEN",
            "entry_time": now_iso,
            "fee_krw": entry_fee_krw,
        }

        # Save position to SQLite
        self.db.save_compounding_position(position_record)

        # Update cash balance and recalculate exact equity
        cash_after = cash_before - total_deducted_krw
        open_positions_after = self.db.get_open_compounding_positions()
        open_val_after = sum(p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in open_positions_after)
        equity_after = round(cash_after + open_val_after, 0)
        peak_equity = max(self.portfolio["peak_equity_krw"], equity_after, self.initial_capital_krw)
        mdd = round(((peak_equity - equity_after) / peak_equity * 100.0), 2) if peak_equity > 0 else 0.0

        self.db.update_compounding_portfolio(
            mode=self.mode,
            current_cash_krw=round(cash_after, 0),
            equity_krw=equity_after,
            peak_equity_krw=round(peak_equity, 0),
            max_drawdown_pct=mdd,
            total_trades=self.portfolio["total_trades"],
            winning_trades=self.portfolio["winning_trades"],
            losing_trades=self.portfolio["losing_trades"],
            total_net_pnl_krw=self.portfolio["total_net_pnl_krw"],
            total_fee_krw=self.portfolio["total_fee_krw"] + entry_fee_krw,
        )
        self.reload_portfolio()

        # Existing held positions (excluding the new one)
        held_positions = [p for p in open_positions_after if p["position_id"] != pos_id]

        logger.info(
            f"[ULTRA ENTRY: {entry_mode}] {candidate.symbol} {candidate.direction.value} @ {entry_price:,.2f} | "
            f"Invested: {actual_invested_krw:,.0f} KRW | Cash After: {cash_after:,.0f} KRW | Equity: {equity_after:,.0f} KRW"
        )

        # Build Entry Event
        entry_event = {
            "pos": position_record,
            "cand": candidate,
            "allocated": actual_invested_krw,
            "entry_mode": entry_mode,
            "cash_before": cash_before,
            "cash_after": cash_after,
            "equity_after": equity_after,
            "held_positions": held_positions,
            "swapped_trade": swapped_trade,
        }

        if immediate:
            self._dispatch_entry_telegram(
                pos=position_record,
                cand=candidate,
                total_allocated=actual_invested_krw,
                entry_mode=entry_mode,
                cash_before=cash_before,
                cash_after=cash_after,
                equity_after=equity_after,
                held_positions=held_positions,
                swapped_trade=swapped_trade,
            )
        else:
            self.pending_entries.append(entry_event)

        return position_record

    def evaluate_open_positions(
        self, current_quotes: Dict[str, float], immediate: bool = True
    ) -> List[Dict[str, Any]]:
        """Evaluates all open positions against live prices for stop-loss and trailing take-profit exits."""
        open_positions = self.db.get_open_compounding_positions()
        if not open_positions:
            return []

        self.reload_portfolio()
        closed_records = []

        for pos in open_positions:
            symbol = pos["symbol"]
            curr_price = current_quotes.get(symbol)
            if curr_price is None or curr_price <= 0:
                continue

            # Skip exit evaluation if the asset's market is currently closed (weekends/holidays/off-hours)
            asset_type = AssetType(pos["asset_type"])
            is_open, _ = is_market_open(asset_type)
            if self.enforce_market_hours and not is_open and not config.use_mock:
                continue

            entry_price = pos["entry_price"]
            direction = pos["direction"]

            # Calculate gross PnL%
            if direction == "LONG":
                gross_pnl_pct = ((curr_price - entry_price) / entry_price) * 100.0
            else:
                gross_pnl_pct = ((entry_price - curr_price) / entry_price) * 100.0

            # Calculate price bounds
            highest_price = max(pos["highest_price"], curr_price)
            lowest_price = min(pos["lowest_price"], curr_price)
            trailing_stop = pos["trailing_stop_price"] or pos["stop_loss_price"]

            # Ratchet Trailing Stop for Multi-Bagger Runners
            if direction == "LONG":
                if gross_pnl_pct >= 25.0:
                    new_trailing = round(highest_price * 0.92, 4 if curr_price < 10 else 2)
                    trailing_stop = max(trailing_stop, new_trailing)
                elif gross_pnl_pct >= 15.0:
                    trailing_stop = max(trailing_stop, entry_price * 1.005)
            else:
                if gross_pnl_pct >= 25.0:
                    new_trailing = round(lowest_price * 1.08, 4 if curr_price < 10 else 2)
                    trailing_stop = min(trailing_stop, new_trailing)
                elif gross_pnl_pct >= 15.0:
                    trailing_stop = min(trailing_stop, entry_price * 0.995)

            # Check Exit Conditions
            is_exit = False
            exit_reason = ""

            # 1. Strict Stop-Loss (-5.2%)
            if direction == "LONG" and curr_price <= pos["stop_loss_price"]:
                is_exit = True
                exit_reason = "원칙 손절 (Strict Risk Invalidation)"
            elif direction == "SHORT" and curr_price >= pos["stop_loss_price"]:
                is_exit = True
                exit_reason = "원칙 손절 (Strict Risk Invalidation)"
            # 2. Trailing Stop Exit (Lock in profit)
            elif direction == "LONG" and trailing_stop > pos["stop_loss_price"] and curr_price <= trailing_stop:
                is_exit = True
                exit_reason = f"트레일링 익절 청산 (+{gross_pnl_pct:.1f}%)"
            elif direction == "SHORT" and trailing_stop < pos["stop_loss_price"] and curr_price >= trailing_stop:
                is_exit = True
                exit_reason = f"트레일링 익절 청산 (+{gross_pnl_pct:.1f}%)"

            if is_exit:
                closed = self._execute_exit(pos, curr_price, exit_reason, gross_pnl_pct, immediate=immediate)
                closed_records.append(closed)
            else:
                # Update mark-to-market
                invested = pos["invested_krw"]
                unrealized_krw = invested * (gross_pnl_pct / 100.0)
                self.db.update_compounding_position_mark(
                    position_id=pos["position_id"],
                    current_price=curr_price,
                    highest_price=highest_price,
                    lowest_price=lowest_price,
                    trailing_stop_price=trailing_stop,
                    unrealized_pnl_pct=round(gross_pnl_pct, 2),
                    unrealized_pnl_krw=round(unrealized_krw, 0),
                )

        # Always sync full portfolio equity after evaluations
        self.sync_portfolio_equity()
        return closed_records

    def _execute_exit(
        self,
        pos: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        gross_pnl_pct: float,
        immediate: bool = True,
    ) -> Dict[str, Any]:
        """Executes position exit, deducts fee, records trade, updates portfolio cash and sends Telegram alert."""
        invested = pos["invested_krw"]
        fee_rate = self.crypto_fee_rate if pos["asset_type"] == "COIN" else self.stock_fee_rate
        gross_value = invested * (1.0 + (gross_pnl_pct / 100.0))
        exit_fee_krw = gross_value * fee_rate
        net_value = gross_value - exit_fee_krw
        net_pnl_krw = net_value - invested
        net_return_pct = (net_pnl_krw / invested) * 100.0

        # Close position in DB
        self.db.close_compounding_position(
            position_id=pos["position_id"],
            exit_price=exit_price,
            exit_reason=exit_reason,
            realized_pnl_krw=round(net_pnl_krw, 0),
            realized_pnl_pct=round(net_return_pct, 2),
            fee_krw=round(exit_fee_krw, 0),
        )

        # Update Portfolio Balance
        new_cash = self.portfolio["current_cash_krw"] + net_value
        remaining_open = [
            p for p in self.db.get_open_compounding_positions() if p["position_id"] != pos["position_id"]
        ]
        remaining_open_val = sum(
            p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in remaining_open
        )
        new_equity = round(new_cash + remaining_open_val, 0)
        new_peak = round(max(self.portfolio["peak_equity_krw"], new_equity, self.initial_capital_krw), 0)
        new_mdd = round(((new_peak - new_equity) / new_peak) * 100.0, 2) if new_peak > 0 else 0.0
        new_trades = self.portfolio["total_trades"] + 1
        new_wins = self.portfolio["winning_trades"] + (1 if net_pnl_krw > 0 else 0)
        new_losses = self.portfolio["losing_trades"] + (1 if net_pnl_krw <= 0 else 0)
        new_net_pnl = self.portfolio["total_net_pnl_krw"] + net_pnl_krw
        new_total_fee = self.portfolio["total_fee_krw"] + exit_fee_krw

        self.db.update_compounding_portfolio(
            mode=self.mode,
            current_cash_krw=round(new_cash, 0),
            equity_krw=new_equity,
            peak_equity_krw=new_peak,
            max_drawdown_pct=new_mdd,
            total_trades=new_trades,
            winning_trades=new_wins,
            losing_trades=new_losses,
            total_net_pnl_krw=round(new_net_pnl, 0),
            total_fee_krw=round(new_total_fee, 0),
        )
        self.reload_portfolio()

        # Record trade history
        trade_record = {
            "position_id": pos["position_id"],
            "symbol": pos["symbol"],
            "asset_type": pos["asset_type"],
            "direction": pos["direction"],
            "strategy_id": pos["strategy_id"],
            "strategy_name": pos["strategy_name"],
            "entry_time": pos["entry_time"],
            "exit_time": datetime.now(timezone.utc).isoformat(),
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "quantity": pos["quantity"],
            "invested_krw": round(invested, 0),
            "exit_value_krw": round(net_value, 0),
            "gross_pnl_pct": round(gross_pnl_pct, 2),
            "fee_krw": round(exit_fee_krw, 0),
            "net_pnl_krw": round(net_pnl_krw, 0),
            "net_return_pct": round(net_return_pct, 2),
            "portfolio_ending_balance": new_equity,
            "exit_reason": exit_reason,
        }
        trade_num = self.db.record_compounding_trade(trade_record)

        logger.info(
            f"[ULTRA EXIT #{trade_num}] {pos['symbol']} @ {exit_price:,.2f} | "
            f"Net PnL: {net_pnl_krw:+,.0f} KRW ({net_return_pct:+.2f}%) | Ending Cash: {new_cash:,.0f} KRW"
        )

        exit_event = {
            "trade": trade_record,
            "trade_num": trade_num,
            "ending_equity": new_equity,
            "wins": new_wins,
            "losses": new_losses,
            "remaining_positions": remaining_open,
        }
        if immediate:
            self._dispatch_exit_telegram(trade_record, trade_num, new_equity, new_wins, new_losses, remaining_open)
        else:
            self.pending_exits.append(exit_event)
        return trade_record

    def _dispatch_entry_telegram(
        self,
        pos: Dict[str, Any],
        cand: SignalCandidate,
        total_allocated: float,
        entry_mode: str = "잔액진입 (신규)",
        cash_before: Optional[float] = None,
        cash_after: Optional[float] = None,
        equity_after: Optional[float] = None,
        held_positions: Optional[List[Dict[str, Any]]] = None,
        swapped_trade: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Sends comprehensive, high-priority final BUY execution order to Telegram.
        
        Covers:
        - Entry mode classification (잔액진입 / 포지션유지+잔액진입 / 종목교체)
        - Swapped out position details if applicable
        - Detailed status of existing open positions marked [유지] with accurate return % and KRW
        - Exact cash transition (진입 전 현금 ➡️ 체결 ➡️ 진입 후 잔액) and portfolio weight breakdown
        """
        if cash_before is None:
            cash_before = self.portfolio["current_cash_krw"] + total_allocated
        if cash_after is None:
            cash_after = self.portfolio["current_cash_krw"]
        if equity_after is None:
            equity_after = self.portfolio["equity_krw"]
        if held_positions is None:
            held_positions = [p for p in self.db.get_open_compounding_positions() if p["position_id"] != pos["position_id"]]

        # Header & Badge
        if swapped_trade:
            header = "🔄 [SIGNAL FORGE ULTRA 종목 교체 (SWAP)]"
            badge = "🔄 종목교체 (부진 종목 청산 후 유망주 교체 진입)"
        elif entry_mode == "포지션유지 + 잔액진입":
            header = "🟢 [SIGNAL FORGE ULTRA 실전 매수 (BUY)]"
            badge = "➕ 포지션유지 + 잔액진입 (기존 보유 유지 및 잔여 현금 추가 매수)"
        else:
            header = "🟢 [SIGNAL FORGE ULTRA 실전 매수 (BUY)]"
            badge = "🆕 잔액진입 (신규 1호 포지션 진입)"

        lines = [
            header,
            f"• 체결 유형: {badge}",
            "--------------------------------------------------",
        ]

        # 1. Swapped Out Trade Section (if applicable)
        if swapped_trade:
            sw_asset = swapped_trade["asset_type"]
            sw_entry_fmt = self._format_price(swapped_trade["entry_price"], sw_asset, swapped_trade["symbol"])
            sw_exit_fmt = self._format_price(swapped_trade["exit_price"], sw_asset, swapped_trade["symbol"])
            pnl_sign = "+" if swapped_trade["net_pnl_krw"] > 0 else ""
            lines.extend([
                "[🔴 교체 청산 종목 (Swap Out)]",
                f"• 종목: {format_symbol_display(swapped_trade['symbol'])} [교체 청산]",
                f"• 매수가: {sw_entry_fmt} ➡️ 청산가: {sw_exit_fmt}",
                f"• 실현 손익: {pnl_sign}{swapped_trade['net_pnl_krw']:,.0f}원 ({pnl_sign}{swapped_trade['net_return_pct']:.2f}%)",
                f"• 자금 회수: {swapped_trade['invested_krw']:,.0f}원 ➡️ {swapped_trade['exit_value_krw']:,.0f}원 (새 종목 투입)",
                f"• 청산 사유: {swapped_trade['exit_reason']}",
                "--------------------------------------------------",
            ])

        # 2. New Buy Position Section
        pos_asset = pos["asset_type"]
        price_fmt = self._format_price(pos["entry_price"], pos_asset, pos["symbol"])
        stop_fmt = self._format_price(pos["stop_loss_price"], pos_asset, pos["symbol"])
        target_fmt = self._format_price(pos["target_price"], pos_asset, pos["symbol"])
        if pos_asset in ("STOCK_KR", "STOCK_US"):
            qty_fmt = f"{int(pos['quantity']):,}주"
        elif pos["symbol"].startswith("KRW-"):
            qty_fmt = f"{pos['quantity']:.4f}개"
        else:
            qty_fmt = f"{pos['quantity']:.4f}"

        # Chart and market link
        if pos["symbol"].startswith("KRW-"):
            chart_link = f"https://upbit.com/exchange?code=CRIX.UPBIT.{pos['symbol']}"
            market_badge = "업비트 (Upbit KRW 마켓)"
        elif pos_asset == "STOCK_KR":
            chart_link = f"https://finance.naver.com/item/main.naver?code={pos['symbol']}"
            market_badge = "국내 주식 (KOSPI/KOSDAQ)"
        else:
            chart_link = f"https://finance.yahoo.com/quote/{pos['symbol']}"
            market_badge = "미국 주식 (NYSE/NASDAQ)"

        action_label = "신규 교체 매수" if swapped_trade else "신규 매수"
        lines.extend([
            f"[🟢 {action_label} 종목 (BUY)]",
            f"• 시장: {market_badge}",
            f"• 종목: {format_symbol_display(pos['symbol'])}",
            f"• 매수가: {price_fmt} ({qty_fmt})",
            f"• 매수 체결금: {pos['invested_krw']:,.0f}원 (공제 수수료: {pos['fee_krw']:,.0f}원)",
            f"• 손절 기준선(SL): {stop_fmt} (-{self.stop_loss_pct:.1f}% 원칙 손절)",
            f"• 1차 목표가(TP): {target_fmt} (+35.0% 추세추종)",
            f"• 진입 전략: {pos['strategy_name']} ({cand.trigger_reason})",
            f"• 차트/주문: {chart_link}",
            "--------------------------------------------------",
        ])

        # 3. Existing Held Positions Status Section
        lines.append("[📌 기존 보유 포지션 현황]")
        if held_positions:
            for h in held_positions:
                h_asset = h["asset_type"]
                h_entry = self._format_price(h["entry_price"], h_asset, h["symbol"])
                h_curr = self._format_price(h.get("current_price") or h["entry_price"], h_asset, h["symbol"])
                h_sl = self._format_price(h["stop_loss_price"], h_asset, h["symbol"])
                h_pnl_pct = h.get("unrealized_pnl_pct", 0.0)
                h_pnl_krw = h.get("unrealized_pnl_krw", 0.0)
                h_sign = "+" if h_pnl_pct >= 0 else ""
                lines.extend([
                    f"• {format_symbol_display(h['symbol'])} [유지]",
                    f"  - 매수가: {h_entry} ➡️ 현재가: {h_curr}",
                    f"  - 평가 손익: {h_sign}{h_pnl_pct:.2f}% ({h_sign}{h_pnl_krw:,.0f}원)",
                    f"  - 손절 기준선: {h_sl}",
                ])
        else:
            lines.append("• 보유 종목 없음 (신규 1호 포지션)")
        lines.append("--------------------------------------------------")

        # 4. Cash & Equity Balance Breakdown Section
        total_open_val = max(0.0, equity_after - cash_after)
        invested_pct = (total_open_val / equity_after * 100.0) if equity_after > 0 else 0.0
        cash_pct = (cash_after / equity_after * 100.0) if equity_after > 0 else 0.0
        tot_pnl_krw = equity_after - self.initial_capital_krw
        tot_ret_pct = (tot_pnl_krw / self.initial_capital_krw) * 100.0
        tot_sign = "+" if tot_pnl_krw >= 0 else ""
        all_open_count = len(held_positions or []) + 1

        lines.extend([
            "💰 [잔액 및 자산 변동]",
            f"• 현금 변동: {cash_before:,.0f}원 ➡️ 체결: {total_allocated:,.0f}원 ➡️ 진입 후 잔액: {cash_after:,.0f}원",
            f"• 총 평가 자산: {equity_after:,.0f} KRW (원금 {self.initial_capital_krw:,.0f}원 대비 {tot_sign}{tot_ret_pct:.2f}%)",
            f"• 포트폴리오 비중: 보유 주식 {invested_pct:.1f}% ({total_open_val:,.0f}원) | 현금 {cash_pct:.1f}% ({cash_after:,.0f}원)",
            f"• 슬롯 현황: {all_open_count} / {self.max_concurrent_positions} 슬롯 사용 중",
        ])
        msg = "\n".join(lines)
        self.dispatcher._dispatch_telegram(cand.signal_id, msg)

    def _dispatch_exit_telegram(
        self,
        trade: Dict[str, Any],
        trade_num: int,
        ending_equity: float,
        wins: int,
        losses: int,
        remaining_positions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Sends comprehensive, high-priority final SELL execution order to Telegram."""
        is_win = trade["net_pnl_krw"] > 0
        header_emoji = "🎯 [SIGNAL FORGE ULTRA 실전 매도 (SELL / 익절 청산)]" if is_win else "🚨 [SIGNAL FORGE ULTRA 실전 매도 (SELL / 원칙 손절)]"
        pnl_sign = "+" if is_win else ""
        win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else 0.0

        asset_str = trade["asset_type"]
        p_entry = trade["entry_price"]
        p_exit = trade["exit_price"]
        entry_fmt = self._format_price(p_entry, asset_str, trade["symbol"])
        exit_fmt = self._format_price(p_exit, asset_str, trade["symbol"])

        lines = [
            header_emoji,
            f"거래 #{trade_num} | {format_symbol_display(trade['symbol'])}",
            "--------------------------------------------------",
            f"• 매수가: {entry_fmt} ➡️ 매도가: {exit_fmt}",
            f"• 매도 사유: {trade['exit_reason']}",
            f"• 실현 손익: {pnl_sign}{trade['net_pnl_krw']:,.0f} KRW ({pnl_sign}{trade['net_return_pct']:.2f}%)",
            f"• 투자금 회수: {trade['invested_krw']:,.0f}원 ➡️ {trade['exit_value_krw']:,.0f}원",
            f"• 공제 수수료: -{trade['fee_krw']:,.0f} KRW",
            "--------------------------------------------------",
        ]

        # Remaining Open Positions
        if remaining_positions is None:
            remaining_positions = self.db.get_open_compounding_positions()

        lines.append("[📌 잔여 보유 포지션 현황]")
        if remaining_positions:
            for r in remaining_positions:
                r_asset = r["asset_type"]
                r_entry = self._format_price(r["entry_price"], r_asset, r["symbol"])
                r_curr = self._format_price(r.get("current_price") or r["entry_price"], r_asset, r["symbol"])
                r_pnl_pct = r.get("unrealized_pnl_pct", 0.0)
                r_pnl_krw = r.get("unrealized_pnl_krw", 0.0)
                r_sign = "+" if r_pnl_pct >= 0 else ""
                lines.append(
                    f"• {format_symbol_display(r['symbol'])} [유지] | {r_entry} ➡️ {r_curr} ({r_sign}{r_pnl_pct:.2f}%, {r_sign}{r_pnl_krw:,.0f}원)"
                )
        else:
            lines.append("• 보유 종목 없음 (전량 현금화 완료)")
        lines.append("--------------------------------------------------")

        # Portfolio Status
        curr_cash = self.portfolio["current_cash_krw"]
        tot_pnl_krw = ending_equity - self.initial_capital_krw
        tot_ret_pct = (tot_pnl_krw / self.initial_capital_krw) * 100.0
        tot_sign = "+" if tot_pnl_krw >= 0 else ""

        lines.extend([
            "💰 [실전 복리 포트폴리오 현황]",
            f"• 가용 현금: {curr_cash:,.0f} KRW | 총 평가 자산: {ending_equity:,.0f} KRW",
            f"• 시작금 대비 수익: {tot_sign}{tot_pnl_krw:,.0f} KRW ({tot_sign}{tot_ret_pct:.2f}%)",
            f"• 누적 전적: {trade_num}전 {wins}승 {losses}패 (승률 {win_rate:.1f}%)",
        ])
        msg = "\n".join(lines)
        self.dispatcher._dispatch_telegram(trade["position_id"], msg)

    def dispatch_pending_alerts(self) -> int:
        """Aggregates and dispatches pending trade alerts.
        If >= 2 alerts occur at once, combines them into ONE aggregated Telegram message.
        If exactly 1 alert occurs, sends standard focused message.
        """
        total = len(self.pending_entries) + len(self.pending_exits)
        if total == 0:
            return 0

        if total == 1:
            if self.pending_entries:
                e = self.pending_entries[0]
                self._dispatch_entry_telegram(
                    pos=e["pos"],
                    cand=e["cand"],
                    total_allocated=e["allocated"],
                    entry_mode=e.get("entry_mode", "잔액진입 (신규)"),
                    cash_before=e.get("cash_before"),
                    cash_after=e.get("cash_after"),
                    equity_after=e.get("equity_after"),
                    held_positions=e.get("held_positions"),
                    swapped_trade=e.get("swapped_trade"),
                )
            elif self.pending_exits:
                x = self.pending_exits[0]
                self._dispatch_exit_telegram(
                    trade=x["trade"],
                    trade_num=x["trade_num"],
                    ending_equity=x["ending_equity"],
                    wins=x["wins"],
                    losses=x["losses"],
                    remaining_positions=x.get("remaining_positions"),
                )
            self.clear_pending_alerts()
            return 1

        # Aggregated 2+ alerts into a single combined Telegram message
        self.sync_portfolio_equity()
        lines = [
            f"📋 [SIGNAL FORGE 실전 매수/매도 취합 알람 (총 {total}건)]",
            "--------------------------------------------------",
        ]

        if self.pending_entries:
            lines.append(f"[🟢 실전 매수 (BUY) - {len(self.pending_entries)}건]")
            for item in self.pending_entries:
                p = item["pos"]
                entry_mode = item.get("entry_mode", "잔액진입")
                p_asset = p["asset_type"]
                price_fmt = self._format_price(p["entry_price"], p_asset, p["symbol"])
                stop_fmt = self._format_price(p["stop_loss_price"], p_asset, p["symbol"])
                target_fmt = self._format_price(p["target_price"], p_asset, p["symbol"])
                if p_asset in ("STOCK_KR", "STOCK_US"):
                    qty_fmt = f"{int(p['quantity']):,}주"
                elif p["symbol"].startswith("KRW-"):
                    qty_fmt = f"{p['quantity']:.4f}개"
                else:
                    qty_fmt = f"{p['quantity']:.4f}"

                swap_note = ""
                if item.get("swapped_trade"):
                    st = item["swapped_trade"]
                    swap_note = f" (🔄 {format_symbol_display(st['symbol'])} 청산 후 교체)"

                lines.append(
                    f"• [{entry_mode}] {format_symbol_display(p['symbol'])}{swap_note} | 매수가: {price_fmt} ({qty_fmt}) | 투자금: {item['allocated']:,.0f}원 | 손절: {stop_fmt} | 목표: {target_fmt}"
                )
            lines.append("")

        if self.pending_exits:
            lines.append(f"[🔴 실전 매도 (SELL) - {len(self.pending_exits)}건]")
            for item in self.pending_exits:
                t = item["trade"]
                t_asset = t["asset_type"]
                entry_fmt = self._format_price(t["entry_price"], t_asset, t["symbol"])
                exit_fmt = self._format_price(t["exit_price"], t_asset, t["symbol"])
                pnl_sign = "+" if t["net_pnl_krw"] > 0 else ""
                lines.append(
                    f"• {format_symbol_display(t['symbol'])} | 매수가: {entry_fmt} ➡️ 매도가: {exit_fmt} ({pnl_sign}{t['net_return_pct']:.2f}%) | 손익: {pnl_sign}{t['net_pnl_krw']:,.0f}원 | {t['exit_reason']}"
                )
            lines.append("")

        # Section: Existing Open Positions
        open_positions = self.db.get_open_compounding_positions()
        lines.append("[📌 현재 보유 포지션 현황]")
        if open_positions:
            for op in open_positions:
                op_asset = op["asset_type"]
                op_entry = self._format_price(op["entry_price"], op_asset, op["symbol"])
                op_curr = self._format_price(op.get("current_price") or op["entry_price"], op_asset, op["symbol"])
                op_pnl_pct = op.get("unrealized_pnl_pct", 0.0)
                op_pnl_krw = op.get("unrealized_pnl_krw", 0.0)
                op_sign = "+" if op_pnl_pct >= 0 else ""
                lines.append(
                    f"• {format_symbol_display(op['symbol'])} [유지] | {op_entry} ➡️ {op_curr} ({op_sign}{op_pnl_pct:.2f}%, {op_sign}{op_pnl_krw:,.0f}원)"
                )
        else:
            lines.append("• 보유 종목 없음 (전량 현금 보유)")

        summary = self.get_summary_status()
        trades = summary["total_trades"]
        wins = summary["winning_trades"]
        losses = summary["losing_trades"]
        win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) > 0 else 0.0
        tot_pnl_krw = summary["equity_krw"] - self.initial_capital_krw
        tot_ret_pct = (tot_pnl_krw / self.initial_capital_krw) * 100.0
        tot_sign = "+" if tot_pnl_krw >= 0 else ""

        lines.extend([
            "--------------------------------------------------",
            f"💰 총 평가 자산: {summary['equity_krw']:,.0f} KRW ({tot_sign}{tot_ret_pct:.2f}%) | 가용 현금: {summary['current_cash_krw']:,.0f} KRW",
            f"📊 누적 전적: {trades}전 {wins}승 {losses}패 (승률 {win_rate:.1f}%)",
        ])

        msg = "\n".join(lines)
        self.dispatcher._dispatch_telegram("batch_aggregate", msg)
        self.clear_pending_alerts()
        return total

    def get_summary_status(self) -> Dict[str, Any]:
        """Returns structured status dictionary."""
        self.sync_portfolio_equity()
        open_pos = self.db.get_open_compounding_positions()
        trades = self.db.get_compounding_trades(limit=10)
        open_market_val = sum(p["invested_krw"] + p.get("unrealized_pnl_krw", 0.0) for p in open_pos)
        current_equity = self.portfolio["current_cash_krw"] + open_market_val
        peak_equity = max(self.portfolio["peak_equity_krw"], current_equity, self.initial_capital_krw)
        mdd = round(((peak_equity - current_equity) / peak_equity * 100.0), 2) if peak_equity > 0 else 0.0
        return {
            "mode": self.portfolio["mode"],
            "initial_capital_krw": self.portfolio["initial_capital_krw"],
            "current_cash_krw": self.portfolio["current_cash_krw"],
            "equity_krw": round(current_equity, 0),
            "peak_equity_krw": round(peak_equity, 0),
            "max_drawdown_pct": mdd,
            "total_trades": self.portfolio["total_trades"],
            "winning_trades": self.portfolio["winning_trades"],
            "losing_trades": self.portfolio["losing_trades"],
            "win_rate_pct": round(
                (self.portfolio["winning_trades"] / self.portfolio["total_trades"] * 100.0)
                if self.portfolio["total_trades"] > 0
                else 0.0,
                2,
            ),
            "total_net_pnl_krw": self.portfolio["total_net_pnl_krw"],
            "total_fee_krw": self.portfolio["total_fee_krw"],
            "open_positions": open_pos,
            "recent_trades": trades,
        }


# Default global instance
compounding_trader = LiveCompoundingTrader()
