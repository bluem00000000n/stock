#!/usr/bin/env python3
"""
Stock Supervisor - 통합 알람 실행 런처 (CLI Entry Point)

사용법:
  python3 send_integrated_alarm.py --market krx    # 한국장 통합 알람 즉시 전송
  python3 send_integrated_alarm.py --market us     # 미국장 통합 알람 즉시 전송
  python3 send_integrated_alarm.py --auto          # 현재 시간에 맞춰 자동 판별 (07~12: KRX, 18~24: US)
  python3 send_integrated_alarm.py --dry-run       # 텔레그램 미전송 (미리보기 출력)
"""

import sys
import argparse
from datetime import datetime
from integrated_alarm_engine import run_integrated_alarm

def main():
    parser = argparse.ArgumentParser(description="Stock Supervisor - Integrated Alarm CLI")
    parser.add_argument("--market", choices=["krx", "us", "auto"], default="auto", help="Target market: krx, us, or auto")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending telegram")

    args = parser.parse_args()

    target_market = args.market
    if target_market == "auto":
        hour = datetime.now().hour
        target_market = "us" if hour >= 18 else "krx"

    print(f"📡 [Stock Supervisor] Triggering Integrated Alarm: {target_market.upper()} (Dry-run: {args.dry_run})")
    success = run_integrated_alarm(market=target_market, dry_run=args.dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
