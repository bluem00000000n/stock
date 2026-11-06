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
    parser.add_argument("--send-telegram", action="store_true", help="텔레그램 발송 여부")
    parser.add_argument("--dry-run", action="store_true", help="출력만 수행하고 전송하지 않음")
    args = parser.parse_args()

    # 매월 1일 자동 스케줄 실행 시 기본적으로 텔레그램 발송 플래그 활성화
    send_tg = args.send_telegram and not args.dry_run

    result = run_monthly_pipeline(send_telegram=send_tg, dry_run=args.dry_run)
    if result.get("success"):
        print(f"\n✅ 리포트 생성 및 저장 완료: {result.get('report_path')}")
        if result.get("telegram_sent"):
            print("✅ 텔레그램 발송 완료!")
    else:
        print("❌ 리포트 생성 중 오류 발생")
        sys.exit(1)


if __name__ == "__main__":
    main()
