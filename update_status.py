#!/usr/bin/env python3
"""
Stock Supervisor - 프로젝트 상태 및 스케줄 데이터 수집기
9대 프로젝트 통합 관제 & 수익률 관리:
1. stock-sniper
2. stock-sepa-pivot
3. stock-swing (Daily 08:40 & 21:30 스케줄 연동)
4. stock-htp-top10
5. stock-us3x
6. stock-dividend_top7
7. kbit-bot
8. signal_forge_alert
9. stock-cyclical-screener
"""

import os
import json
import time
import subprocess
from datetime import datetime

import portfolio_db
import sync_master_db

HOME = os.path.expanduser("~")
SUPERVISOR_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECTS_META = [
    {
        "id": "stock-sniper",
        "name": "stock-sniper",
        "label": "com.stocksniper",
        "category": "KRX",
        "flag": "🇰🇷",
        "type": "Scheduled Alert",
        "summary": "한국 주식 08:45 장전 스나이퍼 트레이딩 시스템 (외인/기관 수급 × RS 상대강도 × 52주 신고가)",
        "schedule_display": "Mon-Fri 08:45",
        "market": "KRX (KOSPI 200, KOSDAQ 150)",
        "strategy": "수급 데이터(외인/기관) x RS 상대강도(지수대비) x 52주 신고가 돌파/임박 x 지수 ETF & 개별 주도주 5선",
        "tags": ["Foreign/Inst Supply", "RS Momentum", "52W High", "Index ETF"],
        "repo": "https://github.com/bluem00000000n/stock-sniper",
        "local_path": os.path.join(HOME, "stock-sniper"),
        "log_path": os.path.join(HOME, "stock-sniper/logs/launchd.log"),
        "err_log_path": os.path.join(HOME, "stock-sniper/logs/launchd_err.log"),
    },
    {
        "id": "stock-sepa-pivot",
        "name": "stock-sepa-pivot",
        "label": "com.stocksepapivot",
        "category": "KRX / US",
        "flag": "🇰🇷 🇺🇸",
        "type": "Scheduled Alert",
        "summary": "마크 미너비니 SEPA 13대 조건 × 댄 쟁거 차트 패턴 피벗 감시 알람 시스템",
        "schedule_display": "Daily 08:40 (KRX) & 21:30 (US)",
        "market": "KRX 20 + US 20 (Total 40)",
        "strategy": "SEPA 트렌드 템플릿(200일선/150일선/50일선) + VCP 변동성 축소 + 댄 쟁거 피벗 돌파율 정밀 추적",
        "tags": ["Mark Minervini", "SEPA", "Dan Zanger", "VCP", "Pivot Breakout"],
        "repo": "https://github.com/bluem00000000n/stock-sepa-pivot",
        "local_path": os.path.join(HOME, "stock-sepa-pivot"),
        "log_path": os.path.join(HOME, "stock-sepa-pivot/logs/alarm.out"),
        "err_log_path": os.path.join(HOME, "stock-sepa-pivot/logs/alarm.err"),
    },
    {
        "id": "stock-swing",
        "name": "stock-swing",
        "label": "com.stockswing.scheduler",
        "category": "KRX / US",
        "flag": "🇰🇷 🇺🇸",
        "type": "Scheduled Daemon",
        "summary": "중대형주 및 러셀 2000 자율·진화·무한 스윙 분할 모아가기(Scale-in) 시스템",
        "schedule_display": "Daily 08:40 (KRX) & 21:30 (US)",
        "market": "KRX 200/150 & US S&P500/NASDAQ/Russell2000 (Total 227)",
        "strategy": "기계적 Scale-in 분할매수, 변동성 기반 익절/손절 트리거 및 포트폴리오 리밸런싱",
        "tags": ["Infinite Swing", "Scale-in", "Russell 2000", "S&P 500", "Scheduled"],
        "repo": "https://github.com/bluem00000000n/stock-swing",
        "local_path": os.path.join(HOME, "stock-swing"),
        "log_path": os.path.join(HOME, "stock-swing/logs/launchd.log"),
        "err_log_path": os.path.join(HOME, "stock-swing/logs/launchd_err.log"),
    },
    {
        "id": "stock-htp-top10",
        "name": "stock-htp-top10",
        "label": "com.stock-htp-top10",
        "category": "US",
        "flag": "🇺🇸",
        "type": "Weekly Scheduled",
        "summary": "High-to-Price (HTP) 모멘텀 알고리즘 기반 미국 대형주/소형주 주도주 10선 퀀트 추적",
        "schedule_display": "Tue 17:00",
        "market": "US S&P 500 & Russell 2000",
        "strategy": "HTP 파워 모멘텀 스코어 산출, Gemini AI 기반 퀀트 리포트 자동 생성 및 리밸런싱 추적",
        "tags": ["HTP Momentum", "S&P 500", "Russell 2000", "Gemini AI", "Top 10"],
        "repo": "https://github.com/bluem00000000n/stock-htp-top10",
        "local_path": os.path.join(HOME, "stock-htp-top10"),
        "log_path": os.path.join(HOME, "stock-htp-top10/logs/launchd.out"),
        "err_log_path": os.path.join(HOME, "stock-htp-top10/logs/launchd.err"),
    },
    {
        "id": "stock-us3x",
        "name": "stock-us3x",
        "label": "com.stock-us3x",
        "category": "US",
        "flag": "🇺🇸",
        "type": "Weekly Scheduled",
        "summary": "미국 3배 레버리지 ETF(TQQQ, SOXL, UPRO 등) 무한매수 및 주기적 리밸런싱 알람 시스템",
        "schedule_display": "Tue 08:30 & 17:00",
        "market": "US 3X Leverage ETFs (TQQQ, SOXL, TECL)",
        "strategy": "라오어 무한매수법 개량형 퀀트 알고리즘 + 변동성 지수(VIX) 가중 리밸런싱",
        "tags": ["3X Leverage", "TQQQ", "SOXL", "Infinite Buy", "Rebalancing"],
        "repo": "https://github.com/bluem00000000n/stock-us3x",
        "local_path": os.path.join(HOME, "stock-us3x"),
        "log_path": os.path.join(HOME, "stock-us3x/logs/launchd.out"),
        "err_log_path": os.path.join(HOME, "stock-us3x/logs/launchd.err"),
    },
    {
        "id": "stock-dividend_top7",
        "name": "stock-dividend_top7",
        "label": "com.stock-dividend_top7",
        "category": "KRX",
        "flag": "🇰🇷",
        "type": "Weekly Scheduled",
        "summary": "한국 거래소 6대 핵심 배당 기준을 100% 만족하는 상위 7대 고배당 성장주 자동 선별",
        "schedule_display": "Mon 08:30",
        "market": "KRX (KOSPI & KOSDAQ)",
        "strategy": "5년 평균 시가배당률 4%+, 배당성향 건전성, 5년 연속 배당성장, 부채비율 100% 미만 등 6대 조건 스크리닝",
        "tags": ["High Dividend", "Dividend Growth", "DART Verified", "Top 7"],
        "repo": "https://github.com/bluem00000000n/stock-dividend_top7",
        "local_path": os.path.join(HOME, "stock-dividend_top7"),
        "log_path": os.path.join(HOME, "stock-dividend_top7/logs/launchd_stdout.log"),
        "err_log_path": os.path.join(HOME, "stock-dividend_top7/logs/launchd_stderr.log"),
    },
    {
        "id": "signal_forge_alert",
        "name": "signal_forge_alert",
        "label": "signal-forge-alert",
        "category": "Global",
        "flag": "🌐",
        "type": "AI System",
        "summary": "유료 API 없는 100% 무료 아키텍처 기반 독립 AI 시장 인텔리전스 & 텔레그램 알림",
        "schedule_display": "Event-driven / Manual",
        "market": "Global Macro & Market Signals",
        "strategy": "거시 경제 지표 및 시장 위험 시그널 독립적 관측 및 텔레그램 알람 전송",
        "tags": ["AI Intelligence", "Macro Watch", "Zero-Paid API", "Alerts"],
        "repo": "https://github.com/bluem00000000n/signal_forge_alert",
        "local_path": os.path.join(HOME, "signal_forge_alert"),
        "log_path": os.path.join(HOME, "signal_forge_alert/runtime/logs/daemon.stdout.log"),
        "err_log_path": os.path.join(HOME, "signal_forge_alert/runtime/logs/daemon.stderr.log"),
    },
    {
        "id": "stock-cyclical-screener",
        "name": "stock-cyclical-screener",
        "label": "com.stock-cyclical-screener",
        "category": "KRX",
        "flag": "🇰🇷",
        "type": "Daily Scheduled",
        "summary": "한국 거래소 경기민감 6대 섹터(반도체/자동차/화학/철강/조선/해운) 퀀트 사이클 스크리너",
        "schedule_display": "Daily 08:30",
        "market": "KRX Cyclical 6 Sectors",
        "strategy": "역발상 시클리컬 투자 밴드(고PER·적자 침체기 매수, 저PER 호황기 매도), 역사적 PBR 밴드 분석",
        "tags": ["Cyclical", "Semi/Auto/Shipbuilding", "PBR Band", "Cycle Quant"],
        "repo": "https://github.com/bluem00000000n/stock-cyclical-screener",
        "local_path": os.path.join(HOME, "stock-cyclical-screener"),
        "log_path": os.path.join(HOME, "stock-cyclical-screener/logs/launchd.stdout.log"),
        "err_log_path": os.path.join(HOME, "stock-cyclical-screener/logs/launchd.stderr.log"),
    }
]

