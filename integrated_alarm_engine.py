#!/usr/bin/env python3
"""
Stock Supervisor - 통합 알람 및 포트폴리오 취합 발송 엔진
(Integrated Alarm & Portfolio Supervisor Engine)

1. 하위 프로젝트(7대 전략)의 자체 DB/파일 데이터를 중앙 stock_master.db로 동기화
2. 조건에 맞는 추천 종목 리스트 및 포트폴리오 관리 현황을 취합
3. 시황, 업종, 테마, 개별 종목의 특장에 따라 선별 매수/매도할 수 있도록 정돈된 통합 브리핑 메시지 생성
4. 알람 시간에 맞춰 한국장(08:45) 또는 미국장(21:30) 텔레그램 통합 알람 발송
5. 발송 내역을 alarms 테이블 및 status.json / index.html에 최신화하여 대시보드에 즉시 반영
"""

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from pathlib import Path

BASE_DIR = "/Users/tothemoon"
SUPERVISOR_DIR = os.path.join(BASE_DIR, "stock-supervisor")
DATA_DIR = os.path.join(SUPERVISOR_DIR, "data")
MASTER_DB_PATH = os.path.join(DATA_DIR, "stock_master.db")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# -------------------------------------------------------------
# 1. 텔레그램 환경 설정 로드
# -------------------------------------------------------------
def load_telegram_credentials():
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    env_paths = [
        os.path.join(SUPERVISOR_DIR, ".env"),
        os.path.join(BASE_DIR, "stock-sniper/.env"),
        os.path.join(BASE_DIR, "stock-swing/.env"),
        os.path.join(BASE_DIR, "stock-sepa-pivot/.env"),
        os.path.join(BASE_DIR, "stock-htp-top10/.env")
    ]

    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k == "TELEGRAM_TOKEN" and not token:
                                token = v
                            elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                                chat_id = v
            except Exception:
                pass
            if token and chat_id:
                break

    token = token or "8928552590:AAG5uUN5qEQA1DYDCoT6DNPKRfZhSGt46go"
    chat_id = chat_id or "-5501244097"
    return token, chat_id

# -------------------------------------------------------------
# 2. 텔레그램 발송 함수 (분할 전송 지원)
# -------------------------------------------------------------
def send_telegram_message(text: str, token: str = None, chat_id: str = None) -> bool:
    if not token or not chat_id:
        token, chat_id = load_telegram_credentials()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # 텔레그램 4096자 제한 대응 (3800자 단위 청크 분할)
    MAX_CHUNK = 3800
    chunks = []
    if len(text) <= MAX_CHUNK:
        chunks = [text]
    else:
        parts = text.split("\n\n")
        curr = ""
        for p in parts:
            if len(curr) + len(p) + 2 < MAX_CHUNK:
                curr += ("\n\n" if curr else "") + p
            else:
                if curr:
                    chunks.append(curr)
                curr = p
        if curr:
            chunks.append(curr)

    success_all = True
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as res:
                result = json.loads(res.read().decode("utf-8"))
                if not result.get("ok"):
                    print(f"❌ Telegram API Error: {result}")
                    success_all = False
        except Exception as e:
            print(f"❌ Telegram Send Exception: {e}")
            success_all = False

    return success_all

