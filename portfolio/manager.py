#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio/manager.py
통합 자율 포트폴리오 관리 엔진 (State & DB Manager)
- 실운영 포트폴리오 규격: 한국장 6종목 / 미국장 6종목 정예 고정
- 대형주 편중 방지: [대형주 3선 + 중형/중소형주 3선] 황금 밸런스 운영
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
from portfolio.selector import (
    select_best_buys,
    select_balanced_portfolio_buys,
    inspect_portfolio_exits,
    classify_cap_size
)


def update_holdings_prices(market: str = "KRX") -> List[Dict[str, Any]]:
    """보유 포지션(HOLDING)의 최신 가격 및 수익률을 DB에 동기화 (대형/중소형 캡사이즈 자동 태깅)"""
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

    updated = get_active_holdings(market=market)
    for u in updated:
        u["cap_size"] = classify_cap_size(u["ticker"], u.get("name", ""), u.get("notes", ""), market)
    return updated


STANDALONE_PROJECT_IDS = {
    "stock-us3x", "us3x"
}


def enforce_portfolio_target_6(market: str = "KRX", candidate_signals: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    [코어 포트폴리오 6종목 황금 밸런스 강제 조정]
    - 단독 전략(US 3X, 중소형 2차 부활, Signal Forge AI, 시클리컬 턴어라운드)은 코어 6종목 쿼터에서 완전 제외 및 독립 보존
    - 한국장 코어: 정확히 6종목 (대형 3선 : 중소형 3선 1:1 황금밸런스 / SEPA 3 + 스나이퍼 2 + 스윙 1)
    - 미국장 코어: 정확히 6종목 (대형 3선 : 중소형 3선 1:1 황금밸런스 / HTP 3 + SEPA 2 + 스윙 1)
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_kr = market.upper() in ("KRX", "KR", "KOR")

    holdings = update_holdings_prices(market=market)

    # 코어 종목과 단독 전략 종목 분리
    core_holdings = [h for h in holdings if (h.get("project_id") or "").lower() not in STANDALONE_PROJECT_IDS]
    standalone_holdings = [h for h in holdings if (h.get("project_id") or "").lower() in STANDALONE_PROJECT_IDS]

    # 1. 코어 6종목 초과 보유 시에만 코어 종목 내에서 대형 3: 중소형 3 (1:1 비율)로 수익률 순 정예화 (단독 전략은 절대 손대지 않음)
    if len(core_holdings) > 6:
        large_holdings = [h for h in core_holdings if h.get("cap_size") == "대형주"]
        mid_holdings = [h for h in core_holdings if h.get("cap_size") != "대형주"]

        # 특정 종목/섹터 하드코딩 우대 없이, 실제 실현/평가 수익률(return_pct) 최상위 순으로 자율 유지
        large_holdings.sort(key=lambda h: float(h.get("return_pct", 0.0)), reverse=True)
        mid_holdings.sort(key=lambda h: float(h.get("return_pct", 0.0)), reverse=True)

        # 대형/중소형 균형을 맞추되, 한쪽이 부족하면 다른 쪽으로 채워 총 6종목 유지
        max_large = max(3, 6 - len(mid_holdings))
        max_mid = max(3, 6 - len(large_holdings))
        keep_large = large_holdings[:max_large]
        keep_mid = mid_holdings[:max_mid]
        keep_holdings = (keep_large + keep_mid)[:6]
        keep_ids = set([h["id"] for h in keep_holdings])
        # 단독 전략 ID도 보존 목록에 추가
        for s in standalone_holdings:
            keep_ids.add(s["id"])

        with get_db_connection() as conn:
            cur = conn.cursor()
            for h in core_holdings:
                if h["id"] not in keep_ids:
                    cur.execute("""
                        UPDATE trades 
                        SET status = 'CLOSED', exit_price = current_price, exit_date = ?, 
                            notes = '코어 포트폴리오 대형 3: 중소형 3 (1:1 황금밸런스) 수익률 순 정예화', updated_at = ?
                        WHERE id = ?
                    """, (today_str, now_str, h["id"]))
            conn.commit()

    # 재조회
    holdings = update_holdings_prices(market=market)
    core_holdings = [h for h in holdings if (h.get("project_id") or "").lower() not in STANDALONE_PROJECT_IDS]
    cur_tickers = {h["ticker"] for h in core_holdings}

    # 2. 신규 편입을 통해 코어 6종목 부족 시 보충
    if len(core_holdings) < 6 and candidate_signals:
        balanced_buys = select_balanced_portfolio_buys(
            candidate_signals=candidate_signals,
            current_holdings=core_holdings,
            market=market,
            target_total=6,
            target_large=3,
            target_mid=3
        )

        with get_db_connection() as conn:
            cur = conn.cursor()
            for b in balanced_buys:
                if b["ticker"] in cur_tickers:
                    continue
                if len(cur_tickers) >= 6:
                    break

                strategies_str = ", ".join(b.get("strategies", []))
                cap_size = b.get("cap_size", "대형주")
                b_price = float(b["price"])

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
                    b_price,
                    today_str,
                    b_price,
                    "HOLDING",
                    0.0,
                    b["target_price"],
                    b["stop_loss_price"],
                    f"[{cap_size} 엄선] {b['theme']} | 전략: {strategies_str}",
                    now_str
                ))
                cur_tickers.add(b["ticker"])

            conn.commit()

    return update_holdings_prices(market=market)


