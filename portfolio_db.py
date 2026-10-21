#!/usr/bin/env python3
"""
Stock Trading Desk - 실전 수익률 및 포트폴리오 데이터베이스 엔진
- 기준일: 2026-10-21 (오늘 알람부터 실전 종목-수익률 관리 시작)
- 장전알람: 당일 09:00 시가(Open Price) 자동 매수 체결
- 장중알람: 알람 시점 시가/체결가 매수 체결
- 매도시: 목표가/손절가 도달 시 DB에 매도가/매도일 기입 및 실현손익 확정
- 일일 수익률(Daily Return) 및 누적 수익률(Cumulative Return) 자동 연산
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
DB_PATH = os.path.join(DATA_DIR, "trading_records.db")

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
        entry_price REAL NOT NULL,   -- 장전알람: 09:00 시가
        entry_date TEXT NOT NULL,
        current_price REAL NOT NULL,
        exit_price REAL,             -- 매도 체결가
        exit_date TEXT,              -- 매도일자
        status TEXT NOT NULL,        -- HOLDING (보유중) / CLOSED (매도완료)
        return_pct REAL NOT NULL,    -- 수익률 (%)
        target_price REAL,           -- 목표가
        stop_loss_price REAL,        -- 손절가
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
# 2026-10-21 오늘 알람부터 실전 대상 종목 세팅 (Reset & Start Today)
# -------------------------------------------------------------
def reset_and_start_from_today():
    """오늘(2026-10-21) 알람부터 대상 종목 및 수익률 관리 시작"""
    conn = get_db()
    cur = conn.cursor()

    # 기존 내역 초기화하고 오늘 날짜부터 새로 관리
    cur.execute("DELETE FROM alarms")
    cur.execute("DELETE FROM trades")
    cur.execute("DELETE FROM daily_performance")
    conn.commit()

    today_str = "2026-10-21"
    now_full = "2026-10-21 08:45:00"

    print(f"🚀 {today_str} 오늘 알람 기준 실전 대상 종목 수집 및 시가 체결 시작...")

    # 1. 오늘 08:40 SEPA x 피벗 감시 알람 종목
    sepa_candidates = [
        {"ticker": "000660", "name": "SK하이닉스", "target_pivot": 1285000, "stop": 1220000, "note": "HBM3E 독점 슈퍼사이클, 20일선 VCP 피벗 돌파"},
        {"ticker": "196170", "name": "알테오젠", "target_pivot": 245000, "stop": 230000, "note": "피하주사(SC) 독점 플랫폼, 하이타이트 플래그 돌파"},
        {"ticker": "003230", "name": "삼양식품", "target_pivot": 1320000, "stop": 1220000, "note": "글로벌 수출 호조, 컵앤핸들 피벗 돌파"},
        {"ticker": "012450", "name": "한화에어로스페이스", "target_pivot": 835000, "stop": 785000, "note": "K9/천무 글로벌 수주 모멘텀, 불플래그 패턴"},
        {"ticker": "267260", "name": "HD현대일렉트릭", "target_pivot": 515000, "stop": 480000, "note": "북미 변압기 쇼티지 수혜, 플랫 베이스 지지"}
    ]

    sepa_msg = f"""📈 [08:40 오전 알람] 🇰🇷 한국장 개장 SEPA x 피벗 브리핑 (기준일: {today_str})
👑 [한국 대형 주도주 TOP 5] 피벗 감시선
1. SK하이닉스 (000660) | 피벗 1,285,000원 | 손절 1,220,000원 | Ascending Triangle
2. 알테오젠 (196170) | 피벗 245,000원 | 손절 230,000원 | High Tight Flag
3. 삼양식품 (003230) | 피벗 1,320,000원 | 손절 1,220,000원 | Cup with Handle
4. 한화에어로스페이스 (012450) | 피벗 835,000원 | 손절 785,000원 | Bull Flag
5. HD현대일렉트릭 (267260) | 피벗 515,000원 | 손절 480,000원 | Flat Base
⚠️ 매매 수칙: 09:00 시가(Open) 확인 후 진입, 피벗 대비 +5% 초과 갭상승 추격 매수 금지."""

    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-sepa-pivot", "Stock SEPA Pivot", f"{today_str} 08:40:02", "장전알람", "KRX",
        "📈 08:40 한국장 SEPA x 피벗 포인트 감시 (SK하이닉스/알테오젠/삼양식품 외)",
        sepa_msg, json.dumps(sepa_candidates, ensure_ascii=False)
    ))

    # 2. 오늘 08:45 스톡 스나이퍼 실전 주문표 종목
    sniper_candidates = [
        {"ticker": "069500", "name": "KODEX 200", "target": 91500, "stop": 87000, "note": "지수 대표 ETF 시가 분할 매수 타점"},
        {"ticker": "229200", "name": "KODEX 코스닥150", "target": 13800, "stop": 13000, "note": "코스닥150 지수 수급 지지선 반등 노림"},
        {"ticker": "042510", "name": "라온시큐어", "target": 19500, "stop": 17500, "note": "생체인증/양자암호 모멘텀, 52주 신고가권"},
        {"ticker": "036930", "name": "주성엔지니어링", "target": 215000, "stop": 195000, "note": "반도체 ALD 대규모 수급 방어, 20일선 지지"},
        {"ticker": "002990", "name": "금호건설", "target": 10500, "stop": 9300, "note": "약세장 속 거래대금 유입 및 양봉 수급 방어"}
    ]

    sniper_msg = f"""🎯 [스톡 스나이퍼 08:45 실전 주문표]
