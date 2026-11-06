#!/bin/bash
# ==============================================================================
# scripts/install_launchd_hourly_update.sh
# 1시간 간격 글로벌 멀티마켓 추세분석 및 전략별 포트폴리오 업데이트 데몬 등록 스크립트
# ==============================================================================

set -e

PLIST_NAME="com.stock.hourly-update.plist"
SOURCE_PLIST="/Users/tothemoon/stock-supervisor/launchd/${PLIST_NAME}"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PLIST="${TARGET_DIR}/${PLIST_NAME}"
LOGS_DIR="/Users/tothemoon/stock-supervisor/logs"

mkdir -p "$LOGS_DIR"
mkdir -p "$TARGET_DIR"

echo "🚀 1시간 간격 업데이트 데몬(${PLIST_NAME}) 설치 중..."
cp "$SOURCE_PLIST" "$TARGET_PLIST"
launchctl unload "$TARGET_PLIST" 2>/dev/null || true
launchctl load "$TARGET_PLIST"

echo "✅ 등록 상태 확인:"
launchctl list | grep "hourly-update" || true

echo "🎉 매시 정각 1시간 주기 자동 업데이트 데몬 등록 완료!"
