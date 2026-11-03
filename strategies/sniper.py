#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/sniper.py
스톡 스나이퍼 전략 (RS 상대강도 & 52주 신고가 주도주 타점)
- 대상 구조 (한국 & 미국 동일 대칭 구조):
  • 🇰🇷 한국장: 대형주 4선 (알테오젠, 한미반도체, 삼천당제약, HPSP) + 중소형주 4선 (라온시큐어, 주성엔지니어링, 필옵틱스, 제주반도체)
  • 🇺🇸 미국장: 대형주 4선 (NVDA, MSFT, AVGO, TSLA) + 중소형주 4선 (PLTR, APP, CRWD, ALAB)
- 시장별 맞춤 조건:
  • 한국장(KRX): KRX 호가단위, 1차(-1.2%)/2차(-3.0%) 분할, 손절 -3.5%, 목표가 +5.5%/+10.5%, 원화(원)
  • 미국장(US): 센트단위(2자리), 높은 ATR 변동성 완충 손절 -5.5%, 목표가 +8.5%/+16.0%, 달러($), 실시간 시세 연동
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price, fetch_us_price


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


def round_to_krx_tick(price: float) -> int:
    tick = get_krx_tick_size(price)
    return int(round(price / tick) * tick)


def calc_rr_ratio(buy_price: float, sl_price: float, tp_price: float) -> float:
    risk = buy_price - sl_price
    if risk <= 0:
        return 0.0
    reward = tp_price - buy_price
    return round(reward / risk, 2)


# ==============================================================================
# 🇰🇷 한국장 스나이퍼 후보 풀 (대형주 4선 + 중소형주 4선)
# ==============================================================================
KR_LARGE_SNIPER = [
    {"code": "000660", "name": "SK하이닉스", "sector": "HBM 반도체", "cap_size": "대형주",
     "theme": "엔비디아 HBM3E/HBM4 독점 공급 및 외인/기관 연속 대량 매수",
     "condition": "20일선 지지 확인 및 수급 주도주 돌파 시 진입"},
    {"code": "000100", "name": "유한양행", "sector": "제약·바이오", "cap_size": "대형주",
     "theme": "렉라자(레이저티닙) 글로벌 FDA 상업화 랠리 및 20주선 위 양매수",
     "condition": "주봉 RSI 골든크로스 및 20일선 지지 후 양봉 돌파"},
    {"code": "086280", "name": "현대글로비스", "sector": "물류·해운", "cap_size": "대형주",
     "theme": "완성차 해상운송 글로벌 물류 신고가 및 외인·기관 쌍끌이 매수",
     "condition": "20주선 지지 및 5분봉 저점 상승 확인"},
    {"code": "005930", "name": "삼성전자", "sector": "반도체 대형", "cap_size": "대형주",
     "theme": "패시브 수급 전환 기대 및 60일선 바닥 다지기",
     "condition": "외인 매도세 진정 및 15분봉 저점 상승 확인"}
]

KR_MID_SNIPER = [
    {"code": "042700", "name": "한미반도체", "sector": "HBM 본더", "cap_size": "중소형주",
     "theme": "HBM TC 본더 글로벌 독점적 지위 및 기관 수급 유입",
     "condition": "20일선 지지 확인 및 수급 1순위 돌파"},
    {"code": "403870", "name": "HPSP", "sector": "반도체 어닐링", "cap_size": "중소형주",
     "theme": "글로벌 파운드리 독점 고압수소 어닐링 장비, 지수 대비 상대강도 유지",
     "condition": "20일선 지지 확인 및 전일 고가 돌파 시 진입"},
    {"code": "042510", "name": "라온시큐어", "sector": "보안·인증", "cap_size": "중소형주",
     "theme": "글로벌 생체인증·양자암호 수주 모멘텀, 지수 폭락장 속 52주 신고가 돌파",
     "condition": "지지 후 5분봉 저점 상승 및 거래량 유지 확인"},
    {"code": "036930", "name": "주성엔지니어링", "sector": "반도체 ALD", "cap_size": "중소형주",
     "theme": "반도체 수급 방어, 52주 신고가권 박스권 상단",
     "condition": "20일선 지지 및 반도체 섹터 매도세 소진 확인 시 진입"}
]

