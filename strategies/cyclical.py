#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/cyclical.py
KRX 시클리컬 퀀트 전략 (PBR 역사적 바닥 & 턴어라운드)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price

CYC_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "strategies_data" / "stock-cyclical-screener" / "data"


def run_analysis() -> List[Dict[str, Any]]:
    """시클리컬 퀀트 전략 활성 포지션 및 신규 매수 시그널 분석"""
    signals = []
    pos_file = CYC_DATA_DIR / "positions.json"
    if not pos_file.exists():
        return signals

    try:
        with open(pos_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            active = data.get("active_positions", {})
    except Exception:
        return signals

    for code, p in active.items():
        name = p.get("name", code)
        entry_price = float(p.get("entry_price", 0.0))
        cur_price = float(p.get("current_price", entry_price))
        target_price = float(p.get("target_price", round(entry_price * 1.40)))
        stop_price = float(p.get("stop_price", round(entry_price * 0.85)))

        # 네이버 실시간 주가 갱신 시도
        p_info = fetch_krx_price(code)
        if p_info["price"] > 0:
            cur_price = p_info["price"]

        return_pct = round(((cur_price - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

        signals.append({
            "project_id": "stock-cyclical-screener",
            "strategy_name": "시클리컬 퀀트",
            "market": "KRX",
            "ticker": code,
            "name": name,
            "signal_type": "BUY" if return_pct >= -3.0 else "HOLD",
            "price": cur_price,
            "target_price": target_price,
            "target_price_2": round(target_price * 1.15),
            "stop_loss_price": stop_price,
            "risk_reward_ratio": 2.5,
            "score": 92.0 + (5.0 if "0.1" in str(p.get("pbr", "")) else 0.0),
            "sector": p.get("sector", "시클리컬"),
            "theme": f"역사적 PBR 하단 ({p.get('pbr')}) 턴어라운드",
            "pattern": "이익 급감기 고PER 바닥 턴어라운드",
            "action_plan": f"PBR {p.get('pbr')} 바닥. 목표가 {int(target_price):,}원 / 손절가 {int(stop_price):,}원",
            "raw_data": {
                "cap": p.get("cap", "대"),
                "pbr": p.get("pbr"),
                "eff_per": p.get("eff_per_str"),
                "entry_price": entry_price,
                "return_pct": return_pct
            }
        })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]


if __name__ == "__main__":
    res = run_analysis()
    print(f"✅ 시클리컬 분석: {len(res)}종목 포착")
    if res:
        print(f"• {res[0]['name']} ({res[0]['ticker']}) - PBR {res[0]['raw_data']['pbr']} | 목표 {res[0]['target_price']:,}원")