def get_launchd_status():
    services = {}
    try:
        out = subprocess.check_output(["launchctl", "list"], text=True)
        for line in out.strip().splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 3:
                pid, status, label = parts[0], parts[1], parts[2]
                services[label] = {
                    "pid": pid if pid != "-" else None,
                    "last_exit_code": int(status) if status.isdigit() or (status.startswith("-") and status[1:].isdigit()) else None,
                    "registered": True
                }
    except Exception as e:
        print(f"launchctl list check failed: {e}")
    return services

def read_recent_lines(filepath, num_lines=15):
    if not filepath or not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return lines[-num_lines:]
    except Exception:
        return []

def collect_data():
    launchd_map = get_launchd_status()
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    today_date = now_dt.strftime("%Y-%m-%d")

    projects_data = []
    total_active_daemons = 0
    today_executed_count = 0

    for meta in PROJECTS_META:
        p_id = meta["id"]
        label = meta["label"]
        ld_info = launchd_map.get(label, {"pid": None, "last_exit_code": None, "registered": False})
        
        log_path = meta.get("log_path")
        log_exists = log_path and os.path.exists(log_path)
        last_modified_str = "기록 없음"
        recent_logs = []
        is_executed_today = False

        if log_exists:
            mtime = os.path.getmtime(log_path)
            last_dt = datetime.fromtimestamp(mtime)
            last_modified_str = last_dt.strftime("%Y-%m-%d %H:%M:%S")
            recent_logs = read_recent_lines(log_path, 10)
            if last_dt.strftime("%Y-%m-%d") == today_date:
                is_executed_today = True

        if ld_info["pid"]:
            status_text = "Running"
            status_code = "running"
            total_active_daemons += 1
        elif ld_info["registered"]:
            if ld_info["last_exit_code"] == 0:
                status_text = "Active"
                status_code = "active"
                total_active_daemons += 1
            else:
                status_text = f"Notice ({ld_info['last_exit_code']})"
                status_code = "warning"
                total_active_daemons += 1
        else:
            status_text = "Ready"
            status_code = "ready"

        if is_executed_today:
            today_executed_count += 1

        last_log_line = recent_logs[-1] if recent_logs else "최근 로그 기록 없음"

        projects_data.append({
            **meta,
            "launchd_registered": ld_info["registered"],
            "pid": ld_info["pid"],
            "last_exit_code": ld_info["last_exit_code"],
            "status_text": status_text,
            "status_code": status_code,
            "last_executed": last_modified_str,
            "executed_today": is_executed_today,
            "recent_logs": recent_logs,
            "last_log_preview": last_log_line
        })

    # 포트폴리오 DB 갱신 및 데이터 취득
    try:
        portfolio_db.init_db()
        portfolio_db.update_trades_and_performance()
        portfolio_data = portfolio_db.get_dashboard_full_data()
    except Exception as e:
        print(f"Warning: portfolio_db failed: {e}")
        portfolio_data = {"alarms": [], "trades": [], "performance": {}, "total_performance": {}}

    summary = {
        "updated_at": now_str,
        "total_projects": len(projects_data),
        "active_daemons": total_active_daemons,
        "today_executed": today_executed_count,
        "market_stats": {
            "KRX": sum(1 for p in projects_data if "KRX" in p["category"]),
            "US": sum(1 for p in projects_data if "US" in p["category"]),
            "Global": sum(1 for p in projects_data if "Global" in p["category"])
        },
        "portfolio": portfolio_data.get("total_performance", {})
    }

    return {
        "summary": summary,
        "projects": projects_data,
        "alarms": portfolio_data.get("alarms", []),
        "trades": portfolio_data.get("trades", []),
        "performance": portfolio_data.get("performance", {})
    }

