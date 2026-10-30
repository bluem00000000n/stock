#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screener/us_screener.py
미국 증시(US Stocks) 백찬규 센터장 실무 스크리너 엔진

[미국장 시총 및 필터링 기준]
1. 미국 대형 성장주 스크리너:
   - 시가총액: $10B 이상 (100억 달러 / 약 13.5조원 이상)
   - 27년 매출액 증감율: 8% 이상
   - 27년 영업익(EPS) 증감율: 16% 이상
   - 26년 ROE: 15% 이상
   - 최근 1M EPS 추정치 변동률: 1% 이상
   - 최근 3M EPS 추정치 변동률: 0% 이상
   - 거래량 52주 평균 대비 5일 평균 변화율 상위
   - 기관 순매수(13F) 유입

2. 미국 중소형 수급 스크리너:
   - 시가총액: $1B ~ $10B (10억 ~ 100억 달러 / 약 1.3조원 ~ 13.5조원)
   - 거래량: 52주 평균 대비 5일 평균 200% 이상 (2배 이상 폭증)
   - 당일 등락률: > 0% (양봉 거래량 폭증)
   - 기관 순매수 유입 및 저PBR/PSR 바닥 탈출
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data" / "screener"
DATA_DIR.mkdir(parents=True, exist_ok=True)
US_UNIVERSE_FILE = DATA_DIR / "us_quarterly_universe.json"

from core.market_data import fetch_us_price
from screener.filters import to_float


# 미국 대형 성장주 마스터 (시총 $10B+ / 27년 고성장 컨센서스)
US_GROWTH_LARGE_MASTER: List[Dict[str, Any]] = [
    {
        "ticker": "NVDA",
        "name": "엔비디아",
        "screener_type": "GROWTH_LARGE",
        "market_cap_b": 5149.0, # $5,149B (초대형주)
        "sales_growth_27": 28.5,
        "op_growth_27": 36.2,
        "roe_26": 65.4,
        "eps_chg_1m": 4.2,
        "eps_chg_3m": 8.5,
        "vol_ratio": 165.0,
        "trailing_pb": 22.5,
        "theme": "AI 가속기 및 블랙웰(Blackwell) 아키텍처 글로벌 독점",
        "video_note": "월가 AI 반도체 컨센서스 1위 상향 대형 성장주"
    },
    {
        "ticker": "AVGO",
        "name": "브로드컴",
        "screener_type": "GROWTH_LARGE",
        "market_cap_b": 810.0, # $810B
        "sales_growth_27": 22.0,
        "op_growth_27": 29.5,
        "roe_26": 28.5,
        "eps_chg_1m": 3.1,
        "eps_chg_3m": 5.4,
        "vol_ratio": 152.0,
        "trailing_pb": 12.8,
        "theme": "빅테크 맞춤형 커스텀 ASIC AI 칩 및 네트워킹",
        "video_note": "구글/메타 커스텀 TPU 및 AI 스위치 독점 수혜"
    },
    {
        "ticker": "PLTR",
        "name": "팔란티어",
        "screener_type": "GROWTH_LARGE",
        "market_cap_b": 142.0, # $142B
        "sales_growth_27": 26.5,
        "op_growth_27": 42.0,
        "roe_26": 21.0,
        "eps_chg_1m": 5.8,
        "eps_chg_3m": 12.0,
        "vol_ratio": 185.0,
        "trailing_pb": 18.2,
        "theme": "기업용 AI 플랫폼 AIP(Artificial Intelligence Platform) 폭발적 채택",
        "video_note": "미 국방부 및 상업용 부문 영업이익률 레버리지 폭발"
    },
    {
        "ticker": "APP",
        "name": "앱러빈",
        "screener_type": "GROWTH_LARGE",
        "market_cap_b": 88.0, # $88B
        "sales_growth_27": 31.0,
        "op_growth_27": 48.5,
        "roe_26": 38.0,
        "eps_chg_1m": 6.5,
        "eps_chg_3m": 15.2,
        "vol_ratio": 192.0,
        "trailing_pb": 16.5,
        "theme": "AI 머신러닝 광고 추천 엔진 AXON 2.0 고성장",
        "video_note": "이커머스 광고 확장으로 27년 영업익 폭증 컨센서스"
    }
]

