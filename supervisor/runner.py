#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supervisor/runner.py
단일 통합 중앙 실행 엔진 (Unified Stock Supervisor Runner)

- 한국장 장전 (08:45)
- 한국장 종가 (15:10)
- 미국장 장전 (21:30)

모든 분석, 시그널 저장, 포트폴리오 선별/청산/매수 및 텔레그램 단일 통합 발송을 관제합니다.
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 경로 참조
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.calendar import is_krx_open, is_us_open
from core.database import init_db, save_signals, record_alarm
from core.market_data import fetch_us_macro
from core.telegram import send_message
from portfolio.manager import process_portfolio_cycle
from portfolio.selector import select_best_buys
from supervisor.alarm_builder import (
    build_krx_morning_alarm,
    build_krx_closing_alarm,
    build_us_night_alarm
)

# 전략 모듈 임포트
from strategies import (
    sniper,
    sepa_pivot,
    swing,
    cyclical,
    dividend,
    htp_momentum,
    us3x
)


def run_pipeline(mode: str = "auto", force: bool = False, dry_run: bool = False) -> bool:
    init_db()
    now = datetime.now()

    # 1. 실행 모드 자동 감지 (auto)
    if mode == "auto":
        hour = now.hour
        minute = now.minute
        if hour < 12:
            mode = "krx_morning"
        elif hour < 18:
            mode = "krx_closing"
        else:
            mode = "us_night"

    print(f"🚀 [Stock Supervisor] 통합 파이프라인 가동 (모드: {mode}, 강제: {force}, Dry-run: {dry_run})")

    # 2. 휴장일 검사
    if mode in ("krx_morning", "krx_closing"):
        is_open, reason = is_krx_open()
        if not is_open and not force:
            print(f"⏸️ [한국장 휴장] {reason} - 프로세스를 건너뜁니다.")
            return True
        market = "KRX"
    else:
        is_open, reason = is_us_open()
        if not is_open and not force:
            print(f"⏸️ [미국장 휴장] {reason} - 프로세스를 건너뜁니다.")
            return True
        market = "US"

    # 3. 전략 분석 실행 및 후보 시그널 수집
    raw_signals = []
    print("📊 7대 전략 분석 실행 중...")

    if market == "KRX":
        try:
            raw_signals.extend(sniper.run_analysis())
        except Exception as e:
            print(f"⚠️ sniper 오류: {e}")
        try:
            raw_signals.extend(sepa_pivot.run_analysis("KRX"))
        except Exception as e:
            print(f"⚠️ sepa_pivot 오류: {e}")
        try:
            raw_signals.extend(swing.run_analysis("KRX"))
        except Exception as e:
            print(f"⚠️ swing 오류: {e}")
        try:
            raw_signals.extend(cyclical.run_analysis())
        except Exception as e:
            print(f"⚠️ cyclical 오류: {e}")
        try:
            raw_signals.extend(dividend.run_analysis())
        except Exception as e:
            print(f"⚠️ dividend 오류: {e}")
    else:
        try:
            raw_signals.extend(htp_momentum.run_analysis())
        except Exception as e:
            print(f"⚠️ htp_momentum 오류: {e}")
        try:
            raw_signals.extend(us3x.run_analysis())
        except Exception as e:
            print(f"⚠️ us3x 오류: {e}")
        try:
            raw_signals.extend(sepa_pivot.run_analysis("US"))
        except Exception as e:
            print(f"⚠️ sepa_pivot_us 오류: {e}")
        try:
            raw_signals.extend(swing.run_analysis("US"))
        except Exception as e:
            print(f"⚠️ swing_us 오류: {e}")

    # 원천 시그널 DB 저장
    saved_count = save_signals(raw_signals)
    print(f"💾 원천 시그널 {len(raw_signals)}건 수집 (DB {saved_count}건 갱신 완료)")

    # 4. 포트폴리오 관리 사이클 실행 (시세 갱신, 손절/익절 자동 청산, 신규 매수 편입)
    print("💼 포트폴리오 상태 머신 및 자율 선별 실행 중...")
    portfolio_res = process_portfolio_cycle(raw_signals, market=market)
    best_buys = select_best_buys(raw_signals, market=market, max_select=3)

    # 5. 알람 메시지 빌드
    macro = fetch_us_macro()
    if mode == "krx_morning":
        alarm_text = build_krx_morning_alarm(portfolio_res, macro, best_buys)
        title = f"KRX 한국장 장전 통합 브리핑 ({portfolio_res['date']})"
    elif mode == "krx_closing":
        alarm_text = build_krx_closing_alarm(portfolio_res, best_buys)
        title = f"KRX 한국장 종가매수 최종 타깃 ({portfolio_res['date']})"
    else:
        alarm_text = build_us_night_alarm(portfolio_res, best_buys)
        title = f"US 미국장 본장 개장 전 브리핑 ({portfolio_res['date']})"

    if dry_run:
        print("\n" + "=" * 60)
        print("🔍 [DRY-RUN 모드: 텔레그램을 발송하지 않고 출력만 합니다]")
        print("=" * 60)
        print(alarm_text)
        print("=" * 60)
        return True

    # 6. 중앙 통합 텔레그램 발송
    print("📤 중앙 통합 텔레그램 발송 중...")
    success = send_message(alarm_text)

    if success:
        print("🎉 텔레그램 통합 알람 발송 완료!")
        # 7. DB 기록 및 대시보드 파일 갱신
        project_ids = list(set([s["project_id"] for s in raw_signals]))
        record_alarm(title, alarm_text, market, project_ids)

        try:
            import update_status
            update_status.main()
            print("✅ 대시보드(status.json 및 index.html) 최신화 완료")
        except Exception as e:
            print(f"⚠️ 대시보드 최신화 오류: {e}")

        return True
    else:
        print("❌ 텔레그램 통합 알람 발송 실패")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Supervisor Unified Pipeline Runner")
    parser.add_argument("--mode", choices=["krx_morning", "krx_closing", "us_night", "auto"], default="auto")
    parser.add_argument("--force", action="store_true", help="휴장일 무시 강제 실행")
    parser.add_argument("--dry-run", action="store_true", help="알람 발송 없이 결과만 확인")
    args = parser.parse_args()

    run_pipeline(mode=args.mode, force=args.force, dry_run=args.dry_run)
