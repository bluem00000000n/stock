#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supervisor/alarm_builder.py
통합 알람 메시지 생성 모듈
하루 2회 단일 브리핑 체제:
- 08:40 : 미국장 장마감 통합 브리핑, 🇰🇷 한국장 장전 통합 브리핑
- 15:00 : 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑, 🇺🇸 미국장 장전 통합 브리핑
"""

from datetime import datetime
from typing import Dict, Any, List


def build_0840_us_close_kr_open_alarm(
    kr_portfolio: Dict[str, Any],
    us_portfolio: Dict[str, Any],
    macro: Dict[str, Any],
    kr_buys: List[Dict[str, Any]]
) -> str:
    """
    08:40 브리핑:
    [미국장 장마감 통합 브리핑, 🇰🇷 한국장 장전 통합 브리핑]
    """
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🌅 <b>[STOCK SUPERVISOR] 미국장 장마감 통합 브리핑, 🇰🇷 한국장 장전 통합 브리핑</b>")
    lines.append(f"📅 <b>일시:</b> {today_str} 08:40 KST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 미국장 마감 결과 및 글로벌 매크로
    lines.append("🌐 <b>1. 🇺🇸 미국장 장마감 결과 & 글로벌 매크로</b>")
    dow = macro.get("dow", {})
    nasdaq = macro.get("nasdaq", {})
    sp500 = macro.get("sp500", {})
    usd_krw = macro.get("usd_krw", "1,330.0")

    lines.append(f"• 다우: {dow.get('val', '-')} ({dow.get('pct', 0.0):+.2f}%)")
    lines.append(f"• 나스닥: {nasdaq.get('val', '-')} ({nasdaq.get('pct', 0.0):+.2f}%)")
    lines.append(f"• S&P 500: {sp500.get('val', '-')} ({sp500.get('pct', 0.0):+.2f}%)")
    lines.append(f"• 원/달러 환율: <b>{usd_krw}원</b>")

    us_active = us_portfolio.get("active_holdings", [])
    if us_active:
        us_summary = ", ".join([f"{h['name']}({h.get('return_pct', 0.0):+.1f}%)" for h in us_active[:4]])
        lines.append(f"• <b>미국장 포지션 현황:</b> {us_summary}")
    lines.append("• <b>장전 시초가 전술:</b> 미 증시 마감 흐름을 반영하여 시초가 갭상승 추격매수 금지. 5분봉 매도세 소진 및 손익비(RR) 1.5 이상 확인 시 선별 출정.\n")

    # 2. 한국장 오늘의 엄선 매수 후보
    lines.append("🎯 <b>2. 🇰🇷 한국장 오늘의 엄선 매수 후보 (TOP Pick)</b>")
    picks = kr_buys[:2]
    if picks:
        for idx, p in enumerate(picks, 1):
            badge = "🔥 <b>[복수전략 교차검증]</b> " if p.get("is_multi_confirmed") else ""
            strategies = ", ".join(p.get("strategies", []))
            lines.append(f"■ {idx}. {badge}<b>{p['name']}</b> ({p['ticker']} / {p.get('sector', '주도주')})")
            lines.append(f" • 기준가: <b>{int(p['price']):,}원</b> | 🎯 목표가: <b>{int(p['target_price']):,}원</b>")
            lines.append(f" • 🛑 기계적 손절가: <b>{int(p['stop_loss_price']):,}원</b> (RR: {p.get('risk_reward_ratio', 1.5)})")
            lines.append(f" • <i>포착 재료/전략:</i> {p.get('theme', '')[:60]} ({strategies})")
            lines.append(f" • <i>실전 지침:</i> {p.get('action_plan', '시가 지지 확인 후 분할 매수')}\n")
    else:
        lines.append("• <i>금일 유효 타점 부재로 신규 진입 보류 및 기존 포지션 관리</i>\n")

    # 3. 한국장 매도 / 청산 실행 알람
    sells_sl = kr_portfolio.get("sells_sl", [])
    sells_tp = kr_portfolio.get("sells_tp", [])
    if sells_sl or sells_tp:
        lines.append("🚨 <b>3. 🇰🇷 한국장 오늘 매도 / 청산 실행 알람</b>")
        for s in sells_sl:
            lines.append(f"• 🔴 <b>[손절 청산] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
        for s in sells_tp:
            lines.append(f"• 🟢 <b>[목표가 익절] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
        lines.append("")

    # 4. 한국장 실시간 운용 포트폴리오
    kr_active = kr_portfolio.get("active_holdings", [])
    stats = kr_portfolio.get("stats", {})
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 🇰🇷 한국장 실시간 운용 포트폴리오 ({stats.get('total_holdings', len(kr_active))}종목)</b>")
    lines.append(f"• <b>평균 수익률:</b> <b>{stats.get('avg_return_pct', 0.0):+.2f}%</b> (여유 슬롯: {stats.get('available_slots', 0)}개)")
    if kr_active:
        for h in kr_active[:5]:
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret >= 0 else "🔵"
            lines.append(f"{sign} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret:+.2f}%</b> (진입: {int(h['entry_price']):,}원)")
        if len(kr_active) > 5:
            lines.append(f"   <i>(외 {len(kr_active)-5}개 보유 종목 대시보드에서 실시간 확인)</i>")
    else:
        lines.append("• <i>현재 100% 현금 보유 대기 상태</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")
    return "\n".join(lines)


def build_1500_kr_close_us_open_alarm(
    kr_portfolio: Dict[str, Any],
    us_portfolio: Dict[str, Any],
    kr_buys: List[Dict[str, Any]],
    us_buys: List[Dict[str, Any]]
) -> str:
    """
    15:00 브리핑:
    [15:00 : 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑, 미국장 장전 통합 브리핑]
    """
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🎯 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑, 미국장 장전 통합 브리핑</b>")
    lines.append(f"📅 <b>기준일자:</b> {today_str} | ⏰ 15:00 KST (장마감 30분 전)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. 한국장 종가매수 정예 후보
    lines.append("🏆 <b>1. 🇰🇷 한국장 종가매수(Strong Close) 정예 후보</b>")
    lines.append("• 5일선 종가 안착 & 상위 25% 이내 마감 예상 종목만 오버나이트 허용 (체결 즉시 -6% 손절 예약)")
    picks = kr_buys[:2]
    if picks:
        for idx, p in enumerate(picks, 1):
            lines.append(f"■ {idx}. <b>{p['name']}</b> ({p['ticker']}) | 종가: <b>{int(p['price']):,}원</b>")
            lines.append(f"   🛑 손절가: <b>{int(p['stop_loss_price']):,}원</b> | 🎯 1차목표가: <b>{int(p['target_price']):,}원</b>")
            lines.append(f"   └ <i>특장/테마:</i> {p.get('theme', '')[:50]}")
    else:
        lines.append("• <i>금일 오버나이트 적합 종목 부재 (현금 비중 유지 권고)</i>")

    # 2. 한국장 포트폴리오 마감 상태
    kr_active = kr_portfolio.get("active_holdings", [])
    kr_stats = kr_portfolio.get("stats", {})
    lines.append(f"\n💼 <b>한국장 운용 포트폴리오 마감 현황 ({len(kr_active)}종목 | 평균 {kr_stats.get('avg_return_pct', 0.0):+.2f}%)</b>")
    for h in kr_active[:4]:
        ret = float(h.get("return_pct", 0.0))
        sign = "🟢" if ret >= 0 else "🔵"
        lines.append(f"• {sign} <b>{h['name']}</b>: <b>{ret:+.2f}%</b> (현재가 {int(h['current_price']):,}원)")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 3. 미국장 장전 통합 브리핑
    lines.append("🌃 <b>2. 🇺🇸 미국장 장전 통합 브리핑 (오늘 밤 개장 전략)</b>")
    lines.append("• 3X 레버리지 무한투자와 HTP 모멘텀 TOP 10 결합 운용")
    lines.append("• 피벗가 대비 +5% 초과 추격매수 절대 금지, 2N 스탑 준수\n")

    lines.append("🚀 <b>[미국장 오늘의 엄선 타깃 TOP 2]</b>")
    us_picks = us_buys[:2]
    if us_picks:
        for idx, p in enumerate(us_picks, 1):
            lines.append(f"■ {idx}. <b>{p['name']}</b> ({p['ticker']} / {p.get('sector', 'US')})")
            lines.append(f"   • 기준가: <b>${p['price']:.2f}</b> | 🎯 목표: <b>${p['target_price']:.2f}</b> | 🛑 손절: <b>${p['stop_loss_price']:.2f}</b>")
            lines.append(f"   └ <i>실전 운용:</i> {p.get('action_plan', '')[:60]}")
    else:
        lines.append("• <i>미국장 신규 진입 대기 (기존 분할 포지션 유지)</i>")

    # 4. 미국장 활성 포지션
    us_active = us_portfolio.get("active_holdings", [])
    lines.append(f"\n💼 <b>미국장 활성 포지션 현황 ({len(us_active)}종목)</b>")
    if us_active:
        for h in us_active[:4]:
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret >= 0 else "🔵"
            lines.append(f"• {sign} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret:+.2f}%</b> (진입: ${float(h['entry_price']):.2f})")
    else:
        lines.append("• <i>미국장 신규 진입 대기 포지션</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")
    return "\n".join(lines)
