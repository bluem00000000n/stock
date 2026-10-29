#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/sniper.py
스톡 스나이퍼 전략 (RS 상대강도 & 52주 신고가 주도주 + 지수 ETF 타점)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price, fetch_url_json


def get_krx_tick_size(price: float) -> int:
    """KRX 호가 단위 계산"""
    if price < 2000:
        return 1
    elif price < 5000:
        return 5
    elif price < 20000:
        return 10
    elif price < 50000:
        return 50
    elif price < 200000:
        return 100
    elif price < 500000:
        return 500
    else:
        return 1000


def round_to_tick(price: float) -> int:
    tick = get_krx_tick_size(price)
    return int(round(price / tick) * tick)


def calc_rr_ratio(buy_price: float, sl_price: float, tp_price: float) -> float:
    risk = buy_price - sl_price
    if risk <= 0:
        return 0.0
    reward = tp_price - buy_price
    return round(reward / risk, 2)


CANDIDATE_POOL = [
    {"code": "042510", "name": "라온시큐어", "sector": "보안·인증",
     "theme": "글로벌 생체인증·양자암호 수주 모멘텀, 지수 폭락장 속 52주 신고가 돌파",
     "condition": "지지 후 5분봉 저점 상승 및 거래량 유지 확인"},
    {"code": "036930", "name": "주성엔지니어링", "sector": "반도체 ALD",
     "theme": "반도체 수급 방어, 52주 신고가권 박스권 상단",
     "condition": "20일선 지지 및 반도체 섹터 매도세 소진 확인 시 진입"},
    {"code": "161580", "name": "필옵틱스", "sector": "유리기판",
     "theme": "차세대 유리기판 TGV 장비 독점력 및 20일선 위 우상향 지지",
     "condition": "20일선 지지력 확인 후 15분봉 양봉 형성 시 검토"},
    {"code": "000250", "name": "삼천당제약", "sector": "바이오 시밀러",
     "theme": "아일리아 글로벌 판권 계약에 따른 독자적 바이오 수급 방어력",
     "condition": "직전 고점 매물대 상단 지지 및 외인 순매수 지속 확인"},
    {"code": "080220", "name": "제주반도체", "sector": "온디바이스 AI",
     "theme": "온디바이스 AI 메모리 컨트롤러 글로벌 공급",
     "condition": "20일선 재돌파 안착 확인"},
    {"code": "042700", "name": "한미반도체", "sector": "HBM 대장주",
     "theme": "HBM TC 본더 글로벌 독점적 지위",
     "condition": "외인 매도세 진정 및 15분봉 저점 상승 확인"},
    {"code": "196170", "name": "알테오젠", "sector": "바이오 대장주",
     "theme": "글로벌 빅파마 피하주사(SC) 제형 변경 독점 플랫폼",
     "condition": "20일선 지지 확인 및 기관 순매수 유입 확인"},
    {"code": "403870", "name": "HPSP", "sector": "반도체 어닐링",
     "theme": "글로벌 파운드리 독점 고압수소 어닐링 장비, 지수 대비 상대강도 유지",
     "condition": "20일선 지지 확인 및 전일 고가 돌파 시 진입"}
]


def run_analysis() -> List[Dict[str, Any]]:
    """스톡 스나이퍼 전략 분석 실행 및 시그널 리스트 반환"""
    signals = []

    for c in CANDIDATE_POOL:
        p_info = fetch_krx_price(c["code"])
        cur_price = p_info["price"]
        if cur_price <= 0:
            continue

        # 타점 산출
        buy1 = round_to_tick(cur_price * 0.988)
        buy2 = round_to_tick(cur_price * 0.970)
        sl = round_to_tick(buy1 * 0.965)          # -3.5% 손절
        tp1 = round_to_tick(buy1 * 1.055)         # +5.5% 1차 목표
        tp2 = round_to_tick(buy1 * 1.105)         # +10.5% 2차 목표
        rr1 = calc_rr_ratio(buy1, sl, tp1)

        score = 85.0
        if p_info["change_pct"] > 0:
            score += 5.0
        if rr1 >= 1.5:
            score += 5.0

        signals.append({
            "project_id": "stock-sniper",
            "strategy_name": "스톡 스나이퍼",
            "market": "KRX",
            "ticker": c["code"],
            "name": p_info["name"] or c["name"],
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": tp1,
            "target_price_2": tp2,
            "stop_loss_price": sl,
            "risk_reward_ratio": rr1,
            "score": score,
            "sector": c["sector"],
            "theme": c["theme"],
            "pattern": "RS 상대강도 우상향",
            "action_plan": f"1차 {buy1:,}원 / 2차 {buy2:,}원 분할 매수. {c['condition']}",
            "raw_data": {
                "change_pct": p_info["change_pct"],
                "volume": p_info["volume"],
                "buy_1": buy1,
                "buy_2": buy2,
                "tp_2": tp2
            }
        })

    # 점수 기준 정렬 후 상위 5선 반환
    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]


if __name__ == "__main__":
    res = run_analysis()
    print(f"✅ 스나이퍼 분석 완료 ({len(res)}종목 포착)")
    for s in res[:2]:
        print(f"• {s['name']} ({s['ticker']}) - {s['price']:,}원 | 목표 {s['target_price']:,}원 / 손절 {s['stop_loss_price']:,}원 (RR {s['risk_reward_ratio']})")
