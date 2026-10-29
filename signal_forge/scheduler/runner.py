"""
Core Market Scanner & Pipeline Runner.
Coordinates collectors, strategy execution, deduplication, scoring, alerting, and database storage.
Explicitly reports REAL vs MOCK data source.
"""

from typing import Any, Dict, List, Optional
from signal_forge.alerts.dedup import dedup_engine
from signal_forge.alerts.telegram import telegram_dispatcher
from signal_forge.collectors.community.community import PublicCommunityCollector
from signal_forge.collectors.market.binance import BinanceFuturesCollector
from signal_forge.collectors.market.kr_stock import KoreanStockCollector
from signal_forge.collectors.market.upbit import UpbitCollector
from signal_forge.collectors.market.us_stock import USStockCollector
from signal_forge.collectors.mock import MockMarketCollector
from signal_forge.config import config
from signal_forge.database.db import DatabaseManager, db
from signal_forge.models.signal import (
    AssetType,
    Direction,
    Signal,
    SignalCandidate,
    SignalStatus,
)
from signal_forge.observability.logger import get_logger
from signal_forge.portfolio.compounding_engine import compounding_trader
from signal_forge.strategies.base import StrategyContext
from signal_forge.strategies.registry import strategy_registry
from signal_forge.utils.market_calendar import is_market_open

logger = get_logger("engine_runner")


