#!/bin/bash
# Stock Supervisor - 통합 알람 launchd 데몬 등록 스크립트

PLIST_NAME="com.stock-supervisor.integrated-alarm.plist"
SRC_PATH="/Users/tothemoon/stock-supervisor/launchd/${PLIST_NAME}"
DEST_PATH="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

echo "🚀 Installing Stock Supervisor Integrated Alarm LaunchAgent..."

# 1. 기존 서비스 언로드 (있을 경우)
launchctl unload "${DEST_PATH}" 2>/dev/null || true

# 2. plist 복사
cp "${SRC_PATH}" "${DEST_PATH}"

# 3. 새 서비스 로드
launchctl load "${DEST_PATH}"

echo "✅ LaunchAgent 등록 완료: ${DEST_PATH}"
echo "⏰ 실행 스케줄:"
echo "   • 월~금 08:45 KST : KRX 한국장 통합 알람"
echo "   • 월~금 21:30 KST : US 미국장 통합 알람"
launchctl list | grep "stock-supervisor" || true
