#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/engine.py
백찬규 센터장(NH투자증권) 실무 스크리너 총괄 실행 엔진

- Excel 파일 자동 감지 및 로드 (우선 모드)
- 파일 부재 시 네이버 증권 온라인 실시간 수집 (자동 백업 모드)
- 성장주 후보 스크리너 & 중소형 스크리너 조건 검출
- stock-supervisor 표준 시그널 규격으로 패키징하여 포트폴리오/알람 엔진에 전달
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from screener.excel_parser import find_latest_screener_file, parse_screener_file
from screener.filters import (
    filter_growth_large_candidates,
    filter_mid_small_candidates,
    to_float
)
from screener.online_collector import collect_online_universe


def run_screener_analysis() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    스크리너 통합 실행:
    Returns:
        (signals_list, metadata_dict)
    """
    signals = []
    meta = {
        "source": "online",
        "file_path": None,
        "total_scanned": 0,
        "growth_large_count": 0,
        "mid_small_count": 0
    }

    # 1. 엑셀 파일 탐색
    latest_file = find_latest_screener_file()
    items = []

    if latest_file and os.path.exists(latest_file):
        try:
            print(f"📂 [Screener] 최신 엑셀 파일 발견: {latest_file}")
            items, mapping = parse_screener_file(latest_file)
            if items:
                meta["source"] = "excel"
                meta["file_path"] = latest_file
                print(f"📊 엑셀 파싱 성공 (총 {len(items)}개 종목 데이터 로드 완료, 매핑 필드: {list(mapping.keys())})")
        except Exception as e:
            print(f"⚠️ 엑셀 파일 파싱 오류: {e} -> 온라인 모드로 전환합니다.")
            items = []

    # 2. 엑셀 데이터가 없을 경우 온라인 수집 실행
    if not items:
        print("🌐 [Screener] 엑셀 파일 미검출 -> 네이버 증권 실시간 온라인 데이터 수집 모드 가동...")
        items = collect_online_universe()
        meta["source"] = "online"
        print(f"🌐 온라인 유니버스 {len(items)}개 종목 수집 완료")

    meta["total_scanned"] = len(items)

    # 3. 성장주 후보 스크리너 필터링
    growth_candidates = filter_growth_large_candidates(items)
    meta["growth_large_count"] = len(growth_candidates)

    # 4. 중소형 스크리너 필터링
    mid_small_candidates = filter_mid_small_candidates(items)
    meta["mid_small_count"] = len(mid_small_candidates)

    # 5. stock-supervisor 표준 시그널 규격으로 변환
    # 성장주 후보 시그널 생성 (상위 최대 3선)
    for c in growth_candidates[:3]:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        cur_price = to_float(c.get("price")) or 100000.0
        target_price = round(cur_price * 1.25)
        stop_loss = round(cur_price * 0.93)
        risk = cur_price - stop_loss
        reward = target_price - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.5

        # 점수 계산: 실적 모멘텀(27년 영업익 증가율) + 수급(외인) + 거래량 변화율
        vol_change = c.get("_vol_change_rate", 0.0)
        op_growth = c.get("_op_growth_27", 16.0)
        roe_26 = c.get("_roe_26", 15.0)
        score = round(70.0 + min(op_growth * 0.5, 15.0) + min(roe_26 * 0.5, 10.0) + min(max(vol_change, 0) * 0.05, 5.0), 1)

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 성장주 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(cur_price * 1.35),
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": score,
            "sector": "대형 성장주 (실적+수급)",
            "theme": "27년 고성장 컨센서스",
            "pattern": f"거래량 {vol_change:+.1f}% 급증",
            "action_plan": f"시총 {c.get('_marcap_eok', 0):,.0f}억 / 27년 영업익 +{op_growth:.1f}% / 26년 ROE {roe_26:.1f}% / 외인 20일 +{c.get('_foreign_net_buy_20d', 0):,.0f}억",
            "raw_data": {
                "screener_type": "GROWTH_LARGE",
                "sales_growth_27": c.get("_sales_growth_27"),
                "op_growth_27": op_growth,
                "roe_26": roe_26,
                "eps_chg_1m": c.get("_eps_chg_1m"),
                "eps_chg_3m": c.get("_eps_chg_3m"),
                "foreign_net_buy_20d": c.get("_foreign_net_buy_20d"),
                "vol_change_rate": vol_change
            }
        })

    # 중소형 스크리너 시그널 생성 (상위 최대 2선)
    for c in mid_small_candidates[:2]:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        cur_price = to_float(c.get("price")) or 25000.0
        target_price = round(cur_price * 1.20)
        stop_loss = round(cur_price * 0.92)
        risk = cur_price - stop_loss
        reward = target_price - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        vol_ratio = c.get("_vol_ratio", 200.0)
        pb_val = c.get("_trailing_pb", 1.0)
        score = round(68.0 + min((vol_ratio - 200.0) * 0.05, 12.0) + (10.0 if pb_val <= 1.0 else 5.0), 1)

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 중소형 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(cur_price * 1.30),
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": score,
            "sector": "중소형 수급 가치주",
            "theme": "거래량 200%+ 폭발 & 저PBR",
            "pattern": f"52주 대비 거래량 {vol_ratio:.0f}%",
            "action_plan": f"시총 {c.get('_marcap_eok', 0):,.0f}억 (2천억~1조) / 5일 거래량 52주 대비 {vol_ratio:.0f}% 폭증 / PBR {pb_val:.2f}배",
            "raw_data": {
                "screener_type": "MID_SMALL",
                "vol_ratio": vol_ratio,
                "trailing_pb": pb_val,
                "marcap_eok": c.get("_marcap_eok")
            }
        })

    return signals, meta


if __name__ == "__main__":
    sigs, m = run_screener_analysis()
    print(f"\n✅ 스크리너 실행 완료 ({m['source']} 모드, 총 포착 시그널: {len(sigs)}건)")
    for s in sigs:
        print(f"• [{s['strategy_name']}] {s['name']} ({s['ticker']}) - {s['price']:,}원 | {s['action_plan']} (점수: {s['score']})")