class ScannerEngine:
    def __init__(
        self,
        use_mock: bool = False,
        dry_run: bool = False,
        database: DatabaseManager = db,
    ):
        self.use_mock = use_mock or config.use_mock
        self.dry_run = dry_run or config.dry_run
        self.db = database

        # Collectors
        self.binance_collector = BinanceFuturesCollector(is_mock=self.use_mock)
        self.upbit_collector = UpbitCollector(is_mock=self.use_mock)
        self.kr_collector = KoreanStockCollector(is_mock=self.use_mock)
        self.us_collector = USStockCollector(is_mock=self.use_mock)
        self.community_collector = PublicCommunityCollector(is_mock=self.use_mock)

    def scan_market(
        self, market: str = "crypto", symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Runs a complete scan cycle for specified market (crypto, stocks_kr, stocks_us, or all)."""
        logger.info(
            f"=== Starting Scan Cycle [Market: {market.upper()}] "
            f"(Data: {'MOCK' if self.use_mock else 'REAL_PUBLIC_ENDPOINTS'}, "
            f"Alerts: {'DRY_RUN' if self.dry_run else ('LIVE' if config.is_telegram_live else 'MOCK_LOG')}) ==="
        )

        detected_count = 0
        alerted_count = 0
        dedup_count = 0
        failed_count = 0
        detected_signals: List[SignalCandidate] = []

        # Reset pending alerts for this scan cycle
        compounding_trader.clear_pending_alerts()

        # 1. Fetch community posts first for context
        try:
            posts = self.community_collector.collect_recent_posts()
            for p in posts:
                self.db.save_community_post(p)
        except Exception as e:
            logger.warning(f"Community collection warning: {e}")
            posts = []

        # 2. Select target symbols & collector
        targets = []
        if market in ("crypto", "all"):
            crypto_cfg = config.markets_cfg.get("crypto", {})
            exchange = crypto_cfg.get("exchange", "upbit").lower()
            if exchange == "upbit":
                c_syms = symbols or crypto_cfg.get(
                    "default_symbols",
                    ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE", "KRW-ADA", "KRW-AVAX", "KRW-SUI"],
                )
                targets.extend([(s, AssetType.COIN, self.upbit_collector) for s in c_syms])
            else:
                c_syms = symbols or crypto_cfg.get("default_symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
                targets.extend([(s, AssetType.COIN, self.binance_collector) for s in c_syms])

        if market in ("stocks_kr", "all"):
            is_open, reason = is_market_open(AssetType.STOCK_KR)
            if not is_open and not self.use_mock:
                logger.info(f"[MARKET CALENDAR] Korean Stock Market is closed: {reason}. Skipping scan.")
            else:
                kr_syms = symbols or config.markets_cfg.get("stocks_kr", {}).get("default_symbols", ["005930", "000660"])
                targets.extend([(s, AssetType.STOCK_KR, self.kr_collector) for s in kr_syms])

        if market in ("stocks_us", "all"):
            is_open, reason = is_market_open(AssetType.STOCK_US)
            if not is_open and not self.use_mock:
                logger.info(f"[MARKET CALENDAR] US Stock Market is closed: {reason}. Skipping scan.")
            else:
                us_syms = symbols or config.markets_cfg.get("stocks_us", {}).get("default_symbols", ["AAPL", "NVDA"])
                targets.extend([(s, AssetType.STOCK_US, self.us_collector) for s in us_syms])

        current_quotes: Dict[str, float] = {}

        # 3. Process each symbol
        for symbol, asset_type, collector in targets:
            try:
                quote = collector.fetch_quote(symbol)
                if not quote:
                    continue
                current_quotes[symbol] = quote.price

                # Periodically evaluate open compounding positions with live price (immediate exit dispatch)
                compounding_trader.evaluate_open_positions({symbol: quote.price}, immediate=True)

                candles = collector.fetch_klines(symbol, timeframe="1h" if asset_type == AssetType.COIN else "1d", limit=60)
                if not candles:
                    continue

                # Cache candles in DB
                self.db.cache_candles(symbol, "1h" if asset_type == AssetType.COIN else "1d", candles, source=quote.source)

                # Build context
                if symbol.startswith("KRW-"):
                    source_url = f"https://upbit.com/exchange?code=CRIX.UPBIT.{symbol}"
                elif asset_type == AssetType.COIN:
                    source_url = f"https://www.binance.com/en/futures/{symbol}"
                elif asset_type == AssetType.STOCK_KR:
                    source_url = f"https://finance.naver.com/item/main.naver?code={symbol}"
                else:
                    source_url = f"https://finance.yahoo.com/quote/{symbol}"

                ctx = StrategyContext(
                    symbol=symbol,
                    asset_type=asset_type,
                    quote=quote,
                    candles=candles,
                    community_posts=posts,
                    is_mock=self.use_mock,
                    source_url=source_url,
                )

                # Run registered strategies for asset type
                strategies = strategy_registry.get_strategies_for_asset(asset_type)
                for strat in strategies:
                    try:
                        candidate = strat.detect(ctx)
                        if candidate:
                            # Verify contract: Stocks and Spot Crypto CANNOT be SHORT
                            is_spot_crypto = symbol.startswith("KRW-") or config.markets_cfg.get("crypto", {}).get("contract_type") == "spot"
                            if (asset_type in [AssetType.STOCK_KR, AssetType.STOCK_US] or is_spot_crypto) and candidate.direction != Direction.LONG:
                                logger.debug(
                                    f"[CONTRACT ENFORCEMENT] SHORT signal on {symbol} ignored for spot/stock asset."
                                )
                                continue

                            detected_count += 1
                            detected_signals.append(candidate)

                            # Deduplication check
                            should_alert, reason = dedup_engine.check_and_filter(candidate)

                            signal_obj = Signal(
                                asset_type=candidate.asset_type,
                                symbol=candidate.symbol,
                                direction=candidate.direction,
                                strategy_id=candidate.strategy_id,
                                strategy_name=candidate.strategy_name,
                                timeframe=candidate.timeframe,
                                price=candidate.price,
                                trigger_reason=candidate.trigger_reason,
                                indicators=candidate.indicators,
                                source_url=candidate.source_url,
                                first_detected_at=candidate.first_detected_at,
                                is_mock=candidate.is_mock,
                                score=candidate.score,
                                tier=candidate.tier,
                                invalidation_condition=candidate.invalidation_condition,
                                catalyst_summary=candidate.catalyst_summary,
                                risk_notes=candidate.risk_notes,
                                status=SignalStatus.ALERTED if should_alert else SignalStatus.SKIPPED_DEDUP,
                            )
                            self.db.save_signal(signal_obj)

                            if should_alert:
                                # Raw candidate alerts are suppressed by default.
                                # ONLY final Buy/Sell trade execution decisions are delivered.
                                if config.send_raw_alerts:
                                    alert_ok = telegram_dispatcher.send_alert(candidate)
                                    if alert_ok:
                                        alerted_count += 1
                                    else:
                                        failed_count += 1

                                # Execute and dispatch Final Buy (Entry) order immediately
                                if not self.dry_run:
                                    pos = compounding_trader.process_signal_for_entry(candidate, current_quotes=current_quotes, immediate=True)
                                    if pos and not config.send_raw_alerts:
                                        alerted_count += 1
                            else:
                                dedup_count += 1

                    except Exception as strat_err:
                        logger.error(f"Error in strategy {strat.strategy_id} on {symbol}: {strat_err}")

            except Exception as e:
                logger.error(f"Failed processing symbol {symbol}: {e}")
                failed_count += 1

        # Dispatch trade execution alerts (aggregates into 1 single message if >= 2 alerts occurred)
        if not self.dry_run:
            trade_alerts = compounding_trader.dispatch_pending_alerts()
            if not config.send_raw_alerts:
                alerted_count = trade_alerts

        self.db.record_execution_log(
            task_name=f"scan_{market}",
            status="SUCCESS" if failed_count == 0 else "WARNING",
            message=f"Detected: {detected_count}, Alerted: {alerted_count}, Dedup Skipped: {dedup_count}, Failed: {failed_count}",
        )

        return {
            "market": market,
            "data_source_mode": "MOCK" if self.use_mock else "REAL_PUBLIC",
            "detected_count": detected_count,
            "alerted_count": alerted_count,
            "dedup_skipped_count": dedup_count,
            "failed_count": failed_count,
            "signals": [
                {
                    "symbol": s.symbol,
                    "direction": s.direction.value,
                    "strategy": s.strategy_name,
                    "price": s.price,
                    "tier": s.tier.value,
                    "score": s.score,
                }
                for s in detected_signals
            ],
        }


# Default global instance
scanner_engine = ScannerEngine()
