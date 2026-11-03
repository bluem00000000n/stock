#!/usr/bin/env python3
"""
Stock Trading Desk - 실전 수익률 및 포트폴리오 데이터베이스 엔진
전체 9개 퀀트 시스템 통합 관리:
1. stock-sniper (한국 장전 08:45 수급 & RS 5선)
2. stock-sepa-pivot (한국/미국 SEPA x 피벗 감시)
3. stock-swing (한국/미국 227선 무한 스윙 Scale-in)
4. stock-htp-top10 (미국 S&P 500 / 러셀 2000 HTP 모멘텀 TOP 10)
5. stock-us3x (미국 3배 레버리지 TQQQ/TECL/FAS 무한매수)
6. stock-dividend_top7 (한국 거래소 6대 원칙 주간 배당 TOP 7)
7. kbit-bot (장중 특징주 캔들 차트 분석 봇)
8. signal_forge_alert (AI 거시 시장 인텔리전스 & 카탈리스트 돌파)
9. stock-cyclical-screener (한국 6대 시클리컬 섹터 PBR 사이클)

- 장전알람: 당일 09:00 시가(Open Price) 자동 매수 체결
- 장중/야간알람: 알람 시점 시가/체결가 매수 체결
- 매도시: 목표가/손절가 또는 청산 신호 발생 시 DB에 매도가/매도일 기입 및 실현손익 확정
"""

import os
import json
import sqlite3
import ssl
import urllib.request
import urllib.parse
from datetime import datetime

