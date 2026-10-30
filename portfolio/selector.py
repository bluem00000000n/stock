#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio/selector.py
주식 지능형 정밀 선별 엔진 (kbit-style Inspector & Scoring)
- 대형주 & 중소형주 표준 판별 (classify_cap_size)
- 대형 3종목 + 중형 3종목 황금 밸런스 선별 (select_balanced_portfolio_buys)
- 원천 시그널 정예 스코어링 및 엑시트(SL/TP) 정밀 검사
"""

from typing import List, Dict, Any, Tuple

# 미국장 메가캡/대형주 집합 ($50B+ 또는 S&P500 상위 우량 대형주)
US_MEGA_LARGE_TICKERS = {
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOG", "GOOGL", "META", "TSLA",
    "AVGO", "BRK-B", "XOM", "LLY", "TSM", "JNJ", "JPM", "V", "WMT",
    "PG", "UNH", "MA", "HD", "CVX", "MRK", "COST", "ABBV", "FTNT",
    "FFIV", "CAT", "MRNA", "VRSN", "CRL"
}

# 한국장 코스피 우량 대형주 집합
KR_LARGE_CODES = {
    "005930", "000660", "005380", "000270", "068270", "005490", "035420",
    "033780", "011200", "028050", "051910", "051915", "000150", "222800",
    "003160", "012450", "003230", "267260", "029780", "004370", "004020",
    "011170", "018880", "017670"
}


def classify_cap_size(ticker: str, name: str = "", sector: str = "", market: str = "KRX") -> str:
    """대형주 vs 중소형주 통합 표준 판별 함수"""
    is_kr = market.upper() in ("KRX", "KR", "KOR")
    if is_kr:
        if ticker in KR_LARGE_CODES or "KOSPI" in sector or "코스피" in sector or "대형" in sector:
            # 단, 기술성장주 중소형주 풀에 속한 것은 중소형주로 우선 분류
            mid_priority_codes = {
                "196170", "403870", "425420", "053800", "093320", "042510",
                "036930", "161580", "080220", "000250", "042700", "075950",
                "033100", "031980", "441270", "295310", "253590", "087800"
            }
            if ticker in mid_priority_codes:
                return "중소형주"
            return "대형주"
        return "중소형주"
    else:
        clean_tick = ticker.upper().strip()
        # 중소형/모멘텀주 우선 분류
        mid_priority_us = {
            "PLTR", "APP", "CRWD", "ALAB", "TECH", "CPAY", "RDDT", "CRDO",
            "CROX", "ADT", "BHC", "PRCH", "NCLH", "PURR", "MESO", "OPCH",
            "NSIT", "XNCR", "CBRL", "TQQQ", "TECL", "SOXL"
        }
        if clean_tick in mid_priority_us:
            return "중소형주"
        if clean_tick in US_MEGA_LARGE_TICKERS or "S&P500" in sector or "대형" in sector:
            return "대형주"
        return "중소형주"


def score_and_aggregate_signals(candidate_signals: List[Dict[str, Any]], market: str = "KRX") -> List[Dict[str, Any]]:
    """
    원천 시그널 중복 집계 및 정밀 스코어링
    1. 중복 추천 가산점: 2개 이상의 전략에 동시 포착된 종목에 대폭 가산점 (+15점)
    2. 손익비(RR) 필터: 손익비 1.5 이상 우선 (+5점)
    3. 대형주 / 중소형주 태깅
    """
    if not candidate_signals:
        return []

    ticker_map = {}
    for s in candidate_signals:
        ticker = s["ticker"]
        name = s.get("name", ticker)
        sec = s.get("sector", "")
        cap_size = s.get("cap_size") or classify_cap_size(ticker, name, sec, market)

        if ticker not in ticker_map:
            ticker_map[ticker] = {
                "ticker": ticker,
                "name": name,
                "market": market,
                "cap_size": cap_size,
                "base_score": float(s.get("score", 80.0)),
                "strategies": [s.get("strategy_name", "")],
                "prices": [float(s.get("price", 0.0))],
                "target_prices": [float(s.get("target_price", 0.0))],
                "stop_prices": [float(s.get("stop_loss_price", 0.0))],
                "rr_ratios": [float(s.get("risk_reward_ratio", 1.5))],
                "sectors": [sec],
                "themes": [s.get("theme", "")],
                "action_plans": [s.get("action_plan", "")]
            }
        else:
            ticker_map[ticker]["strategies"].append(s.get("strategy_name", ""))
            ticker_map[ticker]["base_score"] += 15.0  # 중복 포착 가산점!
            if s.get("theme"):
                ticker_map[ticker]["themes"].append(s["theme"])

    scored_list = []
    for ticker, info in ticker_map.items():
        final_score = info["base_score"]
        avg_rr = sum(info["rr_ratios"]) / len(info["rr_ratios"])
        if avg_rr >= 2.0:
            final_score += 5.0

        scored_list.append({
            "ticker": ticker,
            "name": info["name"],
            "market": market,
            "cap_size": info["cap_size"],
            "final_score": round(final_score, 1),
            "strategies": list(set(info["strategies"])),
            "price": info["prices"][0],
            "target_price": info["target_prices"][0],
            "stop_loss_price": info["stop_prices"][0],
            "risk_reward_ratio": round(avg_rr, 2),
            "sector": info["sectors"][0],
            "theme": " | ".join(filter(None, info["themes"][:2])),
            "action_plan": info["action_plans"][0],
            "is_multi_confirmed": len(info["strategies"]) > 1
        })

    scored_list.sort(key=lambda x: x["final_score"], reverse=True)
    return scored_list


def select_best_buys(candidate_signals: List[Dict[str, Any]], market: str = "KRX", max_select: int = 3) -> List[Dict[str, Any]]:
    """일반 탑픽 선별 (섹터 분산 적용)"""
    scored_list = score_and_aggregate_signals(candidate_signals, market=market)
    selected = []
    seen_sectors = {}

    for item in scored_list:
        sec = item["sector"]
        if seen_sectors.get(sec, 0) >= 1 and not item["is_multi_confirmed"]:
            continue
        selected.append(item)
        seen_sectors[sec] = seen_sectors.get(sec, 0) + 1
        if len(selected) >= max_select:
            break

    return selected


def select_balanced_portfolio_buys(
    candidate_signals: List[Dict[str, Any]],
    current_holdings: List[Dict[str, Any]],
    market: str = "KRX",
    target_total: int = 6,
    target_large: int = 3,
    target_mid: int = 3
) -> List[Dict[str, Any]]:
    """
    [포트폴리오 6종목 황금 밸런스 선별 엔진]
    - 대형주만 편중 금지: 대형주 목표 3선 + 중형/중소형주 목표 3선
    - 현재 보유 중인 대형/중형 구성을 분석하여 부족한 파트를 최우선 보충
    """
    available_slots = max(0, target_total - len(current_holdings))
    if available_slots <= 0:
        return []

    # 1. 현재 보유 중인 대형주 / 중소형주 수 카운트
    cur_large = 0
    cur_mid = 0
    holding_tickers = set()

    for h in current_holdings:
        t = h["ticker"]
        holding_tickers.add(t)
        cap = h.get("cap_size") or classify_cap_size(t, h.get("name", ""), h.get("sector", ""), market)
        if cap == "대형주":
            cur_large += 1
        else:
            cur_mid += 1

    large_needed = max(0, target_large - cur_large)
    mid_needed = max(0, target_mid - cur_mid)

    # 2. 원천 시그널 스코어링 및 미보유 후보 분류
    scored_candidates = score_and_aggregate_signals(candidate_signals, market=market)
    large_candidates = [c for c in scored_candidates if c["cap_size"] == "대형주" and c["ticker"] not in holding_tickers]
    mid_candidates = [c for c in scored_candidates if c["cap_size"] != "대형주" and c["ticker"] not in holding_tickers]

    selected = []

    # 3. 필요한 대형주 슬롯 채우기
    take_large = min(large_needed, len(large_candidates), available_slots)
    for c in large_candidates[:take_large]:
        selected.append(c)
        holding_tickers.add(c["ticker"])

    rem_slots = available_slots - len(selected)

    # 4. 필요한 중소형주 슬롯 채우기
    take_mid = min(mid_needed, len(mid_candidates), rem_slots)
    for c in mid_candidates[:take_mid]:
        selected.append(c)
        holding_tickers.add(c["ticker"])

    rem_slots = available_slots - len(selected)

    # 5. 한쪽에 후보가 부족하여 잔여 슬롯이 남은 경우, 최고 점수 후보로 채움
    if rem_slots > 0:
        remainders = [c for c in scored_candidates if c["ticker"] not in holding_tickers]
        for c in remainders[:rem_slots]:
            selected.append(c)
            holding_tickers.add(c["ticker"])

    return selected


def inspect_portfolio_exits(active_holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    현재 보유 포지션을 전수 검사하여 손절(SL) 및 목표가 익절(TP) 대상 분리
    """
    sells_sl = []  # 손절선 이탈 매도
    sells_tp = []  # 목표가 도달 익절

    for h in active_holdings:
        cur_price = float(h.get("current_price", 0.0))
        stop_price = float(h.get("stop_loss_price", 0.0))
        target_price = float(h.get("target_price", 0.0))
        entry_price = float(h.get("entry_price", cur_price))

        if cur_price <= 0:
            continue

        ret_pct = round(((cur_price - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

        is_us = h.get("market") == "US"
        stop_str = f"${stop_price:.2f}" if is_us else f"{stop_price:,.0f}원"
        target_str = f"${target_price:.2f}" if is_us else f"{target_price:,.0f}원"

        # 손절 조건: 손절가 이하로 이탈했거나 -7% 초과 하락 시
        if (stop_price > 0 and cur_price <= stop_price) or ret_pct <= -7.0:
            sells_sl.append({
                **h,
                "exit_price": cur_price,
                "return_pct": ret_pct,
                "exit_reason": f"손절가({stop_str}) 이탈 ({ret_pct:+.2f}%) 즉시 청산"
            })
        # 익절 조건: 실제 수익률이 +5.0% 이상이고 목표가 도달 시 분할 익절
        elif target_price > 0 and cur_price >= target_price and ret_pct >= 5.0:
            sells_tp.append({
                **h,
                "exit_price": cur_price,
                "return_pct": ret_pct,
                "exit_reason": f"목표가({target_str}) 도달 ({ret_pct:+.2f}%) 분할 익절"
            })

    return sells_sl, sells_tp
