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
from core.market_data import fetch_krx_market_summary, fetch_us_macro


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
        if "sepa" in pid or "sepa" in notes or ticker in ("012450", "093320", "031980"):
            return "sepa_pivot"
        if "sniper" in pid or "스나이퍼" in notes or ticker in ("000660", "042510", "042700"):
            return "sniper"
        if "swing" in pid or "스윙" in notes or ticker in ("267260", "003230"):
            return "swing"
        if "cyclical" in pid or "시클리컬" in notes or ticker in ("005490", "004020", "011170", "051915", "018880", "234100"):
            return "cyclical"
        if "signal" in pid or "forge" in pid or ticker == "068270":
            return "signal_forge"
        return "sniper"


KR_STRATEGY_DISPLAY = [
    ("sepa_pivot", "🚀 <b>[코어: SEPA x 피봇 돌파]</b>", "Stage 2 VCP 변동성축소"),
    ("sniper", "🎯 <b>[코어: 수급 스나이퍼]</b>", "외인·기관 양매수 주도주"),
    ("swing", "🛡️ <b>[코어: 227선 무한 스윙]</b>", "227일선/플랫 지지")
]

US_STRATEGY_DISPLAY = [
    ("htp_momentum", "🏆 <b>[코어: HTP 모멘텀 Top 10]</b>", "나스닥 메가캡 실적 주도주"),
    ("sepa_pivot", "🚀 <b>[코어: SEPA x 피봇 돌파]</b>", "Stage 2 추세추종"),
    ("swing", "🛡️ <b>[코어: 227선 무한 스윙]</b>", "우량 대형주 지지선 스윙")
]

PORTFOLIO_LEGEND = "• <b>수익률 상태 범례:</b> 🟢 수익(+) | 🔵 손실(-) | ⚪ 보합/진입가(0.0%)"

# 1순위 추천/보유 종목 매수 불가 시 즉시 집행하는 2순위 대체 예비 종목 풀
KR_BACKUP_ALTERNATIVES = {
    "012450": {"ticker": "064350", "name": "현대로템", "cap": "대형", "reason": "1단계 [선발대] 주봉 과매도(RSI 27.7) & MACD 히스토그램 반등 바닥 탈출"},
    "093320": {"ticker": "075950", "name": "산일전기", "cap": "중형", "reason": "1단계 [선발대] AI 데이터센터 변압기 VCP 눌림목 지지 (RSI 40.9)"},
    "031980": {"ticker": "058470", "name": "리노공업", "cap": "중형", "reason": "1단계 [선발대] 반도체 테스트 소켓 바닥 다지기 (RSI 35.6)"},
    "000660": {"ticker": "005930", "name": "삼성전자", "cap": "대형", "reason": "1단계 [선발대] 주봉 RSI 43.0 바닥 다지기 & 히스토그램 축소 반등"},
    "042700": {"ticker": "403870", "name": "HPSP", "cap": "중형", "reason": "1단계 [선발대] 고압 수소 어닐링 독점력 및 RSI 42.8 지지선"},
    "042510": {"ticker": "042700", "name": "한미반도체", "cap": "중형", "reason": "1단계 [선발대] 외인·기관 양매수 HBM TC본더 스나이퍼 1위"},
    "267260": {"ticker": "053800", "name": "안랩", "cap": "중형", "reason": "2단계 [대세확증] 주봉 MACD 0선 위 골든크로스 & RSI 75.1 초강세 모멘텀"}
}