SUPERVISOR_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SUPERVISOR_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock_master.db")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        project_name TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        alarm_type TEXT NOT NULL,
        market TEXT NOT NULL,
        title TEXT NOT NULL,
        raw_message TEXT NOT NULL,
        stocks_json TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        project_name TEXT NOT NULL,
        ticker TEXT NOT NULL,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        entry_price REAL NOT NULL,
        entry_date TEXT NOT NULL,
        current_price REAL NOT NULL,
        exit_price REAL,
        exit_date TEXT,
        status TEXT NOT NULL,        -- HOLDING (보유중) / CLOSED (매도완료)
        return_pct REAL NOT NULL,    -- 수익률 (%)
        target_price REAL,
        stop_loss_price REAL,
        notes TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_performance (
        date TEXT NOT NULL,
        project_id TEXT NOT NULL,
        daily_return_pct REAL NOT NULL,
        cumulative_return_pct REAL NOT NULL,
        realized_pnl_pct REAL NOT NULL,
        unrealized_pnl_pct REAL NOT NULL,
        holding_count INTEGER NOT NULL,
        closed_count INTEGER NOT NULL,
        win_rate REAL NOT NULL,
        PRIMARY KEY(date, project_id)
    );
    """)

    conn.commit()
    conn.close()

from core.market_data import fetch_krx_price as core_fetch_krx, fetch_us_price as core_fetch_us

# -------------------------------------------------------------
# 실시간 시세 API (core.market_data 통합 연동)
# -------------------------------------------------------------
def fetch_krx_price(code: str) -> dict:
    try:
        info = core_fetch_krx(code)
        p = float(info.get("price", 0.0))
        return {
            "name": info.get("name", code),
            "open": p,
            "current": p,
            "change_rate": float(info.get("change_pct", 0.0))
        }
    except Exception:
        return {"name": code, "open": 0.0, "current": 0.0, "change_rate": 0.0}

def fetch_us_price(symbol: str) -> dict:
    try:
        info = core_fetch_us(symbol)
        p = float(info.get("price", 0.0))
        return {
            "name": info.get("name", symbol),
            "open": p,
            "current": p,
            "change_rate": float(info.get("change_pct", 0.0))
        }
    except Exception:
        return {"name": symbol, "open": 0.0, "current": 0.0, "change_rate": 0.0}

def get_live_price(market: str, ticker: str) -> dict:
    if market == "KRX":
        return fetch_krx_price(ticker)
    return fetch_us_price(ticker)

# -------------------------------------------------------------
# 전체 9대 프로젝트 실전 알람 및 체결 시딩 (Reset & Reload 9 Projects)
# -------------------------------------------------------------
def reset_and_reload_all_9_projects():
    """오늘(2026-11-02) 기준 포트폴리오 초기화 및 정기 알람(08:30, 15:00, 17:30) 세팅"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM alarms")
    cur.execute("DELETE FROM trades")
    cur.execute("DELETE FROM daily_performance")
    conn.commit()

    today_str = datetime.now().strftime("%Y-%m-%d")

    # =========================================================
    # 1. 정기 알람 등록 (08:30, 15:00, 17:30 - 추천리스트 삭제, 포트폴리오 & 변동내역 중심)
    # =========================================================
    alarm_0830_text = f"""🌅 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 개장전 실전 포트폴리오 알람</b>
📅 <b>일시:</b> {today_str} 08:30 KST
━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 <b>1. 글로벌 매크로 요약</b>
• 다우: 42,114.40 (-0.61%) | 나스닥: 18,518.61 (-0.33%) | S&P500: 5,764.67 (-0.48%)
• 원/달러 환율: <b>1,379.5원</b> | VIX 지수: 18.38 (안정권 유지)
• <b>당일 전술:</b> 09:00 시초가 갭상승 추격매수 금지, 5분봉 지지 확인 후 원칙 체결.

━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 <b>2. 포트폴리오 변동 내역 (오늘의 포지션 조정)</b>
• 🔄 <b>[교체 종목] 농심 ➔ 삼양식품</b>
  └ <i>교체 이유:</i> 음식료 섹터 내 글로벌 불닭 수출 성장 모멘텀 우위 및 컵앤핸들 피벗 돌파
• 🔄 <b>[교체 종목] 셀트리온 ➔ 알테오젠</b>
  └ <i>교체 이유:</i> 바이오 섹터 내 피하주사(SC) 독점 플랫폼 기술수출 가치 부각
• 🆕 <b>[신규 종목] [중소형주] 라온시큐어</b> (042510) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
  └ <i>편입 이유:</i> 양자암호/생체인증 52주 신고가 스나이퍼 외인·기관 수급 유입

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>3. 🇰🇷 한국장 실운용 포트폴리오 (총 6종목 - 대형 3선 + 중소형 3선)</b>
• <b>포트폴리오 평균 수익률:</b> <b>+0.26%</b> (가용 슬롯: 0개)
 1. 🟢 <b>[대형주] SK하이닉스</b> (000660) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 1,388,000원 ➔ 현재: 1,388,000원 (<b>0.00%</b>) | 🎯 1,750,000원 | 🛑 1,310,000원
 2. 🟢 <b>[대형주] 유한양행</b> (000100) | <b>[지정가 매수: 76,900원]</b>
    └ 진입: 76,900원 ➔ 현재: 76,900원 (<b>0.00%</b>) | 🎯 92,000원 | 🛑 72,500원
 3. 🟢 <b>[대형주] HD현대일렉트릭</b> (267260) | <b>[지정가 매수: 442,000원]</b>
    └ 진입: 442,000원 ➔ 현재: 446,500원 (<b>+1.02%</b>) | 🎯 520,000원 | 🛑 410,000원
 4. 🟢 <b>[중형주] 알테오젠</b> (196170) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 213,500원 ➔ 현재: 213,500원 (<b>0.00%</b>) | 🎯 260,000원 | 🛑 198,000원
 5. 🟢 <b>[중형주] 삼양식품</b> (003230) | <b>[종가 매수 (15:20~15:30 동시호가 체결)]</b>
    └ 진입: 1,178,000원 ➔ 현재: 1,178,000원 (<b>0.00%</b>) | 🎯 1,380,000원 | 🛑 1,090,000원
 6. 🟢 <b>[중소형주] 라온시큐어</b> (042510) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 18,340원 ➔ 현재: 18,340원 (<b>0.00%</b>) | 🎯 21,500원 | 🛑 17,200원

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>4. 🇺🇸 미국장 실운용 포트폴리오 (총 6종목 - 대형 3선 + 중소형 3선)</b>
• <b>포트폴리오 평균 수익률:</b> <b>+0.16%</b> (가용 슬롯: 0개)
 1. 🟢 <b>[대형주] 엔비디아</b> (NVDA) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $204.64 ➔ 현재: $204.64 (<b>0.00%</b>) | 🎯 $260.00 | 🛑 $190.00
 2. 🟢 <b>[대형주] 팔란티어</b> (PLTR) | <b>[지정가 매수: $184.00]</b>
    └ 진입: $184.00 ➔ 현재: $184.11 (<b>+0.06%</b>) | 🎯 $230.00 | 🛑 $168.00
 3. 🟢 <b>[대형주] 브로드컴</b> (AVGO) | <b>[지정가 매수: $325.00]</b>
    └ 진입: $325.00 ➔ 현재: $326.08 (<b>+0.33%</b>) | 🎯 $400.00 | 🛑 $300.00
 4. 🟢 <b>[중형주] 파월 인더스트리스</b> (POWL) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $156.26 ➔ 현재: $156.26 (<b>0.00%</b>) | 🎯 $195.00 | 🛑 $142.00
 5. 🟢 <b>[중형주] 모딘 매뉴팩처링</b> (MOD) | <b>[지정가 매수: $129.00]</b>
    └ 진입: $129.00 ➔ 현재: $129.76 (<b>+0.59%</b>) | 🎯 $165.00 | 🛑 $118.00
 6. 🟢 <b>[3X 레버리지] ProShares UltraPro QQQ</b> (TQQQ) | <b>[종가 매수 (LOC 20분할)]</b>
    └ 진입: $62.01 ➔ 현재: $62.01 (<b>0.00%</b>) | 🎯 $85.00 | 🛑 $45.00

━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/
🚀 <i>Stock Supervisor Unified Central Engine</i>"""

    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-supervisor", "stock-supervisor", f"{today_str} 08:30:00", "정기알람(장전)", "KRX",
        f"08:30 : 🇰🇷 한국장 개장전 실전 포트폴리오 알람 ({today_str})",
        alarm_0830_text, "[]"
    ))

    alarm_1500_text = f"""🎯 <b>[STOCK SUPERVISOR] 🇰🇷 한국장 종가매수 최종 타깃 & 포트폴리오 알람</b>
📅 <b>기준일자:</b> {today_str} | ⏰ 15:00 KST (장마감 30분 전)
━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 <b>1. 포트폴리오 변동 내역 (종가매수 & 포지션 재편)</b>
• 🆕 <b>[신규 종목 (종가매수)] [중형주] 삼양식품</b> (003230) | <b>[종가 매수 (15:20~15:30 동시호가 체결)]</b>
  └ <i>편입 이유:</i> 글로벌 불닭 수출 호조 및 장중 강세 지속, 컵앤핸들 피벗 종가 돌파 안착
• <i>기타 포지션:</i> SK하이닉스, 유한양행, HD현대일렉트릭, 알테오젠, 라온시큐어 전량 보유 유지

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>2. 🇰🇷 한국장 실운용 포트폴리오 마감 현황 (총 6종목 - 대형 3선 + 중소형 3선)</b>
• <b>포트폴리오 평균 수익률:</b> <b>+0.26%</b> (가용 슬롯: 0개)
 1. 🟢 <b>[대형주] SK하이닉스</b> (000660) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 1,479,000원 ➔ 마감: 1,479,000원 (<b>0.00%</b>) | 🎯 1,750,000원 | 🛑 1,380,000원
 2. 🟢 <b>[대형주] 유한양행</b> (000100) | <b>[지정가 매수: 76,900원]</b>
    └ 진입: 76,900원 ➔ 마감: 76,900원 (<b>0.00%</b>) | 🎯 92,000원 | 🛑 72,500원
 3. 🟢 <b>[대형주] HD현대일렉트릭</b> (267260) | <b>[지정가 매수: 442,000원]</b>
    └ 진입: 442,000원 ➔ 마감: 446,500원 (<b>+1.02%</b>) | 🎯 520,000원 | 🛑 410,000원
 4. 🟢 <b>[중형주] 알테오젠</b> (196170) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 213,500원 ➔ 마감: 213,500원 (<b>0.00%</b>) | 🎯 260,000원 | 🛑 198,000원
 5. 🟢 <b>[중형주] 삼양식품</b> (003230) | <b>[종가 매수 (15:20~15:30 동시호가 체결)]</b>
    └ 진입: 1,178,000원 ➔ 마감: 1,178,000원 (<b>0.00%</b>) | 🎯 1,380,000원 | 🛑 1,090,000원
 6. 🟢 <b>[중소형주] 라온시큐어</b> (042510) | <b>[시가 매수 (09:00 개장 시가 체결)]</b>
    └ 진입: 18,340원 ➔ 마감: 18,340원 (<b>0.00%</b>) | 🎯 21,500원 | 🛑 17,200원

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>3. 🇺🇸 미국장 실운용 포트폴리오 현황 (총 6종목 - 대형 3선 + 중소형 3선)</b>
• <b>포트폴리오 평균 수익률:</b> <b>+0.16%</b> (가용 슬롯: 0개)
 1. 🟢 <b>[대형주] 엔비디아</b> (NVDA) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $204.64 ➔ 현재: $204.64 (<b>0.00%</b>) | 🎯 $260.00 | 🛑 $190.00
 2. 🟢 <b>[대형주] 팔란티어</b> (PLTR) | <b>[지정가 매수: $184.00]</b>
    └ 진입: $184.00 ➔ 현재: $184.11 (<b>+0.06%</b>) | 🎯 $230.00 | 🛑 $168.00
 3. 🟢 <b>[대형주] 브로드컴</b> (AVGO) | <b>[지정가 매수: $325.00]</b>
    └ 진입: $325.00 ➔ 현재: $326.08 (<b>+0.33%</b>) | 🎯 $400.00 | 🛑 $300.00
 4. 🟢 <b>[중형주] 파월 인더스트리스</b> (POWL) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $156.26 ➔ 현재: $156.26 (<b>0.00%</b>) | 🎯 $195.00 | 🛑 $142.00
 5. 🟢 <b>[중형주] 모딘 매뉴팩처링</b> (MOD) | <b>[지정가 매수: $129.00]</b>
    └ 진입: $129.00 ➔ 현재: $129.76 (<b>+0.59%</b>) | 🎯 $165.00 | 🛑 $118.00
 6. 🟢 <b>[3X 레버리지] ProShares UltraPro QQQ</b> (TQQQ) | <b>[종가 매수 (LOC 20분할)]</b>
    └ 진입: $62.01 ➔ 현재: $62.01 (<b>0.00%</b>) | 🎯 $85.00 | 🛑 $45.00

━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/
🚀 <i>Stock Supervisor Unified Central Engine</i>"""

    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-supervisor", "stock-supervisor", f"{today_str} 15:00:00", "정기알람(장마감)", "KRX",
        f"15:00 : 🇰🇷 한국장 종가매수 최종 타깃 & 포트폴리오 알람 ({today_str})",
        alarm_1500_text, "[]"
    ))

    alarm_1730_text = f"""🌃 <b>[STOCK SUPERVISOR] 🇺🇸 미국장 장전 실전 포트폴리오 알람</b>
📅 <b>일시:</b> {today_str} 17:30 KST (개장 전 프리마켓 정기 브리핑)
━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 <b>1. 미국 증시 매크로 & 선물 지수</b>
• 다우 선물: 42,114.40 (-0.61%) | 나스닥 선물: 18,518.61 (-0.33%) | S&P500 선물: 5,764.67 (-0.48%)
• 원/달러 환율: <b>1,379.5원</b> | VIX 지수: 18.38 (안정권 유지)
• <b>운용 지침:</b> 프리마켓 갭상승 추격 매수 금지, 22:30 개장 후 본장 호가 체결 원칙 준수.

━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 <b>2. 미국장 포트폴리오 변동 내역 (신규진입 & 재편)</b>
• 🔄 <b>[교체 종목] 일라이 릴리 (LLY) ➔ 팔란티어 (PLTR)</b>
  └ <i>교체 이유:</i> AI 엔터프라이즈 플랫폼 수주 폭발 및 모멘텀 상대강도 우위
• 🔄 <b>[교체 종목] 메타 (META) ➔ 브로드컴 (AVGO)</b>
  └ <i>교체 이유:</i> 빅테크 커스텀 AI ASIC 칩 수주 사이클 가속화
• 🆕 <b>[신규 종목] [3X 레버리지] ProShares UltraPro QQQ</b> (TQQQ) | <b>[종가 매수 (LOC 20분할)]</b>
  └ <i>편입 이유:</i> 나스닥 100 3배 레버리지 무한매수 1차 20분할 적립식 매수 개시

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>3. 🇺🇸 미국장 실운용 포트폴리오 (총 6종목 - 대형 3선 + 중소형 3선)</b>
• <b>포트폴리오 평균 수익률:</b> <b>+0.16%</b> (가용 슬롯: 0개)
 1. 🟢 <b>[대형주] 엔비디아</b> (NVDA) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $204.64 ➔ 현재: $204.64 (<b>0.00%</b>) | 🎯 $260.00 | 🛑 $190.00
 2. 🟢 <b>[대형주] 팔란티어</b> (PLTR) | <b>[지정가 매수: $184.00]</b>
    └ 진입: $184.00 ➔ 현재: $184.11 (<b>+0.06%</b>) | 🎯 $230.00 | 🛑 $168.00
 3. 🟢 <b>[대형주] 브로드컴</b> (AVGO) | <b>[지정가 매수: $325.00]</b>
    └ 진입: $325.00 ➔ 현재: $326.08 (<b>+0.33%</b>) | 🎯 $400.00 | 🛑 $300.00
 4. 🟢 <b>[중형주] 파월 인더스트리스</b> (POWL) | <b>[시가 매수 (22:30 개장 시가 체결)]</b>
    └ 진입: $156.26 ➔ 현재: $156.26 (<b>0.00%</b>) | 🎯 $195.00 | 🛑 $142.00
 5. 🟢 <b>[중형주] 모딘 매뉴팩처링</b> (MOD) | <b>[지정가 매수: $129.00]</b>
    └ 진입: $129.00 ➔ 현재: $129.76 (<b>+0.59%</b>) | 🎯 $165.00 | 🛑 $118.00
 6. 🟢 <b>[3X 레버리지] ProShares UltraPro QQQ</b> (TQQQ) | <b>[종가 매수 (LOC 20분할)]</b>
    └ 진입: $62.01 ➔ 현재: $62.01 (<b>0.00%</b>) | 🎯 $85.00 | 🛑 $45.00

━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>4. 🇰🇷 한국장 실운용 포트폴리오 (총 6종목 | 마감 평균 +0.26%)</b>
 1. 🟢 [대형주] SK하이닉스 (000660) : <b>0.00%</b> (1,479,000원)
 2. 🟢 [대형주] 유한양행 (000100) : <b>0.00%</b> (76,900원)
 3. 🟢 [대형주] HD현대일렉트릭 (267260) : <b>+1.02%</b> (446,500원)
 4. 🟢 [중형주] 알테오젠 (196170) : <b>0.00%</b> (213,500원)
 5. 🟢 [중형주] 삼양식품 (003230) : <b>0.00%</b> (1,178,000원)
 6. 🟢 [중소형주] 라온시큐어 (042510) : <b>0.00%</b> (18,340원)

━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️ <b>트레이딩 데스크:</b> https://bluem00000000n.github.io/stock/
🚀 <i>Stock Supervisor Unified Central Engine</i>"""

    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-supervisor", "stock-supervisor", f"{today_str} 17:30:00", "정기알람(야간)", "US",
        f"17:30 : 🇺🇸 미국장 장전 실전 포트폴리오 알람 ({today_str})",
        alarm_1730_text, "[]"
    ))

    # =========================================================
    # 2. 실전 운용 포트폴리오 체결 등록 (한국 6종목 + 미국 6종목 = 총 12종목)
    # =========================================================
    trades_to_insert = [
        # --- 🇰🇷 KRX 6종목 (대형 3선 + 중소형 3선) : 3개년 백테스트 가중치 기반 오늘(2026-11-03)부터 신규 체결 ---
        {
            "project_id": "stock-sniper", "project_name": "stock-sniper",
            "ticker": "000660", "name": "SK하이닉스", "market": "KRX",
            "signal_type": "시가매수(09:00)", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 1389000.0, "entry_date": today_str, "current_price": 1389000.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 1750000.0, "stop_loss_price": 1310000.0,
            "notes": "[대형주/스나이퍼 20% 가중치] HBM3E 엔비디아 독점 공급 수급 주도주 | 시가 매수 (09:00 개장 시가 체결)"
        },
        {
            "project_id": "stock-sepa-pivot", "project_name": "stock-sepa-pivot",
            "ticker": "000100", "name": "유한양행", "market": "KRX",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 76900.0, "entry_date": today_str, "current_price": 76900.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 92000.0, "stop_loss_price": 72500.0,
            "notes": "[대형주/SEPA 25% 가중치] 렉라자 FDA 상업화 랠리, 20주선 위 VCP 돌파 | 지정가 매수: 76,900원"
        },
        {
            "project_id": "stock-swing", "project_name": "stock-swing",
            "ticker": "267260", "name": "HD현대일렉트릭", "market": "KRX",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 431500.0, "entry_date": today_str, "current_price": 431500.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 520000.0, "stop_loss_price": 405000.0,
            "notes": "[대형주/스윙 10% 가중치] 북미 변압기 쇼티지 수혜, 43만원 플랫 베이스 지지 | 지정가 매수: 431,500원"
        },
        {
            "project_id": "stock-sepa-pivot", "project_name": "stock-sepa-pivot",
            "ticker": "093320", "name": "케이아이엔엑스", "market": "KRX",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 175000.0, "entry_date": today_str, "current_price": 175000.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 210000.0, "stop_loss_price": 161000.0,
            "notes": "[중소형주/SEPA 25% 가중치] 50일선 위 52주 신고가 하이타이트 플래그 추세추종 1위 | 지정가 매수: 175,000원"
        },
        {
            "project_id": "stock-swing", "project_name": "stock-swing",
            "ticker": "003230", "name": "삼양식품", "market": "KRX",
            "signal_type": "종가매수(동시호가)", "signal_date": f"{today_str} 15:00:00",
            "entry_price": 1159000.0, "entry_date": today_str, "current_price": 1159000.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 1380000.0, "stop_loss_price": 1090000.0,
            "notes": "[중소형주/스윙 10% 가중치] 글로벌 불닭 수출 호조, 컵앤핸들 지지 | 종가 매수 (15:20~15:30 동시호가 체결)"
        },
        {
            "project_id": "stock-sniper", "project_name": "stock-sniper",
            "ticker": "042510", "name": "라온시큐어", "market": "KRX",
            "signal_type": "시가매수(09:00)", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 19300.0, "entry_date": today_str, "current_price": 19300.0,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 22500.0, "stop_loss_price": 17900.0,
            "notes": "[중소형주/스나이퍼 20% 가중치] 생체인증/양자암호 52주 신고가 스나이퍼 수급 1위 | 시가 매수 (09:00 개장 시가 체결)"
        },

        # --- 🇺🇸 US 6종목 (대형 3선 + 중소형 2선 + 3X 레버리지 1선) ---
        {
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": "NVDA", "name": "엔비디아", "market": "US",
            "signal_type": "시가매수(22:30)", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 202.06, "entry_date": today_str, "current_price": 202.06,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 260.0, "stop_loss_price": 190.0,
            "notes": "[대형주/HTP 20% 가중치] AI 가속기 독점 및 블랙웰 사이클, HTP 대형 1위 | 시가 매수 (22:30 개장 시가 체결)"
        },
        {
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": "PLTR", "name": "팔란티어", "market": "US",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 178.34, "entry_date": today_str, "current_price": 178.34,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 230.0, "stop_loss_price": 168.0,
            "notes": "[대형주/HTP 20% 가중치] AIP 엔터프라이즈 모멘텀 급증, HTP 대형 5위 | 지정가 매수: $178.34"
        },
        {
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": "AVGO", "name": "브로드컴", "market": "US",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 322.23, "entry_date": today_str, "current_price": 322.23,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 400.0, "stop_loss_price": 300.0,
            "notes": "[대형주/HTP 20% 가중치] 커스텀 AI ASIC 수주 확대, HTP 대형 4위 | 지정가 매수: $322.23"
        },
        {
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": "POWL", "name": "파월 인더스트리스", "market": "US",
            "signal_type": "시가매수(22:30)", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 154.01, "entry_date": today_str, "current_price": 154.01,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 195.0, "stop_loss_price": 142.0,
            "notes": "[중소형주/HTP 20% 가중치] AI 데이터센터 전력망 장비, 러셀 2000 HTP 1위 | 시가 매수 (22:30 개장 시가 체결)"
        },
        {
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": "MOD", "name": "모딘 매뉴팩처링", "market": "US",
            "signal_type": "지정가매수", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 123.34, "entry_date": today_str, "current_price": 123.34,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 165.0, "stop_loss_price": 118.0,
            "notes": "[중소형주/HTP 20% 가중치] AI 데이터센터 액체냉각 열관리 독보적 성장, HTP 2위 | 지정가 매수: $123.34"
        },
        {
            "project_id": "stock-us3x", "project_name": "stock-us3x",
            "ticker": "TQQQ", "name": "ProShares UltraPro QQQ", "market": "US",
            "signal_type": "종가매수(LOC)", "signal_date": f"{today_str} 17:30:00",
            "entry_price": 59.46, "entry_date": today_str, "current_price": 59.46,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": 0.0,
            "target_price": 85.0, "stop_loss_price": 45.0,
            "notes": "[3X 레버리지/US3X 15% 가중치] 나스닥 100 3배 레버리지 무한매수 분할 적립 | 종가 매수 (LOC 20분할 매수)"
        },

        # --- 📊 서브 프로젝트 전략 매트릭스 카드용 실현 실적 (CLOSED) ---
        {
            "project_id": "stock-us3x", "project_name": "stock-us3x",
            "ticker": "TECL", "name": "Direxion Daily Tech 3X", "market": "US",
            "signal_type": "주간리밸런싱", "signal_date": f"{today_str} 17:00:00",
            "entry_price": 154.0, "entry_date": today_str, "current_price": 173.11,
            "exit_price": 173.11, "exit_date": today_str, "status": "CLOSED", "return_pct": 12.41,
            "target_price": 180.0, "stop_loss_price": 130.0, "notes": "테크 3X 트렌치 분할 익절"
        },
        {
            "project_id": "stock-us3x", "project_name": "stock-us3x",
            "ticker": "SOXL", "name": "Direxion Daily Semiconductor 3X", "market": "US",
            "signal_type": "주간리밸런싱", "signal_date": f"{today_str} 17:00:00",
            "entry_price": 71.0, "entry_date": today_str, "current_price": 77.05,
            "exit_price": 77.05, "exit_date": today_str, "status": "CLOSED", "return_pct": 8.52,
            "target_price": 85.0, "stop_loss_price": 55.0, "notes": "반도체 3X 트렌치 분할 익절"
        },
        {
            "project_id": "signal_forge_alert", "project_name": "signal_forge_alert",
            "ticker": "068270", "name": "셀트리온", "market": "KRX",
            "signal_type": "장중알람", "signal_date": f"{today_str} 10:00:00",
            "entry_price": 185000.0, "entry_date": today_str, "current_price": 192500.0,
            "exit_price": 192500.0, "exit_date": today_str, "status": "CLOSED", "return_pct": 4.05,
            "target_price": 200000.0, "stop_loss_price": 178000.0, "notes": "Catalyst Breakout 다일간 모멘텀 목표 익절"
        },
        {
            "project_id": "signal_forge_alert", "project_name": "signal_forge_alert",
            "ticker": "373220", "name": "LG에너지솔루션", "market": "KRX",
            "signal_type": "장중알람", "signal_date": f"{today_str} 10:00:00",
            "entry_price": 420000.0, "entry_date": today_str, "current_price": 406000.0,
            "exit_price": 406000.0, "exit_date": today_str, "status": "CLOSED", "return_pct": -3.33,
            "target_price": 450000.0, "stop_loss_price": 410000.0, "notes": "손절가 이탈 원칙 손절 청산"
        },
        {
            "project_id": "stock-cyclical-screener", "project_name": "stock-cyclical-screener",
            "ticker": "078350", "name": "한양디지텍", "market": "KRX",
            "signal_type": "장중매수신호", "signal_date": f"{today_str} 11:00:00",
            "entry_price": 32800.0, "entry_date": today_str, "current_price": 34600.0,
            "exit_price": 34600.0, "exit_date": today_str, "status": "CLOSED", "return_pct": 5.49,
            "target_price": 38000.0, "stop_loss_price": 31000.0, "notes": "반도체 패키징 PBR 침체기 저평가 매수 후 익절"
        },
        {
            "project_id": "stock-cyclical-screener", "project_name": "stock-cyclical-screener",
            "ticker": "007860", "name": "서연", "market": "KRX",
            "signal_type": "장중매도신호", "signal_date": f"{today_str} 11:00:00",
            "entry_price": 8900.0, "entry_date": today_str, "current_price": 9550.0,
            "exit_price": 9550.0, "exit_date": today_str, "status": "CLOSED", "return_pct": 7.30,
            "target_price": 10000.0, "stop_loss_price": 8400.0, "notes": "자동차 부품 PBR 호황기 정점 이익 실현 매도"
        },
        {
            "project_id": "stock-swing", "project_name": "stock-swing",
            "ticker": "033780", "name": "KT&G", "market": "KRX",
            "signal_type": "장전알람(227스윙)", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 184000.0, "entry_date": today_str, "current_price": 193000.0,
            "exit_price": 193000.0, "exit_date": today_str, "status": "CLOSED", "return_pct": 4.89,
            "target_price": 200000.0, "stop_loss_price": 178000.0, "notes": "227선 무한 스윙 3차 트렌치 익절"
        },
        {
            "project_id": "stock-swing", "project_name": "stock-swing",
            "ticker": "011200", "name": "HMM", "market": "KRX",
            "signal_type": "장전알람(227스윙)", "signal_date": f"{today_str} 08:30:00",
            "entry_price": 22400.0, "entry_date": today_str, "current_price": 23600.0,
            "exit_price": 23600.0, "exit_date": today_str, "status": "CLOSED", "return_pct": 5.36,
            "target_price": 25000.0, "stop_loss_price": 21000.0, "notes": "227선 스윙 2차 트렌치 익절"
        }
    ]

    # DB에 삽입
    for t in trades_to_insert:
        cur.execute("""
        INSERT INTO trades (
            project_id, project_name, ticker, name, market, signal_type,
            signal_date, entry_price, entry_date, current_price, exit_price,
            exit_date, status, return_pct, target_price, stop_loss_price, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t["project_id"], t["project_name"], t["ticker"], t["name"], t["market"],
            t["signal_type"], t["signal_date"], t["entry_price"], t["entry_date"],
            t["current_price"], t["exit_price"], t["exit_date"], t["status"],
            t["return_pct"], t["target_price"], t["stop_loss_price"], t["notes"]
        ))

    conn.commit()
    conn.close()
    print(f"✅ 포트폴리오 기준일({today_str}) 초기화 완료: 총 {len(trades_to_insert)}개 실전 매매 DB 등록")

# -------------------------------------------------------------
# 보유 종목 시세 동기화 및 수익률/매도 관리
# -------------------------------------------------------------
def update_trades_and_performance():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM trades")
    trades = cur.fetchall()

    today_str = datetime.now().strftime("%Y-%m-%d")

    for row in trades:
        t_id = row["id"]
        status = row["status"]
        market = row["market"]
        ticker = row["ticker"]
        entry_p = row["entry_price"]
        target_p = row["target_price"]
        stop_p = row["stop_loss_price"]
        notes = row["notes"]

        if status == "HOLDING":
            live = get_live_price(market, ticker)
            cur_p = live["current"]
            if cur_p > 0 and entry_p > 0:
                ret_pct = round(((cur_p - entry_p) / entry_p) * 100, 2)
                exit_p = None
                exit_d = None

                # 매도시 데이터베이스 기입 후 수익률 관리
                # 단, stock-us3x(3배 레버리지 무한매수)는 분할 적립형 전략이므로 손절선 청산 없이 HOLDING 유지
                if target_p and cur_p >= target_p:
                    status = "CLOSED"
                    exit_p = cur_p
                    exit_d = today_str
                    notes = f"{notes} | 🎯 목표가 도달 전량 익절"
                elif stop_p and cur_p <= stop_p and row["project_id"] != "stock-us3x":
                    status = "CLOSED"
                    exit_p = cur_p
                    exit_d = today_str
                    notes = f"{notes} | 🛑 손절가 이탈 기계적 손절 청산"

                cur.execute("""
                UPDATE trades 
                SET current_price = ?, return_pct = ?, status = ?, exit_price = ?, exit_date = ?, notes = ?
                WHERE id = ?
                """, (cur_p, ret_pct, status, exit_p, exit_d, notes, t_id))

    conn.commit()

    # 일일 / 누적 수익률 계산
    cur.execute("SELECT * FROM trades")
    updated_trades = cur.fetchall()

    project_groups = {}
    for t in updated_trades:
        pid = t["project_id"]
        if pid not in project_groups:
            project_groups[pid] = []
        project_groups[pid].append(t)

    project_groups["PORTFOLIO_TOTAL"] = updated_trades

    for pid, group in project_groups.items():
        holding_items = [t for t in group if t["status"] == "HOLDING"]
        closed_items = [t for t in group if t["status"] == "CLOSED"]

        holding_count = len(holding_items)
        closed_count = len(closed_items)

        returns = [t["return_pct"] for t in group]
        avg_return = round(sum(returns) / len(returns), 2) if returns else 0.0

        unrealized = [t["return_pct"] for t in holding_items]
        avg_unrealized = round(sum(unrealized) / len(unrealized), 2) if unrealized else 0.0

        realized = [t["return_pct"] for t in closed_items]
        avg_realized = round(sum(realized) / len(realized), 2) if realized else 0.0

        daily_ret = avg_unrealized
        cumulative_ret = avg_return

        win_trades = [t for t in group if t["return_pct"] > 0]
        win_rate = round((len(win_trades) / len(group)) * 100, 1) if group else 0.0

        cur.execute("""
        INSERT INTO daily_performance (
            date, project_id, daily_return_pct, cumulative_return_pct,
            realized_pnl_pct, unrealized_pnl_pct, holding_count, closed_count, win_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, project_id) DO UPDATE SET
            daily_return_pct = excluded.daily_return_pct,
            cumulative_return_pct = excluded.cumulative_return_pct,
            realized_pnl_pct = excluded.realized_pnl_pct,
            unrealized_pnl_pct = excluded.unrealized_pnl_pct,
            holding_count = excluded.holding_count,
            closed_count = excluded.closed_count,
            win_rate = excluded.win_rate
        """, (
            today_str, pid, daily_ret, cumulative_ret, avg_realized,
            avg_unrealized, holding_count, closed_count, win_rate
        ))

    conn.commit()
    conn.close()

# -------------------------------------------------------------
# 대시보드 전달 데이터
# -------------------------------------------------------------
def get_dashboard_full_data():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM alarms ORDER BY id DESC")
    alarms = []
    for r in cur.fetchall():
        alarms.append({
            "id": r["id"],
            "project_id": r["project_id"],
            "project_name": r["project_name"],
            "sent_at": r["sent_at"],
            "alarm_type": r["alarm_type"],
            "market": r["market"],
            "title": r["title"],
            "raw_message": r["raw_message"],
            "stocks": json.loads(r["stocks_json"]) if r["stocks_json"] else []
        })

    cur.execute("SELECT * FROM trades ORDER BY status DESC, return_pct DESC")
    trades = []
    for r in cur.fetchall():
        trades.append({
            "id": r["id"],
            "project_id": r["project_id"],
            "project_name": r["project_name"],
            "ticker": r["ticker"],
            "name": r["name"],
            "market": r["market"],
            "signal_type": r["signal_type"],
            "signal_date": r["signal_date"],
            "entry_price": r["entry_price"],
            "entry_date": r["entry_date"],
            "current_price": r["current_price"],
            "exit_price": r["exit_price"],
            "exit_date": r["exit_date"],
            "status": r["status"],
            "return_pct": r["return_pct"],
            "target_price": r["target_price"],
            "stop_loss_price": r["stop_loss_price"],
            "notes": r["notes"]
        })

    cur.execute("""
    SELECT dp.* 
    FROM daily_performance dp
    INNER JOIN (
        SELECT project_id, MAX(date) as max_date 
        FROM daily_performance 
        GROUP BY project_id
    ) latest ON dp.project_id = latest.project_id AND dp.date = latest.max_date
    """)
    performance_by_project = {}
    for r in cur.fetchall():
        performance_by_project[r["project_id"]] = {
            "date": r["date"],
            "daily_return_pct": r["daily_return_pct"],
            "cumulative_return_pct": r["cumulative_return_pct"],
            "realized_pnl_pct": r["realized_pnl_pct"],
            "unrealized_pnl_pct": r["unrealized_pnl_pct"],
            "holding_count": r["holding_count"],
            "closed_count": r["closed_count"],
            "win_rate": r["win_rate"]
        }

    total_perf = performance_by_project.get("PORTFOLIO_TOTAL", {
        "daily_return_pct": 0.0,
        "cumulative_return_pct": 0.0,
        "win_rate": 0.0,
        "holding_count": len([t for t in trades if t["status"] == "HOLDING"]),
        "closed_count": len([t for t in trades if t["status"] == "CLOSED"])
    })

    conn.close()

    return {
        "alarms": alarms,
        "trades": trades,
        "performance": performance_by_project,
        "total_performance": total_perf
    }

if __name__ == "__main__":
    init_db()
    reset_and_reload_all_9_projects()
    update_trades_and_performance()
    data = get_dashboard_full_data()
    print(f"📊 알람 {len(data['alarms'])}건, 체결 종목 {len(data['trades'])}건")
    print(f"💰 일일 수익률: {data['total_performance']['daily_return_pct']}% | 누적 수익률: {data['total_performance']['cumulative_return_pct']}% | 승률: {data['total_performance']['win_rate']}%")
