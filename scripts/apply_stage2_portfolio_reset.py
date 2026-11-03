#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

db_path = "data/stock_master.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

today_str = datetime.now().strftime("%Y-%m-%d")
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 1. 기존 KRX HOLDING 종목 삭제 (사용자 명령: '기존 포폴 삭제후', '초기화 후 다시')
cur.execute("DELETE FROM trades WHERE status = 'HOLDING' AND market = 'KRX'")
deleted_cnt = cur.rowcount
print(f"Deleted {deleted_cnt} old KRX HOLDING rows from trades.")

# 2. 신규 Stage 2 주도주 6종목 (대형 3 : 중소형 3, SEPA 2 : Sniper 2 : Swing 2)
new_positions = [
    {
        "project_id": "stock-sepa-pivot",
        "project_name": "SEPA x 피봇 돌파",
        "ticker": "028050",
        "name": "삼성E&A",
        "market": "KRX",
        "signal_type": "BUY [지정가 매수]",
        "entry_price": 61600.0,
        "current_price": 61600.0,
        "target_price": 67800.0,
        "stop_loss_price": 57600.0,
        "notes": "[대형주] 친환경 플랜트 대형 EPC 글로벌 수주 랠리 52주 신고가 VCP 돌파"
    },
    {
        "project_id": "stock-sniper",
        "project_name": "스톡 스나이퍼",
        "ticker": "000810",
        "name": "삼성화재",
        "market": "KRX",
        "signal_type": "BUY [시가 매수]",
        "entry_price": 651000.0,
        "current_price": 651000.0,
        "target_price": 716000.0,
        "stop_loss_price": 615000.0,
        "notes": "[대형주] 역대 최대 순이익 밸류업 대장주 및 외인 집중 순매수 돌파"
    },
    {
        "project_id": "stock-swing",
        "project_name": "227선 무한스윙",
        "ticker": "033780",
        "name": "KT&G",
        "market": "KRX",
        "signal_type": "BUY [종가 매수]",
        "entry_price": 192700.0,
        "current_price": 192700.0,
        "target_price": 212000.0,
        "stop_loss_price": 182000.0,
        "notes": "[대형주] 글로벌 NGP 전자담배 랠리 및 52주 신고가 안착 우상향 스윙"
    },
    {
        "project_id": "stock-sepa-pivot",
        "project_name": "SEPA x 피봇 돌파",
        "ticker": "093320",
        "name": "케이아이엔엑스",
        "market": "KRX",
        "signal_type": "BUY [지정가 매수]",
        "entry_price": 175000.0,
        "current_price": 175000.0,
        "target_price": 195000.0,
        "stop_loss_price": 164000.0,
        "notes": "[중소형주] 과천 AI IDC 본격 가동 및 52주 신고가 하이타이트 플래그 돌파"
    },
    {
        "project_id": "stock-sniper",
        "project_name": "스톡 스나이퍼",
        "ticker": "053800",
        "name": "안랩",
        "market": "KRX",
        "signal_type": "BUY [시가 매수]",
        "entry_price": 113600.0,
        "current_price": 113600.0,
        "target_price": 126000.0,
        "stop_loss_price": 106000.0,
        "notes": "[중소형주] AI 보안 플랫폼 수주 폭발 및 52주 신고가 VCP 수급 분출"
    },
    {
        "project_id": "stock-swing",
        "project_name": "227선 무한스윙",
        "ticker": "425420",
        "name": "티에프이",
        "market": "KRX",
        "signal_type": "BUY [종가 매수]",
        "entry_price": 77600.0,
        "current_price": 77600.0,
        "target_price": 86000.0,
        "stop_loss_price": 73000.0,
        "notes": "[중소형주] AI 반도체 테스트 소켓 국산화 선도 및 227선 지지 2차 파동"
    }
]

for p in new_positions:
    cur.execute("""
        INSERT INTO trades (
            project_id, project_name, ticker, name, market,
            signal_type, signal_date, entry_price, entry_date,
            current_price, status, return_pct, target_price,
            stop_loss_price, notes, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, 'HOLDING', 0.0, ?,
            ?, ?, ?
        )
    """, (
        p["project_id"], p["project_name"], p["ticker"], p["name"], p["market"],
        p["signal_type"], today_str, p["entry_price"], today_str,
        p["current_price"], p["target_price"],
        p["stop_loss_price"], p["notes"], now_str
    ))

conn.commit()
print("Successfully inserted 6 Stage 2 Momentum Leaders into trades.")

cur.execute("SELECT id, market, ticker, name, project_name, entry_price, current_price, return_pct, status FROM trades WHERE status = 'HOLDING'")
for row in cur.fetchall():
    print(row)

conn.close()
