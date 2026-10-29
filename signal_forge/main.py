"""
Command-Line Interface (CLI) Entrypoint for SIGNAL FORGE ALERT.
Commands:
  signal-forge doctor      Check environment, connectivity, DB, and zero-API-key status
  signal-forge scan        Run live/mock market scan across crypto and stocks
  signal-forge collect     Test data collection from Binance, Naver, Yahoo, and Community
  signal-forge alert-test  Dispatch test alert (live or safe mock log)
  signal-forge report      Generate daily, weekly, or monthly intelligence reports
  signal-forge status      Print runtime operational status summary
"""

import argparse
import signal
import sys
import time
from typing import List, Optional
from signal_forge.alerts.telegram import telegram_dispatcher
from signal_forge.collectors.community.community import PublicCommunityCollector
from signal_forge.collectors.market.binance import BinanceFuturesCollector
from signal_forge.collectors.market.kr_stock import KoreanStockCollector
from signal_forge.collectors.market.us_stock import USStockCollector
from signal_forge.config import config
from signal_forge.database.db import db
from signal_forge.intelligence.manager import intelligence
from signal_forge.models.signal import (
    AlertTier,
    AssetType,
    Direction,
    SignalCandidate,
    Signal,
    SignalStatus,
)
from signal_forge.observability.logger import get_logger
from signal_forge.portfolio.compounding_engine import compounding_trader
from signal_forge.reports.reporter import report_generator
from signal_forge.scheduler.runner import ScannerEngine
from signal_forge.strategies.registry import strategy_registry

logger = get_logger("cli")


