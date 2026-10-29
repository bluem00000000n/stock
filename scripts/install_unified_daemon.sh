#!/bin/bash
# ==============================================================================
# scripts/install_unified_daemon.sh
# 단일 통합 데몬(com.stock.unified.plist) 설치 및 기존 파편화 데몬 일괄 정리 스크립트
# ==============================================================================

set -e

PLIST_NAME="com.stock.unified.plist"
SOURCE_PLIST="/Users/tothemoon/stock-supervisor/launchd/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"
LOGS_DIR="/Users/tothemoon/stock-supervisor/logs"

mkdir -p "$LOGS_DIR"
mkdir -p "$TARGET_DIR"

echo "🧹 1. 기존 개별 파편화 데몬들 언로드 및 정리 중..."
OLD_PLISTS=(
    "com.stock-cyclical-screener.plist"
    "com.stock-dividend_top7.plist"
    "com.stock-htp-top10.plist"
    "com.stock-us3x.plist"
    "com.stocksepapivot.plist"
    "com.stocksniper.plist"
    "com.stockswing.scheduler.plist"
    "com.stock-supervisor.integrated-alarm.plist"
)

for plist in "${OLD_PLISTS[@]}"; do
    target="${TARGET_DIR}/${plist}"
    if [ -f "$target" ]; then
        echo "   - Unloading: $plist"
        launchctl unload "$target" 2>/dev/null || true
        rm -f "$target"
    fi
done

echo "🚀 2. 신규 통합 데몬(${PLIST_NAME}) 설치 중..."
cp "$SOURCE_PLIST" "$TARGET_PLIST"
launchctl unload "$TARGET_PLIST" 2>/dev/null || true
launchctl load "$TARGET_PLIST"

echo "✅ 3. 등록 상태 확인:"
launchctl list | grep "stock" || true

echo "🎉 단일 통합 데몬 설치 완료!"
echo "   - 스케줄: 08:45 (KRX 장전) / 15:10 (KRX 종가매수) / 21:30 (US 장전)"