# -------------------------------------------------------------
# 3. 데이터베이스 조회 헬퍼
# -------------------------------------------------------------
def get_db_signals(project_ids: list, limit_per_proj: int = 5) -> dict:
    """stock_master.db에서 해당 프로젝트들의 최신 추천 시그널 조회"""
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    res = {}
    for pid in project_ids:
        rows = conn.execute("""
            SELECT * FROM subproject_signals 
            WHERE project_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (pid, limit_per_proj)).fetchall()
        res[pid] = [dict(r) for r in rows]
    conn.close()
    return res

def get_db_holdings(market_filter: str = None) -> list:
    """stock_master.db에서 현재 보유 중인 포지션 조회"""
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM trades WHERE status = 'HOLDING'"
    params = []
    if market_filter:
        query += " AND market = ?"
        params.append(market_filter)
    query += " ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# -------------------------------------------------------------
# 4. 한국장 (KRX) 통합 브리핑 리포트 생성
# -------------------------------------------------------------
def build_krx_integrated_report() -> tuple:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().strftime("%Y년 %m월 %d일")
    weekday_kor = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]

    project_ids = [
        "stock-sniper",
        "stock-sepa-pivot",
        "stock-swing",
        "stock-cyclical-screener",
        "stock-dividend_top7"
    ]
    signals = get_db_signals(project_ids, limit_per_proj=4)
    holdings = get_db_holdings(market_filter="KRX")

    # 야간 미 증시 및 환율 정보 취득 시도
    overnight_info = "• 야간 미 증시: 안정권 등락 • 환율: 1,320~1,330원 박스권"
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, "stock-sniper"))
        import sniper_generator
        us_data = sniper_generator.fetch_overnight_us_indices()
        fx_str = sniper_generator.fetch_exchange_rate()
        if us_data:
            dow = us_data.get("dow", {})
            nasdaq = us_data.get("nasdaq", {})
            sp500 = us_data.get("sp500", {})
            overnight_info = (
                f"• 다우: {dow.get('val', '-')} ({dow.get('pct', '-')}%) | "
                f"나스닥: {nasdaq.get('val', '-')} ({nasdaq.get('pct', '-')}%) | "
                f"S&P500: {sp500.get('val', '-')} ({sp500.get('pct', '-')}%) | "
                f"환율: {fx_str}"
            )
    except Exception:
        pass

    lines = []
    lines.append("🌅 <b>[STOCK SUPERVISOR] KRX 한국장 통합 실전 브리핑</b>")
    lines.append(f"📅 <b>일시:</b> {today_date} ({weekday_kor}) 08:45 KST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <b>[실전 포트폴리오 트레이딩 원칙]</b>")
    lines.append("• <b>모든 추천 종목을 기계적으로 매수하지 마십시오!</b>")
    lines.append("• 당일 시황, 주도 업종, 테마 수급 및 개별 종목의 특장에 따라 1~2개 종목만 엄선하여 분할 진입/익절 대응합니다.")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # 1. 시황 및 매크로
    lines.append("🌐 <b>1. 당일 장전 시황 & 매크로 환경</b>")
    lines.append(f"{overnight_info}")
    lines.append("• <b>당일 전술:</b> 지수 ETF(KODEX 200, KODEX 레버리지) 수급과 외인/기관 방향성을 체크하며, 시가 급등 추격매수는 지양하고 5분~15분봉 지지선 확인 후 선별 진입합니다.\n")

    # 2. 전략별 엄선 종목 리스트
    lines.append("🎯 <b>2. 전략별 오늘의 핵심 선별 리스트</b>")

    # 2-1. stock-sniper
    sniper_list = signals.get("stock-sniper", [])
    lines.append("\n<b>[스톡 스나이퍼] RS 상대강도 & 52주 신고가 주도주</b>")
    if sniper_list:
        for s in sniper_list[:3]:
            raw = json.loads(s.get("raw_json") or "{}")
            theme = raw.get("theme") or raw.get("sector") or "수급 주도주"
            price_str = f"{int(s['price']):,}원" if s.get("price") else "시가"
            target_str = f"목표: {int(s['target_price']):,}원" if s.get("target_price") else "목표: +5~10%"
            stop_str = f"손절: {int(s['stop_loss_price']):,}원" if s.get("stop_loss_price") else "손절: 20일선"
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | 진입: {price_str} | {target_str} | {stop_str}")
            lines.append(f"  └ <i>특장/테마:</i> {theme[:45]}")
    else:
        lines.append("• 관망 및 장중 수급 주도주 압축 대기")

    # 2-2. stock-sepa-pivot
    sepa_list = [s for s in signals.get("stock-sepa-pivot", []) if s.get("market") in ("KOR", "KR")]
    lines.append("\n<b>[SEPA x 피봇] VCP 변동성 수축 & 돌파 타점</b>")
    if sepa_list:
        for s in sepa_list[:3]:
            raw = json.loads(s.get("raw_json") or "{}")
            theme = raw.get("theme") or raw.get("pattern") or "VCP 수축"
            price_str = f"{int(s['price']):,}원" if s.get("price") else "시가"
            pivot_str = f"피봇: {int(s['target_price']):,}원" if s.get("target_price") else ""
            stop_str = f"손절: {int(s['stop_loss_price']):,}원" if s.get("stop_loss_price") else ""
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | 현재가: {price_str} {pivot_str} {stop_str}")
            lines.append(f"  └ <i>특장/테마:</i> {theme[:45]}")
    else:
        lines.append("• 금일 유효 피봇 압축 진행 중")

    # 2-3. stock-swing
    swing_list = [s for s in signals.get("stock-swing", []) if s.get("market") in ("KOR", "kr")]
    lines.append("\n<b>[227선 무한 스윙] 중기 이평 지지 분할 매수 타점</b>")
    if swing_list:
        for s in swing_list[:3]:
            raw = json.loads(s.get("raw_json") or "{}")
            reason = raw.get("reason") or "227선 지지 분할 매수 타점"
            price_str = f"{int(s['price']):,}원" if s.get("price") else "시가"
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | 분할가: {price_str}")
            lines.append(f"  └ <i>전술:</i> {reason[:40]}")
    else:
        lines.append("• 현재 트렌치 유지 및 지지선 모니터링")

    # 2-4. stock-cyclical-screener
    cyc_list = signals.get("stock-cyclical-screener", [])
    lines.append("\n<b>[시클리컬 스크리너] PBR 바닥 섹터 턴어라운드</b>")
    if cyc_list:
        for s in cyc_list[:2]:
            raw = json.loads(s.get("raw_json") or "{}")
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | {s['signal_type']}")
            lines.append(f"  └ <i>섹터 특장:</i> 역사적 PBR 하단 턴어라운드 진입 검토")
    else:
        lines.append("• 시클리컬 섹터 순환매 대기")

    # 2-5. stock-dividend_top7 (월요일 또는 상시 안내)
    div_list = signals.get("stock-dividend_top7", [])
    if weekday_kor == "월" or len(div_list) > 0:
        lines.append("\n<b>[배당 TOP 7] 국고채 금리 초과 고배당 방어주</b>")
        for s in div_list[:3]:
            raw = json.loads(s.get("raw_json") or "{}")
            theme = raw.get("theme") or "고배당 안정주"
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | {theme}")

    # 3. 실시간 포트폴리오 관리 현황
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>3. 실시간 포트폴리오 포지션 현황 (Active Holdings)</b>")
    if holdings:
        for h in holdings[:5]:
            ret = h.get("return_pct", 0.0)
            ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
            sign_icon = "🟢" if ret >= 0 else "🔵"
            entry_str = f"{int(h['entry_price']):,}원"
            cur_str = f"{int(h['current_price']):,}원"
            target_str = f"목표: {int(h['target_price']):,}원" if h.get("target_price") else ""
            lines.append(f"{sign_icon} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret_str}</b>")
            lines.append(f"   └ 진입: {entry_str} → 현재: {cur_str} {target_str}")
        if len(holdings) > 5:
            lines.append(f"   (외 {len(holdings)-5}개 보유 종목 대시보드에서 실시간 확인 가능)")
    else:
        lines.append("• 현재 신규 진입 대기 상태 (현금 100% 보유)")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Central Engine</i>")

    message = "\n".join(lines)
    title = f"KRX 한국장 통합 실전 브리핑 ({today_date})"
    return message, title, project_ids

# -------------------------------------------------------------
# 5. 미국장 (US) 통합 브리핑 리포트 생성
# -------------------------------------------------------------
def build_us_integrated_report() -> tuple:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date = datetime.now().strftime("%Y년 %m월 %d일")
    weekday_kor = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]

    project_ids = [
        "stock-htp-top10",
        "stock-us3x",
        "stock-sepa-pivot",
        "stock-swing"
    ]
    signals = get_db_signals(project_ids, limit_per_proj=4)
    holdings = get_db_holdings(market_filter="US")

    lines = []
    lines.append("🌃 <b>[STOCK SUPERVISOR] US 미국장 통합 실전 브리핑</b>")
    lines.append(f"📅 <b>일시:</b> {today_date} ({weekday_kor}) 21:30 KST")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <b>[미국장 실전 포트폴리오 운용 원칙]</b>")
    lines.append("• 매크로 지표와 실적 발표 일정에 맞춰 레버리지 비중을 조절합니다.")
    lines.append("• 모든 종목을 매수하지 않고 업종 모멘텀 1위 및 3X 인피니트 원칙에 맞추어 선별 운용합니다.")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # 1. 미국 시장 환경 & 선물 진단
    lines.append("🌐 <b>1. 미국장 개장 전 매크로 환경</b>")
    lines.append("• 나스닥 100 / S&P 500 선물 지수 및 주요 테크 기업 실적 가이던스 확인")
    lines.append("• 미 국채 금리 및 VIX 변동성 지수 안정권 유지 여부 점검 후 진입\n")

    # 2. 미국장 전략별 추천 리스트
    lines.append("🚀 <b>2. 전략별 오늘의 핵심 선별 리스트</b>")

    # 2-1. HTP Momentum Top 10
    htp_list = signals.get("stock-htp-top10", [])
    lines.append("\n<b>[HTP 모멘텀 TOP 10] 기관 수급 & 52주 고가 퀀트 모멘텀</b>")
    if htp_list:
        for s in htp_list[:3]:
            raw = json.loads(s.get("raw_json") or "{}")
            sec = raw.get("sector") or "IT/Tech"
            reason = raw.get("reason") or "52주 최고가권 모멘텀 최상위"
            lines.append(f"• <b>{s['ticker']}</b> ({s['name']}) | {sec}")
            lines.append(f"  └ <i>퀀트 모멘텀:</i> {reason[:45]}")
    else:
        lines.append("• 퀀트 모멘텀 상위 후보군 리밸런싱 대기")

    # 2-2. US 3X Infinite
    us3x_list = signals.get("stock-us3x", [])
    lines.append("\n<b>[US 3X 무한 레버리지] SOXL · TQQQ · FNGU 분할 회전</b>")
    if us3x_list:
        for s in us3x_list[:3]:
            lines.append(f"• <b>{s['ticker']}</b> (3X 레버리지) | {s['signal_type']}")
            lines.append(f"  └ <i>운용법:</i> LOC/RSI 기준 단계별 분할 매수 및 +10% 트레일링 익절")
    else:
        lines.append("• 3X 레버리지 인피니트 분할 포지션 유지")

    # 2-3. SEPA x Pivot US
    sepa_us = [s for s in signals.get("stock-sepa-pivot", []) if s.get("market") in ("USA", "US")]
    lines.append("\n<b>[SEPA x 피봇 US] 미국 주도 성장주 VCP 돌파</b>")
    if sepa_us:
        for s in sepa_us[:2]:
            raw = json.loads(s.get("raw_json") or "{}")
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | 피봇 돌파 확인 시 분할 진입")
    else:
        lines.append("• 미국 성장주 변동성 수축 종목 추적 중")

    # 2-4. Swing US
    swing_us = [s for s in signals.get("stock-swing", []) if s.get("market") in ("USA", "US")]
    lines.append("\n<b>[227선 스윙 US] 미국 우량주 227선 지지 스윙</b>")
    if swing_us:
        for s in swing_us[:2]:
            lines.append(f"• <b>{s['name']}</b> ({s['ticker']}) | 지지선 분할 타점")
    else:
        lines.append("• 미국장 227선 지지 포지션 정상 유지")

    # 3. 실시간 포트폴리오 관리 현황
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>3. 미국장 포트폴리오 포지션 현황 (Active Holdings)</b>")
    if holdings:
        for h in holdings[:5]:
            ret = h.get("return_pct", 0.0)
            ret_str = f"+{ret:.2f}%" if ret >= 0 else f"{ret:.2f}%"
            sign_icon = "🟢" if ret >= 0 else "🔵"
            entry_str = f"${h['entry_price']:.2f}"
            cur_str = f"${h['current_price']:.2f}"
            lines.append(f"{sign_icon} <b>{h['name']}</b> ({h['ticker']}) : <b>{ret_str}</b>")
            lines.append(f"   └ 진입: {entry_str} → 현재: {cur_str}")
    else:
        lines.append("• 미국장 신규 진입 대기 포지션")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/")
    lines.append("🚀 <i>Stock Supervisor Central Engine</i>")

    message = "\n".join(lines)
    title = f"US 미국장 통합 실전 브리핑 ({today_date})"
    return message, title, project_ids

# -------------------------------------------------------------
# 6. 알람 로그 기록 및 대시보드 상태 최신화
# -------------------------------------------------------------
def record_alarm_to_db(title: str, message: str, project_ids: list, market: str):
    conn = sqlite3.connect(MASTER_DB_PATH)
    cur = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 알람 기록 등록
    for pid in project_ids:
        cur.execute("""
            INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, pid, now_str, "통합알람", market, title, message, "[]"))

    conn.commit()
    conn.close()

