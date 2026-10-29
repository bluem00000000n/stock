#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/signal_forge_bridge.py
SIGNAL FORGE ALERT (25대 퀀트 지능 전략) - stock-supervisor 통합 브릿지

- 한국주식 (LONG ONLY 18대 전략)
- 미국주식 (LONG ONLY 18대 전략)
- 바이낸스 선물 크립토 (LONG & SHORT 7대 전략)
Zero-Paid-API-Key 아키텍처 기반의 실시간 신호를 stock-supervisor 표준 시그널로 변환
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# signal_forge 모듈 로드
from signal_forge.scheduler.runner import ScannerEngine
from signal_forge.models.signal import Direction, AssetType


def run_signal_forge_analysis(market: str = "stocks_kr", use_mock: bool = False, dry_run: bool = True) -> List[Dict[str, Any]]:
    """
    signal_forge 엔진을 실행하여 표준 시그널 리스트 반환
    Args:
        market: 'stocks_kr', 'stocks_us', 'crypto', 'all'
    """
    signals = []
    engine = ScannerEngine(use_mock=use_mock, dry_run=dry_run)

    markets_to_scan = [market] if market != "all" else ["stocks_kr", "stocks_us", "crypto"]

    for m in markets_to_scan:
        try:
            res = engine.scan_market(market=m)
            raw_sigs = res.get("signals", [])
            for s in raw_sigs:
                # SignalCandidate or dict
                sym = s.get("symbol", "")
                direction = s.get("direction", "LONG").upper()
                strat_name = s.get("strategy", "SIGNAL_FORGE")
                cur_price = float(s.get("price", 0.0))
                tier = s.get("tier", "TIER_2")
                score = 85.0 if tier == "TIER_1" else (75.0 if tier == "TIER_2" else 65.0)

                # 손익비 산출
                if direction == "LONG":
                    tp = round(cur_price * 1.15, 2)
                    sl = round(cur_price * 0.95, 2)
                    sig_type = "BUY"
                else:
                    tp = round(cur_price * 0.85, 2)
                    sl = round(cur_price * 1.05, 2)
                    sig_type = "SELL"

                risk = abs(cur_price - sl)
                reward = abs(tp - cur_price)
                rr = round(reward / risk, 2) if risk > 0 else 3.0

                m_tag = "KRX" if m == "stocks_kr" else ("US" if m == "stocks_us" else "CRYPTO")

                signals.append({
                    "project_id": "signal-forge-alert",
                    "strategy_name": f"SignalForge {strat_name}",
                    "market": m_tag,
                    "ticker": sym,
                    "name": sym,
                    "signal_type": sig_type,
                    "price": cur_price,
                    "target_price": tp,
                    "target_price_2": round(cur_price * (1.25 if direction == 'LONG' else 0.75), 2),
                    "stop_loss_price": sl,
                    "risk_reward_ratio": rr,
                    "score": score,
                    "sector": f"{m_tag} 퀀트 지능",
                    "theme": f"방향성: {direction} ({tier})",
                    "pattern": f"{strat_name} 감지",
                    "action_plan": f"[{direction}] {strat_name} 포착 / 목표가 {tp:,} / 손절가 {sl:,} (RR {rr})",
                    "raw_data": s
                })
        except Exception as e:
            print(f"⚠️ SignalForge {m} 스캔 중 오류: {e}")

    return signals


if __name__ == "__main__":
    print("🚀 Signal Forge 브릿지 테스트 가동 (Mock)...")
    res = run_signal_forge_analysis("crypto", use_mock=True, dry_run=True)
    print(f"✅ 테스트 완료 (포착: {len(res)}건)")
    for s in res:
        print(f"• [{s['market']}] {s['strategy_name']} {s['ticker']} - {s['action_plan']}")
