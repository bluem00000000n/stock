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

from core.market_data import fetch_us_macro
from portfolio.manager import update_holdings_prices, enforce_portfolio_target_6
from supervisor.alarm_builder import (
    build_0830_kr_open_alarm,
    build_1500_kr_close_alarm,
    build_1730_us_open_alarm
)

# -------------------------------------------------------------
# 4. 정기 알람 리포트 빌더 (추천리스트 삭제, 포트폴리오 & 변동내역 중심)
# -------------------------------------------------------------
STANDALONE_PROJECT_IDS = {
    "stock-us3x", "us3x",
    "stock-stage2-revival", "stage2_revival",
    "signal_forge_alert", "signal-forge-alert", "signal_forge"
}


def get_portfolio_context(market: str = "KRX") -> dict:
    """실운영 코어 6종목 및 단독 독립 트랙 상태 패키징"""
    all_holdings = enforce_portfolio_target_6(market=market)
    core_holdings = [h for h in all_holdings if (h.get("project_id") or "").lower() not in STANDALONE_PROJECT_IDS]
    standalone_holdings = [h for h in all_holdings if (h.get("project_id") or "").lower() in STANDALONE_PROJECT_IDS]

    large_cnt = sum(1 for h in core_holdings if "대형" in str(h.get("cap_size", "")))
    mid_cnt = sum(1 for h in core_holdings if "대형" not in str(h.get("cap_size", "")))
    avg_ret = round(sum(float(h.get("return_pct", 0.0)) for h in core_holdings) / max(1, len(core_holdings)), 2)

    return {
        "market": market,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "active_holdings": core_holdings,
        "standalone_holdings": standalone_holdings,
        "new_buys": [],
        "sells_sl": [],
        "sells_tp": [],
        "replacements": [],
        "stats": {
            "total_holdings": len(core_holdings),
            "large_count": large_cnt,
            "mid_count": mid_cnt,
            "avg_return_pct": avg_ret,
            "available_slots": max(0, 6 - len(core_holdings))
        }
    }


def build_krx_open_report() -> tuple:
    kr_port = get_portfolio_context("KRX")
    us_port = get_portfolio_context("US")
    macro = fetch_us_macro()
    report_text = build_0830_kr_open_alarm(kr_port, us_port, macro)
    title = f"08:30 : 🇰🇷 한국장 개장전 실전 포트폴리오 알람 ({kr_port['date']})"
    return report_text, title, ["stock-supervisor"]


def build_krx_close_report() -> tuple:
    kr_port = get_portfolio_context("KRX")
    us_port = get_portfolio_context("US")
    report_text = build_1500_kr_close_alarm(kr_port, us_port)
    title = f"15:00 : 🇰🇷 한국장 마감 종합 시황 & 실전 포트폴리오 알람 ({kr_port['date']})"
    return report_text, title, ["stock-supervisor"]


def build_us_open_report() -> tuple:
    kr_port = get_portfolio_context("KRX")
    us_port = get_portfolio_context("US")
    macro = fetch_us_macro()
    report_text = build_1730_us_open_alarm(kr_port, us_port, macro)
    title = f"17:30 : 🇺🇸 미국장 장전 실전 포트폴리오 알람 ({kr_port['date']})"
    return report_text, title, ["stock-supervisor"]


# 하위 호환성 별칭
build_krx_integrated_report = build_krx_open_report
build_us_integrated_report = build_us_open_report

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
def run_integrated_alarm(mode: str = "auto", dry_run: bool = False) -> bool:
    now_hour = datetime.now().hour
    if mode == "auto":
        if now_hour < 12:
            mode = "0830"
        elif now_hour < 16:
            mode = "1500"
        else:
            mode = "1730"
    elif mode in ("krx", "kr"):
        mode = "0830" if now_hour < 13 else "1500"
    elif mode in ("us", "usa"):
        mode = "1730"

    print(f"🚀 [Stock Supervisor] Running Integrated Alarm Process (Mode: {mode})")

    # 1. 하위 프로젝트 중앙 DB 동기화
    try:
        import sync_master_db
        sync_master_db.sync_all_subprojects()
    except Exception as e:
        print(f"Warning: sync_master_db error: {e}")

    # 2. 리포트 생성
    if mode == "0830":
        report_text, title, project_ids = build_krx_open_report()
        mkt_code = "KRX"
    elif mode == "1500":
        report_text, title, project_ids = build_krx_close_report()
        mkt_code = "KRX"
    else:  # 1730
        report_text, title, project_ids = build_us_open_report()
        mkt_code = "US"

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
    parser.add_argument("--mode", choices=["0830", "1500", "1730", "auto", "krx", "us"], default="auto", help="Alarm schedule mode")
    parser.add_argument("--market", choices=["krx", "us", "auto"], default=None, help="Legacy market flag")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending telegram")
    args = parser.parse_args()

    chosen_mode = args.mode
    if args.market and args.mode == "auto":
        chosen_mode = args.market

    run_integrated_alarm(mode=chosen_mode, dry_run=args.dry_run)
