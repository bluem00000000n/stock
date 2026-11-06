#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/monthly_liquidity_center.py
매월 1일 오전 실행되는 미국 거시 유동성 & ETF 정량 분석 실행 스크립트

사용법:
  python scripts/monthly_liquidity_center.py --send-telegram
  python scripts/monthly_liquidity_center.py --dry-run
"""

import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from supervisor.us_liquidity_engine import run_monthly_pipeline


def main():
    parser = argparse.ArgumentParser(description="Monthly US Liquidity Command Center")
    parser.add_argument("--send-telegram", action="store_true", help="텔레그램 발송 여부 (비활성화)")
    parser.add_argument("--dry-run", action="store_true", help="출력만 수행하고 저장하지 않음")
    args = parser.parse_args()

    # 텔레그램 알림은 전면 비활성화 (Stock Trading Desk 웹 대시보드 전용)
    send_tg = False
    if args.send_telegram:
        print("ℹ️ 텔레그램 알림이 삭제(비활성화)되었습니다. Stock Trading Desk 대시보드에만 자동 반영됩니다.")

    result = run_monthly_pipeline(send_telegram=send_tg, dry_run=args.dry_run)
    if result.get("success"):
        print(f"\n✅ 리포트 생성 및 저장 완료: {result.get('report_path')}")
        print("✅ Stock Trading Desk (index.html) 최신화 동기화 완료 (텔레그램 알림 전송 안 함)")
    else:
        print("❌ 리포트 생성 중 오류 발생")
        sys.exit(1)


if __name__ == "__main__":
    main()
