#!/usr/bin/env python3
"""
Stock Master Database - 중앙 통합 데이터베이스 허브 (Hub & Spoke ETL)
9개 하위 프로젝트의 로컬 데이터(SQLite, JSON, CSV, Log)를 수집하여
중앙 stock_master.db 로 통합 저장 및 관리합니다.
"""

import os
import sys
import json
import sqlite3
import glob
from datetime import datetime

BASE_DIR = "/Users/tothemoon"
SUPERVISOR_DIR = os.path.join(BASE_DIR, "stock-supervisor")
DATA_DIR = os.path.join(SUPERVISOR_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

MASTER_DB_PATH = os.path.join(DATA_DIR, "stock_master.db")
LEGACY_DB_PATH = os.path.join(DATA_DIR, "trading_records.db")

PROJECT_REGISTRY = [
    {
        "id": "stock-sniper",
        "name": "Stock Sniper",
        "market": "KOR",
        "schedule": "Daily 08:45",
        "source_type": "log",
        "source_path": os.path.join(BASE_DIR, "stock-sniper/logs/execution.log")
    },
    {
        "id": "stock-sepa-pivot",
        "name": "SEPA x Pivot Screener",
        "market": "KOR / USA",
        "schedule": "Daily 08:40 & 21:30",
        "source_type": "json",
        "source_path": os.path.join(BASE_DIR, "stock-sepa-pivot/fgrs_candidates.json")
    },
    {
        "id": "stock-swing",
        "name": "Swing 227 Scale-in",
        "market": "KOR / USA",
        "schedule": "Daily 08:40 & 21:30",
        "source_type": "sqlite",
        "source_path": os.path.join(BASE_DIR, "stock-swing/data/swing_system.db")
    },
    {
        "id": "stock-htp-top10",
        "name": "HTP Momentum TOP 10",
        "market": "USA",
        "schedule": "Daily 22:30",
        "source_type": "sqlite",
        "source_path": os.path.join(BASE_DIR, "stock-htp-top10/portfolio_tracker.db")
    },
    {
        "id": "stock-us3x",
        "name": "US 3X Leverage Infinite",
        "market": "USA",
        "schedule": "Daily 22:00",
        "source_type": "sqlite",
        "source_path": os.path.join(BASE_DIR, "stock-us3x/database/us3x_trading.db")
    },
    {
        "id": "stock-dividend_top7",
        "name": "Weekly Dividend TOP 7",
        "market": "KOR",
        "schedule": "Weekly Mon 08:30",
        "source_type": "log",
        "source_path": os.path.join(BASE_DIR, "stock-dividend_top7/scanner.log")
    },
    {
        "id": "signal_forge_alert",
        "name": "Signal Forge AI Macro",
        "market": "GLOBAL",
        "schedule": "Continuous Daemon",
        "source_type": "log",
        "source_path": os.path.join(BASE_DIR, "signal_forge_alert/logs")
    },
    {
        "id": "stock-cyclical-screener",
        "name": "Cyclical PBR Screener",
        "market": "KOR",
        "schedule": "Daily 08:00",
        "source_type": "json",
        "source_path": os.path.join(BASE_DIR, "stock-cyclical-screener/data/alerts_history.json")
    }
]

def get_master_db():
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_master_db():
    """마스터 DB 스키마 초기화 및 메타데이터 적재"""
    conn = get_master_db()
    cur = conn.cursor()

    # 1. 프로젝트 메타정보 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        schedule TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_path TEXT NOT NULL,
        last_synced_at TEXT,
        signals_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ACTIVE'
    );
    """)

    # 2. 하위 프로젝트 시그널 통합 아카이브
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subproject_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        name TEXT NOT NULL,
        market TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        signal_date TEXT NOT NULL,
        price REAL,
        target_price REAL,
        stop_loss_price REAL,
        raw_json TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(project_id, ticker, signal_date, signal_type)
    );
    """)

    # 3. 실전 체결 및 포트폴리오 관리 테이블 (trades)
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
        notes TEXT,
        updated_at TEXT
    );
    """)

    # 4. 일별/누적 수익률 테이블
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

    # 5. 알람 로그 테이블
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

    # 프로젝트 메타데이터 등록 / 갱신
    for p in PROJECT_REGISTRY:
        cur.execute("""
        INSERT INTO projects (id, name, market, schedule, source_type, source_path)
        VALUES (:id, :name, :market, :schedule, :source_type, :source_path)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            market = excluded.market,
            schedule = excluded.schedule,
            source_type = excluded.source_type,
            source_path = excluded.source_path;
        """, p)

    conn.commit()
    conn.close()

def migrate_legacy_trading_records():
    """기존 trading_records.db 데이터를 stock_master.db로 무손실 1회성 이관"""
    if not os.path.exists(LEGACY_DB_PATH):
        return

    dst = get_master_db()
    cur = dst.cursor()
    cur.execute("SELECT COUNT(*) FROM trades")
    if cur.fetchone()[0] > 0:
        # 이미 데이터가 마스터 DB에 적재되어 있으면 중복 마이그레이션 방지
        dst.close()
        return

    print("🔄 Migrating existing trading_records.db -> stock_master.db ...")
    src = sqlite3.connect(LEGACY_DB_PATH)
    src.row_factory = sqlite3.Row

    # 1. alarms 이관
    try:
        alarms = src.execute("SELECT * FROM alarms").fetchall()
        for a in alarms:
            d = dict(a)
            dst.execute("""
            INSERT OR IGNORE INTO alarms (id, project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
            VALUES (:id, :project_id, :project_name, :sent_at, :alarm_type, :market, :title, :raw_message, :stocks_json)
            """, d)
    except Exception as e:
        print(f"Alarms migration notice: {e}")

    # 2. trades 이관
    try:
        trades = src.execute("SELECT * FROM trades").fetchall()
        for t in trades:
            d = dict(t)
            if "updated_at" not in d or not d["updated_at"]:
                d["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            dst.execute("""
            INSERT OR REPLACE INTO trades (id, project_id, project_name, ticker, name, market, signal_type,
                                           signal_date, entry_price, entry_date, current_price, exit_price,
                                           exit_date, status, return_pct, target_price, stop_loss_price, notes, updated_at)
            VALUES (:id, :project_id, :project_name, :ticker, :name, :market, :signal_type,
                    :signal_date, :entry_price, :entry_date, :current_price, :exit_price,
                    :exit_date, :status, :return_pct, :target_price, :stop_loss_price, :notes, :updated_at)
            """, d)
    except Exception as e:
        print(f"Trades migration notice: {e}")

    # 3. daily_performance 이관
    try:
        perf = src.execute("SELECT * FROM daily_performance").fetchall()
        for p in perf:
            d = dict(p)
            dst.execute("""
            INSERT OR REPLACE INTO daily_performance (date, project_id, daily_return_pct, cumulative_return_pct,
                                                     realized_pnl_pct, unrealized_pnl_pct, holding_count, closed_count, win_rate)
            VALUES (:date, :project_id, :daily_return_pct, :cumulative_return_pct,
                    :realized_pnl_pct, :unrealized_pnl_pct, :holding_count, :closed_count, :win_rate)
            """, d)
    except Exception as e:
        print(f"Daily performance migration notice: {e}")

    dst.commit()
    src.close()
    dst.close()
    print("✅ Migration completed successfully.")

# ==========================================
# 개별 프로젝트 수집기 (Adapters)
# ==========================================

def sync_stock_swing(conn):
    """stock-swing: swing_system.db 에서 signals 및 positions 수집"""
    db_path = "/Users/tothemoon/stock-swing/data/swing_system.db"
    if not os.path.exists(db_path):
        return 0
    sub_conn = sqlite3.connect(db_path)
    sub_conn.row_factory = sqlite3.Row
    count = 0
    try:
        signals = sub_conn.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 50").fetchall()
        for s in signals:
            market = "USA" if s["market"].upper() == "US" else "KOR"
            ticker = s["ticker"].replace(".KS", "").replace(".KQ", "")
            raw_json = json.dumps(dict(s), ensure_ascii=False)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
            INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                price = excluded.price,
                stop_loss_price = excluded.stop_loss_price,
                raw_json = excluded.raw_json;
            """, ("stock-swing", ticker, s["name"], market, s["signal_type"], s["signal_date"], s["price"], None, s["stop_price"], raw_json, now))
            count += 1
    except Exception as e:
        print(f"[stock-swing] sync error: {e}")
    finally:
        sub_conn.close()
    return count

