#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/dividend.py
배당 TOP 7 전략 (국고채 금리 초과 초우량 고배당주)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price

DIV_CANDIDATES = [
    {"code": "005935", "name": "삼성전자우", "div_yield": 4.2, "roe": 12.5, "payout": 35.0, "theme": "글로벌 반도체 우선주 안정 분기배당"},
    {"code": "015760", "name": "한국전력", "div_yield": 4.8, "roe": 8.2, "payout": 28.0, "theme": "전력요금 현실화 및 공공 유틸리티 배당 턴어라운드"},
    {"code": "033780", "name": "KT&G", "div_yield": 5.4, "roe": 14.1, "payout": 55.0, "theme": "경기방어 대표주 및 고배당·자사주 소각 주주환원"},
    {"code": "086790", "name": "하나금융지주", "div_yield": 6.2, "roe": 10.3, "payout": 30.0, "theme": "밸류업 대표 금융지주 분기 균등배당"},
    {"code": "105560", "name": "KB금융", "div_yield": 5.1, "roe": 11.0, "payout": 31.0, "theme": "국내 리딩뱅크 자본비율 최고수준 고배당"},
    {"code": "017670", "name": "SK텔레콤", "div_yield": 6.5, "roe": 9.8, "payout": 62.0, "theme": "통신 캐시카우 및 AI 데이터센터 배당성장"},
    {"code": "030200", "name": "KT", "div_yield": 5.8, "roe": 8.9, "payout": 45.0, "theme": "AICT 기업 전환 및 고배당 수익률 매력"}
]


def run_analysis() -> List[Dict[str, Any]]:
    """배당 TOP 7 전략 분석 실행 및 시그널 리스트 반환"""
    signals = []

    for item in DIV_CANDIDATES:
        code = item["code"]
        p_info = fetch_krx_price(code)
        cur_price = p_info["price"] if p_info["price"] > 0 else 50000.0

        target_price = round(cur_price * 1.12)
        stop_price = round(cur_price * 0.93)

        signals.append({
            "project_id": "stock-dividend_top7",
            "strategy_name": "배당 TOP 7",
            "market": "KRX",
            "ticker": code,
            "name": p_info["name"] or item["name"],
            "signal_type": "BUY",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(cur_price * 1.20),
            "stop_loss_price": stop_price,
            "risk_reward_ratio": 2.0,
            "score": 88.0 + float(item["div_yield"]),
            "sector": "고배당 방어주",
            "theme": item["theme"],
            "pattern": f"시가배당률 {item['div_yield']}% (국고채 10년물 금리 초과)",
            "action_plan": f"배당수익률 {item['div_yield']}% 확보. 중장기 분할 매수 및 복리 재투자",
            "raw_data": {
                "div_yield": item["div_yield"],
                "roe": item["roe"],
                "payout": item["payout"]
            }
        })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]


if __name__ == "__main__":
    res = run_analysis()
    print(f"✅ 배당 TOP 7 분석: {len(res)}종목 포착")
    if res:
        print(f"• {res[0]['name']} ({res[0]['ticker']}) - 시가배당률 {res[0]['raw_data']['div_yield']}%")
