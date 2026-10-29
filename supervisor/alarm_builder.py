#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
supervisor/alarm_builder.py
통합 알람 메시지 생성 모듈
난잡한 다수 종목 나열을 지양하고,
엄선된 [신규 매수 TOP 1~3], [매도/청산], [실전 포트폴리오 보유 현황]만
깔끔하고 명확하게 브리핑합니다.
"""

from datetime import datetime
from typing import Dict, Any, List


def build_krx_morning_alarm(portfolio_res: Dict[str, Any], macro: Dict[str, Any], best_buys: List[Dict[str, Any]]) -> str:
    """한국장 08:40 미국장 장마감 & 한국장 장전 통합 브리핑 메시지 생성"""
    now = datetime.now()
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    today_str = f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({weekdays_kr[now.weekday()]})"

    lines = []
    lines.append("🌅 <b>[STOCK SUPERVISOR] 미국장 장마감 & 🇰🇷 한국장 장전 통합 브리핑</b>")
    lines.append(f"📅 <b>일시:</b> {today_str} 08:40 KST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <b>[실전 포트폴리오 트레이딩 원칙]</b>")
    lines.append("• <b>모든 종목을 기계적으로 매수하지 마십시오!</b>")
    lines.append("• 7대 전략 시그널 중 정밀 2차 검증을 통과한 1~2개 주도주만 선별 진입합니다.")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

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
    lines.append("• <b>당일 전술:</b> 미 증시 마감 흐름을 반영하여 시초가 갭상승 추격매수 금지. 5분봉 매도세 소진 및 손익비(RR) 1.5 이상 확인 시 선별 출정.\n")

    # 2. 오늘의 엄선 신규 매수
    lines.append("🎯 <b>2. 🇰🇷 한국장 오늘의 엄선 매수 후보 (TOP Pick)</b>")
    new_buys = portfolio_res.get("new_buys", [])
    picks = new_buys if new_buys else best_buys[:2]

    if picks:
        for idx, p in enumerate(picks[:2], 1):
            badge = "🔥 <b>[복수전략 교차검증]</b> " if p.get("is_multi_confirmed") else ""
            strategies = ", ".join(p.get("strategies", []))
            lines.append(f"■ {idx}. {badge}<b>{p['name']}</b> ({p['ticker']} / {p.get('sector', '주도주')})")
            lines.append(f" • 기준가: <b>{int(p['price']):,}원</b> | 🎯 목표가: <b>{int(p['target_price']):,}원</b>")
            lines.append(f" • 🛑 기계적 손절가: <b>{int(p['stop_loss_price']):,}원</b> (RR: {p.get('risk_reward_ratio', 1.5)})")
            lines.append(f" • <i>포착 재료/전략:</i> {p.get('theme', '')[:60]} ({strategies})")
            lines.append(f" • <i>실전 지침:</i> {p.get('action_plan', '시가 지지 확인 후 분할 매수')}\n")
    else:
        lines.append("• <i>금일 유효 타점 부재로 신규 진입 보류 및 기존 포지션 관리</i>\n")

    # 3. 매도 / 청산 알람
    sells_sl = portfolio_res.get("sells_sl", [])
    sells_tp = portfolio_res.get("sells_tp", [])

    if sells_sl or sells_tp:
        lines.append("🚨 <b>3. 오늘 매도 / 청산 실행 알람</b>")
        for s in sells_sl:
            lines.append(f"• 🔴 <b>[손절 청산] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"   └ <i>사유:</i> {s.get('exit_reason', '손절선 이탈')}")
        for s in sells_tp:
            lines.append(f"• 🟢 <b>[목표가 익절] {s['name']}</b> ({s['ticker']}) : {s.get('return_pct', 0.0):+.2f}%")
            lines.append(f"   └ <i>사유:</i> {s.get('exit_reason', '1차 목표가 도달')}")
        lines.append("")

    # 4. 실시간 포트폴리오 보유 현황
    active = portfolio_res.get("active_holdings", [])
    stats = portfolio_res.get("stats", {})

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>4. 실시간 운용 포트폴리오 ({stats.get('total_holdings', len(active))}종목 운용 중)</b>")
    lines.append(f"• <b>평균 수익률:</b> <b>{stats.get('avg_return_pct', 0.0):+.2f}%</b> (여유 슬롯: {stats.get('available_slots', 0)}개)")

    if active:
        for h in active[:6]:
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret >= 0 else "🔵"
            lines.append(f"{sign} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret:+.2f}%</b>")
            lines.append(f"   └ 진입: {int(h['entry_price']):,}원 → 현재: {int(h['current_price']):,}원 (목표: {int(h['target_price']):,}원)")
        if len(active) > 6:
            lines.append(f"   <i>(외 {len(active)-6}개 보유 종목 대시보드에서 실시간 확인)</i>")
    else:
        lines.append("• <i>현재 100% 현금 보유 대기 상태</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")

    return "\n".join(lines)


def build_krx_closing_alarm(portfolio_res: Dict[str, Any], best_buys: List[Dict[str, Any]]) -> str:
    """한국장 15:00 종가매수(Strong Close) 최종 타깃 브리핑 메시지 생성"""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    lines = []
    lines.append("🎯 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 종가매수(Strong Close) 최종 타깃 브리핑</b>")
    lines.append(f"📅 <b>기준일자:</b> {today_str} | ⏰ 15:00 KST (장마감 30분 전 골든타임)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆 <b>[팔리 Strong Close x 5일선 종가 지지 모델]</b>")
    lines.append("• 당일 상위 25% 이내(CLV>=75%) 안착 및 5일선 위에 종가가 안착한 종목만 오버나이트 허용")
    lines.append("• 체결 즉시 -6% 자동 손절(Stop-Loss) 예약 필수\n")

    lines.append("🚀 <b>[종가매수 정예 후보 1~2선]</b>")
    picks = best_buys[:2]
    if picks:
        for idx, p in enumerate(picks, 1):
            lines.append(f"{idx}. <b>{p['name']}</b> ({p['ticker']}) | 종가: <b>{int(p['price']):,}원</b>")
            lines.append(f"   🛑 손절: {int(p['stop_loss_price']):,}원 | 🎯 1차목표: {int(p['target_price']):,}원")
            lines.append(f"   └ <i>특장:</i> {p.get('theme', '')[:45]}")
    else:
        lines.append("• <i>금일 오버나이트 적합 종목 부재 (현금 비중 유지 권고)</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")

    return "\n".join(lines)


def build_us_night_alarm(portfolio_res: Dict[str, Any], best_buys: List[Dict[str, Any]]) -> str:
    """미국장 21:30 미국장 장전 통합 브리핑 메시지 생성"""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    lines = []
    lines.append("🌃 <b>[STOCK SUPERVISOR] 🇺🇸 미국장 장전 통합 브리핑</b>")
    lines.append(f"📅 <b>기준일자:</b> {today_str} | ⏰ 21:30 KST (미국 본장 개장 전)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <b>[미국장 실전 운용 원칙]</b>")
    lines.append("• 3X 레버리지 무한투자와 HTP 모멘텀 TOP 10을 결합하여 지수 대비 초과 수익 추구")
    lines.append("• 피벗가 대비 +5% 초과 갭상승 출발 시 추격 금지, 2N 스탑로스 준수\n")

    lines.append("🚀 <b>[미국장 오늘의 엄선 타깃 TOP 2]</b>")
    picks = best_buys[:2]
    if picks:
        for idx, p in enumerate(picks, 1):
            lines.append(f"{idx}. <b>{p['name']}</b> ({p['ticker']} / {p.get('sector', 'US')})")
            lines.append(f"   • 기준가: <b>${p['price']:.2f}</b> | 🎯 목표: <b>${p['target_price']:.2f}</b> | 🛑 손절: <b>${p['stop_loss_price']:.2f}</b>")
            lines.append(f"   └ <i>운용법:</i> {p.get('action_plan', '')[:50]}")
    else:
        lines.append("• <i>기존 포지션 유지 및 분할 타점 모니터링</i>")

    active = portfolio_res.get("active_holdings", [])
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💼 <b>미국장 활성 포지션 현황 ({len(active)}종목)</b>")
    if active:
        for h in active[:5]:
            ret = float(h.get("return_pct", 0.0))
            sign = "🟢" if ret >= 0 else "🔵"
            lines.append(f"{sign} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret:+.2f}%</b> (진입: ${float(h['entry_price']):.2f})")
    else:
        lines.append("• <i>미국장 신규 진입 대기 포지션</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Unified Central Engine</i>")

    return "\n".join(lines)