def sync_stock_htp_top10(conn):
    """stock-htp-top10: portfolio_tracker.db 에서 quant_recommendations 수집"""
    db_path = "/Users/tothemoon/stock-htp-top10/portfolio_tracker.db"
    if not os.path.exists(db_path):
        return 0
    sub_conn = sqlite3.connect(db_path)
    sub_conn.row_factory = sqlite3.Row
    count = 0
    try:
        recs = sub_conn.execute("SELECT * FROM quant_recommendations ORDER BY id DESC LIMIT 50").fetchall()
        for r in recs:
            raw_json = json.dumps(dict(r), ensure_ascii=False)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sig_type = f"HTP_{r['model_type']}_R{r['rank']}"
            conn.execute("""
            INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                price = excluded.price,
                raw_json = excluded.raw_json;
            """, ("stock-htp-top10", r["ticker"], r["name"], "USA", sig_type, r["as_of_date"], r["curr_price"], None, None, raw_json, now))
            count += 1
    except Exception as e:
        print(f"[stock-htp-top10] sync error: {e}")
    finally:
        sub_conn.close()
    return count

def sync_stock_us3x(conn):
    """stock-us3x: us3x_trading.db 에서 infinite_top3_records 수집"""
    db_path = "/Users/tothemoon/stock-us3x/database/us3x_trading.db"
    if not os.path.exists(db_path):
        return 0
    sub_conn = sqlite3.connect(db_path)
    sub_conn.row_factory = sqlite3.Row
    count = 0
    try:
        records = sub_conn.execute("SELECT * FROM infinite_top3_records ORDER BY created_at DESC LIMIT 50").fetchall()
        for r in records:
            raw_json = json.dumps(dict(r), ensure_ascii=False)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sig_date = r["created_at"].split()[0]
            sig_type = f"US3X_RANK_{r['rank']}"
            conn.execute("""
            INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                raw_json = excluded.raw_json;
            """, ("stock-us3x", r["ticker"], f"{r['ticker']} (3X)", "USA", sig_type, sig_date, None, None, None, raw_json, now))
            count += 1
    except Exception as e:
        print(f"[stock-us3x] sync error: {e}")
    finally:
        sub_conn.close()
    return count

