#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/engine.py
백찬규 센터장(NH투자증권) 실무 스크리너 총괄 실행 엔진

[운용 원칙]
1. 엑셀 스크리닝(컨센서스 및 재무 실적 전수 필터링)은 '매 분기 실적보고'가 끝나면
   데이터를 취합하여 정기 스크리닝 작업을 수행한다.
2. 그때까지(차기 분기 실적 발표 전까지)는 현재 확정된 12종목 유니버스 안에서
   실시간 시세와 수급에 기반하여 매수/매도(Trading)를 집행한다.
"""

import sys
import os
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from screener.excel_parser import find_latest_screener_file, parse_screener_file
from screener.filters import (
    filter_growth_large_candidates,
    filter_mid_small_candidates,
    to_float,
    normalize_market_cap
)
from screener.baek_dataset import BAEK_GROWTH_LARGE_MASTER, BAEK_MID_SMALL_MASTER
from screener.quarterly_manager import load_quarterly_universe, evaluate_trading_signal


def refresh_live_quote(code: str) -> Dict[str, Any]:
    """네이버 증권 모바일 API를 통해 종목의 실시간 현재가 및 등락률 조회"""
    result = {
        "price": None,
        "fluctuations_ratio": None,
        "market_cap": None
    }
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        result["price"] = to_float(data.get("closePrice"))
        result["fluctuations_ratio"] = to_float(data.get("fluctuationsRatio"))
    except Exception:
        pass
    return result


def run_screener_analysis() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    백찬규 센터장 스크리너 통합 실행:
    - 분기 확정 12종목 유니버스 기반 실시간 매수/매도 트레이딩 액션 도출
    - 차기 분기 실적보고 시 엑셀 투입으로 자동 재스크리닝 지원
    """
    signals = []
    meta = {
        "source": "quarterly_active_trading",
        "file_path": None,
        "quarter": "2026-Q3",
        "next_screening_expected": "2026-11-20 (3Q 실적공시 마감 후)",
        "total_scanned": 12,
        "growth_large_count": 0,
        "mid_small_count": 0,
        "growth_large_list": [],
        "mid_small_list": []
    }

    # 1. 신규 엑셀 파일 탐색 (분기 실적시즌 종료 후 사용자가 새 엑셀을 투입한 경우)
    latest_file = find_latest_screener_file()
    items = []

    if latest_file and os.path.exists(latest_file):
        try:
            print(f"📂 [Screener] 신규 분기 엑셀 파일 발견: {latest_file} -> 전수 재스크리닝 가동")
            items, mapping = parse_screener_file(latest_file)
            if items:
                meta["source"] = "new_excel_quarterly_screen"
                meta["file_path"] = latest_file
                meta["total_scanned"] = len(items)
                print(f"📊 엑셀 파싱 성공 (총 {len(items)}개 종목 데이터 로드 완료)")
        except Exception as e:
            print(f"⚠️ 엑셀 파일 파싱 오류: {e}")
            items = []

    # 2. 평상시: 분기 확정 12종목 유니버스 로드
    if not items:
        q_data = load_quarterly_universe()
        meta["quarter"] = q_data.get("quarter", "2026-Q3")
        meta["next_screening_expected"] = q_data.get("next_screening_expected", "2026-11-20")
        items = q_data.get("growth_large", BAEK_GROWTH_LARGE_MASTER) + q_data.get("mid_small", BAEK_MID_SMALL_MASTER)

    # 3. 성장주 후보와 중소형 후보 분류
    growth_candidates = filter_growth_large_candidates(items)
    mid_small_candidates = filter_mid_small_candidates(items)

    meta["growth_large_count"] = len(growth_candidates)
    meta["mid_small_count"] = len(mid_small_candidates)
    meta["growth_large_list"] = growth_candidates
    meta["mid_small_list"] = mid_small_candidates

    # 4. 종목별 실시간 시세 반영 및 매수/매도 액션 산출
    # [리스트 1: 대형 성장주 4선 매수/매도 시그널]
    for c in growth_candidates:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        
        quote = refresh_live_quote(ticker)
        cur_price = quote.get("price") or to_float(c.get("price")) or 100000.0
        
        # 실시간 매매 전략 평가
        ts = evaluate_trading_signal(c, quote)
        
        vol_change = c.get("_vol_change_rate", 0.0)
        op_growth = c.get("_op_growth_27", 16.0)
        roe_26 = c.get("_roe_26", 15.0)

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 성장주 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": ts["action"], # BUY, HOLD, TAKE_PROFIT, STOP_LOSS
            "price": cur_price,
            "target_price": ts["target_price_1"],
            "target_price_2": ts["target_price_2"],
            "stop_loss_price": ts["stop_loss_price"],
            "risk_reward_ratio": ts["risk_reward_ratio"],
            "score": ts["score"],
            "sector": "대형 성장주 (실적+수급)",
            "theme": c.get("video_note", "27년 고성장 컨센서스"),
            "pattern": f"거래량 {vol_change:+.1f}% 급증 | {ts['action_desc']}",
            "action_plan": f"[{ts['action']}] {ts['action_desc']} | 기준가 {int(cur_price):,}원 ➔ 목표가 {int(ts['target_price_1']):,}원 (손절 {int(ts['stop_loss_price']):,}원)",
            "raw_data": {
                "screener_type": "GROWTH_LARGE",
                "sales_growth_27": c.get("_sales_growth_27"),
                "op_growth_27": op_growth,
                "roe_26": roe_26,
                "eps_chg_1m": c.get("_eps_chg_1m"),
                "eps_chg_3m": c.get("_eps_chg_3m"),
                "foreign_net_buy_20d": c.get("_foreign_net_buy_20d"),
                "vol_change_rate": vol_change,
                "action": ts["action"],
                "action_desc": ts["action_desc"]
            }
        })

    # [리스트 2: 중소형 수급 가치주 8선 매수/매도 시그널]
    for c in mid_small_candidates:
        ticker = str(c.get("code") or c.get("ticker") or "").zfill(6)
        name = str(c.get("name") or c.get("종목명") or ticker)
        
        quote = refresh_live_quote(ticker)
        cur_price = quote.get("price") or to_float(c.get("price")) or 25000.0
        
        # 실시간 매매 전략 평가
        ts = evaluate_trading_signal(c, quote)

        vol_ratio = c.get("_vol_ratio", 200.0)
        pb_val = c.get("_trailing_pb", 1.0)
        organ_20d = c.get("_organ_net_buy_20d", 0.0)
        theme_text = c.get("theme") or "거래량 200%+ 폭발 & 저PBR"

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 중소형 스크리너",
            "market": "KRX",
            "ticker": ticker,
            "name": name,
            "signal_type": ts["action"],
            "price": cur_price,
            "target_price": ts["target_price_1"],
            "target_price_2": ts["target_price_2"],
            "stop_loss_price": ts["stop_loss_price"],
            "risk_reward_ratio": ts["risk_reward_ratio"],
            "score": ts["score"],
            "sector": "중소형 수급 가치주",
            "theme": f"{theme_text} ({c.get('video_note', '')})",
            "pattern": f"52주 대비 거래량 {vol_ratio:.0f}% 폭증 | {ts['action_desc']}",
            "action_plan": f"[{ts['action']}] {ts['action_desc']} | 기준가 {int(cur_price):,}원 ➔ 목표가 {int(ts['target_price_1']):,}원 (손절 {int(ts['stop_loss_price']):,}원)",
            "raw_data": {
                "screener_type": "MID_SMALL",
                "vol_ratio": vol_ratio,
                "trailing_pb": pb_val,
                "marcap_eok": c.get("_marcap_eok"),
                "organ_net_buy_20d": organ_20d,
                "action": ts["action"],
                "action_desc": ts["action_desc"]
            }
        })

    return signals, meta


if __name__ == "__main__":
    sigs, m = run_screener_analysis()
    print(f"\n✅ 분기 스크리너 운용 엔진 가동 (분기: {m['quarter']} / 다음 갱신: {m['next_screening_expected']})")
    print(f"📌 [원칙] 분기 실적보고 마감 후 데이터 취합 스크리닝, 그때까지는 12개 확정 종목 내에서 매수/매도 집행\n")
    
    print("=== [리스트 1: 대형 성장주 4선 실시간 매매 액션] ===")
    for s in [x for x in sigs if x['strategy_name'] == '백찬규 성장주 스크리너']:
        print(f"• {s['name']} ({s['ticker']}) : {int(s['price']):,}원 | {s['action_plan']}")

    print("\n=== [리스트 2: 중소형 수급 8선 실시간 매매 액션] ===")
    for s in [x for x in sigs if x['strategy_name'] == '백찬규 중소형 스크리너']:
        print(f"• {s['name']} ({s['ticker']}) : {int(s['price']):,}원 | {s['action_plan']}")
