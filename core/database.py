#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/database.py
단일 중앙 데이터베이스(stock_master.db) 관리 모듈
"""

import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "stock_master.db"


def get_db_connection():
    """SQLite 데이터베이스 연결 반환 (ROW 팩토리 적용)"""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """필수 테이블 초기화 및 무결성 확인"""
    with get_db_connection() as conn:
        cur = conn.cursor()

        # 1. 원천 시그널 테이블
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
            )
        """)

        # 2. 통합 실전 포트폴리오 포지션 관리 테이블
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
            )
        """)

        # 3. 일별 성과 기록 테이블
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
            )
        """)

        # 4. 통합 알람 발송 로그 테이블
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
            )
        """)

        conn.commit()


def save_signals(signals: List[Dict[str, Any]]) -> int:
    """전략에서 추출된 시그널을 DB에 저장 (중복 무시)"""
    if not signals:
        return 0

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0

    with get_db_connection() as conn:
        cur = conn.cursor()
        for s in signals:
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO subproject_signals 
                    (project_id, ticker, name, market, signal_type, signal_date, price, target_price, stop_loss_price, raw_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.get("project_id", "unknown"),
                    s.get("ticker", ""),
                    s.get("name", s.get("ticker", "")),
                    s.get("market", "KRX"),
                    s.get("signal_type", "BUY"),
                    s.get("signal_date", datetime.now().strftime("%Y-%m-%d")),
                    s.get("price", 0.0),
                    s.get("target_price", 0.0),
                    s.get("stop_loss_price", 0.0),
                    json.dumps(s, ensure_ascii=False),
                    now_str
                ))
                inserted += 1
            except Exception as e:
                print(f"[db.save_signals] 오류: {e}")
        conn.commit()

    return inserted


def get_latest_signals(market: str = "KRX", limit: int = 50) -> List[Dict[str, Any]]:
    """가장 최근 날짜의 시그널 조회"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM subproject_signals 
            WHERE market = ? OR market = ?
            ORDER BY signal_date DESC, id DESC
            LIMIT ?
        """, (market, "KOR" if market == "KRX" else "USA", limit))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_active_holdings(market: Optional[str] = None) -> List[Dict[str, Any]]:
    """현재 보유(HOLDING) 중인 포지션 조회"""
    with get_db_connection() as conn:
        cur = conn.cursor()
        if market:
            cur.execute("""
                SELECT * FROM trades 
                WHERE status = 'HOLDING' AND (market = ? OR market = ?)
                ORDER BY entry_date ASC
            """, (market, "KOR" if market == "KRX" else "USA"))
        else:
            cur.execute("""
                SELECT * FROM trades 
                WHERE status = 'HOLDING'
                ORDER BY entry_date ASC
            """)
        return [dict(r) for r in cur.fetchall()]


def record_alarm(title: str, message: str, market: str, project_ids: List[str]):
    """발송된 알람을 DB에 아카이빙"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        for pid in project_ids:
            cur.execute("""
                INSERT INTO alarms (project_id, project_name, sent_at, alarm_type, market, title, raw_message, stocks_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pid, pid, now_str, "통합알람", market, title, message, "[]"))
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("✅ stock_master.db 초기화 완료")
