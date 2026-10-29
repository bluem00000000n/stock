#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/swing.py
227선 무한 스윙 전략 (한국 KRX & 미국 US)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price

SWING_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "strategies_data" / "stock-swing" / "data"


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """227선 스윙 전략 활성 포지션 및 신규 분할 타점 분석"""
    signals = []

    pos_file = SWING_DATA_DIR / ("positions_kr.json" if market.upper() in ("KRX", "KR", "KOR") else "positions_us.json")
    if not pos_file.exists():
        return signals

    try:
        with open(pos_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            active = data.get("active_positions", {})
    except Exception:
        return signals

    is_kr = market.upper() in ("KRX", "KR", "KOR")

    for ticker_raw, p in active.items():
        clean_ticker = ticker_raw.split(".")[0] if is_kr else ticker_raw
        name = p.get("name", clean_ticker)
        avg_price = float(p.get("avg_price", 0.0))
        last_price = float(p.get("last_price", avg_price))
        stop_price = float(p.get("stop_price", round(avg_price * 0.95, 2)))
        stage = p.get("stage", 1)

        # 현재가 갱신 시도
        if is_kr:
            p_info = fetch_krx_price(clean_ticker)
            if p_info["price"] > 0:
                last_price = p_info["price"]

        return_pct = round(((last_price - avg_price) / avg_price) * 100, 2) if avg_price > 0 else 0.0
        target_price = round(avg_price * 1.10, 2) if not is_kr else int(round(avg_price * 1.10))

        signals.append({
            "project_id": "stock-swing",
            "strategy_name": f"227선 무한스윙 ({'KRX' if is_kr else 'US'})",
            "market": "KRX" if is_kr else "US",
            "ticker": clean_ticker,
            "name": name,
            "signal_type": "HOLD" if stage >= 2 else "BUY",
            "price": last_price,
            "target_price": target_price,
            "target_price_2": round(target_price * 1.08, 2) if not is_kr else int(round(target_price * 1.08)),
            "stop_loss_price": stop_price,
            "risk_reward_ratio": 2.0,
            "score": 90.0 + (return_pct if return_pct > 0 else 0.0),
            "sector": "스윙 우량주",
            "theme": f"227선 지지 {stage}단계 분할 진입 중 (수익률 {return_pct:+.2f}%)",
            "pattern": "227선 이평 지지",
            "action_plan": f"평단 {avg_price:,}원 / 손절선 {stop_price:,}원. +10% 목표가({target_price:,}원) 도달 시 분할 익절",
            "raw_data": {
                "stage": stage,
                "avg_price": avg_price,
                "return_pct": return_pct,
                "weight_accum": p.get("weight_accum", 0.35)
            }
        })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]


if __name__ == "__main__":
    kr = run_analysis("KRX")
    us = run_analysis("US")
    print(f"✅ 스윙 분석: KR {len(kr)}개 포지션 | US {len(us)}개 포지션")
    if kr:
        print(f"• KR: {kr[0]['name']} ({kr[0]['ticker']}) - 평단 {kr[0]['price']:,}원")
