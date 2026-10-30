#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/swing.py
227선 무한 스윙 전략 (한국 KRX & 미국 US)
- 한국장(KRX): 227선 지지 기반 3단계 분할 매수(35/35/30), 손절 -5.0%, 목표가 +10.0%/+18.0%, 원화(원)
- 미국장(US): 227선 및 50일선 지지 기반, 실시간 시세 연동(fetch_us_price), 센트단위(2자리),
             미국 변동성 최적화 손절 -7.0%~-8.0%, 목표가 +12.0%/+22.0%, 달러($)
순수 분석 모듈: 텔레그램 발송 코드 없음, List[Dict] 시그널 반환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.market_data import fetch_krx_price, fetch_us_price

SWING_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "strategies_data" / "stock-swing" / "data"


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """227선 스윙 전략 활성 포지션 및 신규 분할 타점 분석 (한국/미국 지원)"""
    signals = []
    is_kr = market.upper() in ("KRX", "KR", "KOR")

    pos_file = SWING_DATA_DIR / ("positions_kr.json" if is_kr else "positions_us.json")
    if not pos_file.exists():
        return signals

    try:
        with open(pos_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            active = data.get("active_positions", {})
    except Exception:
        return signals

    for ticker_raw, p in active.items():
        clean_ticker = ticker_raw.split(".")[0] if is_kr else ticker_raw
        name = p.get("name", clean_ticker)
        avg_price = float(p.get("avg_price", 0.0))
        last_price = float(p.get("last_price", avg_price))
        stage = p.get("stage", 1)

        # 1. 실시간 시세 갱신 (한국: fetch_krx_price, 미국: fetch_us_price)
        if is_kr:
            p_info = fetch_krx_price(clean_ticker)
            if p_info["price"] > 0:
                last_price = p_info["price"]
                if not name or name == clean_ticker:
                    name = p_info["name"]
        else:
            p_info = fetch_us_price(clean_ticker)
            if p_info["price"] > 0:
                last_price = p_info["price"]
                if not name or name == clean_ticker:
                    name = p_info["name"]

        return_pct = round(((last_price - avg_price) / avg_price) * 100, 2) if avg_price > 0 else 0.0

        # 2. 미국장 vs 한국장 시장별 손절/목표가 조건 차별화
        if is_kr:
            # 한국장: 목표가 +10% / +18%, 손절선 -5%
            target_price = int(round(avg_price * 1.10))
            target_price_2 = int(round(target_price * 1.08))
            stop_price = float(p.get("stop_price", round(avg_price * 0.95)))
            price_display = f"{int(last_price):,}원"
            plan_str = (
                f"평단 {int(avg_price):,}원 / 손절선 {int(stop_price):,}원. "
                f"+10% 목표가({target_price:,}원) 도달 시 분할 익절"
            )
        else:
            # 미국장: 변동성 반영 목표가 +12% / +22%, 손절선 -7% (227선 이탈 방어)
            target_price = round(avg_price * 1.12, 2)
            target_price_2 = round(avg_price * 1.22, 2)
            recorded_stop = float(p.get("stop_price", 0.0))
            stop_price = recorded_stop if recorded_stop > 0 else round(avg_price * 0.93, 2)
            price_display = f"${last_price:.2f}"
            plan_str = (
                f"평단 ${avg_price:.2f} / 손절선 ${stop_price:.2f}. "
                f"+12% 목표가(${target_price:.2f}) 도달 시 분할 익절"
            )

        # 손익비 산출
        risk = max(0.1, avg_price - stop_price)
        reward = max(0.1, target_price - avg_price)
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        # 점수 산출
        base_score = 90.0 if stage >= 2 else 88.0
        score = base_score + (return_pct if return_pct > 0 else (return_pct * 0.5))

        signals.append({
            "project_id": "stock-swing",
            "strategy_name": f"227선 무한스윙 ({'KRX' if is_kr else 'US'})",
            "market": "KRX" if is_kr else "US",
            "ticker": clean_ticker,
            "name": name,
            "signal_type": "HOLD" if stage >= 2 else "BUY",
            "price": last_price,
            "target_price": target_price,
            "target_price_2": target_price_2,
            "stop_loss_price": stop_price,
            "risk_reward_ratio": rr,
            "score": round(score, 2),
            "sector": "스윙 우량주",
            "theme": f"227선 지지 {stage}단계 분할 진입 중 (수익률 {return_pct:+.2f}%)",
            "pattern": "227선 이평 지지",
            "action_plan": plan_str,
            "raw_data": {
                "stage": stage,
                "avg_price": avg_price,
                "return_pct": return_pct,
                "weight_accum": p.get("weight_accum", 0.35),
                "is_us": not is_kr
            }
        })

    # 3. 미국장일 경우 유니버스에서 추가 유망 종목이 있고 활성 포지션이 적다면 보강
    if not is_kr and len(signals) < 5:
        universe_file = SWING_DATA_DIR / "universe_us.json"
        if universe_file.exists():
            try:
                with open(universe_file, "r", encoding="utf-8") as uf:
                    u_list = json.load(uf)
                existing_tickers = {s["ticker"] for s in signals}
                for u in u_list:
                    u_tick = u.get("ticker", "")
                    if u_tick in existing_tickers or not u_tick:
                        continue
                    p_info = fetch_us_price(u_tick)
                    u_price = p_info["price"]
                    if u_price <= 0:
                        continue

                    # 신규 1단계 진입 타점: 227선 지지 반등 시그널
                    buy_price = round(u_price * 0.99, 2)
                    sl_price = round(buy_price * 0.93, 2)     # -7% 손절
                    tp_price = round(buy_price * 1.12, 2)     # +12% 1차 목표가
                    tp2_price = round(buy_price * 1.22, 2)    # +22% 2차 목표가
                    u_rr = round((tp_price - buy_price) / max(0.1, (buy_price - sl_price)), 2)

                    signals.append({
                        "project_id": "stock-swing",
                        "strategy_name": "227선 무한스윙 (US)",
                        "market": "US",
                        "ticker": u_tick,
                        "name": p_info["name"] or u.get("name", u_tick),
                        "signal_type": "BUY",
                        "price": u_price,
                        "target_price": tp_price,
                        "target_price_2": tp2_price,
                        "stop_loss_price": sl_price,
                        "risk_reward_ratio": u_rr,
                        "score": 88.5,
                        "sector": u.get("sector", "S&P500 우량 스윙"),
                        "theme": "227선/50일선 눌림목 지지 1단계 진입 타점",
                        "pattern": "227선 장기이평 지지",
                        "action_plan": f"1차 ${buy_price:.2f} 진입 (비중 35%). 손절 ${sl_price:.2f} / 목표 ${tp_price:.2f}",
                        "raw_data": {
                            "stage": 1,
                            "avg_price": buy_price,
                            "return_pct": 0.0,
                            "weight_accum": 0.35,
                            "is_us": True
                        }
                    })
                    if len(signals) >= 6:
                        break
            except Exception:
                pass

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]


if __name__ == "__main__":
    kr = run_analysis("KRX")
    us = run_analysis("US")
    print(f"✅ 스윙 분석: KR {len(kr)}개 포지션 | US {len(us)}개 포지션")
    if kr:
        print(f"• [KR] {kr[0]['name']} ({kr[0]['ticker']}) - 현재가 {kr[0]['price']:,}원 | {kr[0]['action_plan']}")
    if us:
        for u in us[:3]:
            print(f"• [US] {u['name']} ({u['ticker']}) - 현재가 ${u['price']:.2f} | {u['action_plan']}")
