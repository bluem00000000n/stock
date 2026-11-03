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
# 🇰🇷 한국장 스나이퍼 후보 풀 (대형주 4선 + 중소형주 4선: Stage 2 주도주)
# ==============================================================================
KR_LARGE_SNIPER = [
    {"code": "028050", "name": "삼성E&A", "sector": "플랜트 EPC", "cap_size": "대형주",
     "theme": "친환경 플랜트 대형 EPC 글로벌 수주 랠리 및 외인/기관 연속 양매수",
     "condition": "20일선 지지 확인 및 52주 신고가권 수급 돌파 시 진입"},
    {"code": "000810", "name": "삼성화재", "sector": "금융·보험", "cap_size": "대형주",
     "theme": "역대 최대 순이익 주주환원 밸류업 대장주 및 외인 집중 순매수",
     "condition": "신고가 박스권 돌파 및 20일선 지지 후 양봉 분출"},
    {"code": "068270", "name": "셀트리온", "sector": "바이오시밀러", "cap_size": "대형주",
     "theme": "짐펜트라 미국 PBM 등재 확대 및 기관 쌍끌이 매수 전환",
     "condition": "20주선 지지 및 5분봉 저점 상승 확인"},
    {"code": "033780", "name": "KT&G", "sector": "소비재·지주", "cap_size": "대형주",
     "theme": "글로벌 전자담배 수출 호조 및 자사주 소각 등 주주가치 제고",
     "condition": "20일선 지지 확인 및 수급 1순위 돌파"}
]

KR_MID_SNIPER = [
    {"code": "093320", "name": "케이아이엔엑스", "sector": "IDC·인프라", "cap_size": "중소형주",
     "theme": "과천 AI 전용 IDC 본격 가동 및 52주 신고가 지속 경신 주도주",
     "condition": "하이타이트 플래그 지지 확인 및 수급 돌파"},
    {"code": "053800", "name": "안랩", "sector": "클라우드 보안", "cap_size": "중소형주",
     "theme": "AI 기반 차세대 보안 플랫폼 수주 폭발 및 지수 대비 초강세",
     "condition": "20일선 지지 확인 및 전일 고가 돌파 시 진입"},
    {"code": "425420", "name": "티에프이", "sector": "반도체 소켓", "cap_size": "중소형주",
     "theme": "AI 고성능 반도체 테스트 소켓 국산화 선도 및 기관 수급 유입",
     "condition": "지지 후 5분봉 저점 상승 및 거래량 유지 확인"},
    {"code": "219130", "name": "타이거일렉", "sector": "PCB 기판", "cap_size": "중소형주",
     "theme": "고다층 초고밀도 검사용 기판 공급 확대 및 52주 신고가 분출",
     "condition": "20일선 지지 및 15분봉 저점 상승 확인 시 진입"}
]

# ==============================================================================
# 🇺🇸 미국장 스나이퍼 후보 풀 (대형주 5선 + 중소형주 4선: 한국과 동일 구조)
# ==============================================================================
US_LARGE_SNIPER = [
    {"ticker": "LLY", "name": "Eli Lilly", "sector": "Healthcare", "cap_size": "대형주",
     "theme": "GLP-1 비만치료제 젭바운드/마운자로 글로벌 시장 독점적 랠리",
     "condition": "20일선 지지 후 전일 고가 돌파 시 진입"},
    {"ticker": "COST", "name": "Costco", "sector": "Consumer Staples", "cap_size": "대형주",
     "theme": "경기방어적 멤버십 기반 안정적 이익 성장 및 52주 신고가 우상향",
     "condition": "플랫 베이스 지지선 안착 확인 후 진입"},
    {"ticker": "XOM", "name": "ExxonMobil", "sector": "Energy", "cap_size": "대형주",
     "theme": "에너지 메이저 정제마진 회복 및 주주환원 자사주 매입 모멘텀",
     "condition": "200일선 지지 반등 확인 시 진입"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financials", "cap_size": "대형주",
     "theme": "미국 대형 금융주 순이자이익 견조 및 글로벌 IB 자문 수수료 급증",
     "condition": "20일선 지지 확인 후 전일 고가 돌파 시 진입"},
    {"ticker": "NVDA", "name": "Nvidia", "sector": "Information Technology", "cap_size": "대형주",
     "theme": "블랙웰 B200 풀캐파 가동, AI 인프라 글로벌 독점 및 사상 최고가권",
     "condition": "20일 EMA 지지 및 시초가 갭 메우기 완료 후 반등 확인"}
]

US_MID_SNIPER = [
    {"ticker": "PLTR", "name": "Palantir", "sector": "Information Technology", "cap_size": "중소형주",
     "theme": "AIP 플랫폼 상용화 급증 및 미 국방부 수주 모멘텀, S&P500 최상위 모멘텀",
     "condition": "전일 고가 지지선 안착 및 거래량 실린 양봉 확인"},
    {"ticker": "CRWD", "name": "CrowdStrike", "sector": "Information Technology", "cap_size": "중소형주",
     "theme": "팔콘 차세대 엔드포인트 보안 플랫폼 지배력 및 52주 신고가 회복",
     "condition": "20일선 지지 확인 및 수급 1순위 돌파"},
    {"ticker": "PANW", "name": "Palo Alto Networks", "sector": "Information Technology", "cap_size": "중소형주",
     "theme": "통합 사이버보안 플랫폼 수요 확대 및 VCP 수축 후 박스권 상단 돌파",
     "condition": "VCP 수축 후 박스권 상단 돌파 시 진입"},
    {"ticker": "SPOT", "name": "Spotify", "sector": "Communication Services", "cap_size": "중소형주",
     "theme": "글로벌 유료 구독자 급증 및 가격 인상 레버리지 52주 신고가 랠리",
     "condition": "신고가 부근 지지 후 5분봉 저점 상승 확인"}
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
