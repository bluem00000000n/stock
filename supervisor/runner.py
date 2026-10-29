#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supervisor/runner.py
단일 통합 중앙 실행 엔진 (Unified Stock Supervisor Runner)

하루 2회 단일 통합 브리핑:
1. 08:40 : 미국장 장마감 통합 브리핑, 🇰🇷 한국장 장전 통합 브리핑
2. 15:00 : 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑, 미국장 장전 통합 브리핑
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.calendar import is_krx_open, is_us_open
from core.database import init_db, save_signals, record_alarm
from core.market_data import fetch_us_macro
from core.telegram import send_message
from portfolio.manager import process_portfolio_cycle
from portfolio.selector import select_best_buys
from supervisor.alarm_builder import (
    build_0840_us_close_kr_open_alarm,
    build_1500_kr_close_us_open_alarm
)

# 7대 전략 모듈 임포트
from strategies import (
    sniper,
    sepa_pivot,
    swing,
    cyclical,
    dividend,
    htp_momentum,
    us3x,
    signal_forge_bridge
)
from screener.engine import run_screener_analysis


def run_pipeline(mode: str = "auto", force: bool = False, dry_run: bool = False) -> bool:
    init_db()
    now = datetime.now()

    # 1. 실행 모드 자동 감지
    if mode == "auto":
        mode = "0840" if now.hour < 12 else "1500"

    print(f"🚀 [Stock Supervisor] 통합 파이프라인 가동 (모드: {mode}, 강제: {force}, Dry-run: {dry_run})")

    # 한국장 개장 여부 검사
    is_kr_open, kr_reason = is_krx_open()
    if not is_kr_open and not force:
        print(f"⏸️ [한국장 휴장] {kr_reason} - 당일 통합 브리핑을 건너뜁니다.")
        return True

    # 2. 전 전략 분석 실행 (한국장 5대 전략 + 미국장 4대 전략)
    kr_signals = []
    us_signals = []
    print("📊 한국/미국 7대 전략 분석 실행 중...")

    # 한국장 전략
    try:
        kr_signals.extend(sniper.run_analysis())
    except Exception as e:
        print(f"⚠️ sniper 오류: {e}")
    try:
        kr_signals.extend(sepa_pivot.run_analysis("KRX"))
    except Exception as e:
        print(f"⚠️ sepa_pivot_kr 오류: {e}")
    try:
        kr_signals.extend(swing.run_analysis("KRX"))
    except Exception as e:
        print(f"⚠️ swing_kr 오류: {e}")
    try:
        kr_signals.extend(cyclical.run_analysis())
    except Exception as e:
        print(f"⚠️ cyclical 오류: {e}")
    try:
        kr_signals.extend(dividend.run_analysis())
    except Exception as e:
        print(f"⚠️ dividend 오류: {e}")

    # 백찬규 센터장 실무 스크리너 (성장주 후보 + 중소형 수급가치)
    screener_signals = []
    try:
        screener_signals, s_meta = run_screener_analysis()
        kr_signals.extend(screener_signals)
        print(f"🎯 실무 스크리너 분석 완료 ({len(screener_signals)}건 포착 / 소스: {s_meta['source']})")
    except Exception as e:
        print(f"⚠️ screener 오류: {e}")

    # Signal Forge 25대 퀀트 전략 (한국주식, 미국주식, 크립토)
    crypto_signals = []
    try:
        sf_kr = signal_forge_bridge.run_signal_forge_analysis("stocks_kr")
        kr_signals.extend(sf_kr)
    except Exception as e:
        print(f"⚠️ SignalForge KR 오류: {e}")

    try:
        sf_us = signal_forge_bridge.run_signal_forge_analysis("stocks_us")
        us_signals.extend(sf_us)
    except Exception as e:
        print(f"⚠️ SignalForge US 오류: {e}")

    try:
        crypto_signals = signal_forge_bridge.run_signal_forge_analysis("crypto")
        print(f"🪙 SignalForge 크립토 레이더 스캔 완료 ({len(crypto_signals)}건)")
    except Exception as e:
        print(f"⚠️ SignalForge Crypto 오류: {e}")

    # 미국장 전략
    try:
        us_signals.extend(htp_momentum.run_analysis())
    except Exception as e:
        print(f"⚠️ htp_momentum 오류: {e}")
    try:
        us_signals.extend(us3x.run_analysis())
    except Exception as e:
        print(f"⚠️ us3x 오류: {e}")
    try:
        us_signals.extend(sepa_pivot.run_analysis("US"))
    except Exception as e:
        print(f"⚠️ sepa_pivot_us 오류: {e}")
    try:
        us_signals.extend(swing.run_analysis("US"))
    except Exception as e:
        print(f"⚠️ swing_us 오류: {e}")

    # DB 저장
    save_signals(kr_signals)
    save_signals(us_signals)
    print(f"💾 시그널 수집 완료 (한국: {len(kr_signals)}건, 미국: {len(us_signals)}건)")

    # 3. 포트폴리오 상태 머신 및 자율 선별 실행
    print("💼 포트폴리오 상태 머신 및 정예 선별 실행 중...")
    kr_portfolio = process_portfolio_cycle(kr_signals, market="KRX")
    us_portfolio = process_portfolio_cycle(us_signals, market="US")

    kr_best_buys = select_best_buys(kr_signals, market="KRX", max_select=3)
    us_best_buys = select_best_buys(us_signals, market="US", max_select=2)

    macro = fetch_us_macro()

    # 4. 알람 메시지 생성
    if mode in ("0840", "morning"):
        alarm_text = build_0840_us_close_kr_open_alarm(
            kr_portfolio, us_portfolio, macro, kr_best_buys,
            screener_signals=screener_signals,
            crypto_signals=crypto_signals
        )
        title = f"미국장 장마감 통합 브리핑, 🇰🇷 한국장 장전 통합 브리핑 ({kr_portfolio['date']})"
    else:
        alarm_text = build_1500_kr_close_us_open_alarm(
            kr_portfolio, us_portfolio, kr_best_buys, us_best_buys,
            screener_signals=screener_signals,
            crypto_signals=crypto_signals
        )
        title = f"15:00 : 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑 , 미국장 장전 통합 브리핑 ({kr_portfolio['date']})"

    if dry_run:
        print("\n" + "=" * 60)
        print("🔍 [DRY-RUN 모드: 텔레그램을 발송하지 않고 출력만 합니다]")
        print("=" * 60)
        print(alarm_text)
        print("=" * 60)
        return True

    # 5. 중앙 통합 텔레그램 발송
    print("📤 중앙 통합 텔레그램 발송 중...")
    success = send_message(alarm_text)

    if success:
        print("🎉 텔레그램 통합 알람 발송 완료!")
        all_signals = kr_signals + us_signals
        project_ids = list(set([s["project_id"] for s in all_signals]))
        record_alarm(title, alarm_text, "ALL", project_ids)

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
    parser.add_argument("--mode", choices=["0840", "1500", "morning", "closing", "auto"], default="auto")
    parser.add_argument("--force", action="store_true", help="휴장일 무시 강제 실행")
    parser.add_argument("--dry-run", action="store_true", help="알람 발송 없이 결과만 확인")
    args = parser.parse_args()

    run_pipeline(mode=args.mode, force=args.force, dry_run=args.dry_run)
