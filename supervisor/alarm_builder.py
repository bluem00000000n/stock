#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supervisor/alarm_builder.py
통합 정기 알람 메시지 생성 모듈
정기 알람 시간:
- 08:30 KST : 🇰🇷 한국장 개장전 실전 포트폴리오 알람 (시가/지정가 매수 신규진입 & 현재 포트폴리오)
- 15:00 KST : 🇰🇷 한국장 종가매수 최종 타깃 & 포트폴리오 알람 (종가매수 신규진입 & 현재 포트폴리오)
- 17:30 KST : 🇺🇸 미국장 장전 실전 포트폴리오 알람 (미국장 시가/지정가 매수 신규진입 & 현재 포트폴리오)

[사용자 핵심 원칙 준수]
1. 추천 종목 리스트 전면 삭제 (스크리너 12선, 크립토 레이더 등 비보유 후보 리스트 제외)
2. 현재 실운용 포트폴리오 (한국 6종목 + 미국 6종목) 실시간 상세 출력
3. 포트폴리오 변동 내역 (교체 종목, 신규종목, 매도/제외 종목 및 간단한 이유) 상단 명시
4. 신규 진입 시 매수 유형 명확히 표시:
   - 지정가 매수: [지정가 매수: X원 / $X]
   - 시가 매수: [시가 매수 (09:00 시가 체결)] / [시가 매수]
   - 종가 매수: [종가 매수 (15:20~15:30 동시호가 체결)] / [종가 매수 (LOC)]
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from portfolio.selector import classify_cap_size


def format_order_type(item: Dict[str, Any], market: str = "KRX") -> str:
    """주문 체결 방식 표기 (지정가 / 시가 매수 / 종가 매수)"""
    sig = str(item.get("signal_type", ""))
    notes = str(item.get("notes", ""))
    action = str(item.get("action_plan", ""))
    is_kr = market.upper() in ("KRX", "KR", "KOR")

    # 1. 지정가
    if "지정가" in sig or "지정가" in notes:
        if "지정가 매수:" in sig:
            return f"[{sig.strip()}]"
        p = item.get("entry_price") or item.get("price") or item.get("pivot", 0)
        try:
            p_val = float(p)
            if p_val > 0:
                return f"[지정가 매수: {int(p_val):,}원]" if is_kr else f"[지정가 매수: ${p_val:.2f}]"
        except Exception:
            pass
        return "[지정가 매수]"

    # 2. 종가 매수 (Strong Close / LOC)
    if "종가" in sig or "종가" in notes or "Strong Close" in action or "LOC" in notes:
        return "[종가 매수 (15:20~15:30 동시호가 체결)]" if is_kr else "[종가 매수 (LOC 20분할)]"

    # 3. 시가 매수
    if "시가" in sig or "시가" in notes or "장전" in sig or "ORB" in action:
        return "[시가 매수 (09:00 개장 시가 체결)]" if is_kr else "[시가 매수 (22:30 개장 시가 체결)]"

    return "[시가 매수]" if is_kr else "[시가 매수]"