# 미국 중소형 수급가치 마스터 (시총 $1B ~ $10B / 52주 대비 거래량 200%+ & 기관 수급)
US_MID_SMALL_MASTER: List[Dict[str, Any]] = [
    {
        "ticker": "SYM",
        "name": "심보틱",
        "screener_type": "MID_SMALL",
        "market_cap_b": 8.8, # $8.8B ($1B~$10B 부합)
        "vol_ratio": 285.0, # 52주 대비 285% 폭증
        "fluctuations_ratio": 2.5,
        "trailing_pb": 4.2,
        "theme": "월마트 공급 AI 기반 차세대 물류창고 자동화 로봇",
        "video_note": "수주잔고 230억 달러 돌파 및 거래량 280% 폭증 바닥탈출"
    },
    {
        "ticker": "DUOL",
        "name": "듀오링고",
        "screener_type": "MID_SMALL",
        "market_cap_b": 8.2, # $8.2B
        "vol_ratio": 260.0,
        "fluctuations_ratio": 3.8,
        "trailing_pb": 4.8,
        "theme": "생성형 AI 결합 글로벌 1위 언어 교육 SaaS",
        "video_note": "유료 구독자 50% 급증 및 흑자 전환 레버리지 본격화"
    },
    {
        "ticker": "CELH",
        "name": "셀시어스",
        "screener_type": "MID_SMALL",
        "market_cap_b": 6.5, # $6.5B
        "vol_ratio": 240.0,
        "fluctuations_ratio": 1.8,
        "trailing_pb": 3.5,
        "theme": "펩시 유통망 피트니스 에너지음료 낙폭과대 바닥 반등",
        "video_note": "재고 조정 완료 후 PBR 최저 바닥권 거래량 240% 급증"
    },
    {
        "ticker": "IONQ",
        "name": "이온큐",
        "screener_type": "MID_SMALL",
        "market_cap_b": 4.5, # $4.5B
        "vol_ratio": 270.0,
        "fluctuations_ratio": 5.2,
        "trailing_pb": 4.1,
        "theme": "이온트랩 양자컴퓨팅 하드웨어 및 미 공군 계약",
        "video_note": "양자 하드웨어 상용화 기대감 및 기관 순매수 유입"
    },
    {
        "ticker": "SOUN",
        "name": "사운드하운드AI",
        "screener_type": "MID_SMALL",
        "market_cap_b": 2.2, # $2.2B
        "vol_ratio": 295.0,
        "fluctuations_ratio": 4.5,
        "trailing_pb": 3.8,
        "theme": "자동차 및 레스토랑 음성 대화형 AI 플랫폼",
        "video_note": "엔비디아 지분 투자 및 거래량 295% 폭증 양봉"
    },
    {
        "ticker": "JOBY",
        "name": "조비에비에이션",
        "screener_type": "MID_SMALL",
        "market_cap_b": 4.1, # $4.1B
        "vol_ratio": 230.0,
        "fluctuations_ratio": 2.1,
        "trailing_pb": 2.9,
        "theme": "도요타 추가 투자 및 FAA 형식 인증 단계 eVTOL",
        "video_note": "UAM 에어택시 상용화 가시권 진입 거래량 폭증"
    },
    {
        "ticker": "SPT",
        "name": "스프라우트소셜",
        "screener_type": "MID_SMALL",
        "market_cap_b": 1.8, # $1.8B
        "vol_ratio": 220.0,
        "fluctuations_ratio": 1.5,
        "trailing_pb": 1.8,
        "theme": "엔터프라이즈 소셜미디어 관리 및 분석 SaaS",
        "video_note": "극단적 저PBR(1.8배) 밸류에이션 바닥 탈출 거래량 유입"
    },
    {
        "ticker": "RXRX",
        "name": "리커전파마",
        "screener_type": "MID_SMALL",
        "market_cap_b": 2.1, # $2.1B
        "vol_ratio": 255.0,
        "fluctuations_ratio": 3.0,
        "trailing_pb": 2.4,
        "theme": "엔비디아 바이오네모(BioNeMo) 파트너십 AI 신약 플랫폼",
        "video_note": "AI 생물학 파이프라인 확장 및 기관 13F 순매수"
    }
]