📅 기준일시: {today_str} (수) 08:45:04 장전 출정 브리핑
📊 지수 ETF 진입 타점:
  - KODEX 200 (069500) | 목표: 91,500원 | 손절: 87,000원
  - KODEX 코스닥150 (229200) | 목표: 13,800원 | 손절: 13,000원
🚀 RS 상대강도 & 52주 신고가 주도주 3선:
  1. 라온시큐어 (042510) | 목표: 19,500원 | 손절: 17,500원
  2. 주성엔지니어링 (036930) | 목표: 215,000원 | 손절: 195,000원
  3. 금호건설 (002990) | 목표: 10,500원 | 손절: 9,300원
⚠️ 실전 원칙: 장전 알람 종목은 09:00 시가(Open) 확인 후 즉시 분할 매수 체결."""

    cur.execute("""
    INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "stock-sniper", "Stock Sniper", f"{today_str} 08:45:04", "장전알람", "KRX",
        "🎯 08:45 장전 스나이퍼 실전 주문표 (KODEX 200/150 & 수급 주도주 3선)",
        sniper_msg, json.dumps(sniper_candidates, ensure_ascii=False)
    ))

    # 3. 각 알람 종목을 "장전알람 > 당일 시가(09:00 Open)" 기준으로 매수 체결 등록
    all_today_picks = []

    for s in sepa_candidates:
        price_info = get_live_price("KRX", s["ticker"])
        open_p = price_info["open"]
        cur_p = price_info["current"]
        ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0

        all_today_picks.append({
            "project_id": "stock-sepa-pivot",
            "project_name": "Stock SEPA Pivot",
            "ticker": s["ticker"],
            "name": price_info["name"] if price_info["name"] != s["ticker"] else s["name"],
            "market": "KRX",
            "signal_type": "장전알람(시가매수)",
            "signal_date": f"{today_str} 08:40:00",
            "entry_price": open_p,
            "entry_date": today_str,
            "current_price": cur_p,
            "target_price": s["target_pivot"],
            "stop_loss_price": s["stop"],
            "status": "HOLDING",
            "return_pct": ret,
            "notes": s["note"]
        })

    for s in sniper_candidates:
        price_info = get_live_price("KRX", s["ticker"])
        open_p = price_info["open"]
        cur_p = price_info["current"]
        ret = round(((cur_p - open_p) / open_p) * 100, 2) if open_p > 0 else 0.0

        all_today_picks.append({
            "project_id": "stock-sniper",
            "project_name": "Stock Sniper",
            "ticker": s["ticker"],
            "name": price_info["name"] if price_info["name"] != s["ticker"] else s["name"],
            "market": "KRX",
            "signal_type": "장전알람(시가매수)",
            "signal_date": f"{today_str} 08:45:00",
            "entry_price": open_p,
            "entry_date": today_str,
            "current_price": cur_p,
            "target_price": s["target"],
            "stop_loss_price": s["stop"],
            "status": "HOLDING",
            "return_pct": ret,
            "notes": s["note"]
        })

    # DB에 삽입
    for t in all_today_picks:
        cur.execute("""
        INSERT INTO trades (
            project_id, project_name, ticker, name, market, signal_type,
            signal_date, entry_price, entry_date, current_price, exit_price,
            exit_date, status, return_pct, target_price, stop_loss_price, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
        """, (
            t["project_id"], t["project_name"], t["ticker"], t["name"], t["market"],
            t["signal_type"], t["signal_date"], t["entry_price"], t["entry_date"],
            t["current_price"], t["status"], t["return_pct"], t["target_price"],
            t["stop_loss_price"], t["notes"]
        ))

    conn.commit()
    conn.close()
    print(f"✅ 오늘({today_str}) 알람 종목 총 {len(all_today_picks)}개 시가 매수 체결 등록 완료")

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

                # 매도시 데이터베이스 기입 후 수익률 관리 (목표가 익절 / 손절가 이탈)
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

        # 오늘 시작했으므로 일일 수익률 = 당일 체결분 평균 수익률
        daily_ret = avg_return
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
        "holding_count": len(trades),
        "closed_count": 0
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
    reset_and_start_from_today()
    update_trades_and_performance()
    data = get_dashboard_full_data()
    print(f"📊 당일 알람 {len(data['alarms'])}건, 오늘 체결 종목 {len(data['trades'])}건")
    print(f"💰 일일 수익률: {data['total_performance']['daily_return_pct']}% | 누적 수익률: {data['total_performance']['cumulative_return_pct']}% | 승률: {data['total_performance']['win_rate']}%")