US_BACKUP_ALTERNATIVES = {
    "NVDA": {"ticker": "META", "name": "메타 플랫폼스", "cap": "대형", "reason": "2단계 [대세확증] AI 추천 알고리즘 및 광고 실적 HTP 2위"},
    "AVGO": {"ticker": "LLY", "name": "일라이 릴리", "cap": "대형", "reason": "2단계 [대세확증] 비만 치료제 메가트렌드 HTP 파워 모멘텀 1위"},
    "AAPL": {"ticker": "MSFT", "name": "마이크로소프트", "cap": "대형", "reason": "1단계 [선발대] 클라우드 애저(Azure) AI 인프라 지지선 스윙"},
    "PLTR": {"ticker": "ALAB", "name": "아스테라 랩스", "cap": "중형", "reason": "2단계 [대세확증] AI PCIe 인터커넥트 VCP 돌파 1위"},
    "APP": {"ticker": "VRT", "name": "버티브 홀딩스", "cap": "중형", "reason": "2단계 [대세확증] AI 데이터센터 전력/냉각 피봇 돌파 2위"},
    "CPAY": {"ticker": "XOM", "name": "엑슨모빌", "cap": "대형", "reason": "1단계 [선발대] 227일선 우량 가치주 지지 스윙 스코어 1위"}
}


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
        if market.upper() in ("KRX", "KR"):
            return ["• <i>현재 한국장 보유 포지션 없음 (신규 진입 대기)</i>"]
        else:
            return [
                "• <i>현재 미국장 보유 포지션 없음 (미국장 개장 21:30~22:30 KST 일정에 맞추어 1순위/2순위 자동 분할 매수 집행 및 포트폴리오 업데이트 예정)</i>",
                "• 📋 <b>[오늘 밤 미국장 매수 대기 예정 리스트 (대형 3선 : 중소형 3선 [1:1])]</b>",
                "   ├ 🏆 <b>[HTP/대형] 엔비디아 (NVDA)</b> ➔ 🥈 2순위 대체: 메타 플랫폼스 (META)",
                "   ├ 🏆 <b>[HTP/대형] 브로드컴 (AVGO)</b> ➔ 🥈 2순위 대체: 일라이 릴리 (LLY)",
                "   ├ 🏆 <b>[HTP/대형] 애플 (AAPL)</b> ➔ 🥈 2순위 대체: 마이크로소프트 (MSFT)",
                "   ├ 🚀 <b>[SEPA/중형] 팔란티어 (PLTR)</b> ➔ 🥈 2순위 대체: 아스테라 랩스 (ALAB)",
                "   ├ 🚀 <b>[SEPA/중형] 앱러빈 (APP)</b> ➔ 🥈 2순위 대체: 버티브 홀딩스 (VRT)",
                "   └ 🛡️ <b>[스윙/대형] 콜페이 (CPAY)</b> ➔ 🥈 2순위 대체: 엑슨모빌 (XOM)"
            ]

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

            alt = (KR_BACKUP_ALTERNATIVES if is_kr else US_BACKUP_ALTERNATIVES).get(ticker)
            if is_summary:
                out.append(f" {summary_line}")
                if alt:
                    out.append(f"    └ 🥈 <i>[2순위 대체]</i> <b>{alt['name']}</b> ({alt['ticker']} / {alt['cap']}) - <i>{alt['reason']}</i>")
            else:
                is_new = (ticker in new_tickers) or h.get("is_new_entry", False)
                status_tag = format_holding_status(h, market, is_new=is_new)
                notes = h.get("notes", "")
                stage_tag = ""
                if "[2단계 대세확증]" in notes:
                    stage_tag = " • 🔥 <b>[2단계 대세확증]</b>"
                elif "[1단계 선발대]" in notes:
                    stage_tag = " • 🛡️ <b>[1단계 선발대]</b>"

                out.append(f" • {sign} <b>[{short_cap}] {name}</b> ({ticker}) | <b>{status_tag}</b>{stage_tag}")
                out.append(f"    {price_line}")
                if notes:
                    out.append(f"    └ 💡 <i>{notes}</i>")
                if alt:
                    out.append(f"    └ 🥈 <b>[2순위 대체 예비] {alt['name']}</b> ({alt['ticker']} / {alt['cap']}) : <i>{alt['reason']}</i>")

        # 스나이퍼 전략에서 손절 청산 등으로 1슬롯 현금 대기 중일 때 신규 1순위 및 2순위 안내
        if strat_key == "sniper" and is_kr and len(strat_holdings) < 2 and not is_summary:
            out.append(" • ⚪ <b>[중형] 한미반도체</b> (042700) | <b>[가용 현금 슬롯 / 1순위 대기]</b>")
            out.append("    └ <i>선정 근거:</i> 외인·기관 양매수 HBM TC본더 수급 1위 (시가/눌림목 분할 진입)")
            out.append("    └ 🥈 <b>[2순위 대체 예비] HPSP</b> (403870 / 중형) : <i>고압 수소 어닐링 독점력 및 기관 수급 2순위</i>")

    return out


