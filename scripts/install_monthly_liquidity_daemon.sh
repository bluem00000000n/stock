#!/bin/bash
# ==============================================================================
# scripts/install_monthly_liquidity_daemon.sh
# 매월 1일 오전 09:00 KST 월간 유동성·ETF 분석 데몬 등록 스크립트
# ==============================================================================

set -e

PLIST_NAME="com.stock.monthly-liquidity.plist"
SOURCE_PLIST="/Users/tothemoon/stock-supervisor/launchd/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"
LOGS_DIR="/Users/tothemoon/stock-supervisor/logs"

mkdir -p "$LOGS_DIR"
mkdir -p "$TARGET_DIR"

echo "🚀 월간 유동성 데몬(${PLIST_NAME}) 설치 중..."
cp "$SOURCE_PLIST" "$TARGET_PLIST"
launchctl unload "$TARGET_PLIST" 2>/dev/null || true
launchctl load "$TARGET_PLIST"

echo "✅ 등록 상태 확인:"
launchctl list | grep "monthly-liquidity" || true

echo "🎉 매월 1일 오전 09:00 데몬 등록 완료!"
