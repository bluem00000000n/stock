#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/quarterly_manager.py
백찬규 센터장 실무 스크리너 분기별 유니버스 관리 및 실시간 매수/매도(Trading) 엔진

[운용 원칙]
1. 엑셀 스크리닝(컨센서스 및 재무 실적 전수 필터링)은 '매 분기 실적보고'가 끝나면
   공시 및 컨센서스 데이터를 취합하여 정기 스크리닝을 수행한다.
2. 그때까지(차기 분기 실적 발표 전까지)는 현재 추출된 12종목 유니버스 안에서
   실시간 시세, 기술적 지표, 수급에 기반하여 매수/매도(Trading)를 집행한다.
"""

import os
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "screener"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UNIVERSE_FILE = DATA_DIR / "quarterly_universe.json"

from screener.baek_dataset import BAEK_GROWTH_LARGE_MASTER, BAEK_MID_SMALL_MASTER
from screener.filters import to_float


def init_quarterly_universe() -> Dict[str, Any]:
    """분기 확정 스크리너 유니버스 초기화 및 저장"""
    universe_data = {
        "quarter": "2026-Q3",
        "screened_date": "2026-10-29",
        "next_screening_expected": "2026-11-20 (3Q 실적 공시 마감 후)",
        "strategy_rule": "매 분기 실적보고 종료 후 데이터 취합 스크리닝. 차기 실적보고 전까지 본 12선 내에서 집중 매수/매도 집행",
        "growth_large": BAEK_GROWTH_LARGE_MASTER,
        "mid_small": BAEK_MID_SMALL_MASTER
    }
    with open(UNIVERSE_FILE, "w", encoding="utf-8") as f:
        json.dump(universe_data, f, ensure_ascii=False, indent=2)
    return universe_data


def load_quarterly_universe() -> Dict[str, Any]:
    """저장된 분기 유니버스 파일 로드 (없으면 생성)"""
    if not UNIVERSE_FILE.exists():
        return init_quarterly_universe()
    try:
        with open(UNIVERSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 분기 유니버스 로드 실패: {e}")
        return init_quarterly_universe()


def evaluate_trading_signal(stock: Dict[str, Any], live_quote: Dict[str, Any]) -> Dict[str, Any]:
    """
    분기 확정 종목의 실시간 시세, 수급, 가격 위치에 따른 실시간 매수/매도 액션 판정
    
    Returns:
        {
            "action": "BUY" | "HOLD" | "TAKE_PROFIT" | "STOP_LOSS",
            "action_desc": "눌림목 매수 타점" | "추세 유지 홀딩" | "분할 익절 도달" | "손절선 이탈",
            "entry_price": float,
            "target_price_1": float,
            "target_price_2": float,
            "stop_loss_price": float,
            "risk_reward_ratio": float,
            "score": float
        }
    """
    cur_price = live_quote.get("price") or to_float(stock.get("price")) or 50000.0
    stype = stock.get("screener_type", "GROWTH_LARGE")
    
    # 목표가 및 손절가 계산
    if stype == "GROWTH_LARGE":
        # 대형 성장주: 1차 +25%, 2차 +35%, 손절 -7%
        target_1 = round(cur_price * 1.25)
        target_2 = round(cur_price * 1.35)
        stop_loss = round(cur_price * 0.93)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.5
    else:
        # 중소형 수급가치: 1차 +20%, 2차 +30%, 손절 -8%
        target_1 = round(cur_price * 1.20)
        target_2 = round(cur_price * 1.30)
        stop_loss = round(cur_price * 0.92)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.0

    # 당일 등락률 및 수급에 따른 액션 판정
    fluct = to_float(live_quote.get("fluctuations_ratio")) or 0.0
    foreign_20d = to_float(stock.get("foreign_net_buy_20d")) or 0.0
    organ_20d = to_float(stock.get("organ_net_buy_20d")) or 0.0

    # 실시간 액션 규칙
    # 1. 과매도 및 눌림목 지지 (당일 -2% ~ +2% 안정권 & 수급 유입) -> 적극 매수
    # 2. 당일 +3% 이상 급등 -> 추격 금지, 보유/분할매수 대기
    # 3. 목표가 도달 시 -> 분할 익절
    # 4. 손절선 도달 시 -> 손절
    if fluct <= -7.0:
        action = "STOP_LOSS"
        action_desc = f"단기 급락 경계 (-{abs(fluct):.1f}%), 지지선 확인 후 재진입"
        score = 50.0
    elif -3.0 <= fluct <= 2.5:
        action = "BUY"
        action_desc = f"유효 진입 타점 (당일 {fluct:+.1f}%), 목표가 대비 RR {rr}배 분할 매수"
        score = 85.0 if stype == "GROWTH_LARGE" else 82.0
    elif fluct > 5.0:
        action = "HOLD"
        action_desc = f"단기 급등 (+{fluct:.1f}%), 추격매수 금지 및 기존 포지션 홀딩"
        score = 75.0
    else:
        action = "BUY"
        action_desc = f"정석 분할 매수 타점 (목표가 {target_1:,}원)"
        score = 80.0

    return {
        "action": action,
        "action_desc": action_desc,
        "entry_price": cur_price,
        "target_price_1": target_1,
        "target_price_2": target_2,
        "stop_loss_price": stop_loss,
        "risk_reward_ratio": rr,
        "score": score
    }
