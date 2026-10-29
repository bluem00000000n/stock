#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/us3x.py
미국 3X 레버리지 무한투자 퀀트 전략 (TECL, TQQQ, SOXL, FNGU 등)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

US3X_DIR = Path(__file__).resolve().parent.parent / "data" / "strategies_data" / "stock-us3x"


def run_analysis() -> List[Dict[str, Any]]:
    """US 3X 무한투자 레버리지 전략 분석 및 시그널 리스트 반환"""
    signals = []
    reports_dir = US3X_DIR / "reports"
    if not reports_dir.exists():
        return signals

    # 가장 최근 날짜 폴더 찾기
    date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir() and d.name.startswith("202")], reverse=True)
    if not date_dirs:
        return signals

    latest_dir = date_dirs[0]
    summary_file = latest_dir / "summary.json"
    if not summary_file.exists():
        return signals

    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            macro = data.get("macro_regime", {})
            top3 = data.get("infinite_top3", [])
    except Exception:
        return signals

    risk_regime = macro.get("risk_regime", "NEUTRAL")
    vix = macro.get("vix", 18.0)

    for item in top3:
        rank = item.get("rank", 1)
        ticker = item.get("ticker", "")
        name = item.get("name", ticker)
        score = float(item.get("score", 90.0))
        dca_cond = item.get("dca_condition", "20분할 LOC 매수")
        reason = item.get("reason", "무한투자 적합도 최상위")

        signals.append({
            "project_id": "stock-us3x",
            "strategy_name": "US 3X 무한레버리지",
            "market": "US",
            "ticker": ticker,
            "name": name,
            "signal_type": "BUY" if risk_regime == "RISK_ON" else "HOLD",
            "price": 50.0,
            "target_price": 55.0,
            "target_price_2": 60.0,
            "stop_loss_price": 42.0,
            "risk_reward_ratio": 2.5,
            "score": score,
            "sector": "3X 레버리지 ETF",
            "theme": f"체제: {risk_regime} (VIX: {vix}) | {reason[:50]}",
            "pattern": f"3X 무한투자 적합도 랭킹 {rank}위",
            "action_plan": f"20분할 LOC 매수 운용. {dca_cond[:60]}",
            "raw_data": {
                "rank": rank,
                "regime": risk_regime,
                "vix": vix,
                "score": score
            }
        })

    return signals


if __name__ == "__main__":
    res = run_analysis()
    print(f"✅ US 3X 분석: {len(res)}종목 포착")
    if res:
        print(f"• 1위: {res[0]['name']} ({res[0]['ticker']}) - 체제: {res[0]['raw_data']['regime']}")
