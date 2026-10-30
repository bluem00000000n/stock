#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio/selector.py
주식 지능형 정밀 선별 엔진 (kbit-style Inspector & Scoring)
각 전략에서 도출된 수십 개의 원천 후보를 정밀 분석하여
'오늘의 정예 매수 1~3선' 및 '매도/교체 대상'을 최종 엄선합니다.
"""

from typing import List, Dict, Any, Tuple


def select_best_buys(candidate_signals: List[Dict[str, Any]], market: str = "KRX", max_select: int = 3) -> List[Dict[str, Any]]:
    """
    각 전략의 원천 시그널들을 종합 분석하여 오늘의 정예 매수 종목 선별
    1. 중복 추천 가산점: 2개 이상의 전략에 동시 포착된 종목에 대폭 가산점 (+15점)
    2. 손익비(RR) 필터: 손익비 1.5 이상 우선
    3. 업종/테마 중복 배제: 특정 테마 쏠림 방지 (다양성 확보)
    """
    if not candidate_signals:
        return []

    # 1. 티커별 중복도 및 점수 합산 집계
    ticker_map = {}
    for s in candidate_signals:
        ticker = s["ticker"]
        if ticker not in ticker_map:
            ticker_map[ticker] = {
                "ticker": ticker,
                "name": s["name"],
                "market": s["market"],
                "base_score": float(s.get("score", 80.0)),
                "strategies": [s.get("strategy_name", "")],
                "prices": [float(s.get("price", 0.0))],
                "target_prices": [float(s.get("target_price", 0.0))],
                "stop_prices": [float(s.get("stop_loss_price", 0.0))],
                "rr_ratios": [float(s.get("risk_reward_ratio", 1.5))],
                "sectors": [s.get("sector", "")],
                "themes": [s.get("theme", "")],
                "action_plans": [s.get("action_plan", "")]
            }
        else:
            ticker_map[ticker]["strategies"].append(s.get("strategy_name", ""))
            ticker_map[ticker]["base_score"] += 15.0  # 중복 포착 가산점!
            ticker_map[ticker]["themes"].append(s.get("theme", ""))

    scored_list = []
    for ticker, info in ticker_map.items():
        # 복수 전략 가산점 반영 최종 점수
        final_score = info["base_score"]

        # 손익비 가산점
        avg_rr = sum(info["rr_ratios"]) / len(info["rr_ratios"])
        if avg_rr >= 2.0:
            final_score += 5.0

        scored_list.append({
            "ticker": ticker,
            "name": info["name"],
            "market": info["market"],
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

    # 점수 높은 순으로 정렬
    scored_list.sort(key=lambda x: x["final_score"], reverse=True)

    # 2. 섹터 분산 선별 (동일 섹터 최대 1~2개 제한)
    selected = []
    seen_sectors = {}

    for item in scored_list:
        sec = item["sector"]
        if seen_sectors.get(sec, 0) >= 1 and not item["is_multi_confirmed"]:
            continue  # 중복 검증된 특급 주도주가 아니면 동일 섹터 배제

        selected.append(item)
        seen_sectors[sec] = seen_sectors.get(sec, 0) + 1

        if len(selected) >= max_select:
            break

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
        # 익절 조건: 1차 목표가 도달 (+10% 이상)
        elif target_price > 0 and cur_price >= target_price:
            sells_tp.append({
                **h,
                "exit_price": cur_price,
                "return_pct": ret_pct,
                "exit_reason": f"목표가({target_str}) 도달 ({ret_pct:+.2f}%) 분할 익절"
            })

    return sells_sl, sells_tp