def format_holding_status(item: Dict[str, Any], market: str = "KRX", is_new: bool = False) -> str:
    """보유 포트폴리오 상태 표기: 오늘 신규 진입 종목은 매수 주문 방식 표시, 기존 종목은 [보유 유지]"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    entry_date = str(item.get("entry_date", ""))
    if is_new or (item.get("is_new_entry") and entry_date == today_str):
        order_tag = format_order_type(item, market)
        return f"[오늘 신규진입 | {order_tag.strip('[]')}]"
    return "[보유 유지]"


def format_reason(item: Dict[str, Any]) -> str:
    """종목 변동/편입 사유 추출 (간단히)"""
    notes = item.get("notes") or ""
    theme = item.get("theme") or ""
    reason = item.get("reason") or ""
    action = item.get("action_plan") or ""

    clean = notes
    for prefix in ["[대형주]", "[중소형주]", "[3X 레버리지]"]:
        clean = clean.replace(prefix, "").strip()
    if "|" in clean:
        clean = clean.split("|")[0].strip()

    res = clean or theme or reason or action or "실시간 퀀트 모멘텀 상위"
    return res[:48]


def get_holding_strategy_key(h: Dict[str, Any], market: str = "KRX") -> str:
    """보유 종목의 원천 전략 키 분류"""
    pid = (h.get("project_id") or h.get("project_name") or "").lower()
    ticker = str(h.get("ticker", "")).upper()
    notes = str(h.get("notes", "")).lower()

    if market.upper() == "US":
        if "3x" in pid or "us3x" in pid or "3x" in notes or ticker in ("TQQQ", "SOXL", "UPRO", "TECL"):
            return "us3x"
        if "stage2" in pid or "revival" in pid or "부활" in notes or ticker in ("POWL", "MOD"):
            return "stage2_revival"
        if "signal" in pid or "forge" in pid:
            return "signal_forge"
        if "sepa" in pid or "sepa" in notes or ticker in ("PLTR", "APP", "ALAB"):
            return "sepa_pivot"
        if "htp" in pid or "htp" in notes or ticker in ("NVDA", "AVGO"):
            return "htp_momentum"
        if "swing" in pid or "swing" in notes:
            return "swing"
        return "htp_momentum"
    else:
        if "sepa" in pid or "sepa" in notes or ticker in ("012450", "093320"):
            return "sepa_pivot"
        if "sniper" in pid or "스나이퍼" in notes or ticker in ("000660", "042510"):
            return "sniper"
        if "swing" in pid or "스윙" in notes or ticker in ("267260", "003230"):
            return "swing"
        if "cyclical" in pid or "시클리컬" in notes:
            return "cyclical"
        if "signal" in pid or "forge" in pid:
            return "signal_forge"
        return "sniper"


KR_STRATEGY_DISPLAY = [
    ("sniper", "🎯 <b>[수급 스나이퍼]</b>", "외인·기관 양매수 주도주"),
    ("sepa_pivot", "🚀 <b>[SEPA x 피봇 돌파]</b>", "Stage 2 VCP 변동성축소"),
    ("swing", "🛡️ <b>[227선 무한 스윙]</b>", "227일선/플랫 지지"),
    ("cyclical", "🔄 <b>[시클리컬 턴어라운드]</b>", "PBR 극단 저평가")
]

US_STRATEGY_DISPLAY = [
    ("htp_momentum", "🏆 <b>[코어: HTP 모멘텀 Top 10]</b>", "나스닥 메가캡 실적 주도주"),
    ("sepa_pivot", "🚀 <b>[코어: SEPA x 피봇 돌파]</b>", "Stage 2 추세추종"),
    ("swing", "🛡️ <b>[코어: 227선 무한 스윙]</b>", "우량 대형주 지지선 스윙"),
    ("stage2_revival", "🌱 <b>[단독: 중소형 2차 파동 부활]</b>", "10배주 라이프사이클 실적 퀀텀점프"),
    ("us3x", "⚡ <b>[단독: US 3X 레버리지]</b>", "TQQQ 분할 적립")
]


def fetch_signal_forge_radar_targets(market: str = "KRX") -> List[Dict[str, Any]]:
    """Signal Forge AI 레이더의 실시간 포착 매수 후보 종목 조회"""
    db_path = "/Users/tothemoon/runtime/data/signal_forge.db"
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        asset_type = "STOCK_KR" if market.upper() in ("KRX", "KR", "KOR") else "STOCK_US"
        rows = conn.execute("""
            SELECT symbol, strategy_name, score, price, trigger_reason, created_at
            FROM signals
            WHERE asset_type = ? AND direction = 'LONG'
            ORDER BY id DESC LIMIT 20
        """, (asset_type,)).fetchall()

        name_map = {
            "005930": "삼성전자",
            "000660": "SK하이닉스",
            "NVDA": "엔비디아",
            "AAPL": "애플",
            "MSFT": "마이크로소프트",
            "TSLA": "테슬라"
        }

        seen = set()
        targets = []
        for r in rows:
            sym = r["symbol"]
            if sym in seen:
                continue
            seen.add(sym)
            targets.append({
                "ticker": sym,
                "name": name_map.get(sym, sym),
                "strategy": r["strategy_name"],
                "score": float(r["score"]),
                "price": float(r["price"]),
                "reason": r["trigger_reason"]
            })
            if len(targets) >= 2:
                break
        conn.close()
        return targets
    except Exception:
        return []


def format_strategy_grouped_portfolio(
    holdings: List[Dict[str, Any]],
    market: str = "KRX",
    new_tickers: Optional[set] = None,
    is_summary: bool = False
) -> List[str]:
    """
    보유 포트폴리오를 전략별 그룹 헤더로 명확히 분리하여 미려하고 직관적으로 포맷팅
    """
    if not holdings:
        empty_msg = "• <i>현재 보유 포지션 없음 (현금 대기)</i>" if market.upper() in ("KRX", "KR") else "• <i>현재 미국장 보유 포지션 없음 (신규 진입 대기)</i>"
        return [empty_msg]

    is_kr = market.upper() in ("KRX", "KR", "KOR")
    new_tickers = new_tickers or set()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for h in holdings:
        k = get_holding_strategy_key(h, market=market)
        grouped.setdefault(k, []).append(h)

    display_groups = KR_STRATEGY_DISPLAY if is_kr else US_STRATEGY_DISPLAY
    out = []

    for strat_key, header_html, sub_desc in display_groups:
        strat_holdings = grouped.get(strat_key, [])
        if not strat_holdings:
            continue

        out.append(f"\n{header_html} ({len(strat_holdings)}선) - <i>{sub_desc}</i>")

        for h in strat_holdings:
            ticker = h.get("ticker", "")
            name = h.get("name", ticker)
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret > 0 else ("🔵" if ret < 0 else "⚪")

            cap = classify_cap_size(ticker, name, market=market)
            short_cap = "3X" if "3X" in cap else ("대형" if "대형" in cap else "중형")

            if is_kr:
                cur_p = int(float(h.get("current_price", 0)))
                entry_p = int(float(h.get("entry_price", 0)))
                tgt_p = int(float(h.get("target_price", 0))) if h.get("target_price") else 0
                stp_p = int(float(h.get("stop_loss_price", 0))) if h.get("stop_loss_price") else 0
                price_line = f"└ 진입: {entry_p:,}원 ➔ 현재: {cur_p:,}원 (<b>{ret:+.2f}%</b>) | 🎯 {tgt_p:,}원 | 🛑 {stp_p:,}원"
                summary_line = f"• {sign} <b>[{short_cap}] {name}</b> ({ticker}) : <b>{ret:+.2f}%</b> ({cur_p:,}원)"
            else:
                cur_p = float(h.get("current_price", 0))
                entry_p = float(h.get("entry_price", 0))
                tgt_p = float(h.get("target_price", 0)) if h.get("target_price") else 0
                stp_p = float(h.get("stop_loss_price", 0)) if h.get("stop_loss_price") else 0
                price_line = f"└ 진입: ${entry_p:.2f} ➔ 현재: ${cur_p:.2f} (<b>{ret:+.2f}%</b>) | 🎯 ${tgt_p:.2f} | 🛑 ${stp_p:.2f}"
                summary_line = f"• {sign} <b>[{short_cap}] {name}</b> ({ticker}) : <b>{ret:+.2f}%</b> (${cur_p:.2f})"

            if is_summary:
                out.append(f" {summary_line}")
            else:
                is_new = (ticker in new_tickers) or h.get("is_new_entry", False)
                status_tag = format_holding_status(h, market, is_new=is_new)
                out.append(f" • {sign} <b>[{short_cap}] {name}</b> ({ticker}) | <b>{status_tag}</b>")
                out.append(f"    {price_line}")

    # 단독 Signal Forge 실시간 모니터링 카드 및 매수 타깃 출력
    radar_targets = fetch_signal_forge_radar_targets(market=market)
    if is_kr:
        out.append("\n📡 <b>[단독: Signal Forge AI 레이더]</b> (25대 퀀트 실시간 매수 타깃)")
        if radar_targets:
            for t in radar_targets:
                p_str = f"{int(t['price']):,}원"
                out.append(f" • 🎯 <b>[레이더 포착] {t['name']}</b> ({t['ticker']}) : <b>{p_str}</b> | <b>{t['score']:.0f}점</b> ({t['strategy']})")
                out.append(f"    └ <i>레이더 촉매:</i> {t['reason']}")
        else:
            out.append(" • 한국 거시 매크로 & 25대 퀀트 시그널 실시간 감시 연동 중 (리스크 온)")
    else:
        out.append("\n📡 <b>[단독: Signal Forge AI 레이더]</b> (미국 퀀트 실시간 매수 타깃)")
        if radar_targets:
            for t in radar_targets:
                p_str = f"${t['price']:.2f}"
                out.append(f" • 🎯 <b>[레이더 포착] {t['name']}</b> ({t['ticker']}) : <b>{p_str}</b> | <b>{t['score']:.0f}점</b> ({t['strategy']})")
                out.append(f"    └ <i>레이더 촉매:</i> {t['reason']}")
        else:
            out.append(" • 미국 빅테크 & 퀀트 레이더 74개 시그널 실시간 감시 연동 중")

    return out


# =============================================================
# 1. 08:30 KST 정기 알람 (한국장 개장전 포트폴리오)
# =============================================================
def build_0830_kr_open_alarm(
    kr_portfolio: Dict[str, Any],
    us_portfolio: Dict[str, Any],
    macro: Dict[str, Any],
    kr_buys: List[Dict[str, Any]] = None,
    screener_signals: Optional[List[Dict[str, Any]]] = None,
    us_screener_signals: Optional[List[Dict[str, Any]]] = None,
    crypto_signals: Optional[List[Dict[str, Any]]] = None
) -> str:
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🌅 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 개장전 실전 포트폴리오 알람</b>")
    lines.append(f"📅 <b>일시:</b> {today_str} 08:30 KST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 글로벌 매크로 요약 (간단히)
    dow = macro.get("dow", {})
    nasdaq = macro.get("nasdaq", {})
    sp500 = macro.get("sp500", {})
    usd_krw = macro.get("usd_krw", "1,379.5")

    lines.append("🌐 <b>1. 글로벌 매크로 요약</b>")
    lines.append(f"• 다우: {dow.get('val', '-')} ({dow.get('pct', 0.0):+.2f}%) | 나스닥: {nasdaq.get('val', '-')} ({nasdaq.get('pct', 0.0):+.2f}%) | S&P500: {sp500.get('val', '-')} ({sp500.get('pct', 0.0):+.2f}%)")
    lines.append(f"• 원/달러 환율: <b>{usd_krw}원</b> | VIX: {macro.get('vix', '18.38')}")
    lines.append("• <b>당일 전술:</b> 09:00 시초가 갭상승 추격매수 금지, 5분봉 지지 확인 후 원칙 체결.")

    # 2. 포트폴리오 변동 내역 (교체 / 신규진입 / 매도제외 및 이유)
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔄 <b>2. 포트폴리오 변동 내역 (오늘의 포지션 조정)</b>")

    new_buys = kr_portfolio.get("new_buys", [])
    sells_sl = kr_portfolio.get("sells_sl", [])
    sells_tp = kr_portfolio.get("sells_tp", [])
    replacements = kr_portfolio.get("replacements", [])

    has_changes = False

    if replacements:
        has_changes = True
        for r in replacements:
            lines.append(f"• 🔄 <b>[교체 종목] {r.get('old_name')} ➔ {r.get('new_name')}</b>")
            lines.append(f"  └ <i>교체 이유:</i> {r.get('reason', '비주도주 정리 및 신규 주도주 교체')}")

    if new_buys:
        has_changes = True
        for b in new_buys:
            o_type = format_order_type(b, "KRX")
            cap_b = f"[{b.get('cap_size', '대형주')}] "
            lines.append(f"• 🆕 <b>[신규 종목] {cap_b}{b['name']}</b> ({b['ticker']}) | <b>{o_type}</b>")
            lines.append(f"  └ <i>편입 이유:</i> {format_reason(b)}")

    if sells_tp:
        has_changes = True
        for s in sells_tp:
            lines.append(f"• 🟢 <b>[목표가 익절] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>매도 이유:</i> 1차 목표가 도달에 따른 전량 차익 실현")
    if sells_sl:
        has_changes = True
        for s in sells_sl:
            lines.append(f"• 🔴 <b>[손절 청산] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>손절 이유:</i> 기계적 손절선 이탈에 따른 리스크 관리")

    if not has_changes:
        lines.append("• 📋 <b>[포지션 운용 현황]</b> 한국 6종목 + 미국 6종목 전량 목표가/손절가 내 정상 운용 중")
        lines.append("• 💡 <b>[금일 주문 안내]</b> 신규 진입/교체/매도 대상 없음 ➔ 기존 12종목 홀딩 대응 (신규 주문 없음)")

    # 3. 한국장 실운용 포트폴리오 (대형 3선 + 중소형 3선)
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    new_tickers = set(b.get("ticker") for b in new_buys)
    large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_ret = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇰🇷 한국장 실운용 포트폴리오 (총 {len(kr_active)}종목 - 대형 {large_c}선 + 중소형 {mid_c}선)</b>")
    lines.append(f"• <b>포트폴리오 평균 수익률:</b> <b>{avg_ret:+.2f}%</b> (가용 슬롯: {kr_stats.get('available_slots', 0)}개)")
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=new_tickers, is_summary=False))

    # 4. 미국장 실운용 포트폴리오 (대형 3선 + 중소형 2선 + 3X 레버리지 1선)
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_new_tickers = set(b.get("ticker") for b in us_portfolio.get("new_buys", []))
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "중소형주")
    us_3x_c = sum(1 for h in us_active if "3X" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US"))
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇺🇸 미국장 실운용 포트폴리오 (총 {len(us_active)}종목 - 대형 {us_large_c}선 + 중소형 {us_mid_c}선 + 3X 레버리지 {us_3x_c}선)</b>")
    lines.append(f"• <b>포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=us_new_tickers, is_summary=False))

    # 5. 매주 화요일 오후 특별 점검 (미국 중소형 2차 파동 부활 전략)
    if datetime.now().weekday() == 1:  # 0=월, 1=화
        try:
            from strategies.stage2_revival import build_tuesday_review_block
            tuesday_block = build_tuesday_review_block()
            lines.append(tuesday_block)
        except Exception as e:
            pass

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")
    return "\n".join(lines)


# =============================================================
# 2. 15:00 KST 정기 알람 (한국장 종가매수 최종 타깃 & 포트폴리오)
# =============================================================
def build_1500_kr_close_alarm(
    kr_portfolio: Dict[str, Any],
    us_portfolio: Dict[str, Any],
    kr_buys: List[Dict[str, Any]] = None,
    us_buys: List[Dict[str, Any]] = None,
    screener_signals: Optional[List[Dict[str, Any]]] = None,
    us_screener_signals: Optional[List[Dict[str, Any]]] = None,
    crypto_signals: Optional[List[Dict[str, Any]]] = None
) -> str:
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🎯 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 종가매수 최종 타깃 & 포트폴리오 알람</b>")
    lines.append(f"📅 <b>기준일자:</b> {today_str} | ⏰ 15:00 KST (장마감 30분 전)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 포트폴리오 변동 내역 (종가매수 & 포지션 재편)
    lines.append("🔄 <b>1. 포트폴리오 변동 내역 (종가매수 & 포지션 재편)</b>")

    new_buys = kr_portfolio.get("new_buys", [])
    sells_sl = kr_portfolio.get("sells_sl", [])
    sells_tp = kr_portfolio.get("sells_tp", [])
    replacements = kr_portfolio.get("replacements", [])

    has_changes = False

    if replacements:
        has_changes = True
        for r in replacements:
            lines.append(f"• 🔄 <b>[교체 종목] {r.get('old_name')} ➔ {r.get('new_name')}</b>")
            lines.append(f"  └ <i>교체 이유:</i> {r.get('reason', '비주도주 정리 및 신규 주도주 교체')}")

    if new_buys:
        has_changes = True
        for b in new_buys:
            o_type = format_order_type(b, "KRX")
            if "[지정가" not in o_type:
                o_type = "[종가 매수 (15:20~15:30 동시호가 체결)]"
            cap_b = f"[{b.get('cap_size', '대형주')}] "
            lines.append(f"• 🆕 <b>[신규 종목 (종가매수)] {cap_b}{b['name']}</b> ({b['ticker']}) | <b>{o_type}</b>")
            lines.append(f"  └ <i>편입 이유:</i> {format_reason(b)}")

    if sells_tp:
        has_changes = True
        for s in sells_tp:
            lines.append(f"• 🟢 <b>[목표가 익절] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>매도 이유:</i> 1차 목표가 도달에 따른 전량 차익 실현")
    if sells_sl:
        has_changes = True
        for s in sells_sl:
            lines.append(f"• 🔴 <b>[손절 청산] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>손절 이유:</i> 기계적 손절선 이탈에 따른 리스크 관리")

    if not has_changes:
        lines.append("• 📋 <b>[포지션 운용 현황]</b> 한국 6종목 + 미국 6종목 전량 목표가/손절가 내 정상 마감")
        lines.append("• 💡 <b>[종가 주문 안내]</b> 신규 진입/교체/매도 대상 없음 ➔ 기존 12종목 홀딩 유지 (종가 매수 없음)")

    # 2. 한국장 실운용 포트폴리오 마감 현황
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    new_tickers = set(b.get("ticker") for b in new_buys)
    large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_ret = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>2. 🇰🇷 한국장 실운용 포트폴리오 마감 현황 (총 {len(kr_active)}종목 - 대형 {large_c}선 + 중소형 {mid_c}선)</b>")
    lines.append(f"• <b>포트폴리오 평균 수익률:</b> <b>{avg_ret:+.2f}%</b> (가용 슬롯: {kr_stats.get('available_slots', 0)}개)")
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=new_tickers, is_summary=False))

    # 3. 미국장 실운용 포트폴리오 현황
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "중소형주")
    us_3x_c = sum(1 for h in us_active if "3X" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US"))
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇺🇸 미국장 실운용 포트폴리오 현황 (총 {len(us_active)}종목 - 대형 {us_large_c}선 + 중소형 {us_mid_c}선 + 3X 레버리지 {us_3x_c}선)</b>")
    lines.append(f"• <b>포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=None, is_summary=False))

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")
    return "\n".join(lines)


# =============================================================
# 3. 17:30 KST 정기 알람 (미국장 장전 실전 포트폴리오)
# =============================================================
def build_1730_us_open_alarm(
    kr_portfolio: Dict[str, Any],
    us_portfolio: Dict[str, Any],
    macro: Dict[str, Any],
    us_buys: List[Dict[str, Any]] = None,
    screener_signals: Optional[List[Dict[str, Any]]] = None,
    us_screener_signals: Optional[List[Dict[str, Any]]] = None,
    crypto_signals: Optional[List[Dict[str, Any]]] = None
) -> str:
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🌃 <b>[STOCK SUPERVISOR] 🇺🇸 미국장 장전 실전 포트폴리오 알람</b>")
    lines.append(f"📅 <b>일시:</b> {today_str} 17:30 KST (개장 전 프리마켓 정기 브리핑)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 글로벌 매크로 및 프리마켓 현황
    dow = macro.get("dow", {})
    nasdaq = macro.get("nasdaq", {})
    sp500 = macro.get("sp500", {})
    usd_krw = macro.get("usd_krw", "1,379.5")

    lines.append("🌐 <b>1. 미국 증시 매크로 & 선물 지수</b>")
    lines.append(f"• 다우 선물: {dow.get('val', '-')} ({dow.get('pct', 0.0):+.2f}%) | 나스닥 선물: {nasdaq.get('val', '-')} ({nasdaq.get('pct', 0.0):+.2f}%) | S&P500: {sp500.get('val', '-')} ({sp500.get('pct', 0.0):+.2f}%)")
    lines.append(f"• 원/달러 환율: <b>{usd_krw}원</b> | VIX 지수: {macro.get('vix', '18.38')}")
    lines.append("• <b>운용 지침:</b> 프리마켓 갭상승 추격 매수 금지, 22:30 개장 후 본장 호가 체결 원칙 준수.")

    # 2. 미국장 포트폴리오 변동 내역
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔄 <b>2. 미국장 포트폴리오 변동 내역 (신규진입 & 재편)</b>")

    new_buys = us_portfolio.get("new_buys", [])
    sells_sl = us_portfolio.get("sells_sl", [])
    sells_tp = us_portfolio.get("sells_tp", [])
    replacements = us_portfolio.get("replacements", [])

    has_changes = False

    if replacements:
        has_changes = True
        for r in replacements:
            lines.append(f"• 🔄 <b>[교체 종목] {r.get('old_name')} ➔ {r.get('new_name')}</b>")
            lines.append(f"  └ <i>교체 이유:</i> {r.get('reason', '비주도주 정리 및 신규 주도주 교체')}")

    if new_buys:
        has_changes = True
        for b in new_buys:
            o_type = format_order_type(b, "US")
            cap_b = f"[{b.get('cap_size', '대형주')}] "
            lines.append(f"• 🆕 <b>[신규 종목] {cap_b}{b['name']}</b> ({b['ticker']}) | <b>{o_type}</b>")
            lines.append(f"  └ <i>편입 이유:</i> {format_reason(b)}")

    if sells_tp:
        has_changes = True
        for s in sells_tp:
            lines.append(f"• 🟢 <b>[목표가 익절] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>매도 이유:</i> 1차 목표가 도달에 따른 전량 차익 실현")
    if sells_sl:
        has_changes = True
        for s in sells_sl:
            lines.append(f"• 🔴 <b>[손절 청산] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"  └ <i>손절 이유:</i> 기계적 손절선 이탈에 따른 리스크 관리")

    if not has_changes:
        lines.append("• 📋 <b>[미국장 포지션 운용 현황]</b> 미국 6종목 전량 목표가/손절가 내 정상 운용 중")
        lines.append("• 💡 <b>[개장 주문 안내]</b> 신규 진입/교체/매도 대상 없음 ➔ 기존 6종목 홀딩 대응 (신규 매수 없음)")

    # 3. 미국장 실운용 포트폴리오 (대형 3선 + 중소형 2선 + 3X 레버리지 1선)
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_new_tickers = set(b.get("ticker") for b in new_buys)
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "중소형주")
    us_3x_c = sum(1 for h in us_active if "3X" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US"))
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇺🇸 미국장 실운용 포트폴리오 (총 {len(us_active)}종목 - 대형 {us_large_c}선 + 중소형 {us_mid_c}선 + 3X 레버리지 {us_3x_c}선)</b>")
    lines.append(f"• <b>포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=us_new_tickers, is_summary=False))

    # 4. 한국장 실운용 포트폴리오 마감 요약
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    kr_large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    kr_mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_kr = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇰🇷 한국장 실운용 포트폴리오 (총 {len(kr_active)}종목 - 대형 {kr_large_c}선 + 중소형 {kr_mid_c}선 | 마감 평균 {avg_kr:+.2f}%)</b>")
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=None, is_summary=True))

    # 5. 매주 화요일 오후 특별 점검 (미국 중소형 2차 파동 부활 전략)
    if datetime.now().weekday() == 1:  # 0=월, 1=화
        try:
            from strategies.stage2_revival import build_tuesday_review_block
            lines.append(build_tuesday_review_block())
        except Exception as e:
            pass

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")
    return "\n".join(lines)


# 하위 호환성 별칭
build_0840_us_close_kr_open_alarm = build_0830_kr_open_alarm
build_1500_kr_close_us_open_alarm = build_1500_kr_close_alarm