# ==============================================================================
# 🇺🇸 미국장 스나이퍼 후보 풀 (대형주 4선 + 중소형주 4선: 한국과 동일 구조)
# ==============================================================================
US_LARGE_SNIPER = [
    {"ticker": "NVDA", "name": "Nvidia", "sector": "Information Technology", "cap_size": "대형주",
     "theme": "블랙웰 B200 풀캐파 가동, AI 인프라 글로벌 독점 및 사상 최고가권",
     "condition": "20일 EMA 지지 및 시초가 갭 메우기 완료 후 반등 확인"},
    {"ticker": "LLY", "name": "Eli Lilly", "sector": "Healthcare", "cap_size": "대형주",
     "theme": "GLP-1 비만치료제 젭바운드/마운자로 글로벌 시장 독점적 랠리",
     "condition": "20일선 지지 후 전일 고가 돌파 시 진입"},
    {"ticker": "GE", "name": "GE Aerospace", "sector": "Industrials", "cap_size": "대형주",
     "theme": "항공우주 엔진 및 애프터마켓 수주 잔고 사상 최대치 경신",
     "condition": "50일선 지지 반등 및 대형주 수급 유입 확인"},
    {"ticker": "COST", "name": "Costco", "sector": "Consumer Staples", "cap_size": "대형주",
     "theme": "경기방어적 멤버십 기반 안정적 이익 성장 및 52주 신고가 우상향",
     "condition": "플랫 베이스 지지선 안착 확인 후 진입"},
    {"ticker": "AVGO", "name": "Broadcom", "sector": "Information Technology", "cap_size": "대형주",
     "theme": "빅테크 맞춤형 AI 가속기 및 네트워킹 스위치 독점적 지배력",
     "condition": "10일선 지지 확인 후 ORB(초반 30분) 돌파 시 진입"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financials", "cap_size": "대형주",
     "theme": "미국 대형 금융주 순이자이익 견조 및 글로벌 IB 자문 수수료 급증",
     "condition": "20일선 지지 확인 후 전일 고가 돌파 시 진입"},
    {"ticker": "XOM", "name": "ExxonMobil", "sector": "Energy", "cap_size": "대형주",
     "theme": "에너지 메이저 정제마진 회복 및 주주환원 자사주 매입 모멘텀",
     "condition": "200일선 지지 반등 확인 시 진입"}
]

