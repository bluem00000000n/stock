#!/usr/bin/env bash
# ==============================================================================
# scripts/run_daily_signal_forge.sh
# SIGNAL FORGE ALERT (25대 퀀트 전략 & 거시 경제 인텔리전스) 매일 자동 스캔 실행기
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "============================================================"
echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] SIGNAL FORGE ALERT Daily Scan Running..."
echo "============================================================"

# 가상환경 파이썬으로 signal_forge 실시간 공용 엔드포인트 25대 퀀트 스캔 가동
PYTHONPATH=. .venv/bin/python3 signal_forge/main.py scan --market all

# 중앙 마스터 DB로 신규 시그널 즉시 동기화
python3 -c "
import sqlite3
from sync_master_db import get_master_db, sync_signal_forge_alert
conn = get_master_db()
cnt = sync_signal_forge_alert(conn)
conn.commit()
print(f'✅ 중앙 DB(stock_master.db)로 {cnt}건의 신규 시그널 동기화 완료')
"

echo "============================================================"
echo "✅ SIGNAL FORGE ALERT 데일리 스캔 및 동기화 완료!"
echo "============================================================"