def process_portfolio_cycle(candidate_signals: List[Dict[str, Any]], market: str = "KRX", max_holdings: int = 6) -> Dict[str, Any]:
    """
    1회 트레이딩 사이클 실행:
    1. 6종목 (대형 3 + 중소형 3) 황금 밸런스 점검 및 시세 동기화
    2. 손절/익절 대상 자동 매도 청산 집행
    3. 잔여 슬롯 대형/중소형 균형 신규 매수 편입
    4. 대시보드 및 알람용 통합 결과 반환
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 6종목 황금 밸런스 강제 조정
    holdings = enforce_portfolio_target_6(market=market, candidate_signals=candidate_signals)

    # 2. 엑시트(손절/익절) 대상 검사
    sells_sl, sells_tp = inspect_portfolio_exits(holdings)

    if sells_sl or sells_tp:
        with get_db_connection() as conn:
            cur = conn.cursor()
            for s in sells_sl:
                cur.execute("""
                    UPDATE trades 
                    SET status = 'CLOSED', exit_price = ?, exit_date = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                """, (s["exit_price"], today_str, s["exit_reason"], now_str, s["id"]))

            for s in sells_tp:
                cur.execute("""
                    UPDATE trades 
                    SET status = 'CLOSED', exit_price = ?, exit_date = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                """, (s["exit_price"], today_str, s["exit_reason"], now_str, s["id"]))

            conn.commit()

    # 엑시트 후 활성 포지션 재조회
    active_after_exits = update_holdings_prices(market=market)
    active_tickers = {h["ticker"] for h in active_after_exits}

    # 3. 잔여 슬롯 신규 매수 편입
    new_buys_executed = []
    if len(active_after_exits) < max_holdings and candidate_signals:
        balanced_buys = select_balanced_portfolio_buys(
            candidate_signals=candidate_signals,
            current_holdings=active_after_exits,
            market=market,
            target_total=max_holdings,
            target_large=3,
            target_mid=3
        )

        with get_db_connection() as conn:
            cur = conn.cursor()
            for b in balanced_buys:
                if b["ticker"] in active_tickers:
                    continue
                if len(active_after_exits) + len(new_buys_executed) >= max_holdings:
                    break

                strategies_str = ", ".join(b.get("strategies", []))
                cap_size = b.get("cap_size", "대형주")
                b_price = float(b["price"])

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
                    b_price,
                    today_str,
                    b_price,
                    "HOLDING",
                    0.0,
                    b["target_price"],
                    b["stop_loss_price"],
                    f"[{cap_size} 엄선] {b['theme']} | 전략: {strategies_str}",
                    now_str
                ))
                new_buys_executed.append(b)
                active_tickers.add(b["ticker"])

            conn.commit()

    # 최종 보유 포지션 조회 및 통계 계산
    final_holdings = update_holdings_prices(market=market)
    avg_ret = round(sum(h.get("return_pct", 0.0) for h in final_holdings) / max(1, len(final_holdings)), 2)

    large_cnt = sum(1 for h in final_holdings if h.get("cap_size") == "대형주")
    mid_cnt = sum(1 for h in final_holdings if h.get("cap_size") == "중소형주")
    lev3x_cnt = sum(1 for h in final_holdings if "3X" in str(h.get("cap_size", "")) or "레버리지" in str(h.get("cap_size", "")))

    return {
        "market": market,
        "date": today_str,
        "new_buys": new_buys_executed,
        "sells_sl": sells_sl,
        "sells_tp": sells_tp,
        "active_holdings": final_holdings,
        "stats": {
            "total_holdings": len(final_holdings),
            "large_count": large_cnt,
            "mid_count": mid_cnt,
            "lev3x_count": lev3x_cnt,
            "avg_return_pct": avg_ret,
            "available_slots": max(0, max_holdings - len(final_holdings))
        }
    }


if __name__ == "__main__":
    from strategies import sniper, sepa_pivot, swing
    kr_sigs = sniper.run_analysis("KRX") + sepa_pivot.run_analysis("KRX") + swing.run_analysis("KRX")
    us_sigs = sniper.run_analysis("US") + sepa_pivot.run_analysis("US") + swing.run_analysis("US")

    res_kr = process_portfolio_cycle(kr_sigs, market="KRX", max_holdings=6)
    res_us = process_portfolio_cycle(us_sigs, market="US", max_holdings=6)

    print(f"\n🇰🇷 한국장 포트폴리오 (총 {len(res_kr['active_holdings'])}종목 / 대형 {res_kr['stats']['large_count']} : 중소형 {res_kr['stats']['mid_count']})")
    for h in res_kr["active_holdings"]:
        print(f" • [{h['cap_size']}] {h['name']} ({h['ticker']}) : {h['return_pct']:+.2f}%")

    print(f"\n🇺🇸 미국장 포트폴리오 (총 {len(res_us['active_holdings'])}종목 / 대형 {res_us['stats']['large_count']} : 중소형 {res_us['stats']['mid_count']})")
    for h in res_us["active_holdings"]:
        print(f" • [{h['cap_size']}] {h['name']} ({h['ticker']}) : {h['return_pct']:+.2f}%")
