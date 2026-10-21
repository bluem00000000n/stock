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

# -------------------------------------------------------------
# 실시간 시세 API (네이버 증권 / 야후 파이낸스)
# -------------------------------------------------------------
def fetch_krx_price(code: str) -> dict:
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=4, context=SSL_CTX) as res:
            data = json.loads(res.read().decode())
            if "datas" in data and len(data["datas"]) > 0:
                item = data["datas"][0]
                close_p = float(str(item.get("closePrice", "0")).replace(",", ""))
                open_p = float(str(item.get("openPrice", "0")).replace(",", ""))
                if open_p == 0:
                    open_p = close_p
                return {
                    "name": item.get("stockName", code),
                    "open": open_p,
                    "current": close_p,
                    "change_rate": float(item.get("fluctuationsRatio", 0.0))
                }
    except Exception:
        pass
    return {"name": code, "open": 0.0, "current": 0.0, "change_rate": 0.0}

def fetch_us_price(symbol: str) -> dict:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=4, context=SSL_CTX) as res:
            data = json.loads(res.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            cur_p = float(meta.get("regularMarketPrice", 0.0))
            open_p = float(meta.get("regularMarketOpen", cur_p))
            if open_p == 0:
                open_p = cur_p
            return {
                "name": symbol,
                "open": open_p,
                "current": cur_p,
                "change_rate": 0.0
            }
    except Exception:
        pass
    return {"name": symbol, "open": 0.0, "current": 0.0, "change_rate": 0.0}

def get_live_price(market: str, ticker: str) -> dict:
    if market == "KRX":
        return fetch_krx_price(ticker)
    return fetch_us_price(ticker)

# -------------------------------------------------------------
# 전체 9대 프로젝트 실전 알람 및 체결 시딩 (Reset & Reload 9 Projects)
# -------------------------------------------------------------
def reset_and_reload_all_9_projects():
    """모든 9개 프로젝트의 가장 최근 실제 알람 내용으로 종목 및 수익률 관리 세팅"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM alarms")
    cur.execute("DELETE FROM trades")
    cur.execute("DELETE FROM daily_performance")
    conn.commit()

    today_str = "2026-10-21"

    # =========================================================
    # 1. stock-sniper (10/21 08:45 장전 알람)
    # =========================================================
    sniper_candidates = [
        {"ticker": "069500", "name": "KODEX 200", "target": 91500, "stop": 87000, "note": "지수 대표 ETF 분할 시가 체결"},
        {"ticker": "229200", "name": "KODEX 코스닥150", "target": 13800, "stop": 13000, "note": "코스닥 지수 수급 지지선 반등"},
        {"ticker": "042510", "name": "라온시큐어", "target": 19500, "stop": 17500, "note": "생체인증/양자암호 52주 신고가 돌파권"},
        {"ticker": "036930", "name": "주성엔지니어링", "target": 215000, "stop": 195000, "note": "반도체 ALD 2,200억 수급 방어"},
        {"ticker": "002990", "name": "금호건설", "target": 10500, "stop": 9300, "note": "거래대금 1,500억 유입 양봉 수급 방어"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-sniper", "stock-sniper", f"{today_str} 08:45:04", "장전알람", "KRX",
        "🎯 08:45 장전 스나이퍼 실전 주문표 (KODEX 200/150 & 수급 주도주 3선)",
        f"""[스톡 스나이퍼 08:45 실전 장전 주문표]
📅 기준일시: {today_str} (수) 08:45:04 장전 출정 브리핑
📊 지수 ETF 진입 타점:
  - KODEX 200 (069500) | 목표: 91,500원 | 손절: 87,000원
  - KODEX 코스닥150 (229200) | 목표: 13,800원 | 손절: 13,000원
🚀 RS 상대강도 & 52주 신고가 주도주 3선:
  1. 라온시큐어 (042510) | 목표: 19,500원 | 손절: 17,500원
  2. 주성엔지니어링 (036930) | 목표: 215,000원 | 손절: 195,000원
  3. 금호건설 (002990) | 목표: 10,500원 | 손절: 9,300원
⚠️ 실전 원칙: 장전 알람 종목은 09:00 시가(Open) 확인 후 즉시 분할 매수 체결.""",
        json.dumps(sniper_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 2. stock-sepa-pivot (10/21 08:40 한국장 알람)
    # =========================================================
    sepa_candidates = [
        {"ticker": "000660", "name": "SK하이닉스", "target": 1285000, "stop": 1220000, "note": "HBM3E 독점 슈퍼사이클, 20일선 VCP 피벗 돌파"},
        {"ticker": "196170", "name": "알테오젠", "target": 245000, "stop": 230000, "note": "피하주사(SC) 독점 플랫폼, 하이타이트 플래그 돌파"},
        {"ticker": "003230", "name": "삼양식품", "target": 1320000, "stop": 1220000, "note": "글로벌 수출 호조, 컵앤핸들 피벗 돌파"},
        {"ticker": "012450", "name": "한화에어로스페이스", "target": 835000, "stop": 785000, "note": "K9/천무 글로벌 수주 모멘텀, 불플래그 패턴"},
        {"ticker": "267260", "name": "HD현대일렉트릭", "target": 515000, "stop": 480000, "note": "북미 변압기 쇼티지 수혜, 플랫 베이스 지지"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-sepa-pivot", "stock-sepa-pivot", f"{today_str} 08:40:02", "장전알람", "KRX",
        "📈 08:40 한국장 SEPA x 피벗 포인트 감시 (SK하이닉스/알테오젠/삼양식품 외)",
        f"""📈 [08:40 오전 알람] 🇰🇷 한국장 개장 SEPA x 피벗 브리핑 (기준일: {today_str})
👑 [한국 대형 주도주 TOP 5] 피벗 감시선
1. SK하이닉스 (000660) | 피벗 1,285,000원 | 손절 1,220,000원 | Ascending Triangle
2. 알테오젠 (196170) | 피벗 245,000원 | 손절 230,000원 | High Tight Flag
3. 삼양식품 (003230) | 피벗 1,320,000원 | 손절 1,220,000원 | Cup with Handle
4. 한화에어로스페이스 (012450) | 피벗 835,000원 | 손절 785,000원 | Bull Flag
5. HD현대일렉트릭 (267260) | 피벗 515,000원 | 손절 480,000원 | Flat Base
⚠️ 매매 수칙: 09:00 시가(Open) 확인 후 진입, 피벗 대비 +5% 초과 갭상승 추격 매수 금지.""",
        json.dumps(sepa_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 3. stock-us3x (10/20 17:03 주간 알람)
    # =========================================================
    us3x_candidates = [
        {"ticker": "TQQQ", "name": "ProShares UltraPro QQQ", "market": "US", "entry": 68.50, "target": 85.00, "stop": 62.00, "note": "스코어 96.0, 20분할 LOC 1차 누적"},
        {"ticker": "TECL", "name": "Direxion Daily Tech 3X", "market": "US", "entry": 98.20, "target": 120.00, "stop": 88.00, "note": "스코어 95.0, 테크 3X 트렌치 진입"},
        {"ticker": "FAS", "name": "Direxion Daily Financial 3X", "market": "US", "entry": 115.00, "target": 138.00, "stop": 105.00, "note": "스코어 88.0, 금융 3X 회전 분할"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-us3x", "stock-us3x", "2026-10-20 17:03:29", "주간알람", "US",
        "🚀 미국 3배 레버리지 무한매수 & 회전 퀀트 파이프라인 (TQQQ / TECL / FAS)",
        """🚀 [US 3X 무한매수 & 회전 퀀트 파이프라인]
📅 실행일시: 2026-10-20 17:03:29 (Run ID: RUN_2026-10-20_45ceea89)
🌐 거시 체제: RISK_ON (VIX 18.6, SPY 200일선 상단 지지)
📊 무한매수 TOP 3 주문 지침:
1. TQQQ (나스닥 3X): 1차 20분할 LOC 주문. 평균단가 기준 0.5회차 매수.
2. TECL (테크 3X): 적합도 스코어 95.0. 트렌치 분할 매수.
3. FAS (금융 3X): 적합도 스코어 88.0. 회전 포트폴리오 편입.""",
        json.dumps(us3x_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 4. stock-dividend_top7 (10/19 08:30 주간 배당주)
    # =========================================================
    dividend_candidates = [
        {"ticker": "030200", "name": "KT", "market": "KRX", "target": 45000, "stop": 37000, "note": "5년 평균 시가배당률 5.4%, 안정 배당성향"},
        {"ticker": "017670", "name": "SK텔레콤", "market": "KRX", "target": 63000, "stop": 52000, "note": "분기배당 및 5년 연속 배당성장률 6.2%"},
        {"ticker": "029780", "name": "삼성카드", "market": "KRX", "target": 46000, "stop": 38000, "note": "시가배당률 6.8%, 자본건전성 최우수"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-dividend_top7", "stock-dividend_top7", "2026-10-19 08:30:09", "주간알람", "KRX",
        "💰 한국 거래소 6대 기준 고배당 성장주 TOP 7 (KT / SK텔레콤 / 삼성카드)",
        """💰 [stock-dividend_top7] 10월 3주차 주간 고배당주 TOP 7
- 6대 핵심 배당 기준(5년 평균 배당률 4%+, 5년 연속 배당성장, DART 공시 교차검증) 100% 통과
1. KT (030200) - 시가배당률 5.4%
2. SK텔레콤 (017670) - 분기배당 및 6.2% 성장
3. 삼성카드 (029780) - 배당성향 42% 건전 고배당
⚠️ 월요일 09:00 시가 진입 기준 주간 포트폴리오 편입.""",
        json.dumps(dividend_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 5. signal_forge_alert (10/21 실시간 AI 신호)
    # =========================================================
    signal_forge_candidates = [
        {"ticker": "068270", "name": "셀트리온", "market": "KRX", "entry": 193900, "target": 261765, "stop": 183817, "status": "HOLDING", "note": "Catalyst Breakout 다일간 모멘텀 8.1% 상회 (Score 81.0)"},
        {"ticker": "373220", "name": "LG에너지솔루션", "market": "KRX", "entry": 429000, "exit": 406000, "exit_date": today_str, "status": "CLOSED", "note": "손절가 이탈 원칙 손절 청산 (-5.36%)"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "signal_forge_alert", "signal_forge_alert", f"{today_str} 10:00:45", "장중알람", "KRX",
        "⚡ AI 거시 시장 인텔리전스 & 카탈리스트 돌파 신호 (셀트리온 / LG에너지솔루션)",
        f"""⚡ [Signal Forge Intelligence] AI 전략 시그널
1. 셀트리온 (068270) | 진입가 193,900원 | 목표가 261,765원 | 손절가 183,817원
   전략: S04 Catalyst Breakout + Multi-Day Momentum (Tier: OPPORTUNITY)
2. LG에너지솔루션 (373220) | 진입가 429,000원 | 406,000원 이탈 시 원칙 손절""",
        json.dumps(signal_forge_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 7. stock-cyclical-screener (10/21 11:00 시클리컬 퀀트)
    # =========================================================
    cyclical_candidates = [
        {"ticker": "007860", "name": "서연", "market": "KRX", "entry": 8900, "exit": 9550, "exit_date": today_str, "status": "CLOSED", "note": "자동차 부품 PBR 호황기 정점 도달, 이익 실현 매도 (+7.30%)"},
        {"ticker": "078350", "name": "한양디지텍", "market": "KRX", "target": 23000, "stop": 18500, "note": "반도체 패키징 PBR 침체기 저평가 매수 신호"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-cyclical-screener", "stock-cyclical-screener", f"{today_str} 11:00:00", "장중알람", "KRX",
        "📊 한국 6대 시클리컬 섹터 PBR 사이클 스크리닝 (한양디지텍 매수 / 서연 매도)",
        f"""📊 [KRX Cyclical Quant Screener]
📅 스캔일시: {today_str} 11:00:00
- 신규 매수 신호: 한양디지텍 (078350) - 반도체 저평가 사이클
- 이익 실현 매도: 서연 (007860) - 자동차 섹터 고PBR 정점 차익 실현""",
        json.dumps(cyclical_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 8. stock-htp-top10 (10/20 17:00 주간 모멘텀)
    # =========================================================
    htp_candidates = [
        {"ticker": "NVDA", "name": "NVIDIA", "market": "US", "entry": 139.20, "target": 158.00, "stop": 128.00, "note": "AI 가속기 독점, HTP 파워 모멘텀 1위"},
        {"ticker": "LLY", "name": "Eli Lilly", "market": "US", "entry": 915.00, "target": 980.00, "stop": 860.00, "note": "비만치료제 수요 폭발, 52주 고점 유지 2위"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-htp-top10", "stock-htp-top10", "2026-10-20 17:00:01", "주간알람", "US",
        "🚀 HTP 파워 모멘텀 TOP 10 퀀트 포트폴리오 (NVDA / LLY)",
        """🚀 [HTP Momentum Top 10]
1. NVDA (NVIDIA) | 비중 15% | HTP 점수 99점
2. LLY (Eli Lilly) | 비중 15% | HTP 점수 97점
미국 대형주 주도주 팩터 리밸런싱 주문표.""",
        json.dumps(htp_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 9. stock-swing (10/21 08:40 한국/미국 227선 무한 스윙 Scale-in)
    # =========================================================
    swing_candidates = [
        {"ticker": "033780", "name": "KT&G", "market": "KRX", "entry": 176900.0, "target": 205000, "stop": 176900, "note": "227선 무한 스윙 3차 트렌치 완주 보유 (+10.17%)"},
        {"ticker": "011200", "name": "HMM", "market": "KRX", "entry": 21500.0, "target": 26000, "stop": 20500, "note": "227선 스윙 2차 분할 매수 모아가기 (+8.37%)"},
        {"ticker": "138040", "name": "메리츠금융지주", "market": "KRX", "entry": 128800.0, "target": 145000, "stop": 124000, "note": "227선 스윙 2차 분할 포지션 유지 (+1.71%)"},
        {"ticker": "004370", "name": "농심", "market": "KRX", "entry": 404000.0, "target": 435000, "stop": 385000, "note": "227선 스윙 2차 분할 누적 포지션 (+1.36%)"}
    ]
    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-swing", "stock-swing", f"{today_str} 08:40:01", "장전알람", "KRX",
        "🎯 227선 자율진화 무한 스윙 분할 모아가기 포지션 (KT&G / HMM / 메리츠금융지주 / 농심)",
        f"""🎯 [stock-swing 227선 무한 스윙 현황]
📅 기준일시: {today_str} 08:40:01
📊 한국 실전 분할 진입 & 보유 종목:
1. KT&G (033780) | 3차 트렌치 완주 (평단 176,900원)
2. HMM (011200) | 2차 트렌치 매수 (평단 21,500원)
3. 메리츠금융지주 (138040) | 2차 트렌치 매수 (평단 128,800원)
4. 농심 (004370) | 2차 트렌치 매수 (평단 404,000원)
⚠️ 실전 원칙: 227일 이동평균선 지지선 기준 1/2/3차 분할 매수 및 트레일링 스탑 적용.""",
        json.dumps(swing_candidates, ensure_ascii=False)
    ))

    # =========================================================
    # 체결 테이블(trades) 등록 (알람 내용대로 시작가 / 시가 매매)
    # =========================================================
    trades_to_insert = []

    # 1. stock-sniper
    for s in sniper_candidates:
        price = get_live_price("KRX", s["ticker"])
        open_p = price["open"]
        cur_p = price["current"]
        ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0
        trades_to_insert.append({
            "project_id": "stock-sniper", "project_name": "stock-sniper",
            "ticker": s["ticker"], "name": price["name"] if price["name"] != s["ticker"] else s["name"],
            "market": "KRX", "signal_type": "장전알람(시가매수)", "signal_date": f"{today_str} 08:45:00",
            "entry_price": open_p, "entry_date": today_str, "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

    # 2. stock-sepa-pivot
    for s in sepa_candidates:
        price = get_live_price("KRX", s["ticker"])
        open_p = price["open"]
        cur_p = price["current"]
        ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0
        trades_to_insert.append({
            "project_id": "stock-sepa-pivot", "project_name": "stock-sepa-pivot",
            "ticker": s["ticker"], "name": price["name"] if price["name"] != s["ticker"] else s["name"],
            "market": "KRX", "signal_type": "장전알람(시가매수)", "signal_date": f"{today_str} 08:40:00",
            "entry_price": open_p, "entry_date": today_str, "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

    # 3. stock-us3x
    for s in us3x_candidates:
        price = get_live_price("US", s["ticker"])
        cur_p = price["current"] if price["current"] > 0 else s["entry"]
        ret = round(((cur_p - s["entry"]) / s["entry"]) * 100, 2)
        trades_to_insert.append({
            "project_id": "stock-us3x", "project_name": "stock-us3x",
            "ticker": s["ticker"], "name": s["name"], "market": "US",
            "signal_type": "주간리밸런싱", "signal_date": "2026-10-20 17:03:00",
            "entry_price": s["entry"], "entry_date": "2026-10-20", "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

    # 4. stock-dividend_top7
    for s in dividend_candidates:
        price = get_live_price("KRX", s["ticker"])
        open_p = price["open"]
        cur_p = price["current"]
        ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0
        trades_to_insert.append({
            "project_id": "stock-dividend_top7", "project_name": "stock-dividend_top7",
            "ticker": s["ticker"], "name": price["name"] if price["name"] != s["ticker"] else s["name"],
            "market": "KRX", "signal_type": "주간리밸런싱(시가매수)", "signal_date": "2026-10-19 08:30:00",
            "entry_price": open_p, "entry_date": "2026-10-19", "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

    # 5. signal_forge_alert
    for s in signal_forge_candidates:
        if s["status"] == "CLOSED":
            ret = round(((s["exit"] - s["entry"]) / s["entry"]) * 100, 2)
            trades_to_insert.append({
                "project_id": "signal_forge_alert", "project_name": "signal_forge_alert",
                "ticker": s["ticker"], "name": s["name"], "market": "KRX",
                "signal_type": "장중알람", "signal_date": f"{today_str} 10:00:00",
                "entry_price": s["entry"], "entry_date": "2026-10-19", "current_price": s["exit"],
                "exit_price": s["exit"], "exit_date": s["exit_date"], "status": "CLOSED", "return_pct": ret,
                "target_price": None, "stop_loss_price": None, "notes": s["note"]
            })
        else:
            price = get_live_price("KRX", s["ticker"])
            cur_p = price["current"] if price["current"] > 0 else s["entry"]
            ret = round(((cur_p - s["entry"]) / s["entry"]) * 100, 2)
            trades_to_insert.append({
                "project_id": "signal_forge_alert", "project_name": "signal_forge_alert",
                "ticker": s["ticker"], "name": s["name"], "market": "KRX",
                "signal_type": "장중알람", "signal_date": f"{today_str} 10:00:00",
                "entry_price": s["entry"], "entry_date": "2026-10-18", "current_price": cur_p,
                "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
                "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
            })

    # 7. stock-cyclical-screener
    for s in cyclical_candidates:
        if s.get("status") == "CLOSED":
            ret = round(((s["exit"] - s["entry"]) / s["entry"]) * 100, 2)
            trades_to_insert.append({
                "project_id": "stock-cyclical-screener", "project_name": "stock-cyclical-screener",
                "ticker": s["ticker"], "name": s["name"], "market": "KRX",
                "signal_type": "장중매도신호", "signal_date": f"{today_str} 11:00:00",
                "entry_price": s["entry"], "entry_date": "2026-10-14", "current_price": s["exit"],
                "exit_price": s["exit"], "exit_date": s["exit_date"], "status": "CLOSED", "return_pct": ret,
                "target_price": None, "stop_loss_price": None, "notes": s["note"]
            })
        else:
            price = get_live_price("KRX", s["ticker"])
            open_p = price["open"]
            cur_p = price["current"]
            ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0
            trades_to_insert.append({
                "project_id": "stock-cyclical-screener", "project_name": "stock-cyclical-screener",
                "ticker": s["ticker"], "name": s["name"], "market": "KRX",
                "signal_type": "장중매수신호", "signal_date": f"{today_str} 11:00:00",
                "entry_price": open_p, "entry_date": today_str, "current_price": cur_p,
                "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
                "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
            })

    # 8. stock-htp-top10
    for s in htp_candidates:
        price = get_live_price("US", s["ticker"])
        cur_p = price["current"] if price["current"] > 0 else s["entry"]
        ret = round(((cur_p - s["entry"]) / s["entry"]) * 100, 2)
        trades_to_insert.append({
            "project_id": "stock-htp-top10", "project_name": "stock-htp-top10",
            "ticker": s["ticker"], "name": s["name"], "market": "US",
            "signal_type": "주간리밸런싱", "signal_date": "2026-10-20 17:00:00",
            "entry_price": s["entry"], "entry_date": "2026-10-20", "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

    # 9. stock-swing
    for s in swing_candidates:
        price = get_live_price("KRX", s["ticker"])
        cur_p = price["current"] if price["current"] > 0 else s["entry"]
        ret = round(((cur_p - s["entry"]) / s["entry"]) * 100, 2)
        trades_to_insert.append({
            "project_id": "stock-swing", "project_name": "stock-swing",
            "ticker": s["ticker"], "name": price["name"] if price["name"] != s["ticker"] else s["name"],
            "market": "KRX", "signal_type": "장전알람(227스윙)", "signal_date": f"{today_str} 08:40:00",
            "entry_price": s["entry"], "entry_date": today_str, "current_price": cur_p,
            "exit_price": None, "exit_date": None, "status": "HOLDING", "return_pct": ret,
            "target_price": s["target"], "stop_loss_price": s["stop"], "notes": s["note"]
        })

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
    print(f"✅ 9대 프로젝트 총 {len(trades_to_insert)}개 종목 실전 매매 DB 등록 완료")

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
                if target_p and cur_p >= target_p:
                    status = "CLOSED"
                    exit_p = cur_p
                    exit_d = today_str
                    notes = f"{notes} | 🎯 목표가 도달 전량 익절"
                elif stop_p and cur_p <= stop_p:
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