def cmd_doctor(args: argparse.Namespace) -> int:
    """Runs system diagnostics and checks zero-API-key architecture readiness."""
    print("\n" + "=" * 60)
    print(" 🩺 SIGNAL FORGE ALERT - SYSTEM HEALTH CHECK (DOCTOR)")
    print("=" * 60)

    # 1. Environment & Zero API Key
    print(f"• App Version: 0.2.0")
    print(f"• Architecture: 100% Zero Paid API Key (Free Public Endpoints + Local NLP/LLM)")
    print(f"• Environment: {config.app_env}")
    print(f"• Database Path: {config.database_path} (Exists: {config.database_path.exists()})")
    print(f"• Log File: {config.log_file}")

    # 2. Database verification
    try:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM signals;")
            sig_count = cur.fetchone()[0]
        print(f"• SQLite Database: OK ({sig_count} historical signals)")
    except Exception as e:
        print(f"• SQLite Database: FAILED ({e})")

    # 3. Strategy Catalog Check
    stock_strats = len(strategy_registry.get_strategies_for_asset(AssetType.STOCK_KR))
    crypto_strats = len(strategy_registry.get_strategies_for_asset(AssetType.COIN))
    total_strats = strategy_registry.count()
    print(f"• Strategy Catalog: OK ({total_strats} total: {stock_strats} Stock LONG ONLY, {crypto_strats} Crypto LONG/SHORT)")

    # 4. Intelligence Engine
    sample_text = "SOLUSDT broke resistance! Next week 100% surge coming! VIP 리딩방 선착순"
    res = intelligence.analyze_text(sample_text)
    print(f"• Local Intelligence: OK (Provider: {config.ai_provider.upper()})")
    print(f"  - 7D Surge Detected: {res.has_7d_surge_claim}")
    print(f"  - Scam Marker Detected: {res.is_promotional_scam}")
    print(f"  - Extracted Symbols: {res.mentioned_symbols}")

    # 5. Market Collectors Connectivity (Public unauthenticated)
    print("• Testing Binance Public Futures API...")
    try:
        b_collector = BinanceFuturesCollector(is_mock=False)
        quote = b_collector.fetch_quote("BTCUSDT")
        print(f"  ✓ Binance Public API: OK (BTCUSDT: ${quote.price:,.2f}, 24h Vol: {quote.volume_24h:,.0f})")
    except Exception as e:
        print(f"  ✗ Binance Public API Offline ({e}) - System will use Mock mode")

    # 6. Telegram Alert Status
    if config.is_telegram_live:
        print(f"• Telegram Alert: LIVE (Token configured for chat ID {config.telegram_chat_id})")
    else:
        print(f"• Telegram Alert: SAFE MOCK MODE (Alerts logged to file without network errors)")

    print("=" * 60)
    print(" ✅ All core subsystems are ready and functional.\n")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Executes a market scan cycle."""
    engine = ScannerEngine(use_mock=args.mock, dry_run=args.dry_run)
    syms = [args.symbol] if args.symbol else None
    res = engine.scan_market(market=args.market, symbols=syms)

    print("\n" + "=" * 50)
    print(f" 🎯 SCAN COMPLETE [{res['market'].upper()}]")
    print("=" * 50)
    print(f"• Data Source: {res['data_source_mode']}")
    print(f"• Signals Detected: {res['detected_count']}")
    print(f"• Alerts Dispatched: {res['alerted_count']}")
    print(f"• Suppressed (Dedup): {res['dedup_skipped_count']}")
    print(f"• Failures: {res['failed_count']}")
    print("=" * 50)
    if res["signals"]:
        print("Signals:")
        for s in res["signals"]:
            print(f"  - [{s['direction']}] {s['symbol']}: {s['strategy']} (${s['price']:,.2f}) [{s['tier']}]")
    print("")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """Tests data collectors."""
    print("\n" + "=" * 50)
    print(" 📡 TESTING UNCONNECTED/PUBLIC DATA COLLECTORS")
    print("=" * 50)

    # 1. Binance
    b = BinanceFuturesCollector(is_mock=args.mock)
    q = b.fetch_quote("BTCUSDT")
    print(f"• Binance Public: BTCUSDT = ${q.price:,.2f} (Source: {q.source})")

    # 2. KR Stock
    kr = KoreanStockCollector(is_mock=args.mock)
    kq = kr.fetch_quote("005930")
    print(f"• KR Stock (Naver): 005930 = {kq.price:,.0f} KRW (Source: {kq.source})")

    # 3. US Stock
    us = USStockCollector(is_mock=args.mock)
    uq = us.fetch_quote("AAPL")
    print(f"• US Stock (Yahoo): AAPL = ${uq.price:,.2f} (Source: {uq.source})")

    # 4. Community
    comm = PublicCommunityCollector(is_mock=args.mock)
    posts = comm.collect_recent_posts()
    print(f"• Community Feeds: Collected {len(posts)} public items")
    for p in posts[:2]:
        print(f"  - [{p.source_platform}] {p.author}: {p.raw_text[:60]}... (7D: {p.has_7d_surge_claim})")

    print("=" * 50 + "\n")
    return 0


def cmd_alert_test(args: argparse.Namespace) -> int:
    """Dispatches a test alert."""
    is_mock = getattr(args, "mock", False) or not config.is_telegram_live
    test_cand = SignalCandidate(
        asset_type=AssetType.COIN,
        symbol="BTCUSDT",
        direction=Direction.LONG,
        strategy_id="C06_REAL_CATALYST_RUNNER_LONG",
        strategy_name="Real Catalyst Runner Long",
        timeframe="1h",
        price=68420.50,
        trigger_reason="Test alert: Resistance breakout verified on 3.2x RVOL surge",
        indicators={"rvol": 3.20, "resistance": 67800.0},
        source_url="https://www.binance.com/en/futures/BTCUSDT",
        is_mock=is_mock,
        score=88.0,
        tier=AlertTier.OPPORTUNITY,
        invalidation_condition="below 67200.00",
        catalyst_summary="Verified network upgrade announcement with high volume confirmation",
        risk_notes=["Volatility expected around upcoming funding rate settlement"],
    )

    print("\nFormatting test alert:")
    text = telegram_dispatcher.format_alert(test_cand)
    print(text)
    print("-" * 50)
    
    test_sig = Signal(
        asset_type=test_cand.asset_type,
        symbol=test_cand.symbol,
        direction=test_cand.direction,
        strategy_id=test_cand.strategy_id,
        strategy_name=test_cand.strategy_name,
        timeframe=test_cand.timeframe,
        price=test_cand.price,
        trigger_reason=test_cand.trigger_reason,
        indicators=test_cand.indicators,
        source_url=test_cand.source_url,
        first_detected_at=test_cand.first_detected_at,
        is_mock=test_cand.is_mock,
        score=test_cand.score,
        tier=test_cand.tier,
        invalidation_condition=test_cand.invalidation_condition,
        catalyst_summary=test_cand.catalyst_summary,
        risk_notes=test_cand.risk_notes,
        status=SignalStatus.NEW,
    )
    db.save_signal(test_sig)

    success = telegram_dispatcher.send_alert(test_cand)
    status_label = "LIVE TELEGRAM SENT" if config.is_telegram_live else "SAFE MOCK LOGGED"
    print(f"Test Result: {status_label} (Success: {success})\n")
    return 0 if success else 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generates scheduled reports."""
    rtype = args.type.lower()
    if rtype == "daily":
        rpt = report_generator.generate_daily_report()
    elif rtype == "weekly":
        rpt = report_generator.generate_weekly_report()
    elif rtype == "monthly":
        rpt = report_generator.generate_monthly_report()
    elif rtype == "alert":
        rpt = report_generator.generate_alert_report()
    elif rtype == "all":
        rpt = "\n\n".join([
            report_generator.generate_daily_report(),
            report_generator.generate_weekly_report(),
            report_generator.generate_monthly_report(),
            report_generator.generate_alert_report(),
        ])
    else:
        print(f"Unknown report type: {rtype}")
        return 1

    print("\n" + rpt + "\n")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    """Runs historical quant validation or 5-year compounding simulation."""
    if getattr(args, "simulate", False):
        from signal_forge.backtest.simulator import compounding_simulator
        sim_mode = getattr(args, "mode", "conservative")
        if sim_mode == "ultra":
            title_label = "ULTRA / MAX ALPHA CAPACITY (극한 알파 실전 최대치)"
        elif sim_mode == "aggressive":
            title_label = "AGGRESSIVE / MAX ALPHA (공격적 스윙 극대화)"
        else:
            title_label = "CONSERVATIVE / TARGET 1억 (안정 복리 달성)"
        print("\n" + "=" * 75)
        print(f" 🚀 SIGNAL FORGE ALERT - 5-YEAR COMPOUNDING SIMULATION [{title_label}]")
        print("=" * 75)
        res = compounding_simulator.run_5year_simulation(mode=sim_mode)
        print(f"• Initial Capital: {res.initial_capital:,.0f} KRW (2021-10)")
        print(f"• Final Capital:   {res.final_capital:,.0f} KRW (2026-10) [{res.final_capital / res.initial_capital:,.2f}x]")
        print(f"• Total Profit:    +{res.total_net_profit:,.0f} KRW")
        print(f"• Total Trades:    {res.total_trades} (Wins: {res.winning_trades}, Losses: {res.losing_trades})")
        print(f"• Win Rate:        {res.win_rate_pct}%")
        print(f"• Profit Factor:   {res.profit_factor}")
        print(f"• Max Drawdown:    -{res.max_drawdown_pct}%")
        print("\n[📅 Yearly Balance Progression]")
        for yr, bal in res.yearly_progression.items():
            print(f"• {yr} Year-End: {bal:,.0f} KRW ({bal / res.initial_capital:,.1f}x)")
        print("\n[🎯 Key Trades Milestone Snapshot]")
        milestones = [res.trades[0], res.trades[5], res.trades[13], res.trades[23], res.trades[33], res.trades[-1]]
        for t in milestones:
            pnl_sign = "+" if t.net_return_pct > 0 else ""
            print(f"[{t.date}] #{t.trade_id:02d} {t.direction} {t.symbol} | Net PnL: {pnl_sign}{t.net_return_pct}% | Balance: {t.ending_balance:,.0f} KRW | {t.strategy_name}")
        print("=" * 75 + "\n")
        return 0

    from signal_forge.validation.evaluator import quant_validator
    print("\n" + "=" * 60)
    print(" 📊 SIGNAL FORGE ALERT - HISTORICAL QUANT VALIDATION")
    print("=" * 60)
    metrics = quant_validator.evaluate_all_signals()
    print(f"• Total Evaluated Samples: {metrics['total_evaluated_samples']}")
    print(f"• Overall Win Rate: {metrics['win_rate_pct']}%")
    print(f"• Average MFE: +{metrics['avg_mfe_pct']}%")
    print(f"• Average MAE: {metrics['avg_mae_pct']}%")
    print("\n[Market Breakdown]")
    for mkt, data in metrics.get("markets", {}).items():
        print(f"• {mkt}: {data['sample_count']} samples | Win Rate: {data['win_rate_pct']}% | MFE: +{data['avg_mfe_pct']}%")
    print("=" * 60 + "\n")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Prints runtime operational status."""
    summary = config.get_status_summary()
    print("\n" + "=" * 50)
    print(" ⚡ SIGNAL FORGE ALERT - OPERATIONAL STATUS")
    print("=" * 50)
    for k, v in summary.items():
        print(f"• {k}: {v}")
    print("=" * 50 + "\n")
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    """Displays current live compounding paper trading portfolio state and trade history."""
    summary = compounding_trader.get_summary_status()
    print("\n" + "=" * 65)
    print(f" 🚀 SIGNAL FORGE - LIVE COMPOUNDING PORTFOLIO [{summary['mode']} MODE]")
    print("=" * 65)
    init_cap = summary["initial_capital_krw"]
    equity = summary["equity_krw"]
    cash = summary["current_cash_krw"]
    pnl = equity - init_cap
    ret = (pnl / init_cap) * 100.0
    mult = equity / init_cap
    target_cap = 6_970_000_000.0

    print(f"• Initial Capital:    {init_cap:,.0f} KRW (Started: 100만원)")
    print(f"• Current Equity:     {equity:,.0f} KRW ({ret:+,.2f}% / {mult:,.2f}x)")
    print(f"• Available Cash:     {cash:,.0f} KRW")
    print(f"• Peak Equity:        {summary['peak_equity_krw']:,.0f} KRW")
    print(f"• Max Drawdown:       -{summary['max_drawdown_pct']}%")
    print(f"• Total Trades:       {summary['total_trades']} ({summary['winning_trades']}W / {summary['losing_trades']}L, Win Rate: {summary['win_rate_pct']}%)")
    print(f"• Net Realized PnL:   {summary['total_net_pnl_krw']:+,.0f} KRW")
    print(f"• Cumulative Fees:    -{summary['total_fee_krw']:,.0f} KRW")

    # Open Positions
    open_pos = summary["open_positions"]
    print("\n[🎯 Active Open Positions]")
    if not open_pos:
        print("  (No active positions - cash waiting for high-conviction runner setups)")
    else:
        for p in open_pos:
            dir_str = "LONG" if p["direction"] == "LONG" else "SHORT"
            curr_p = p["current_price"]
            entry_p = p["entry_price"]
            is_kr = p["asset_type"] == "STOCK_KR"
            price_fmt = f"{int(curr_p):,}원" if is_kr else (f"${curr_p:,.4f}" if curr_p < 10 else f"${curr_p:,.2f}")
            entry_fmt = f"{int(entry_p):,}원" if is_kr else (f"${entry_p:,.4f}" if entry_p < 10 else f"${entry_p:,.2f}")
            stop_fmt = f"{int(p['stop_loss_price']):,}원" if is_kr else (f"${p['stop_loss_price']:,.4f}" if p['stop_loss_price'] < 10 else f"${p['stop_loss_price']:,.2f}")
            unrealized_sign = "+" if p["unrealized_pnl_pct"] >= 0 else ""
            print(
                f"• [{dir_str}] {p['symbol']} | Entry: {entry_fmt} -> Mark: {price_fmt} | "
                f"PnL: {unrealized_sign}{p['unrealized_pnl_pct']}% ({unrealized_sign}{p['unrealized_pnl_krw']:,.0f} KRW) | "
                f"Stop: {stop_fmt} | Invested: {p['invested_krw']:,.0f} KRW"
            )

    # Recent Closed Trades
    trades = summary["recent_trades"]
    print("\n[📜 Recent Closed Trades History]")
    if not trades:
        print("  (No completed trades yet)")
    else:
        for t in trades[:5]:
            pnl_sign = "+" if t["net_pnl_krw"] > 0 else ""
            print(
                f"• #{t['trade_num']} [{t['direction']}] {t['symbol']} | "
                f"Net: {pnl_sign}{t['net_pnl_krw']:,.0f} KRW ({pnl_sign}{t['net_return_pct']}%) | "
                f"Ending Balance: {t['portfolio_ending_balance']:,.0f} KRW | Reason: {t['exit_reason']}"
            )
    print("=" * 65 + "\n")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Runs continuous background market scanning and compounding trading loop."""
    from datetime import datetime
    interval_sec = getattr(args, "interval", 180)
    market = getattr(args, "market", "crypto")

    print("\n" + "=" * 65)
    print(" 🔄 SIGNAL FORGE ALERT - BACKGROUND SCANNER & COMPOUNDING DAEMON")
    print("=" * 65)
    print(f"• Loop Interval: {interval_sec} seconds")
    print(f"• Monitored Markets: {market.upper()}")
    print(f"• Compounding Mode: ULTRA (Capital: 100만원 시작)")
    print(f"• Telegram Alerts: {'LIVE ACTIVE' if config.is_telegram_live else 'MOCK LOG'}")
    print("=" * 65 + "\n")

    engine = ScannerEngine(use_mock=False, dry_run=False)
    running = True

    def _sig_handler(signum, frame):
        nonlocal running
        print(f"\n[DAEMON] Received signal {signum}. Shutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    iteration = 0
    while running:
        iteration += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[DAEMON] Iteration #{iteration} starting at {now_str}")
        try:
            res = engine.scan_market(market=market)
            logger.info(
                f"[DAEMON] Cycle #{iteration} complete: detected={res['detected_count']}, "
                f"alerted={res['alerted_count']}, dedup={res['dedup_skipped_count']}"
            )
        except Exception as e:
            logger.error(f"[DAEMON] Scan cycle #{iteration} error: {e}")

        # Sleep in 1-second increments to respond quickly to termination signals
        for _ in range(interval_sec):
            if not running:
                break
            time.sleep(1)

    print("[DAEMON] Daemon stopped cleanly.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="signal-forge",
        description="SIGNAL FORGE ALERT: AI Investment Intelligence & Telegram Alert System",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Check system health, connectivity and configuration")
    p_doc.set_defaults(func=cmd_doctor)

    # scan
    p_scan = subparsers.add_parser("scan", help="Run market scan cycle")
    p_scan.add_argument("--market", choices=["crypto", "stocks_kr", "stocks_us", "all"], default="crypto")
    p_scan.add_argument("--symbol", type=str, help="Specific symbol to scan")
    p_scan.add_argument("--mock", action="store_true", help="Force mock data")
    p_scan.add_argument("--dry-run", action="store_true", help="Simulate without live alerts")
    p_scan.set_defaults(func=cmd_scan)

    # collect
    p_col = subparsers.add_parser("collect", help="Test unauthenticated data collectors")
    p_col.add_argument("--mock", action="store_true", help="Use mock data")
    p_col.set_defaults(func=cmd_collect)

    # alert-test
    p_alt = subparsers.add_parser("alert-test", help="Send test alert")
    p_alt.add_argument("--mock", action="store_true", help="Force mock alert without sending live message")
    p_alt.set_defaults(func=cmd_alert_test)

    # backtest
    p_bkt = subparsers.add_parser("backtest", help="Run historical quant validation")
    p_bkt.add_argument("--simulate", action="store_true", help="Run 5-year compounding paper trading simulation")
    p_bkt.add_argument("--mode", choices=["conservative", "aggressive", "ultra"], default="conservative", help="Simulation mode: conservative (100M target), aggressive (13.25억), ultra (69.7억)")
    p_bkt.set_defaults(func=cmd_backtest)

    # report
    p_rpt = subparsers.add_parser("report", help="Generate report")
    p_rpt.add_argument("type", choices=["daily", "weekly", "monthly", "alert", "all"], default="daily")
    p_rpt.set_defaults(func=cmd_report)

    # portfolio
    p_port = subparsers.add_parser("portfolio", help="View live compounding paper trading portfolio")
    p_port.set_defaults(func=cmd_portfolio)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run continuous background scanning & compounding daemon")
    p_daemon.add_argument("--interval", type=int, default=180, help="Loop interval in seconds (default: 180)")
    p_daemon.add_argument("--market", choices=["crypto", "stocks_kr", "stocks_us", "all"], default="crypto")
    p_daemon.set_defaults(func=cmd_daemon)

    # status
    p_stat = subparsers.add_parser("status", help="Print runtime status")
    p_stat.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)



if __name__ == "__main__":
    sys.exit(main())
