#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategies/swing.py
227선 무한 스윙 전략 (한국 KRX & 미국 US)
- 대상 구조 (한국 & 미국 동일 대칭 구조):
  • 🇰🇷 한국장: 대형주(KOSPI 우량주: KT&G, HMM, 삼성E&A 등) + 중소형주(KOSDAQ 수급주: 티에프이, 안랩, 케이아이엔엑스 등)
  • 🇺🇸 미국장: 대형주(S&P500 대형주: AAPL, BRK-B, XOM, VRSN 등) + 중소형주(Mid/Small-Cap: TECH, CPAY, NSIT, XNCR 등)
- 시장별 맞춤 조건:
  • 한국장(KRX): 227선 지지 3단계 분할, 손절 -5.0%, 목표가 +10.0%/+18.0%, 원화(원)
  • 미국장(US): 227선/50일선 지지, 실시간 시세 연동(fetch_us_price), 센트단위(2자리),
               미국 변동성 최적화 손절 -7.0%, 목표가 +12.0%/+22.0%, 달러($)
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

# 대형주 대표 티커 매핑
US_LARGE_TICKERS = {"AAPL", "BRK-B", "XOM", "VRSN", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JNJ", "JPM", "PG", "MRNA", "CRL"}
KR_LARGE_CODES = {"033780", "011200", "028050", "005930", "000660", "005380", "051910", "068270", "005490", "035420"}


def determine_cap_size(ticker: str, sector: str, is_kr: bool) -> str:
    """대형주 vs 중소형주 자동 판별 (한국 및 미국 통일)"""
    if is_kr:
        if ticker in KR_LARGE_CODES or "KOSPI" in sector or ".KS" in sector:
            return "대형주"
        return "중소형주"
    else:
        if ticker in US_LARGE_TICKERS or "S&P500" in sector:
            return "대형주"
        return "중소형주"


def run_analysis(market: str = "KRX") -> List[Dict[str, Any]]:
    """227선 스윙 전략 활성 포지션 및 신규 분할 타점 분석 (대형/중소형 대상 체계화)"""
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
        active = {}

    for ticker_raw, p in active.items():
        clean_ticker = ticker_raw.split(".")[0] if is_kr else ticker_raw
        name = p.get("name", clean_ticker)
        avg_price = float(p.get("avg_price", 0.0))
        last_price = float(p.get("last_price", avg_price))
        stage = p.get("stage", 1)
        raw_sector = p.get("sector", "")

        # 1. 실시간 시세 갱신
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
        cap_size = determine_cap_size(clean_ticker, raw_sector, is_kr)

        # 2. 시장별 맞춤 조건
        if is_kr:
            target_price = int(round(avg_price * 1.10))
            target_price_2 = int(round(target_price * 1.08))
            stop_price = float(p.get("stop_price", round(avg_price * 0.95)))
            plan_str = (
                f"[{cap_size}] 평단 {int(avg_price):,}원 / 손절선 {int(stop_price):,}원. "
                f"+10% 목표가({target_price:,}원) 도달 시 분할 익절"
            )
        else:
            target_price = round(avg_price * 1.12, 2)
            target_price_2 = round(avg_price * 1.22, 2)
            recorded_stop = float(p.get("stop_price", 0.0))
            stop_price = recorded_stop if recorded_stop > 0 else round(avg_price * 0.93, 2)
            plan_str = (
                f"[{cap_size}] 평단 ${avg_price:.2f} / 손절선 ${stop_price:.2f}. "
                f"+12% 목표가(${target_price:.2f}) 도달 시 분할 익절"
            )

        risk = max(0.1, avg_price - stop_price)
        reward = max(0.1, target_price - avg_price)
        rr = round(reward / risk, 2) if risk > 0 else 2.0

        base_score = 90.0 if stage >= 2 else 88.0
        score = base_score + (return_pct if return_pct > 0 else (return_pct * 0.5))

        signals.append({
            "project_id": "stock-swing",
            "strategy_name": f"227선 무한스윙 ({'KRX' if is_kr else 'US'} {cap_size})",
            "market": "KRX" if is_kr else "US",
            "cap_size": cap_size,
            "ticker": clean_ticker,
            "name": name,
            "signal_type": "HOLD" if stage >= 2 else "BUY",
            "price": last_price,
            "target_price": target_price,
            "target_price_2": target_price_2,
            "stop_loss_price": stop_price,
            "risk_reward_ratio": rr,
            "score": round(score, 2),
            "sector": f"{cap_size} / 스윙 우량주",
            "theme": f"[{cap_size}] 227선 지지 {stage}단계 분할 진입 중 (수익률 {return_pct:+.2f}%)",
            "pattern": "227선 이평 지지",
            "action_plan": plan_str,
            "raw_data": {
                "stage": stage,
                "avg_price": avg_price,
                "return_pct": return_pct,
                "weight_accum": p.get("weight_accum", 0.35),
                "is_us": not is_kr,
                "cap_size": cap_size
            }
        })

    # 3. 유니버스에서 신규 감시 타점 보강 (대형주/중소형주 균형 확보)
    universe_file = SWING_DATA_DIR / ("universe_kr.json" if is_kr else "universe_us.json")
    if universe_file.exists() and len(signals) < 8:
        try:
            with open(universe_file, "r", encoding="utf-8") as uf:
                u_list = json.load(uf)
            existing_tickers = {s["ticker"] for s in signals}

            for u in u_list:
                raw_u_tick = u.get("ticker", "")
                u_tick = raw_u_tick.split(".")[0] if is_kr else raw_u_tick
                if u_tick in existing_tickers or not u_tick:
                    continue

                u_sector = u.get("sector", "")
                cap_size = determine_cap_size(u_tick, u_sector, is_kr)

                if is_kr:
                    p_info = fetch_krx_price(u_tick)
                    u_price = p_info["price"]
                    if u_price <= 0:
                        continue
                    buy_price = int(round(u_price * 0.99))
                    sl_price = int(round(buy_price * 0.95))
                    tp_price = int(round(buy_price * 1.10))
                    tp2_price = int(round(buy_price * 1.18))
                    u_rr = round((tp_price - buy_price) / max(1.0, (buy_price - sl_price)), 2)
                    action_plan = f"[{cap_size}] 1차 {buy_price:,}원 진입 (비중 35%). 손절 {sl_price:,}원 / 목표 {tp_price:,}원"
                else:
                    p_info = fetch_us_price(u_tick)
                    u_price = p_info["price"]
                    if u_price <= 0:
                        continue
                    buy_price = round(u_price * 0.99, 2)
                    sl_price = round(buy_price * 0.93, 2)
                    tp_price = round(buy_price * 1.12, 2)
                    tp2_price = round(buy_price * 1.22, 2)
                    u_rr = round((tp_price - buy_price) / max(0.1, (buy_price - sl_price)), 2)
                    action_plan = f"[{cap_size}] 1차 ${buy_price:.2f} 진입 (비중 35%). 손절 ${sl_price:.2f} / 목표 ${tp_price:.2f}"

                signals.append({
                    "project_id": "stock-swing",
                    "strategy_name": f"227선 무한스윙 ({'KRX' if is_kr else 'US'} {cap_size})",
                    "market": "KRX" if is_kr else "US",
                    "cap_size": cap_size,
                    "ticker": u_tick,
                    "name": p_info["name"] or u.get("name", u_tick),
                    "signal_type": "BUY",
                    "price": u_price,
                    "target_price": tp_price,
                    "target_price_2": tp2_price,
                    "stop_loss_price": sl_price,
                    "risk_reward_ratio": u_rr,
                    "score": 88.5 if cap_size == "대형주" else 88.0,
                    "sector": f"{cap_size} / {u_sector}",
                    "theme": f"[{cap_size}] 227선 눌림목 지지 1단계 진입 타점",
                    "pattern": "227선 장기이평 지지",
                    "action_plan": action_plan,
                    "raw_data": {
                        "stage": 1,
                        "avg_price": buy_price,
                        "return_pct": 0.0,
                        "weight_accum": 0.35,
                        "is_us": not is_kr,
                        "cap_size": cap_size
                    }
                })
                if len(signals) >= 8:
                    break
        except Exception:
            pass

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:6]


if __name__ == "__main__":
    kr = run_analysis("KRX")
    print(f"✅ 스윙 분석: KR {len(kr)}개 포지션")
    for k in kr:
        print(f"• [KR {k['cap_size']}] {k['name']} ({k['ticker']}) - {k['action_plan']}")

    us = run_analysis("US")
    print(f"\n✅ 스윙 분석: US {len(us)}개 포지션")
    for u in us:
        print(f"• [US {u['cap_size']}] {u['name']} ({u['ticker']}) - {u['action_plan']}")
