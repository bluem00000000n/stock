#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio/manager.py
통합 자율 포트폴리오 관리 엔진 (State & DB Manager)
- 시세 추적 및 실시간 수익률 최신화
- 손절선 이탈 / 목표가 도달 기계적 청산(CLOSED) 집행
- 정예 엄선 신규 매수 편입(HOLDING)
- 종목 교체(Rebalancing) 및 히스토리 영구 보존
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# 상위 core 및 selector 모듈 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.database import get_db_connection, get_active_holdings
from core.market_data import fetch_krx_price, fetch_us_price
from portfolio.selector import select_best_buys, inspect_portfolio_exits


def update_holdings_prices(market: str = "KRX") -> List[Dict[str, Any]]:
    """보유 포지션(HOLDING)의 최신 가격 및 수익률을 DB에 동기화 (한국/미국 전종목 실시간 반영)"""
    holdings = get_active_holdings(market=market)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    is_kr = market.upper() in ("KRX", "KR", "KOR")

    with get_db_connection() as conn:
        cur = conn.cursor()
        for h in holdings:
            ticker = h["ticker"]
            entry_price = float(h["entry_price"])
            cur_price = float(h["current_price"])
            h_name = h["name"]

            if is_kr:
                p_info = fetch_krx_price(ticker)
                if p_info.get("price", 0) > 0:
                    cur_price = p_info["price"]
                    if p_info.get("name"):
                        h_name = p_info["name"]
            else:
                us_info = fetch_us_price(ticker)
                if us_info.get("price", 0) > 0:
                    cur_price = us_info["price"]
                    if us_info.get("name") and us_info["name"] != ticker:
                        h_name = us_info["name"]

            ret_pct = round(((cur_price - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

            cur.execute("""
                UPDATE trades 
                SET current_price = ?, name = ?, return_pct = ?, updated_at = ?
                WHERE id = ?
            """, (cur_price, h_name, ret_pct, now_str, h["id"]))

        conn.commit()

    return get_active_holdings(market=market)


def process_portfolio_cycle(candidate_signals: List[Dict[str, Any]], market: str = "KRX", max_holdings: int = 6) -> Dict[str, Any]:
    """
    1회 트레이딩 사이클 실행:
    1. 기존 보유 종목 시세 최신화
    2. 손절/익절 대상 자동 매도 청산 집행
    3. 잔여 슬롯 계산 후 신규 정예 매수 편입
    4. 대시보드 및 알람용 통합 결과 반환
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 기존 보유 종목 시세 최신화
    holdings = update_holdings_prices(market=market)

    # 2. 엑시트(손절/익절) 대상 검사
    sells_sl, sells_tp = inspect_portfolio_exits(holdings)

    with get_db_connection() as conn:
        cur = conn.cursor()

        # 손절 처리
        for s in sells_sl:
            cur.execute("""
                UPDATE trades 
                SET status = 'CLOSED', exit_price = ?, exit_date = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (s["exit_price"], today_str, s["exit_reason"], now_str, s["id"]))

        # 익절 처리
        for s in sells_tp:
            cur.execute("""
                UPDATE trades 
                SET status = 'CLOSED', exit_price = ?, exit_date = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (s["exit_price"], today_str, s["exit_reason"], now_str, s["id"]))

        conn.commit()

    # 엑시트 반영 후 활성 보유 종목 재조회
    active_after_exits = get_active_holdings(market=market)
    active_tickers = {h["ticker"] for h in active_after_exits}

    # 3. 신규 매수 정예 종목 선별
    best_buys = select_best_buys(candidate_signals, market=market, max_select=3)
    new_buys_executed = []

    available_slots = max(0, max_holdings - len(active_after_exits))

    if available_slots > 0:
        with get_db_connection() as conn:
            cur = conn.cursor()
            for b in best_buys:
                if b["ticker"] in active_tickers:
                    continue  # 이미 보유 중인 종목 제외

                if len(new_buys_executed) >= available_slots:
                    break  # 최대 포트폴리오 슬롯 초과 방지

                strategies_str = ", ".join(b.get("strategies", []))

                cur.execute("""
                    INSERT INTO trades 
                    (project_id, project_name, ticker, name, market, signal_type, signal_date, entry_price, entry_date, current_price, status, return_pct, target_price, stop_loss_price, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "stock-supervisor",
                    strategies_str,
                    b["ticker"],
                    b["name"],
                    market,
                    "BUY",
                    today_str,
                    b["price"],
                    today_str,
                    b["price"],
                    "HOLDING",
                    0.0,
                    b["target_price"],
                    b["stop_loss_price"],
                    f"엄선진입: {b['theme']} | 전략: {strategies_str}",
                    now_str
                ))
                new_buys_executed.append(b)
                active_tickers.add(b["ticker"])

            conn.commit()

    # 최종 보유 포지션
    final_holdings = get_active_holdings(market=market)

    # 포트폴리오 수익률 통계 계산
    avg_ret = round(sum(h.get("return_pct", 0.0) for h in final_holdings) / max(1, len(final_holdings)), 2)

    return {
        "market": market,
        "date": today_str,
        "new_buys": new_buys_executed,
        "sells_sl": sells_sl,
        "sells_tp": sells_tp,
        "active_holdings": final_holdings,
        "stats": {
            "total_holdings": len(final_holdings),
            "avg_return_pct": avg_ret,
            "available_slots": max(0, max_holdings - len(final_holdings))
        }
    }


if __name__ == "__main__":
    from strategies import sniper, sepa_pivot, cyclical
    sigs = sniper.run_analysis() + sepa_pivot.run_analysis("KRX") + cyclical.run_analysis()
    res = process_portfolio_cycle(sigs, market="KRX")
    print(f"✅ 포트폴리오 사이클 완료:")
    print(f"• 신규 진입: {len(res['new_buys'])}건 | 손절: {len(res['sells_sl'])}건 | 익절: {len(res['sells_tp'])}건")
    print(f"• 현재 보유: {res['stats']['total_holdings']}종목 (평균수익률: {res['stats']['avg_return_pct']:+.2f}%)")