def build_standalone_tracks_block(section_no: int = 5) -> str:
    """
    [단독 독립 운용 트랙 블록]
    - 코어 6종목 포트폴리오 N수에 포함되지 않는 독립 계좌/단독 운용 트랙
    1. 📡 [단독: Signal Forge AI 레이더] : 셀트리온(068270) 보유 포지션 및 25대 퀀트 실시간 매수 타깃
    2. 🌱 [단독: 중소형 2차 파동 부활] : 파월 인더스트리스(POWL), 모딘 매뉴팩처링(MOD)
    3. ⚡ [단독: US 3X 레버리지] : ProShares UltraPro QQQ (TQQQ) 무한매수 분할적립
    4. 🔄 [단독: 시클리컬 턴어라운드] : PBR 역사적 바닥 역발상 퀀트 (POSCO홀딩스, LG화학우 등 6대 시클리컬)
    """
    lines = []
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⚡ <b>{section_no}. [단독 독립 운용 트랙] (코어 N수 미포함 / 독립 계좌 운용)</b>")
    lines.append(PORTFOLIO_LEGEND)

    standalone_trades = []
    try:
        from core.database import get_db_connection
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM trades 
                WHERE status = 'HOLDING' AND (
                    LOWER(project_id) IN ('signal_forge_alert', 'signal-forge-alert', 'signal_forge', 'stock-stage2-revival', 'stage2_revival', 'stock-us3x', 'us3x', 'stock-cyclical-screener', 'cyclical')
                    OR ticker IN ('068270', 'POWL', 'MOD', 'TQQQ', '005490', '051915', '018880', '011170', '004020', '234100')
                )
                ORDER BY id ASC
            """).fetchall()
            standalone_trades = [dict(r) for r in rows]
    except Exception:
        standalone_trades = []

    # 1. Signal Forge AI 레이더
    sf_holdings = [t for t in standalone_trades if t.get("ticker") == "068270" or "signal" in (t.get("project_id") or "").lower()]
    lines.append("\n📡 <b>[단독: Signal Forge AI 레이더]</b> (25대 퀀트 매크로 & 실시간 레이더)")
    if sf_holdings:
        for h in sf_holdings:
            cur_p = int(float(h.get("current_price", 0)))
            entry_p = int(float(h.get("entry_price", 0)))
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret > 0 else ("🔵" if ret < 0 else "⚪")
            tgt_p = int(float(h.get("target_price", 0))) if h.get("target_price") else 200000
            stp_p = int(float(h.get("stop_loss_price", 0))) if h.get("stop_loss_price") else 178000
            lines.append(f" • {sign} <b>[포지션 보유] {h.get('name', '셀트리온')}</b> ({h.get('ticker')}) | <b>[보유 지속]</b>")
            lines.append(f"    └ 진입: {entry_p:,}원 ➔ 현재: {cur_p:,}원 (<b>{ret:+.2f}%</b>) | 🎯 {tgt_p:,}원 | 🛑 {stp_p:,}원")
            notes = h.get("notes", "")
            if notes:
                clean_notes = notes.split('|')[0].strip().replace("[단독/Signal Forge AI 레이더]", "").strip()
                if clean_notes:
                    lines.append(f"    └ <i>레이더 촉매:</i> {clean_notes}")
    else:
        lines.append(" • <i>현재 Signal Forge 보유 포지션 없음 (관망)</i>")

    radar_targets = fetch_signal_forge_radar_targets(market="KRX")
    if radar_targets:
        for t in radar_targets:
            p_str = f"{int(t['price']):,}원"
            lines.append(f" • 🎯 <b>[실시간 레이더 포착] {t['name']}</b> ({t['ticker']}) : <b>{p_str}</b> | <b>{t['score']:.0f}점</b> ({t['strategy']})")
            lines.append(f"    └ <i>포착 근거:</i> {t['reason']}")

    # 2. 중소형 2차 파동 부활
    s2_holdings = [t for t in standalone_trades if t.get("ticker") in ("POWL", "MOD") or "stage2" in (t.get("project_id") or "").lower()]
    lines.append("\n🌱 <b>[단독: 중소형 2차 파동 부활]</b> (10배주 라이프사이클 실적 퀀텀점프)")
    if s2_holdings:
        for h in s2_holdings:
            cur_p = float(h.get("current_price", 0))
            entry_p = float(h.get("entry_price", 0))
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret > 0 else ("🔵" if ret < 0 else "⚪")
            tgt_p = float(h.get("target_price", 0)) if h.get("target_price") else 165.0
            stp_p = float(h.get("stop_loss_price", 0)) if h.get("stop_loss_price") else 118.0
            lines.append(f" • {sign} <b>[포지션 보유] {h.get('name', h.get('ticker'))}</b> ({h.get('ticker')}) | <b>[추세 추종]</b>")
            lines.append(f"    └ 진입: ${entry_p:.2f} ➔ 현재: ${cur_p:.2f} (<b>{ret:+.2f}%</b>) | 🎯 ${tgt_p:.2f} | 🛑 ${stp_p:.2f}")
            notes = h.get("notes", "")
            if notes:
                clean_notes = notes.split('|')[0].strip().replace("[중소형주/단독 Stage2부활]", "").strip()
                if clean_notes:
                    lines.append(f"    └ <i>전략 테마:</i> {clean_notes}")
    else:
        lines.append(" • <i>현재 부활 전략 편입 대기 중</i>")

    # 3. US 3X 레버리지
    us3x_holdings = [t for t in standalone_trades if t.get("ticker") in ("TQQQ", "SOXL", "UPRO") or "3x" in (t.get("project_id") or "").lower()]
    lines.append("\n⚡ <b>[단독: US 3X 레버리지]</b> (나스닥 100 무한매수 분할 적립)")
    if us3x_holdings:
        for h in us3x_holdings:
            cur_p = float(h.get("current_price", 0))
            entry_p = float(h.get("entry_price", 0))
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret > 0 else ("🔵" if ret < 0 else "⚪")
            tgt_p = float(h.get("target_price", 0)) if h.get("target_price") else 85.0
            stp_p = float(h.get("stop_loss_price", 0)) if h.get("stop_loss_price") else 45.0
            lines.append(f" • {sign} <b>[분할 적립] {h.get('name', h.get('ticker'))}</b> ({h.get('ticker')}) | <b>[적립 분할매수]</b>")
            lines.append(f"    └ 진입: ${entry_p:.2f} ➔ 현재: ${cur_p:.2f} (<b>{ret:+.2f}%</b>) | 🎯 ${tgt_p:.2f} | 🛑 ${stp_p:.2f}")
            notes = h.get("notes", "")
            if notes:
                clean_notes = notes.split('|')[0].strip().replace("[3X 레버리지/US3X 15% 가중치]", "").strip()
                if clean_notes:
                    lines.append(f"    └ <i>운용 원칙:</i> {clean_notes}")
    else:
        lines.append(" • <i>현재 3X 레버리지 편입 대기 중</i>")

    # 4. 시클리컬 턴어라운드 (단독 독립 운용 트랙)
    cyc_holdings = [t for t in standalone_trades if "cyclical" in (t.get("project_id") or "").lower() or t.get("ticker") in ("005490", "051915", "018880", "011170", "004020", "234100")]
    lines.append(f"\n🔄 <b>[단독: 시클리컬 턴어라운드]</b> (역사적 PBR 바닥 역발상 퀀트 - 6대 섹터 턴어라운드 {len(cyc_holdings)}선)")
    if cyc_holdings:
        for h in cyc_holdings:
            ticker = h.get("ticker", "")
            name = h.get("name", ticker)
            cur_p = int(float(h.get("current_price", 0)))
            entry_p = int(float(h.get("entry_price", 0)))
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret > 0 else ("🔵" if ret < 0 else "⚪")
            tgt_p = int(float(h.get("target_price", 0))) if h.get("target_price") else int(entry_p * 1.4)
            stp_p = int(float(h.get("stop_loss_price", 0))) if h.get("stop_loss_price") else int(entry_p * 0.85)
            cap = classify_cap_size(ticker, name, market="KRX")
            short_cap = "대형" if "대형" in cap else ("소형" if "소" in cap else "중형")
            lines.append(f" • {sign} <b>[{short_cap}] {name}</b> ({ticker}) | <b>[바닥 턴어라운드]</b>")
            lines.append(f"    └ 진입: {entry_p:,}원 ➔ 현재: {cur_p:,}원 (<b>{ret:+.2f}%</b>) | 🎯 {tgt_p:,}원 | 🛑 {stp_p:,}원")
            notes = h.get("notes", "")
            if notes:
                clean_notes = notes.split('|')[0].strip().replace("[시클리컬 바닥 매수 턴어라운드]", "").replace("코어 포트폴리오 6종목 황금밸런스 정예화(슬롯 초과 정리)", "").strip()
                if clean_notes:
                    lines.append(f"    └ <i>PBR/턴어라운드 근거:</i> {clean_notes}")
    else:
        lines.append(" • <i>현재 시클리컬 포지션 없음 (모니터링 중)</i>")

    return "\n".join(lines)


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

    # 1. 미 증시 마감 시황 & 글로벌 매크로 요약
    dow = macro.get("dow", {})
    nasdaq = macro.get("nasdaq", {})
    sp500 = macro.get("sp500", {})
    usd_krw = macro.get("usd_krw", "1,340.0")
    vix = macro.get("vix", "18.38")
    us10y = macro.get("us10y", "4.20%")

    lines.append("🌐 <b>1. 🇺🇸 미 증시 마감 시황 & 글로벌 매크로 요약</b>")
    lines.append(f"• <b>미국 3대 지수:</b> 다우 {dow.get('val', '-')} ({dow.get('pct', 0.0):+.2f}%) | 나스닥 {nasdaq.get('val', '-')} ({nasdaq.get('pct', 0.0):+.2f}%) | S&P500 {sp500.get('val', '-')} ({sp500.get('pct', 0.0):+.2f}%)")
    lines.append(f"• <b>환율/변동성/금리:</b> 원/달러 <b>{usd_krw}원</b> | VIX <b>{vix}</b> | 美 10년물 국채 <b>{us10y}</b>")
    lines.append("• <b>한국장 개장 전술:</b> 09:00 시초가 갭상승 추격매수 금지, 5분봉 지지 확인 후 원칙 체결.")

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

    # 3. 한국장 코어 실운용 포트폴리오 (대형 3선 + 중소형 3선)
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    new_tickers = set(b.get("ticker") for b in new_buys)
    large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_ret = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇰🇷 한국장 코어 실운용 포트폴리오 (정예 {len(kr_active)}종목 - 대형 {large_c}선 : 중소형 {mid_c}선 [1:1 황금밸런스])</b>")
    lines.append(f"• <b>코어 포트폴리오 평균 수익률:</b> <b>{avg_ret:+.2f}%</b> (가용 슬롯: {kr_stats.get('available_slots', 0)}개)")
    lines.append(PORTFOLIO_LEGEND)
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=new_tickers, is_summary=False))

    # 4. 미국장 코어 실운용 포트폴리오
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_new_tickers = set(b.get("ticker") for b in us_portfolio.get("new_buys", []))
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") != "대형주")
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇺🇸 미국장 코어 실운용 포트폴리오 (정예 {len(us_active)}종목 - 대형 {us_large_c}선 + 중소형 {us_mid_c}선)</b>")
    lines.append(f"• <b>코어 포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.append(PORTFOLIO_LEGEND)
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=us_new_tickers, is_summary=False))

    # 5. 단독 독립 운용 트랙
    lines.append(build_standalone_tracks_block(section_no=5))

    # 6. 매주 화요일 오후 특별 점검 (미국 중소형 2차 파동 부활 전략)
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
    crypto_signals: Optional[List[Dict[str, Any]]] = None,
    market_summary: Optional[Dict[str, Any]] = None
) -> str:
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🎯 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 마감 종합 시황 & 실전 포트폴리오 알람</b>")
    lines.append(f"📅 <b>기준일자:</b> {today_str} | ⏰ 15:00~15:30 KST (장마감 종합 브리핑)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 한국장 당일 마감 시황 요약 (지수, 수급, 환율, 주도 테마, AI 시황 총평)
    if market_summary is None:
        try:
            market_summary = fetch_krx_market_summary()
        except Exception:
            market_summary = {}

    kp = market_summary.get("kospi", {})
    kd = market_summary.get("kosdaq", {})
    kp_inv = market_summary.get("kospi_investors", {})
    kd_inv = market_summary.get("kosdaq_investors", {})
    fx = market_summary.get("usd_krw", {})
    themes = market_summary.get("leading_themes", [])
    diagnosis = market_summary.get("market_diagnosis", "지수 변동성 속 개별 주도 섹터 중심 순환매")
    action_guide = market_summary.get("action_guide", "보유 포지션 목표가/손절가 원칙 준수 및 분할 대응")

    kp_pct = kp.get("pct", 0.0)
    kd_pct = kd.get("pct", 0.0)
    kp_sign = "🟢" if kp_pct > 0 else ("🔵" if kp_pct < 0 else "⚪")
    kd_sign = "🟢" if kd_pct > 0 else ("🔵" if kd_pct < 0 else "⚪")

    lines.append("📊 <b>1. 🇰🇷 한국장 당일 마감 시황 & 자금 이동(Money Flow) 요약</b>")
    lines.append(f"• <b>종가 지수:</b> 코스피 {kp_sign} <b>{kp.get('price', '-')}</b> ({kp.get('diff', '-')}p, <b>{kp_pct:+.2f}%</b>) | 코스닥 {kd_sign} <b>{kd.get('price', '-')}</b> ({kd.get('diff', '-')}p, <b>{kd_pct:+.2f}%</b>)")
    lines.append(f"• <b>원/달러 환율:</b> <b>{fx.get('price', '1,340.0')}원</b> (전일비 {fx.get('diff', '0.0')}원, {fx.get('pct', '0.0%')})")

    # A. 특이 자금 동향
    major_flow = market_summary.get("major_flow_summary", "")
    unusual_cap = market_summary.get("unusual_capital_comment", "")
    lines.append(f"\n💸 <b>[특이 자금 동향 (Unusual Capital Flows)]</b>")
    if major_flow:
        lines.append(f"• <b>메이저 수급 합산:</b> {major_flow}")
    lines.append(f"  └ 코스피: 외인 <b>{kp_inv.get('foreign', '0')}억</b> | 기관 <b>{kp_inv.get('inst', '0')}억</b> | 개인 <b>{kp_inv.get('personal', '0')}억</b>")
    lines.append(f"  └ 코스닥: 외인 <b>{kd_inv.get('foreign', '0')}억</b> | 기관 <b>{kd_inv.get('inst', '0')}억</b> | 개인 <b>{kd_inv.get('personal', '0')}억</b>")
    if unusual_cap:
        lines.append(f"• <b>수급 집중 분석:</b> {unusual_cap}")

    # B. 자금 이동 & 섹터 로테이션
    outflow = market_summary.get("money_outflow", "")
    inflow = market_summary.get("money_inflow", "")
    money_rot = market_summary.get("money_rotation_comment", "")
    lines.append(f"\n🔄 <b>[자금 이동 & 섹터 로테이션 (Money Migration)]</b>")
    if outflow:
        lines.append(f"• <b>자금 유출 섹터:</b> {outflow}")
    if inflow:
        lines.append(f"• <b>자금 유입 섹터:</b> {inflow}")
    if money_rot:
        lines.append(f"• <b>로테이션 분석:</b> {money_rot}")

    # C. 특이 업종 & 역주행 테마
    anom_theme = market_summary.get("anomalous_theme_comment", "")
    lines.append(f"\n🚀 <b>[특이 업종 & 역주행 테마 (Anomalous Themes)]</b>")
    if themes:
        lines.append(f"• <b>역주행 강세 테마 Top 3:</b> " + " | ".join(themes[:3]))
    if anom_theme:
        lines.append(f"• <b>테마 모멘텀 분석:</b> {anom_theme}")

    # D. AI 종합 진단 & 종가 전술
    lines.append(f"\n💡 <b>[AI 시황 종합 진단 & 종가 운용 전술]</b>")
    lines.append(f"• <b>시황 진단:</b> {diagnosis}")
    lines.append(f"• <b>종가 전술:</b> {action_guide}")

    # 2. 포트폴리오 변동 내역 (종가매수 & 포지션 재편)
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔄 <b>2. 포트폴리오 변동 내역 (종가매수 & 포지션 재편)</b>")

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

    # 3. 한국장 코어 실운용 포트폴리오 마감 현황
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    new_tickers = set(b.get("ticker") for b in new_buys)
    large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_ret = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇰🇷 한국장 코어 실운용 포트폴리오 마감 현황 (정예 {len(kr_active)}종목 - 대형 {large_c}선 : 중소형 {mid_c}선 [1:1 황금밸런스])</b>")
    lines.append(f"• <b>코어 포트폴리오 평균 수익률:</b> <b>{avg_ret:+.2f}%</b> (가용 슬롯: {kr_stats.get('available_slots', 0)}개)")
    lines.append(PORTFOLIO_LEGEND)
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=new_tickers, is_summary=False))

    # 4. 미국장 코어 실운용 포트폴리오 현황
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") != "대형주")
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇺🇸 미국장 코어 실운용 포트폴리오 현황 (정예 {len(us_active)}종목 - 대형 {us_large_c}선 : 중소형 {us_mid_c}선 [1:1 황금밸런스])</b>")
    lines.append(f"• <b>코어 포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.append(PORTFOLIO_LEGEND)
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=None, is_summary=False))

    # 5. 단독 독립 운용 트랙
    lines.append(build_standalone_tracks_block(section_no=5))

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

    # 3. 미국장 코어 실운용 포트폴리오
    us_active = us_portfolio.get("active_holdings", [])
    us_stats = us_portfolio.get("stats", {})
    us_new_tickers = set(b.get("ticker") for b in new_buys)
    us_large_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") == "대형주")
    us_mid_c = sum(1 for h in us_active if classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="US") != "대형주")
    us_avg_ret = us_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>3. 🇺🇸 미국장 코어 실운용 포트폴리오 (정예 {len(us_active)}종목 - 대형 {us_large_c}선 + 중소형 {us_mid_c}선)</b>")
    lines.append(f"• <b>코어 포트폴리오 평균 수익률:</b> <b>{us_avg_ret:+.2f}%</b> (가용 슬롯: {us_stats.get('available_slots', 0)}개)")
    lines.append(PORTFOLIO_LEGEND)
    lines.extend(format_strategy_grouped_portfolio(us_active, market="US", new_tickers=us_new_tickers, is_summary=False))

    # 4. 한국장 코어 실운용 포트폴리오 마감 요약
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    kr_large_c = sum(1 for h in kr_active if "대형" in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    kr_mid_c = sum(1 for h in kr_active if "대형" not in classify_cap_size(h.get("ticker", ""), h.get("name", ""), market="KRX"))
    avg_kr = kr_stats.get("avg_return_pct", 0.0)

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇰🇷 한국장 코어 실운용 포트폴리오 (정예 {len(kr_active)}종목 - 대형 {kr_large_c}선 : 중소형 {kr_mid_c}선 [1:1 황금밸런스] | 마감 평균 {avg_kr:+.2f}%)</b>")
    lines.append(PORTFOLIO_LEGEND)
    try:
        kr_mkt = fetch_krx_market_summary()
        kp_p = kr_mkt.get("kospi", {}).get("price", "-")
        kp_r = kr_mkt.get("kospi", {}).get("pct", 0.0)
        kd_p = kr_mkt.get("kosdaq", {}).get("price", "-")
        kd_r = kr_mkt.get("kosdaq", {}).get("pct", 0.0)
        lines.append(f"• <b>국내 증시 마감 요약:</b> 코스피 <b>{kp_p}</b> ({kp_r:+.2f}%) | 코스닥 <b>{kd_p}</b> ({kd_r:+.2f}%) | {kr_mkt.get('market_diagnosis', '')}")
    except Exception:
        pass
    lines.extend(format_strategy_grouped_portfolio(kr_active, market="KRX", new_tickers=None, is_summary=True))

    # 5. 단독 독립 운용 트랙
    lines.append(build_standalone_tracks_block(section_no=5))

    # 6. 매주 화요일 오후 특별 점검 (미국 중소형 2차 파동 부활 전략)
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