def update_index_html(data):
    index_path = os.path.join(SUPERVISOR_DIR, "index.html")
    if not os.path.exists(index_path):
        return
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        data_json = json.dumps(data, ensure_ascii=False, indent=2)
        pattern = r"(const INITIAL_DATA = )(\{[\s\S]*?\n\s*\});"

        if re.search(pattern, content):
            # lambda 콜백을 사용하여 JSON 내의 이스케이프 문자(\n 등)가 치환 템플릿에 의해 풀리는 치명적 SyntaxError 방지
            new_content = re.sub(pattern, lambda m: f"{m.group(1)}{data_json};", content, count=1)
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"✅ index.html 인라인 데이터 동기화 완료 (JSON Escape 안전 보장)")
    except Exception as e:
        print(f"Warning: Failed to update index.html inline data: {e}")

def main():
    # 1. 하위 9개 프로젝트 데이터 중앙 DB (stock_master.db) 통합 동기화
    try:
        sync_master_db.sync_all_subprojects()
    except Exception as e:
        print(f"Warning: sync_master_db failed: {e}")

    # 2. 데이터 수집 및 수익률 계산
    data = collect_data()
    data_dir = os.path.join(SUPERVISOR_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    json_path = os.path.join(data_dir, "status.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    update_index_html(data)

    print(f"✅ 상태 데이터 저장 완료: {json_path}")
    print(f"📊 총 {data['summary']['total_projects']}대 프로젝트 (가동/대기 중: {data['summary']['active_daemons']}, 오늘 실행: {data['summary']['today_executed']})")

if __name__ == "__main__":
    main()