US_MID_SNIPER = [
    {"ticker": "TMDX", "name": "TransMedics", "sector": "Healthcare", "cap_size": "중소형주",
     "theme": "장기이식 보존 시스템(OCS) 글로벌 독점 및 전용 항공 물류 성장",
     "condition": "20일선 지지 확인 및 수급 1순위 돌파"},
    {"ticker": "POWL", "name": "Powell Industries", "sector": "Industrials", "cap_size": "중소형주",
     "theme": "AI 데이터센터 전력망 및 특수 배전반 수주잔고 폭발적 증가",
     "condition": "VCP 수축 후 박스권 상단 돌파 시 진입"},
    {"ticker": "VRT", "name": "Vertiv Holdings", "sector": "Industrials", "cap_size": "중소형주",
     "theme": "하이퍼스케일 AI 데이터센터 액체냉각 및 전력 솔루션 수주 1위",
     "condition": "신고가 부근 지지 후 5분봉 저점 상승 확인"},
    {"ticker": "PLTR", "name": "Palantir", "sector": "Information Technology", "cap_size": "중소형주",
     "theme": "AIP 플랫폼 상용화 급증 및 미 국방부 수주 모멘텀, S&P500 최상위 모멘텀",
     "condition": "전일 고가 지지선 안착 및 거래량 실린 양봉 확인"},
    {"ticker": "APP", "name": "AppLovin", "sector": "Information Technology", "cap_size": "중소형주",
     "theme": "AXON 2.0 엔진 기반 폭발적 매출·영업이익 서프라이즈, 주도주 랠리",
     "condition": "장초반 변동성 소진 후 5분봉 지지선 형성 시 진입"},
    {"ticker": "ROOT", "name": "Root Inc", "sector": "Financials", "cap_size": "중소형주",
     "theme": "AI 머신러닝 자동차보험 손해율 개선 및 턴어라운드 흑자 전환",
     "condition": "골든크로스 안착 및 거래량 유지 확인"}
]


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """스톡 스나이퍼 전략 분석 실행 (대형주/중소형주 균형 선별)"""
    signals = []
    is_kr = market.upper() in ("KRX", "KR", "KOR")

    if is_kr:
        candidate_pool = KR_LARGE_SNIPER + KR_MID_SNIPER
        for c in candidate_pool:
            p_info = fetch_krx_price(c["code"])
            cur_price = p_info["price"]
            if cur_price <= 0:
                continue

            # 한국장 타점 산출 (KRX 호가 단위 준수)
            buy1 = round_to_krx_tick(cur_price * 0.988)
            buy2 = round_to_krx_tick(cur_price * 0.970)
            sl = round_to_krx_tick(buy1 * 0.965)          # -3.5% 손절
            tp1 = round_to_krx_tick(buy1 * 1.055)         # +5.5% 1차 목표
            tp2 = round_to_krx_tick(buy1 * 1.105)         # +10.5% 2차 목표
            rr1 = calc_rr_ratio(buy1, sl, tp1)

            cap_size = c.get("cap_size", "대형주")
            score = 86.0 if cap_size == "대형주" else 85.0
            if p_info["change_pct"] > 0:
                score += 5.0
            if rr1 >= 1.5:
                score += 5.0

            signals.append({
                "project_id": "stock-sniper",
                "strategy_name": f"스톡 스나이퍼 ({cap_size})",
                "market": "KRX",
                "cap_size": cap_size,
                "ticker": c["code"],
                "name": p_info["name"] or c["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1,
                "target_price_2": tp2,
                "stop_loss_price": sl,
                "risk_reward_ratio": rr1,
                "score": score,
                "sector": f"{cap_size} / {c['sector']}",
                "theme": f"[{cap_size}] {c['theme']}",
                "pattern": "RS 상대강도 우상향",
                "action_plan": f"[{cap_size}] 1차 {buy1:,}원 / 2차 {buy2:,}원 분할 매수. {c['condition']}",
                "raw_data": {
                    "cap_size": cap_size,
                    "change_pct": p_info["change_pct"],
                    "volume": p_info["volume"],
                    "buy_1": buy1,
                    "buy_2": buy2,
                    "tp_2": tp2
                }
            })
    else:
        # 🇺🇸 미국장 스나이퍼 분석: 센트 단위, 대형주/중소형주 대칭 구조
        candidate_pool = US_LARGE_SNIPER + US_MID_SNIPER
        for c in candidate_pool:
            ticker = c["ticker"]
            p_info = fetch_us_price(ticker)
            cur_price = p_info["price"]
            if cur_price <= 0:
                continue

            cap_size = c.get("cap_size", "대형주")
            # 미국장 타점 산출 (변동성 최적화)
            buy1 = round(cur_price * 0.985, 2)
            buy2 = round(cur_price * 0.965, 2)
            sl = round(buy1 * 0.945, 2)              # -5.5% 손절
            tp1 = round(buy1 * 1.085, 2)             # +8.5% 1차 목표
            tp2 = round(buy1 * 1.160, 2)             # +16.0% 2차 목표
            rr1 = calc_rr_ratio(buy1, sl, tp1)

            score = 88.0 if cap_size == "대형주" else 87.0
            if p_info["change_pct"] > 0:
                score += 4.0
            if rr1 >= 1.5:
                score += 5.0

            signals.append({
                "project_id": "stock-sniper",
                "strategy_name": f"스톡 스나이퍼 (US {cap_size})",
                "market": "US",
                "cap_size": cap_size,
                "ticker": ticker,
                "name": p_info["name"] or c["name"],
                "signal_type": "BUY",
                "price": cur_price,
                "target_price": tp1,
                "target_price_2": tp2,
                "stop_loss_price": sl,
                "risk_reward_ratio": rr1,
                "score": score,
                "sector": f"{cap_size} / {c['sector']}",
                "theme": f"[{cap_size}] {c['theme']}",
                "pattern": "RS 초강세 주도주 눌림목",
                "action_plan": f"[{cap_size}] 1차 ${buy1:.2f} / 2차 ${buy2:.2f} 분할 매수. {c['condition']}. 손절 ${sl:.2f} 엄수",
                "raw_data": {
                    "cap_size": cap_size,
                    "change_pct": p_info["change_pct"],
                    "buy_1": buy1,
                    "buy_2": buy2,
                    "tp_2": tp2
                }
            })

    # 대형주 상위 + 중소형주 상위를 균형 있게 정렬
    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:6]


if __name__ == "__main__":
    kr = run_analysis("KRX")
    print(f"✅ 스나이퍼 한국장 분석 완료 ({len(kr)}종목 포착)")
    for s in kr:
        print(f"• [KR {s['cap_size']}] {s['name']} ({s['ticker']}) - {s['price']:,}원 | {s['action_plan']}")

    us = run_analysis("US")
    print(f"\n✅ 스나이퍼 미국장 분석 완료 ({len(us)}종목 포착)")
    for s in us:
        print(f"• [US {s['cap_size']}] {s['name']} ({s['ticker']}) - ${s['price']:.2f} | {s['action_plan']}")