def sync_stock_sepa_pivot(conn):
    """stock-sepa-pivot: fgrs_candidates.json 수집"""
    json_path = "/Users/tothemoon/stock-sepa-pivot/fgrs_candidates.json"
    if not os.path.exists(json_path):
        return 0
    count = 0
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for c in candidates:
            market = "USA" if c.get("market", "KR").upper() == "US" else "KOR"
            ticker = c.get("code") or c.get("ticker", "")
            raw_json = json.dumps(c, ensure_ascii=False)
            conn.execute("""
            INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                price = excluded.price,
                target_price = excluded.target_price,
                stop_loss_price = excluded.stop_loss_price,
                raw_json = excluded.raw_json;
            """, ("stock-sepa-pivot", ticker, c.get("name", ticker), market, "SEPA_PIVOT_CANDIDATE", today, c.get("current_price"), c.get("pivot"), c.get("stop"), raw_json, now))
            count += 1
    except Exception as e:
        print(f"[stock-sepa-pivot] sync error: {e}")
    return count

def sync_kbit_bot(conn):
    """kbit-bot: posted_history.json 수집"""
    json_path = "/Users/tothemoon/kbit-bot/posted_history.json"
    if not os.path.exists(json_path):
        return 0
    count = 0
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for ticker, val in data.items():
            name = val.get("name", ticker)
            sig_date = val.get("date", datetime.now().strftime("%Y-%m-%d"))
            raw_json = json.dumps(val, ensure_ascii=False)
            conn.execute("""
            INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                raw_json = excluded.raw_json;
            """, ("kbit-bot", ticker, name, "KOR", "FEATURE_HOT_STOCK", sig_date, None, None, None, raw_json, now))
            count += 1
    except Exception as e:
        print(f"[kbit-bot] sync error: {e}")
    return count

