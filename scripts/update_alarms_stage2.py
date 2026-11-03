#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
db_path = "data/stock_master.db"

# 1. Clean up stray test rows >= 139
conn = sqlite3.connect(db_path, timeout=30)
cur = conn.cursor()
cur.execute("DELETE FROM alarms WHERE id >= 139")
print(f"Deleted {cur.rowcount} stray rows from alarms.")
conn.commit()
conn.close()
time.sleep(0.5)

# 2. Build fresh reports with Stage 2 portfolio
from integrated_alarm_engine import build_krx_open_report, build_krx_close_report, build_us_open_report

msg_0830, title_0830, _ = build_krx_open_report()
msg_1500, title_1500, _ = build_krx_close_report()
msg_1730, title_1730, _ = build_us_open_report()

# 3. Update rows 136, 137, 138
conn = sqlite3.connect(db_path, timeout=30)
cur = conn.cursor()
cur.execute("UPDATE alarms SET title = ?, raw_message = ? WHERE id = 136", (title_0830, msg_0830))
cur.execute("UPDATE alarms SET title = ?, raw_message = ? WHERE id = 137", (title_1500, msg_1500))
cur.execute("UPDATE alarms SET title = ?, raw_message = ? WHERE id = 138", (title_1730, msg_1730))
conn.commit()
print("Successfully updated alarms 136, 137, 138 with Stage 2 portfolio.")
conn.close()