# -------------------------------------------------------------
# 7. 메인 실행 프로세스
# -------------------------------------------------------------
def run_integrated_alarm(market: str = "krx", dry_run: bool = False) -> bool:
    print(f"🚀 [Stock Supervisor] Running Integrated Alarm Process (Market: {market.upper()})")

    # 1. 하위 프로젝트 중앙 DB 동기화
    try:
        import sync_master_db
        sync_master_db.sync_all_subprojects()
    except Exception as e:
        print(f"Warning: sync_master_db error: {e}")

    # 2. 리포트 생성
    if market.lower() == "us":
        report_text, title, project_ids = build_us_integrated_report()
        mkt_code = "US"
    else:
        report_text, title, project_ids = build_krx_integrated_report()
        mkt_code = "KRX"

    if dry_run:
        print("\n" + "=" * 60)
        print("🔍 [DRY-RUN MODE - NO TELEGRAM SENT]")
        print("=" * 60)
        print(report_text)
        print("=" * 60)
        return True

    # 3. 텔레그램 전송
    print("📤 텔레그램 통합 알람 발송 중...")
    success = send_telegram_message(report_text)

    if success:
        print("✅ 텔레그램 통합 알람 전송 성공!")
        # 4. DB에 알람 기록 저장
        record_alarm_to_db(title, report_text, project_ids, mkt_code)

        # 5. status.json 및 index.html 인라인 데이터 동기화
        try:
            import update_status
            update_status.main()
            print("✅ 대시보드(status.json 및 index.html) 최신 알람 시간 갱신 완료")
        except Exception as e:
            print(f"Warning: update_status error: {e}")
        return True
    else:
        print("❌ 텔레그램 통합 알람 전송 실패!")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stock Supervisor Integrated Alarm Engine")
    parser.add_argument("--market", choices=["krx", "us", "auto"], default="krx", help="Target market for integrated alarm")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending telegram")
    args = parser.parse_args()

    target_market = args.market
    if target_market == "auto":
        now_hour = datetime.now().hour
        # 07:00 ~ 12:00 -> KRX, 19:00 ~ 23:59 -> US
        target_market = "us" if now_hour >= 18 else "krx"

    run_integrated_alarm(market=target_market, dry_run=args.dry_run)