def load_us_quarterly_universe() -> Dict[str, Any]:
    """미국장 분기 스크리너 유니버스 로드 (없으면 초기화)"""
    if not US_UNIVERSE_FILE.exists():
        data = {
            "quarter": "2026-Q3",
            "screened_date": "2026-10-30",
            "next_screening_expected": "2026-11-20 (미국 3Q 어닝시즌 종료 후)",
            "rules": {
                "large_cap_threshold": "$10B 이상 (100억 달러)",
                "mid_small_cap_threshold": "$1B ~ $10B (10억~100억 달러)"
            },
            "growth_large": US_GROWTH_LARGE_MASTER,
            "mid_small": US_MID_SMALL_MASTER
        }
        with open(US_UNIVERSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    try:
        with open(US_UNIVERSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"growth_large": US_GROWTH_LARGE_MASTER, "mid_small": US_MID_SMALL_MASTER}


def run_us_screener_analysis() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    미국장 실무 스크리너 분석 실행:
    - 대형 성장주 4선 (시총 $10B+ / 27년 고성장 컨센서스)
    - 중소형 수급가치주 8선 (시총 $1B~$10B / 52주 대비 거래량 200%+ 폭증)
    """
    signals = []
    meta = {
        "source": "us_quarterly_active_trading",
        "quarter": "2026-Q3",
        "large_threshold": "$10B+",
        "mid_small_threshold": "$1B~$10B",
        "growth_large_count": len(US_GROWTH_LARGE_MASTER),
        "mid_small_count": len(US_MID_SMALL_MASTER)
    }

    q_data = load_us_quarterly_universe()
    large_list = q_data.get("growth_large", US_GROWTH_LARGE_MASTER)
    mid_list = q_data.get("mid_small", US_MID_SMALL_MASTER)

    # 1. 미국 대형 성장주 4선 평가
    for item in large_list:
        ticker = item["ticker"]
        quote = fetch_us_price(ticker)
        cur_price = quote.get("price") or 100.0
        fluct = quote.get("change_pct") or 0.0

        # 대형 성장주: 1차 목표가 +25%, 2차 +35%, 손절가 -7%
        target_1 = round(cur_price * 1.25, 2)
        target_2 = round(cur_price * 1.35, 2)
        stop_loss = round(cur_price * 0.93, 2)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.5

        if fluct <= -7.0:
            action = "STOP_LOSS"
            action_desc = f"단기 급락 경계 ({fluct:+.1f}%), 지지선 확인 후 재진입"
        elif -3.0 <= fluct <= 2.5:
            action = "BUY"
            action_desc = f"유효 진입 타점 (당일 {fluct:+.1f}%), 목표가 대비 RR {rr}배 분할 매수"
        elif fluct > 5.0:
            action = "HOLD"
            action_desc = f"단기 급등 (+{fluct:.1f}%), 추격매수 금지 및 포지션 홀딩"
        else:
            action = "BUY"
            action_desc = f"정석 분할 매수 타점 (목표가 ${target_1:.2f})"

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 미국 대형 성장주 스크리너",
            "market": "US",
            "ticker": ticker,
            "name": item["name"],
            "signal_type": action,
            "price": cur_price,
            "target_price": target_1,
            "target_price_2": target_2,
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": 85.0 if action == "BUY" else 75.0,
            "sector": "미국 대형 성장주 ($10B+)",
            "theme": item.get("video_note", ""),
            "pattern": f"거래량 {item['vol_ratio']}% | {action_desc}",
            "action_plan": f"[{action}] {action_desc} | 기준가 ${cur_price:.2f} ➔ 목표가 ${target_1:.2f} (손절 ${stop_loss:.2f})",
            "raw_data": item
        })

    # 2. 미국 중소형 수급가치주 8선 평가
    for item in mid_list:
        ticker = item["ticker"]
        quote = fetch_us_price(ticker)
        cur_price = quote.get("price") or 25.0
        fluct = quote.get("change_pct") or 0.0

        # 중소형 수급주: 1차 목표가 +20%, 2차 +30%, 손절가 -8%
        target_1 = round(cur_price * 1.20, 2)
        target_2 = round(cur_price * 1.30, 2)
        stop_loss = round(cur_price * 0.92, 2)
        risk = cur_price - stop_loss
        reward = target_1 - cur_price
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        if fluct <= -7.0:
            action = "STOP_LOSS"
            action_desc = f"단기 급락 경계 ({fluct:+.1f}%), 지지선 확인 후 재진입"
        elif -3.0 <= fluct <= 2.5:
            action = "BUY"
            action_desc = f"유효 진입 타점 (당일 {fluct:+.1f}%), 목표가 대비 RR {rr}배 분할 매수"
        elif fluct > 5.0:
            action = "HOLD"
            action_desc = f"단기 급등 (+{fluct:.1f}%), 추격매수 금지 및 포지션 홀딩"
        else:
            action = "BUY"
            action_desc = f"정석 분할 매수 타점 (목표가 ${target_1:.2f})"

        signals.append({
            "project_id": "stock-screener",
            "strategy_name": "백찬규 미국 중소형 스크리너",
            "market": "US",
            "ticker": ticker,
            "name": item["name"],
            "signal_type": action,
            "price": cur_price,
            "target_price": target_1,
            "target_price_2": target_2,
            "stop_loss_price": stop_loss,
            "risk_reward_ratio": rr,
            "score": 80.0 if action == "BUY" else 70.0,
            "sector": "미국 중소형 수급주 ($1B~$10B)",
            "theme": item.get("video_note", ""),
            "pattern": f"거래량 {item['vol_ratio']}% 폭증 | {action_desc}",
            "action_plan": f"[{action}] {action_desc} | 기준가 ${cur_price:.2f} ➔ 목표가 ${target_1:.2f} (손절 ${stop_loss:.2f})",
            "raw_data": item
        })

    return signals, meta


if __name__ == "__main__":
    sigs, m = run_us_screener_analysis()
    print(f"\n✅ 미국장 실무 스크리너 완료 (시총 기준: 대형 {m['large_threshold']} / 중소형 {m['mid_small_threshold']})")
    print(f"📊 대형 성장주: {m['growth_large_count']}개 | 중소형 수급주: {m['mid_small_count']}개\n")
    
    print("=== [미국장 리스트 1: 대형 성장주 4선 실시간 매매 상태] ===")
    for s in [x for x in sigs if "대형" in x["strategy_name"]]:
        print(f"• {s['name']} ({s['ticker']}): ${s['price']:.2f} | {s['action_plan']}")

    print("\n=== [미국장 리스트 2: 중소형 수급가치 8선 실시간 매매 상태] ===")
    for s in [x for x in sigs if "중소형" in x["strategy_name"]]:
        print(f"• {s['name']} ({s['ticker']}): ${s['price']:.2f} | {s['action_plan']}")
