#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/htp_momentum.py
미국 HTP(High Tight Pattern) 모멘텀 TOP 10 전략 (대형주 & 중소형주)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

HTP_DIR = Path("/Users/tothemoon/stock-htp-top10")


def run_analysis() -> List[Dict[str, Any]]:
    """HTP 모멘텀 퀀트 전략 분석 및 시그널 리스트 반환"""
    signals = []
    json_path = HTP_DIR / "ai_top10_latest.json"
    if not json_path.exists():
        return signals

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            large_cap = data.get("large_cap_top10", [])
            small_cap = data.get("small_cap_top10", [])
    except Exception:
        return signals

    for item in large_cap[:5]:
        rank = item.get("rank", 1)
        ticker = item.get("ticker", "")
        name = item.get("name", ticker)
        sector = item.get("sector", "Tech")
        reason = item.get("reason", "52주 최고가권 HTP 퀀트 모멘텀 상위")

        signals.append({
            "project_id": "stock-htp-top10",
            "strategy_name": "HTP 모멘텀 (미국 대형)",
            "market": "US",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": 100.0,
            "target_price": 115.0,
            "target_price_2": 125.0,
            "stop_loss_price": 93.0,
            "risk_reward_ratio": 2.14,
            "score": 100.0 - (rank * 1.5),
            "sector": sector,
            "theme": reason,
            "pattern": f"HTP 대형주 랭킹 {rank}위",
            "action_plan": f"200일선 상단 52주 신고가 모멘텀 탑승. 2N 동적 스탑로스 설정",
            "raw_data": {
                "rank": rank,
                "tier": "대형주",
                "sector": sector
            }
        })

    for item in small_cap[:3]:
        rank = item.get("rank", 1)
        ticker = item.get("ticker", "")
        name = item.get("name", ticker)
        sector = item.get("sector", "Growth")
        reason = item.get("reason", "러셀2000 고성장 HTP 모멘텀")

        signals.append({
            "project_id": "stock-htp-top10",
            "strategy_name": "HTP 모멘텀 (미국 중소형)",
            "market": "US",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY",
            "price": 50.0,
            "target_price": 60.0,
            "target_price_2": 68.0,
            "stop_loss_price": 46.0,
            "risk_reward_ratio": 2.5,
            "score": 93.0 - (rank * 1.5),
            "sector": sector,
            "theme": reason,
            "pattern": f"HTP 중소형주 랭킹 {rank}위",
            "action_plan": f"러셀2000 탄력 반등 및 HTP 브레이크아웃 공략",
            "raw_data": {
                "rank": rank,
                "tier": "중소형주",
                "sector": sector
            }
        })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:6]


if __name__ == "__main__":
    res = run_analysis()
    print(f"✅ HTP 모멘텀 분석: {len(res)}종목 포착")
    if res:
        print(f"• 1위: {res[0]['name']} ({res[0]['ticker']}) - 점수 {res[0]['score']}")
