#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_monthly_sector_rotation.py
매월 1일 미국 ETF 시장 자금순환(Sector Rotation) 퀀트 리서치 로컬 분석 및 대시보드 동기화 스크립트

기능:
1. 퀀트 자금순환 분석 엔진(core.etf_rotation_analyzer) 호출
2. 전체 Universe 실시간 및 시계열 데이터 수집 & 1M/3M/6M Flow 교차 검증
3. 16개 섹션 분석 보고서 생성 및 data/etf_rotation/ 저장
4. 사후검증용 가설 및 스냅샷 영구 보관
5. 웹 대시보드(status.json 및 index.html) 자동 최신화 동기화
* 텔레그램 발송 기능 완전 삭제 (대시보드 전용 관제)
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 경로 추가
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.etf_rotation_analyzer import ETFRotationEngine


def run(date_str: str = None) -> bool:
    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now()}] 🚀 미국 ETF 자금순환(Sector Rotation) 퀀트 분석 시작 (기준일: {target_date})")

    engine = ETFRotationEngine()
    try:
        report_md, _, record_data = engine.generate_full_report(run_date=target_date)
        print(f"[{datetime.now()}] ✅ 퀀트 분석 완료 및 로컬 보고서/스냅샷 저장 완료.")
        print(f"   • 주도 섹터(Leaders): {record_data['leaders']}")
        print(f"   • 차기 후보(Candidates): {record_data['next_candidates']}")
        print(f"   • 구조적 이탈(Outflows): {record_data['outflows']}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ 분석 엔진 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 대시보드(status.json 및 index.html) 자동 동기화
    print(f"[{datetime.now()}] 🔄 웹 대시보드(status.json & index.html) 데이터 동기화 시작...")
    try:
        py_exec = sys.executable
        update_script = os.path.join(BASE_DIR, "update_status.py")
        res = subprocess.run([py_exec, update_script], capture_output=True, text=True, check=True)
        print(f"[{datetime.now()}] ✅ 대시보드 데이터 동기화 성공!")
    except Exception as e:
        print(f"[{datetime.now()}] ⚠️ 대시보드 동기화 중 오류 (수동 update_status.py 필요): {e}")

    print(f"[{datetime.now()}] 🏁 미국 ETF 자금순환 월간 관제 작업이 성공적으로 완료되었습니다 (대시보드 확인 가능).")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="월간 미국 ETF 자금순환 퀀트 리서치 (로컬 대시보드 연동)")
    parser.add_argument("--date", type=str, default=None, help="기준일자 (YYYY-MM-DD)")
    args = parser.parse_args()

    success = run(date_str=args.date)
    sys.exit(0 if success else 1)