def sync_stock_cyclical(conn):
    """stock-cyclical-screener: alerts_history.json 및 data/state.json 수집"""
    alerts_path = "/Users/tothemoon/stock-cyclical-screener/data/alerts_history.json"
    if not os.path.exists(alerts_path):
        return 0
    count = 0
    try:
        with open(alerts_path, "r", encoding="utf-8") as f:
            alerts = json.load(f)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for a in alerts:
            sig_date = a.get("date", datetime.now().strftime("%Y-%m-%d"))
            for stock_name in a.get("new_sells", []):
                raw_json = json.dumps({"action": "SELL", "event": a}, ensure_ascii=False)
                conn.execute("""
                INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                    raw_json = excluded.raw_json;
                """, ("stock-cyclical-screener", stock_name, stock_name, "KOR", "CYCLICAL_SELL", sig_date, None, None, None, raw_json, now))
                count += 1
            for stock_name in a.get("new_buys", []):
                raw_json = json.dumps({"action": "BUY", "event": a}, ensure_ascii=False)
                conn.execute("""
                INSERT INTO subproject_signals (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, ticker, signal_date, signal_type) DO UPDATE SET
                    raw_json = excluded.raw_json;
                """, ("stock-cyclical-screener", stock_name, stock_name, "KOR", "CYCLICAL_BUY", sig_date, None, None, None, raw_json, now))
                count += 1
    except Exception as e:
        print(f"[stock-cyclical-screener] sync error: {e}")
    return count

def sync_all_subprojects():
    """모든 하위 프로젝트를 일괄 스캔하여 stock_master.db로 동기화"""
    print("=" * 60)
    print("🚀 Running Central Master DB Sync Engine (Hub & Spoke)")
    print("=" * 60)
    
    init_master_db()
    migrate_legacy_trading_records()

    conn = get_master_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sync_map = {
        "stock-swing": sync_stock_swing,
        "stock-htp-top10": sync_stock_htp_top10,
        "stock-us3x": sync_stock_us3x,
        "stock-sepa-pivot": sync_stock_sepa_pivot,
        "stock-cyclical-screener": sync_stock_cyclical,
    }

    for p_id, func in sync_map.items():
        cnt = func(conn)
        # 프로젝트 테이블에 동기화 상태 갱신
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM subproject_signals WHERE project_id = ?", (p_id,))
        total_signals = cur.fetchone()[0]
        cur.execute("""
        UPDATE projects SET last_synced_at = ?, signals_count = ? WHERE id = ?
        """, (now_str, total_signals, p_id))
        print(f"  ✓ [{p_id}] Synced {cnt} new/updated signals (Total: {total_signals})")

    # 나머지 프로젝트(stock-sniper, stock-dividend_top7, signal_forge_alert) 상태 갱신
    other_projects = ["stock-sniper", "stock-dividend_top7", "signal_forge_alert"]
    for p_id in other_projects:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM subproject_signals WHERE project_id = ?", (p_id,))
        total_signals = cur.fetchone()[0]
        cur.execute("""
        UPDATE projects SET last_synced_at = ?, signals_count = ? WHERE id = ?
        """, (now_str, total_signals, p_id))

    conn.commit()

    # 요약 통계 출력
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM projects")
    p_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM subproject_signals")
    s_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trades")
    t_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM alarms")
    a_cnt = cur.fetchone()[0]

    print("-" * 60)
    print(f"📊 stock_master.db Stats:")
    print(f"  • Registered Projects: {p_cnt}")
    print(f"  • Subproject Signals Archive: {s_cnt}")
    print(f"  • Managed Live Trades: {t_cnt}")
    print(f"  • Alarm Records: {a_cnt}")
    print(f"  • Master DB Path: {MASTER_DB_PATH}")
    print("=" * 60)
    conn.close()

if __name__ == "__main__":
    sync_all_subprojects()
